"""Hybrid retrieval orchestration with coarse ranking and reranker-based fine ranking."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

from rag_qa_system.backend.models.llm_client import EmbeddingClient, RerankerClient
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository
from rag_qa_system.backend.utils.text_utils import keyword_tokens, normalize_text, overlap_score


@dataclass
class RetrievalService:
    embedding_client: EmbeddingClient
    reranker_client: RerankerClient
    milvus_repo: MilvusRepository
    mysql_repo: MysqlRepository
    redis_repo: RedisRepository
    retrieval_top_k: int = 6
    rerank_top_k: int = 3
    cache_ttl_seconds: int = 3600
    rrf_k: int = 60
    _bm25_docs: List[Dict[str, object]] = field(init=False, default_factory=list, repr=False)
    _bm25_doc_freq: Dict[str, int] = field(init=False, default_factory=dict, repr=False)
    _bm25_avg_doc_len: float = field(init=False, default=0.0, repr=False)
    _bm25_corpus_size: int = field(init=False, default=0, repr=False)
    _bm25_signature: str = field(init=False, default="", repr=False)

    def __post_init__(self) -> None:
        if not self.reranker_client.enabled or not self.reranker_client.model_path:
            raise RuntimeError("Hybrid retrieval requires a reranker model. Configure BGE_RERANKER_MODEL and enable reranker.")

    def retrieve(self, question: str, top_k: int = 5, document_id: str = "") -> List[Dict[str, str]]:
        effective_top_k = top_k or self.rerank_top_k
        normalized_question = normalize_text(question)
        scoped_document_id = document_id.strip()
        cache_key = self._cache_key(normalized_question, effective_top_k, scoped_document_id)
        cached = self.redis_repo.get(cache_key)
        if cached:
            return cached

        recall_top_k = max(self.retrieval_top_k, self.rerank_top_k, effective_top_k) * 3
        dense_hits = self._dense_recall(normalized_question, recall_top_k, scoped_document_id)
        bm25_hits = self._bm25_recall(normalized_question, recall_top_k, scoped_document_id)
        fused_hits = self._rrf_fuse(
            named_rankings={
                "dense": dense_hits,
                "bm25": bm25_hits,
            },
            top_k=max(self.rerank_top_k, effective_top_k) * 2,
        )
        reranked = self._fine_rerank(normalized_question, fused_hits, max(self.rerank_top_k, effective_top_k))

        results = [
            {
                "chunk_id": item["chunk_id"],
                "document_id": item.get("document_id", ""),
                "document_name": item.get("document_name", ""),
                "text": item.get("text", ""),
                "score": round(float(item.get("rerank_score", item.get("rrf_score", 0.0))), 4),
                "coarse_score": round(float(item.get("rrf_score", 0.0)), 4),
            }
            for item in reranked[:effective_top_k]
        ]
        self.redis_repo.set(cache_key, results, ttl_seconds=self.cache_ttl_seconds)
        return results

    def _cache_key(self, question: str, top_k: int, document_id: str) -> str:
        digest = hashlib.md5(question.encode("utf-8")).hexdigest()
        return f"retrieval:{digest}:{document_id or 'all'}:{top_k}:{self.retrieval_top_k}:{self.rerank_top_k}:{self.rrf_k}"

    def _dense_recall(self, question: str, top_k: int, document_id: str) -> List[Dict[str, object]]:
        vector = self.embedding_client.embed(question)
        return self.milvus_repo.search(vector=vector, question=question, top_k=top_k, document_id=document_id)

    def _bm25_recall(self, question: str, top_k: int, document_id: str) -> List[Dict[str, object]]:
        self._ensure_bm25_index(document_id)
        query_terms = keyword_tokens(question)
        if not query_terms or not self._bm25_docs:
            return []

        scores: List[Dict[str, object]] = []
        for doc in self._bm25_docs:
            term_counts = doc["term_counts"]
            doc_len = doc["doc_len"]
            score = 0.0
            for term in query_terms:
                tf = term_counts.get(term, 0)
                if tf <= 0:
                    continue
                idf = self._bm25_idf(term)
                numerator = tf * 2.2
                denominator = tf + 1.2 * (1.0 - 0.75 + 0.75 * doc_len / max(self._bm25_avg_doc_len, 1.0))
                score += idf * (numerator / max(denominator, 1e-9))
            if score <= 0:
                continue
            payload = dict(doc["payload"])
            payload["bm25_score"] = float(score)
            payload["lexical_score"] = overlap_score(question, payload.get("text", ""))
            scores.append(payload)

        scores.sort(
            key=lambda item: (
                item.get("bm25_score", 0.0),
                item.get("lexical_score", 0.0),
            ),
            reverse=True,
        )
        return scores[:top_k]

    def _rrf_fuse(self, named_rankings: Dict[str, List[Dict[str, object]]], top_k: int) -> List[Dict[str, object]]:
        merged: Dict[str, Dict[str, object]] = {}
        rank_sources: Dict[str, Dict[str, int]] = defaultdict(dict)

        for source_name, ranking in named_rankings.items():
            for rank, item in enumerate(ranking, start=1):
                chunk_id = str(item.get("chunk_id", ""))
                if not chunk_id:
                    continue
                rank_sources[chunk_id][source_name] = rank
                if chunk_id not in merged:
                    merged[chunk_id] = dict(item)
                else:
                    merged[chunk_id].update({key: value for key, value in item.items() if key not in {"chunk_id", "text"}})

        fused: List[Dict[str, object]] = []
        for chunk_id, item in merged.items():
            rrf_score = 0.0
            source_ranks = rank_sources.get(chunk_id, {})
            for rank in source_ranks.values():
                rrf_score += 1.0 / (self.rrf_k + rank)
            payload = dict(item)
            payload["rrf_score"] = rrf_score
            payload["dense_rank"] = source_ranks.get("dense")
            payload["bm25_rank"] = source_ranks.get("bm25")
            fused.append(payload)

        fused.sort(
            key=lambda item: (
                item.get("rrf_score", 0.0),
                1.0 if item.get("dense_rank") is not None else 0.0,
                1.0 if item.get("bm25_rank") is not None else 0.0,
                item.get("lexical_score", 0.0),
                item.get("vector_score", 0.0),
                item.get("bm25_score", 0.0),
            ),
            reverse=True,
        )
        return fused[:top_k]

    def _fine_rerank(self, question: str, documents: List[Dict[str, object]], top_k: int) -> List[Dict[str, object]]:
        if not documents:
            return []
        return self.reranker_client.rerank(question=question, documents=documents, top_k=top_k)

    def _ensure_bm25_index(self, document_id: str = "") -> None:
        chunks = self.mysql_repo.list_document_chunks(document_id=document_id)
        signature = self._chunk_signature(chunks, document_id)
        if signature == self._bm25_signature:
            return

        docs: List[Dict[str, object]] = []
        doc_freq: Counter[str] = Counter()
        total_len = 0

        for chunk in chunks:
            text = str(chunk.get("text", ""))
            tokens = keyword_tokens(text)
            if not tokens:
                continue
            total_len += len(tokens)
            term_counts = Counter(tokens)
            docs.append(
                {
                    "payload": chunk,
                    "term_counts": term_counts,
                    "doc_len": len(tokens),
                }
            )
            for term in term_counts:
                doc_freq[term] += 1

        self._bm25_docs = docs
        self._bm25_doc_freq = dict(doc_freq)
        self._bm25_corpus_size = len(docs)
        self._bm25_avg_doc_len = total_len / max(len(docs), 1)
        self._bm25_signature = signature

    def _bm25_idf(self, term: str) -> float:
        doc_freq = self._bm25_doc_freq.get(term, 0)
        numerator = self._bm25_corpus_size - doc_freq + 0.5
        denominator = doc_freq + 0.5
        return math.log(1.0 + numerator / max(denominator, 1e-9))

    def _chunk_signature(self, chunks: List[Dict[str, object]], document_id: str = "") -> str:
        if not chunks:
            return f"empty:{document_id or 'all'}"
        digest = hashlib.md5()
        digest.update((document_id or "all").encode("utf-8"))
        digest.update(str(len(chunks)).encode("utf-8"))
        for item in chunks:
            digest.update(str(item.get("chunk_id", "")).encode("utf-8"))
        return digest.hexdigest()
