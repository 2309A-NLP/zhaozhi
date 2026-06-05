"""Model clients for chat, embeddings, and reranking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence
from urllib import error, request

from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.models")


@dataclass
class LLMClient:
    base_url: str
    api_key: str
    model: str
    max_tokens: int = 512
    temperature: float = 0.5
    max_retries: int = 1
    timeout_seconds: int = 12

    def chat(self, messages: List[Dict[str, str]]) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")

        endpoint = self._build_chat_url()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries)):
            http_request = request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    response_body = response.read().decode("utf-8")
                return self._parse_content(response_body)
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                LOGGER.error("llm_http_error | status=%s | body=%s", exc.code, error_body)
                last_error = RuntimeError(f"LLM API returned HTTP {exc.code}")
            except error.URLError as exc:
                LOGGER.exception("llm_network_error")
                last_error = RuntimeError(f"LLM API network error: {exc.reason}")

        assert last_error is not None
        raise last_error

    def _build_chat_url(self) -> str:
        trimmed = self.base_url.rstrip("/")
        if trimmed.endswith("/chat/completions"):
            return trimmed
        return f"{trimmed}/chat/completions"

    def _parse_content(self, response_body: str) -> str:
        data = json.loads(response_body)
        choices = data.get("choices") or []
        if not choices:
            LOGGER.error("llm_invalid_response | body=%s", response_body)
            raise RuntimeError("LLM API response does not contain choices")
        message = choices[0].get("message", {})
        content = (message.get("content") or "").strip()
        if not content:
            LOGGER.error("llm_empty_content | body=%s", response_body)
            raise RuntimeError("LLM API returned empty content")
        return content


@dataclass
class EmbeddingClient:
    model_path: str
    expected_dim: int = 0
    _model: object = field(init=False, default=None, repr=False)
    _actual_dim: int = field(init=False, default=0, repr=False)

    def __post_init__(self) -> None:
        if not self.model_path:
            raise RuntimeError("BGE_EMBEDDING_MODEL is not configured")
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            raise FileNotFoundError(f"Embedding model not found: {model_dir}")
        actual_dim = self.dimension
        if self.expected_dim and self.expected_dim != actual_dim:
            LOGGER.warning(
                "embedding_dim_mismatch | configured=%s | actual=%s | model=%s",
                self.expected_dim,
                actual_dim,
                self.model_path,
            )
        self.expected_dim = actual_dim

    def embed(self, text: str) -> List[float]:
        if not text.strip():
            return [0.0] * self.expected_dim
        model = self._get_model()
        vector = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
        if len(values) != self.expected_dim:
            raise RuntimeError(f"Embedding dimension mismatch: expected {self.expected_dim}, got {len(values)}")
        return [float(item) for item in values]

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(list(texts), normalize_embeddings=True, batch_size=8, show_progress_bar=False)
        rows = vectors.tolist() if hasattr(vectors, "tolist") else list(vectors)
        payload: List[List[float]] = []
        for row in rows:
            if len(row) != self.expected_dim:
                raise RuntimeError(f"Embedding dimension mismatch: expected {self.expected_dim}, got {len(row)}")
            payload.append([float(item) for item in row])
        return payload

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_path, trust_remote_code=True)
        return self._model

    @property
    def dimension(self) -> int:
        if not self._actual_dim:
            model = self._get_model()
            self._actual_dim = int(model.get_sentence_embedding_dimension())
        return self._actual_dim


@dataclass
class RerankerClient:
    model_path: str = ""
    enabled: bool = False
    _model: object = field(init=False, default=None, repr=False)

    def rerank(self, question: str, documents: Sequence[Dict[str, object]], top_k: int) -> List[Dict[str, object]]:
        if not documents:
            return []
        if not self.enabled or not self.model_path:
            return list(documents[:top_k])
        model = self._get_model()
        pairs = [(question, str(item.get("text", ""))) for item in documents]
        scores = model.predict(pairs)
        rescored: List[Dict[str, object]] = []
        for item, score in zip(documents, scores):
            payload = dict(item)
            payload["rerank_score"] = float(score)
            rescored.append(payload)
        rescored.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return rescored[:top_k]

    def _get_model(self):
        if self._model is None:
            model_dir = Path(self.model_path)
            if not model_dir.exists():
                raise FileNotFoundError(f"Reranker model not found: {model_dir}")
            from sentence_transformers.cross_encoder import CrossEncoder

            self._model = CrossEncoder(self.model_path, trust_remote_code=True)
        return self._model
