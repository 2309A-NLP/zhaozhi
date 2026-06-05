"""Milvus-backed vector repository."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List

from rag_qa_system.backend.utils.logger import get_logger
from rag_qa_system.backend.utils.text_utils import overlap_score


LOGGER = get_logger("rag.milvus")


@dataclass
class MilvusRepository:
    host: str
    port: int
    database: str
    collection_name: str
    embedding_dim: int
    _collection_loaded: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, db, utility
        except ImportError as exc:
            raise RuntimeError("pymilvus is required for Milvus access") from exc

        self._Collection = Collection
        self._CollectionSchema = CollectionSchema
        self._DataType = DataType
        self._FieldSchema = FieldSchema
        self._connections = connections
        self._db = db
        self._utility = utility

        admin_alias = "__milvus_admin__"
        self._connections.connect(alias=admin_alias, host=self.host, port=str(self.port))
        self._ensure_database(admin_alias)
        self._connections.disconnect(admin_alias)

        self._connections.connect(alias="default", host=self.host, port=str(self.port), db_name=self.database)
        self._collection = self._ensure_collection()

    def upsert_vectors(self, items: List[Dict[str, Any]]) -> None:
        if not items:
            return
        chunk_ids = [item["chunk_id"] for item in items]
        self._delete_by_chunk_ids(chunk_ids)
        entities = [
            [item["chunk_id"] for item in items],
            [item["document_id"] for item in items],
            [item["document_name"] for item in items],
            [item["source_path"] for item in items],
            [item["text"] for item in items],
            [item["vector"] for item in items],
        ]
        self._collection.insert(entities)
        self._collection.flush()

    def delete_document_vectors(self, document_id: str) -> None:
        self._collection.delete(expr=f'document_id == "{self._escape(document_id)}"')
        self._collection.flush()

    def search(
        self,
        vector: List[float],
        question: str,
        top_k: int = 5,
        document_id: str = "",
        lexical_weight: float = 0.3,
        diversify_documents: bool = True,
        limit_multiplier: int = 6,
    ) -> List[Dict[str, Any]]:
        self._load_collection()
        expr = None
        scoped_document_id = document_id.strip()
        if scoped_document_id:
            expr = f'document_id == "{self._escape(scoped_document_id)}"'
        search_hits = self._collection.search(
            data=[vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=max(top_k * max(1, limit_multiplier), top_k),
            expr=expr,
            output_fields=["chunk_id", "document_id", "document_name", "source_path", "text"],
        )
        hits: List[Dict[str, Any]] = []
        vector_weight = max(0.0, 1.0 - lexical_weight)
        for hit in search_hits[0]:
            entity = hit.entity
            lexical = overlap_score(question, entity.get("text", ""))
            score = float(hit.score) * vector_weight + lexical * lexical_weight
            hits.append(
                {
                    "chunk_id": entity.get("chunk_id"),
                    "document_id": entity.get("document_id"),
                    "document_name": entity.get("document_name"),
                    "source_path": entity.get("source_path"),
                    "text": entity.get("text"),
                    "score": score,
                    "vector_score": float(hit.score),
                    "lexical_score": lexical,
                }
            )
        hits.sort(key=lambda item: item["score"], reverse=True)
        if diversify_documents and not scoped_document_id:
            hits = self._diversify_hits_by_document(hits, top_k)
        return hits[:top_k]

    def count_vectors(self) -> int:
        self._load_collection()
        return self._collection.num_entities

    def list_documents(self) -> List[Dict[str, str]]:
        self._load_collection()
        entities = self._collection.query(
            expr='document_id != ""',
            output_fields=["document_id", "document_name", "source_path"],
            limit=max(self._collection.num_entities, 1),
        )
        documents_by_id: Dict[str, Dict[str, str]] = {}
        for entity in entities:
            document_id = str(entity.get("document_id", "")).strip()
            if not document_id or document_id in documents_by_id:
                continue
            documents_by_id[document_id] = {
                "document_id": document_id,
                "name": str(entity.get("document_name", "")).strip(),
                "path": str(entity.get("source_path", "")).strip(),
            }
        return sorted(documents_by_id.values(), key=lambda item: item["name"].lower())

    def _ensure_collection(self):
        if self._utility.has_collection(self.collection_name):
            collection = self._Collection(self.collection_name)
            field_names = {field.name for field in collection.schema.fields}
            expected_names = {"chunk_id", "document_id", "document_name", "source_path", "text", "embedding"}
            vector_field = next((field for field in collection.schema.fields if field.name == "embedding"), None)
            schema_matches = field_names == expected_names and vector_field is not None
            existing_dim = int((vector_field.params or {}).get("dim", 0)) if vector_field else 0
            if not schema_matches or existing_dim != self.embedding_dim:
                if collection.num_entities > 0:
                    raise RuntimeError(
                        f"Milvus collection '{self.collection_name}' schema mismatch. Existing fields={sorted(field_names)}, "
                        f"existing_dim={existing_dim}, expected_dim={self.embedding_dim}. "
                        "Please migrate or drop the collection manually."
                    )
                collection.drop()
                return self._create_collection()
            collection.load()
            self._collection_loaded = True
            return collection
        return self._create_collection()

    def _ensure_database(self, alias: str) -> None:
        existing = set(self._db.list_database(using=alias))
        if self.database in existing:
            return
        self._db.create_database(db_name=self.database, using=alias)
        LOGGER.info("milvus_database_created | database=%s", self.database)

    def _create_collection(self):
        fields = [
            self._FieldSchema(name="chunk_id", dtype=self._DataType.VARCHAR, is_primary=True, auto_id=False, max_length=128),
            self._FieldSchema(name="document_id", dtype=self._DataType.VARCHAR, max_length=64),
            self._FieldSchema(name="document_name", dtype=self._DataType.VARCHAR, max_length=255),
            self._FieldSchema(name="source_path", dtype=self._DataType.VARCHAR, max_length=1024),
            self._FieldSchema(name="text", dtype=self._DataType.VARCHAR, max_length=65535),
            self._FieldSchema(name="embedding", dtype=self._DataType.FLOAT_VECTOR, dim=self.embedding_dim),
        ]
        schema = self._CollectionSchema(fields=fields, description="RAG document chunks")
        collection = self._Collection(name=self.collection_name, schema=schema)
        collection.create_index(
            field_name="embedding",
            index_params={"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}},
        )
        collection.load()
        self._collection_loaded = True
        return collection

    def _load_collection(self) -> None:
        if self._collection_loaded:
            return
        self._collection.load()
        self._collection_loaded = True

    def _delete_by_chunk_ids(self, chunk_ids: List[str]) -> None:
        if not chunk_ids:
            return
        escaped = ", ".join(f'"{self._escape(chunk_id)}"' for chunk_id in chunk_ids)
        self._collection.delete(expr=f"chunk_id in [{escaped}]")

    def _diversify_hits_by_document(self, hits: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        if len(hits) <= 1:
            return hits

        buckets: Dict[str, List[Dict[str, Any]]] = {}
        document_order: List[str] = []
        for hit in hits:
            document_key = str(hit.get("document_id", "")).strip() or "__unknown__"
            if document_key not in buckets:
                buckets[document_key] = []
                document_order.append(document_key)
            buckets[document_key].append(hit)

        if len(document_order) <= 1:
            return hits

        max_per_document = max(1, math.ceil(top_k / len(document_order)))
        diversified: List[Dict[str, Any]] = []
        consumed_per_document = {document_key: 0 for document_key in document_order}

        while len(diversified) < top_k:
            added_in_round = False
            for document_key in document_order:
                bucket = buckets[document_key]
                if not bucket or consumed_per_document[document_key] >= max_per_document:
                    continue
                diversified.append(bucket.pop(0))
                consumed_per_document[document_key] += 1
                added_in_round = True
                if len(diversified) >= top_k:
                    break
            if not added_in_round:
                break

        if len(diversified) < top_k:
            remaining_hits: List[Dict[str, Any]] = []
            for document_key in document_order:
                remaining_hits.extend(buckets[document_key])
            diversified.extend(remaining_hits[: top_k - len(diversified)])

        return diversified

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
