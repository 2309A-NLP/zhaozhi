"""Model clients for chat, embeddings, and reranking."""

from __future__ import annotations

import json
import socket
import time
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence
from urllib import error, request

from rag_qa_system.backend.utils.text_utils import normalize_text
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
    enable_thinking: bool | None = None

    def chat(self, messages: List[Dict[str, Any]]) -> str:
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY is not configured")

        endpoint = self._build_chat_url()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_error: Exception | None = None
        attempts = max(1, self.max_retries)
        include_thinking = self.enable_thinking is not None
        attempt = 0
        while attempt < attempts:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            if include_thinking:
                payload["enable_thinking"] = self.enable_thinking
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            http_request = request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                    response_body = response.read().decode("utf-8")
                return self._parse_content(response_body)
            except error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                body_preview = self._preview(error_body)
                LOGGER.error("llm_http_error | status=%s | body_preview=%s", exc.code, body_preview)
                last_error = RuntimeError(f"LLM API returned HTTP {exc.code}: {body_preview}")
                if include_thinking and "enable_thinking" in error_body:
                    LOGGER.warning("llm_retry_without_enable_thinking | model=%s", self.model)
                    include_thinking = False
                    continue
            except error.URLError as exc:
                LOGGER.exception("llm_network_error")
                last_error = RuntimeError(f"LLM API network error: {exc.reason}")
            except (TimeoutError, socket.timeout):
                LOGGER.error("llm_timeout | timeout_seconds=%s | model=%s", self.timeout_seconds, self.model)
                last_error = RuntimeError(f"LLM API timed out after {self.timeout_seconds} seconds")
            attempt += 1
            if attempt + 1 < attempts:
                time.sleep(min(2.0, 0.25 * (2**attempt)))

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
            LOGGER.error("llm_invalid_response | body_preview=%s", self._preview(response_body))
            raise RuntimeError("LLM API response does not contain choices")
        message = choices[0].get("message", {})
        content = (message.get("content") or "").strip()
        if not content:
            if message.get("reasoning_content"):
                LOGGER.error("llm_empty_content_reasoning_only | body_preview=%s", self._preview(response_body))
                raise RuntimeError("LLM API returned empty content; disable thinking mode for reasoning models")
            LOGGER.error("llm_empty_content | body_preview=%s", self._preview(response_body))
            raise RuntimeError("LLM API returned empty content")
        return content

    def _preview(self, value: str, limit: int = 500) -> str:
        compact = " ".join(value.split())
        return compact[:limit]


