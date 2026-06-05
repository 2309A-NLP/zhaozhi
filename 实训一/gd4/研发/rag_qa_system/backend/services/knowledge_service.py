"""Knowledge ingestion and listing service."""

from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository
from rag_qa_system.backend.utils.logger import get_logger
from rag_qa_system.offline.ingest import KnowledgeIngestor


LOGGER = get_logger("rag.knowledge_service")
PDF_MAGIC = b"%PDF-"


@dataclass
class KnowledgeService:
    project_root: Path
    pdf_dir: Path
    uploads_dir: Path
    mysql_repo: MysqlRepository
    milvus_repo: MilvusRepository
    ingestor: KnowledgeIngestor
    redis_repo: RedisRepository | None = None
    max_upload_bytes: int = 50 * 1024 * 1024

    def list_available_pdfs(self) -> List[Dict[str, str]]:
        try:
            return [
                {
                    "document_id": str(item.get("document_id", "")),
                    "name": str(item.get("document_name", "")),
                    "path": str(item.get("source_path", "")),
                }
                for item in self.mysql_repo.list_documents()
            ]
        except Exception:
            LOGGER.exception("list_documents_from_mysql_failed")
            return self.milvus_repo.list_documents()

    def ingest_pdf_path(self, pdf_path: str) -> Dict[str, object]:
        path = Path(pdf_path).expanduser()
        if not path.is_absolute():
            candidate_paths = [
                self.pdf_dir / path,
                self.project_root / path,
            ]
            for candidate in candidate_paths:
                if candidate.exists():
                    path = candidate.resolve()
                    break
            else:
                path = candidate_paths[0].resolve()
        if not path.exists() or not path.is_file():
            return {"error": f"PDF not found: {path}"}
        result = self.ingestor.ingest_pdf(str(path), display_name=path.name)
        self._invalidate_retrieval_cache()
        return result

    def ingest_uploaded_pdf(self, filename: str, content_base64: str) -> Dict[str, object]:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path(filename).name
        safe_display_name = self._sanitize_filename(original_name)
        safe_name = f"{uuid.uuid4().hex}_{safe_display_name}"
        target = self.uploads_dir / safe_name
        try:
            file_bytes = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError):
            return {"error": "invalid base64 file content"}
        validation_error = self._validate_pdf_bytes(file_bytes)
        if validation_error:
            return {"error": validation_error}
        target.write_bytes(file_bytes)
        result = self.ingestor.ingest_pdf(str(target), display_name=original_name)
        self._invalidate_retrieval_cache()
        return result

    def get_stats(self) -> Dict[str, int]:
        return {
            "document_count": len(self.mysql_repo.list_documents()),
            "chunk_count": self.mysql_repo.count_chunks(),
            "vector_count": self.milvus_repo.count_vectors(),
        }

    def _sanitize_filename(self, filename: str) -> str:
        invalid_chars = set('<>:"/\\|?*')
        cleaned = "".join("_" if char in invalid_chars or ord(char) < 32 else char for char in filename)
        cleaned = cleaned.strip().rstrip(". ")
        cleaned = cleaned or f"upload_{uuid.uuid4().hex}.pdf"
        return cleaned if cleaned.lower().endswith(".pdf") else f"{cleaned}.pdf"

    def _validate_pdf_bytes(self, file_bytes: bytes) -> str:
        if not file_bytes:
            return "uploaded file is empty"
        if len(file_bytes) > self.max_upload_bytes:
            return f"uploaded file is too large; max bytes is {self.max_upload_bytes}"
        if not file_bytes.startswith(PDF_MAGIC):
            return "uploaded file is not a valid PDF"
        return ""

    def _invalidate_retrieval_cache(self) -> None:
        if self.redis_repo is None:
            return
        try:
            deleted = self.redis_repo.delete_prefix("retrieval:")
            LOGGER.info("retrieval_cache_invalidated | deleted=%s", deleted)
        except Exception:
            LOGGER.exception("retrieval_cache_invalidate_failed")
