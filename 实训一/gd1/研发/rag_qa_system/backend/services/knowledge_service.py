"""Knowledge ingestion and listing service."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.repositories.milvus_repo import MilvusRepository
from rag_qa_system.offline.ingest import KnowledgeIngestor


@dataclass
class KnowledgeService:
    project_root: Path
    pdf_dir: Path
    uploads_dir: Path
    mysql_repo: MysqlRepository
    milvus_repo: MilvusRepository
    ingestor: KnowledgeIngestor

    def list_available_pdfs(self) -> List[Dict[str, str]]:
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
        return self.ingestor.ingest_pdf(str(path), display_name=path.name)

    def ingest_uploaded_pdf(self, filename: str, content_base64: str) -> Dict[str, object]:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path(filename).name
        safe_display_name = self._sanitize_filename(original_name)
        safe_name = f"{uuid.uuid4().hex}_{safe_display_name}"
        target = self.uploads_dir / safe_name
        target.write_bytes(base64.b64decode(content_base64))
        return self.ingestor.ingest_pdf(str(target), display_name=original_name)

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
        return cleaned or f"upload_{uuid.uuid4().hex}.pdf"