@dataclass
class PdfTextCleanupClient:
    llm_client: LLMClient
    chunk_chars: int = 12000
    chunk_overlap: int = 600

    def cleanup_text(self, text: str, source_name: str = "") -> str:
        if not text.strip():
            return ""

        cleaned_chunks: List[str] = []
        for index, chunk in enumerate(self._chunk_text(text), start=1):
            messages = self._build_messages(chunk=chunk, chunk_index=index, source_name=source_name)
            try:
                cleaned = self.llm_client.chat(messages)
            except Exception as exc:
                LOGGER.warning(
                    "pdf_cleanup_failed | chunk_index=%s | source_name=%s | detail=%s",
                    index,
                    source_name,
                    exc,
                )
                cleaned = chunk
            cleaned_chunks.append(self._strip_markdown_fences(cleaned))
        return self._merge_chunks(cleaned_chunks)

    def _build_messages(self, chunk: str, chunk_index: int, source_name: str) -> List[Dict[str, str]]:
        system_prompt = (
            "你是一个PDF清洗助手。"
            "你会基于已有抽取文本做清洗和结构化整理，删除页眉页脚、页码、水印噪声和明显断裂，"
            "尽量修复排版，但绝不能编造、总结、改写事实，也不要补充原文没有的信息。"
            "输出必须是纯文本，不要使用Markdown代码块，不要解释你的处理过程。"
        )
        user_prompt = (
            f"文件名：{source_name or 'unknown'}\n"
            f"分段：{chunk_index}\n"
            "请清洗下面这段 PDF 抽取文本。要求：\n"
            "1. 保留原文信息和顺序。\n"
            "2. 删除重复页眉、页脚、页码、链接水印等噪声。\n"
            "3. 尽量把被错误拆开的句子重新接顺。\n"
            "4. 表格内容保持为普通文本行，可用 ` | ` 分隔列。\n"
            "5. 如果内容本身已经干净，就原样返回。\n\n"
            "待清洗文本：\n"
            f"{chunk}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _chunk_text(self, text: str) -> List[str]:
        normalized = text.strip()
        if len(normalized) <= self.chunk_chars:
            return [normalized]

        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        if not paragraphs:
            paragraphs = [line.strip() for line in normalized.splitlines() if line.strip()]

        chunks: List[str] = []
        current_parts: List[str] = []
        current_len = 0
        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_chars:
                if current_parts:
                    chunks.append("\n\n".join(current_parts))
                    current_parts = []
                    current_len = 0
                chunks.extend(self._split_large_paragraph(paragraph))
                continue

            paragraph_len = len(paragraph)
            projected_len = current_len + paragraph_len + (2 if current_parts else 0)
            if current_parts and projected_len > self.chunk_chars:
                chunks.append("\n\n".join(current_parts))
                overlap_text = self._tail_text(chunks[-1])
                current_parts = [overlap_text, paragraph] if overlap_text else [paragraph]
                current_len = sum(len(part) for part in current_parts) + (2 * max(0, len(current_parts) - 1))
                continue
            current_parts.append(paragraph)
            current_len = projected_len

        if current_parts:
            chunks.append("\n\n".join(current_parts))
        return chunks

    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        chunks: List[str] = []
        step = max(1, self.chunk_chars - max(0, self.chunk_overlap))
        for start in range(0, len(paragraph), step):
            chunk = paragraph[start : start + self.chunk_chars].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def _tail_text(self, text: str) -> str:
        if self.chunk_overlap <= 0 or len(text) <= self.chunk_overlap:
            return ""
        tail = text[-self.chunk_overlap :]
        split_at = tail.find("\n")
        return tail[split_at + 1 :].strip() if split_at >= 0 else tail.strip()

    def _strip_markdown_fences(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            lines = stripped.splitlines()
            return "\n".join(lines[1:-1]).strip()
        return stripped

    def _merge_chunks(self, chunks: Sequence[str]) -> str:
        merged_lines: List[str] = []
        seen_recent: List[str] = []
        for chunk in chunks:
            for raw_line in chunk.splitlines():
                line = normalize_text(raw_line)
                if not line:
                    continue
                if seen_recent and line == seen_recent[-1]:
                    continue
                merged_lines.append(line)
                seen_recent.append(line)
                if len(seen_recent) > 20:
                    seen_recent.pop(0)
        return "\n".join(merged_lines)


@dataclass
class PdfVisionChartClient:
    llm_client: LLMClient

    def describe_page_image(self, image_png: bytes, page_number: int, surrounding_text: str, source_name: str = "") -> str:
        if not image_png:
            return ""
        image_base64 = base64.b64encode(image_png).decode("ascii")
        prompt = (
            f"文件名：{source_name or 'unknown'}\n"
            f"页码：{page_number}\n"
            "周边文本：\n"
            f"{surrounding_text[:2000]}\n\n"
            "请解析这张 PDF 页面中的视觉信息，尤其是组织结构图、层级关系图、饼图、柱状图、折线图、图例、标签、数值、占比和增长率。\n"
            "要求：\n"
            "1. 只依据图片和周边文本，不要编造；看不清的数值写入 notes，不要猜。\n"
            "2. 只输出 JSON，不要输出 Markdown 代码块，不要解释过程。\n"
            "3. 如果页面没有可解析图表，按 JSON 返回 has_chart=false。\n"
            "4. 组织结构图必须明确上下级关系，不要把子部门写成与父部门同级。例如图中若 6 个销售处挂在“大客户销售部”下，必须写 parent=大客户销售部。\n"
            "5. 组织结构图里的所有下级节点必须逐个列出，不能概括成“6个销售处”“多个销售处”等汇总说法；每个下级节点都要使用图中实际出现的名称，并分别写清 parent。\n"
            "6. hierarchy_text 也必须展开为具体名称，例如“父节点 -> 子节点1、子节点2、子节点3”，不要只写“父节点 -> 多个子节点”。\n"
            "7. 同一页面有多个图时全部解析，例如饼图旁边的柱状图/直方图也要分别给出完整数据。\n"
            "8. 如果页面同时有饼图和增长率柱状图，左侧饼图表示结构，右侧柱状图表示增长率；必须逐项读取右侧柱状图的标签和百分比，写入 bar 或 growth_rate。回答增长率最快/负增长时只能依据柱状图里实际出现的标签和值，不能写图中没有的行业名称。\n"
            "9. 对增长率柱状图，正数最大者是增长率最快，负数项是负增长；如果存在负值必须完整保留负号。\n"
            "10. JSON 字段格式如下：\n"
            "{\n"
            '  "has_chart": true,\n'
            '  "page": 1,\n'
            '  "title": "图表标题",\n'
            '  "chart_type": "org_chart|pie|bar|line|table_image|mixed|unknown",\n'
            '  "org_chart": {\n'
            '    "nodes": [{"name": "部门/岗位名称", "level": 1, "parent": "上级名称或空字符串"}],\n'
            '    "edges": [{"parent": "上级名称", "child": "下级名称"}],\n'
            '    "hierarchy_text": ["上级 -> 下级1、下级2"]\n'
            '  },\n'
            '  "pie": [{"name": "类别", "amount": 0, "unit": "亿元", "ratio": "0%"}],\n'
            '  "bar": [{"name": "类别/年份", "value": "数值", "unit": "", "series": "系列名称"}],\n'
            '  "line": [{"name": "类别/年份", "value": "数值", "unit": "", "series": "系列名称"}],\n'
            '  "growth_rate": [{"name": "类别", "rate": "0%"}],\n'
            '  "other_values": [{"name": "指标", "value": "数值", "unit": ""}],\n'
            '  "source": "图表资料来源",\n'
            '  "confidence": 0.0,\n'
            '  "notes": "无法确定的信息写在这里"\n'
            "}"
        )
        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "你是 PDF 视觉解析助手，擅长把招股说明书、年报中的组织结构图、流程图、饼图、柱状图、折线图转写为结构化中文文本。"
                    "你的输出会被写入知识库，请保持事实性、完整性和可检索性。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            },
        ]
        return self.llm_client.chat(messages)


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
