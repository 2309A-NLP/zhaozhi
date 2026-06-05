"""Milvus-backed vector repository."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from rag_qa_system.backend.utils.logger import get_logger
from rag_qa_system.backend.utils.text_utils import overlap_score


LOGGER = get_logger("rag.milvus")


@dataclass
class MilvusRepository:
    host: str
    port: int
    collection_name: str
    embedding_dim: int

    def __post_init__(self) -> None:
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
        except ImportError as exc:
            raise RuntimeError("pymilvus is required for Milvus access") from exc

        self._Collection = Collection
        self._CollectionSchema = CollectionSchema
        self._DataType = DataType
        self._FieldSchema = FieldSchema
        self._connections = connections
        self._utility = utility

        self._connections.connect(alias="default", host=self.host, port=str(self.port))
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

    def search(self, vector: List[float], question: str, top_k: int = 5, document_id: str = "") -> List[Dict[str, Any]]:
        self._collection.load()
        expr = None
        if document_id.strip():
            expr = f'document_id == "{self._escape(document_id.strip())}"'
        search_hits = self._collection.search(
            data=[vector],
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=max(top_k * 3, top_k),
            expr=expr,
            output_fields=["chunk_id", "document_id", "document_name", "source_path", "text"],
        )
        hits: List[Dict[str, Any]] = []
        for hit in search_hits[0]:
            entity = hit.entity
            lexical = overlap_score(question, entity.get("text", ""))
            score = float(hit.score) * 0.7 + lexical * 0.3
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
        return hits[:top_k]

    def count_vectors(self) -> int:
        self._collection.load()
        return self._collection.num_entities

    def list_documents(self) -> List[Dict[str, str]]:
        self._collection.load()
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
            return collection
        return self._create_collection()

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
        return collection

    def _delete_by_chunk_ids(self, chunk_ids: List[str]) -> None:
        if not chunk_ids:
            return
        escaped = ", ".join(f'"{self._escape(chunk_id)}"' for chunk_id in chunk_ids)
        self._collection.delete(expr=f"chunk_id in [{escaped}]")

    def _escape(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
