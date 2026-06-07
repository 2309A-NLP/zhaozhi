"""Answer orchestration service."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from rag_qa_system.backend.models.llm_client import LLMClient
from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.services.prompt_service import PromptService
from rag_qa_system.backend.services.retrieval_service import RetrievalService
from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.answer")


@dataclass
class AnswerService:
    retrieval_service: RetrievalService
    prompt_service: PromptService
    llm_client: LLMClient
    mysql_repo: MysqlRepository
    top_k: int = 5

    def answer(self, question: str, document_id: str = "") -> Dict[str, object]:
        started_at = time.perf_counter()
        try:
            results = self.retrieval_service.retrieve(question=question, top_k=self.top_k, document_id=document_id)
            messages = self.prompt_service.build_messages(question, results)
            answer = self.llm_client.chat(messages)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            payload = {
                "question": question,
                "answer": answer,
                "sources": results,
                "source_count": len(results),
                "duration_ms": duration_ms,
                "document_id": document_id,
            }
            self.mysql_repo.save_qa_log(payload)
            LOGGER.info(
                "qa_success | question=%r | duration_ms=%s | source_count=%s | answer=%r",
                question,
                duration_ms,
                len(results),
                answer,
            )
            return payload
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            LOGGER.exception("qa_failed | question=%r | duration_ms=%s", question, duration_ms)
            raise
