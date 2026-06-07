"""Offline ingestion pipeline."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from rag_qa_system.backend.models.llm_client import EmbeddingClient
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.offline.chunker import TextChunker
from rag_qa_system.offline.pdf_parser import PdfParser


@dataclass
class KnowledgeIngestor:
    parser: PdfParser
    chunker: TextChunker
    embedding_client: EmbeddingClient
    mysql_repo: MysqlRepository
    milvus_repo: MilvusRepository

    def ingest_pdf(self, pdf_path: str, display_name: str | None = None) -> Dict[str, object]:
        path = Path(pdf_path).resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        file_bytes = path.read_bytes()
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError(f"File is not a valid PDF: {path.name}")

        text = self.parser.parse(str(path))
        chunks = self.chunker.split(text)
        if not chunks:
            raise ValueError(f"No text chunks produced from PDF: {path.name}")

        document_id = hashlib.md5(file_bytes).hexdigest()
        document_name = (display_name or path.name).strip() or path.name
        vectors = self.embedding_client.embed_batch(chunks)

        metadata_chunks: List[Dict[str, object]] = []
        vector_items: List[Dict[str, object]] = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{document_id}-{index}"
            content_type = self._detect_content_type(chunk)
            page_number = self._extract_page_number(chunk)
            metadata = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "document_name": document_name,
                "source_path": str(path),
                "text": chunk,
                "page_number": page_number,
                "content_type": content_type,
            }
            metadata_chunks.append(metadata)
            vector_items.append({**metadata, "vector": vector})

        self.mysql_repo.save_document(
            {
                "document_id": document_id,
                "document_name": document_name,
                "source_path": str(path),
                "chunk_count": len(metadata_chunks),
            }
        )
        self.mysql_repo.replace_document_chunks(document_id, metadata_chunks)
        self.milvus_repo.delete_document_vectors(document_id)
        self.milvus_repo.upsert_vectors(vector_items)

        return {
            "message": "知识库导入完成",
            "document_id": document_id,
            "document_name": document_name,
            "chunk_count": len(metadata_chunks),
        }

    def _detect_content_type(self, text: str) -> str:
        if (
            "[PDF图表视觉解析]" in text
            or "[PDF图表OCR解析]" in text
            or "[PDF组织结构解析]" in text
            or "组织结构关系：" in text
            or "上下级关系：" in text
        ):
            return "chart"
        if "|" in text and "\n" in text:
            return "table"
        return "text"

    def _extract_page_number(self, text: str) -> int | None:
        match = re.search(r"页码[:：]\s*(\d+)", text)
        if not match:
            return None
        return int(match.group(1))
