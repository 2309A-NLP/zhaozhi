"""Controller layer for knowledge ingestion."""

from __future__ import annotations

from dataclasses import dataclass

from rag_qa_system.backend.services.knowledge_service import KnowledgeService


@dataclass
class KnowledgeController:
    knowledge_service: KnowledgeService

    def list_files(self) -> dict:
        return {"files": self.knowledge_service.list_available_pdfs()}

    def ingest_path(self, payload: dict) -> dict:
        pdf_path = payload.get("pdf_path", "").strip()
        if not pdf_path:
            return {"error": "pdf_path is required"}
        return self.knowledge_service.ingest_pdf_path(pdf_path)

    def ingest_file(self, payload: dict) -> dict:
        filename = payload.get("filename", "").strip()
        content_base64 = payload.get("content_base64", "").strip()
        if not filename or not content_base64:
            return {"error": "filename and content_base64 are required"}
        return self.knowledge_service.ingest_uploaded_pdf(filename, content_base64)

    def stats(self) -> dict:
        return self.knowledge_service.get_stats()

