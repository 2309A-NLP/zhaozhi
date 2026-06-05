"""Retrieval orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from rag_qa_system.backend.models.llm_client import EmbeddingClient, RerankerClient
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository


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
        scoped_document_id = document_id.strip()
        cache_key = f"retrieval:{question}:{scoped_document_id or 'all'}:{effective_top_k}:{self.retrieval_top_k}:{self.rerank_top_k}"
        cached = self.redis_repo.get(cache_key)
        if cached:
            return cached
        vector = self.embedding_client.embed(question)
        hits = self.milvus_repo.search(
            vector=vector,
            question=question,
            top_k=max(self.retrieval_top_k, effective_top_k),
            document_id=scoped_document_id,
        )
        reranked = self.reranker_client.rerank(question=question, documents=hits, top_k=max(self.rerank_top_k, effective_top_k))
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
