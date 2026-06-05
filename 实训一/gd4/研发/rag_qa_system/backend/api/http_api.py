"""API facade that keeps transport details out of business logic."""

from __future__ import annotations

from dataclasses import dataclass

from rag_qa_system.backend.controllers.knowledge_controller import KnowledgeController
from rag_qa_system.backend.controllers.qa_controller import QAController


@dataclass
class HttpApi:
    qa_controller: QAController
    knowledge_controller: KnowledgeController

    def post_answer(self, payload: dict) -> dict:
        return self.qa_controller.handle_question(
            payload.get("question", ""),
            payload.get("document_id", ""),
        )

    def post_ingest_path(self, payload: dict) -> dict:
        return self.knowledge_controller.ingest_path(payload)

    def post_ingest_file(self, payload: dict) -> dict:
        return self.knowledge_controller.ingest_file(payload)

    def get_files(self) -> dict:
        return self.knowledge_controller.list_files()

    def get_stats(self) -> dict:
        return self.knowledge_controller.stats()
