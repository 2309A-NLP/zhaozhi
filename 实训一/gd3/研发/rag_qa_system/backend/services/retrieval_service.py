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

    def retrieve(self, question: str, top_k: int = 5, document_id: str = "") -> List[Dict[str, str]]:
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
                "score": round(float(item.get("rerank_score", item.get("score", 0.0))), 4),
            }
            for item in reranked[:effective_top_k]
        ]
        self.redis_repo.set(cache_key, results, ttl_seconds=self.cache_ttl_seconds)
        return results

    def _cache_key(self, question: str, top_k: int, document_id: str) -> str:
        digest = hashlib.md5(question.encode("utf-8")).hexdigest()
        return f"retrieval:{digest}:{document_id or 'all'}:{top_k}:{self.retrieval_top_k}:{self.rerank_top_k}"

    def _rerank_documents(self, question: str, documents: List[Dict[str, object]], top_k: int) -> List[Dict[str, object]]:
        if not documents:
            return []
        if self.reranker_client.enabled and self.reranker_client.model_path:
            return self.reranker_client.rerank(question=question, documents=documents, top_k=top_k)

        query_terms = set(keyword_tokens(question))
        rescored: List[Dict[str, object]] = []
        for item in documents:
            lexical = float(item.get("lexical_score", 0.0))
            vector_score = float(item.get("vector_score", item.get("score", 0.0)))
            text = str(item.get("text", ""))
            term_hits = sum(1 for term in query_terms if term in text)
            coverage = term_hits / max(1, len(query_terms))
            payload = dict(item)
            payload["rerank_score"] = vector_score * 0.65 + lexical * 0.2 + coverage * 0.15
            rescored.append(payload)
        rescored.sort(
            key=lambda item: (
                item.get("rerank_score", 0.0),
                item.get("lexical_score", 0.0),
                item.get("vector_score", 0.0),
            ),
            reverse=True,
        )
        return rescored[:top_k]
