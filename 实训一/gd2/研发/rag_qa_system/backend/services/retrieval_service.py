"""Retrieval orchestration service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List

from rag_qa_system.backend.models.llm_client import EmbeddingClient, RerankerClient
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository
from rag_qa_system.backend.utils.text_utils import keyword_tokens, normalize_text


@dataclass
class RetrievalService:
    embedding_client: EmbeddingClient
    reranker_client: RerankerClient
    milvus_repo: MilvusRepository
    redis_repo: RedisRepository
    retrieval_top_k: int = 6
    rerank_top_k: int = 3
    cache_ttl_seconds: int = 3600

    def retrieve(self, question: str, top_k: int = 5, document_id: str = "") -> List[Dict[str, object]]:
        effective_top_k = top_k or self.rerank_top_k
        normalized_question = normalize_text(question)
        scoped_document_id = document_id.strip()
        cache_key = self._cache_key(normalized_question, effective_top_k, scoped_document_id)
        cached = self.redis_repo.get(cache_key)
        if cached:
            return cached

        vector = self.embedding_client.embed(normalized_question)
        search_top_k = max(self.retrieval_top_k, effective_top_k, self.rerank_top_k)
        hits = self.milvus_repo.search(
            vector=vector,
            question=normalized_question,
            top_k=search_top_k,
            document_id=scoped_document_id,
        )
        rerank_limit = min(len(hits), max(self.rerank_top_k, effective_top_k))
        reranked = self._rerank_documents(question=normalized_question, documents=hits, top_k=rerank_limit)
        results = [
            {
                "chunk_id": item["chunk_id"],
                "document_id": item.get("document_id", ""),
                "document_name": item.get("document_name", ""),
                "text": item.get("text", ""),
                "score": round(float(item.get("final_score", item.get("rerank_score", item.get("score", 0.0)))), 4),
                "retrieval_score": round(float(item.get("score", 0.0)), 4),
                "vector_score": round(float(item.get("vector_score", 0.0)), 4),
                "lexical_score": round(float(item.get("lexical_score", 0.0)), 4),
            }
            for item in reranked[:effective_top_k]
        ]
        self.redis_repo.set(cache_key, results, ttl_seconds=self.cache_ttl_seconds)
        return results

    def _cache_key(self, question: str, top_k: int, document_id: str) -> str:
        digest = hashlib.md5(question.encode("utf-8")).hexdigest()
        document_scope = document_id or "all"
        return f"retrieval:v3:{digest}:{document_scope}:{top_k}:{self.retrieval_top_k}:{self.rerank_top_k}"

    def _rerank_documents(self, question: str, documents: List[Dict[str, object]], top_k: int) -> List[Dict[str, object]]:
        if not documents:
            return []
        if self.reranker_client.enabled and self.reranker_client.model_path:
            rescored = self.reranker_client.rerank(question=question, documents=documents, top_k=len(documents))
            rescored = self._blend_model_rerank_scores(rescored)
            return rescored[:top_k]

        query_terms = set(keyword_tokens(question))
        rescored: List[Dict[str, object]] = []
        for item in documents:
            lexical = float(item.get("lexical_score", 0.0))
            vector_score = float(item.get("vector_score", item.get("score", 0.0)))
            retrieval_score = float(item.get("score", 0.0))
            text = str(item.get("text", ""))
            term_hits = sum(1 for term in query_terms if term in text)
            coverage = term_hits / max(1, len(query_terms))
            payload = dict(item)
            payload["final_score"] = retrieval_score * 0.55 + lexical * 0.25 + coverage * 0.2
            payload["vector_score"] = vector_score
            rescored.append(payload)
        rescored.sort(
            key=lambda item: (
                item.get("final_score", 0.0),
                item.get("lexical_score", 0.0),
                item.get("vector_score", 0.0),
            ),
            reverse=True,
        )
        return rescored[:top_k]

    def _blend_model_rerank_scores(self, documents: List[Dict[str, object]]) -> List[Dict[str, object]]:
        if not documents:
            return []
        raw_scores = [float(item.get("rerank_score", 0.0)) for item in documents]
        min_score = min(raw_scores)
        max_score = max(raw_scores)
        score_span = max_score - min_score

        blended: List[Dict[str, object]] = []
        for item, raw_score in zip(documents, raw_scores):
            rerank_score = 1.0 if score_span <= 1e-6 else (raw_score - min_score) / score_span
            retrieval_score = float(item.get("score", 0.0))
            lexical_score = float(item.get("lexical_score", 0.0))
            vector_score = float(item.get("vector_score", 0.0))
            payload = dict(item)
            payload["final_score"] = (
                rerank_score * 0.55
                + retrieval_score * 0.3
                + lexical_score * 0.1
                + vector_score * 0.05
            )
            blended.append(payload)

        blended.sort(
            key=lambda item: (
                item.get("final_score", 0.0),
                item.get("rerank_score", 0.0),
                item.get("score", 0.0),
            ),
            reverse=True,
        )
        return blended
