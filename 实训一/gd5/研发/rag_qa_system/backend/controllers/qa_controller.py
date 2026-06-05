"""Controller layer for question answering."""

from __future__ import annotations

from dataclasses import dataclass

from rag_qa_system.backend.services.answer_service import AnswerService
from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.qa_controller")


@dataclass
class QAController:
    answer_service: AnswerService

    def handle_question(self, question: str, session_id: str = "", document_id: str = "") -> dict:
        question = question.strip()
        if not question:
            LOGGER.warning("qa_rejected | reason=empty_question")
            return {"error": "question is required"}
        return self.answer_service.answer(question=question, session_id=session_id, document_id=document_id.strip())

    def get_history(self, session_id: str) -> dict:
        return self.answer_service.get_conversation(session_id)

    def clear_history(self, session_id: str) -> dict:
        return self.answer_service.clear_conversation(session_id)
