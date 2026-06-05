"""Answer orchestration service."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
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
    min_context_score: float = 0.1
    _log_executor: ThreadPoolExecutor = field(
        init=False,
        repr=False,
        default_factory=lambda: ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-log"),
    )

    def answer(self, question: str, document_id: str = "") -> Dict[str, object]:
        started_at = time.perf_counter()
        try:
            results = self.retrieval_service.retrieve(
                question=question,
                top_k=self.top_k,
                document_id=document_id,
            )
            if self._should_short_circuit(results):
                answer = "无法根据当前知识库确认该问题，建议补充更相关的文档，或把问题描述得更具体一些。"
            else:
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
            self._save_qa_log_async(payload)
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

    def _save_qa_log_async(self, payload: Dict[str, object]) -> None:
        def worker() -> None:
            try:
                self.mysql_repo.save_qa_log(payload)
            except Exception:
                LOGGER.exception("qa_log_save_failed | question=%r", payload.get("question", ""))

        self._log_executor.submit(worker)

    def _should_short_circuit(self, results: list[Dict[str, object]]) -> bool:
        if not results:
            return True
        best_retrieval = max(float(item.get("retrieval_score", item.get("score", 0.0))) for item in results)
        best_vector = max(float(item.get("vector_score", 0.0)) for item in results)
        best_lexical = max(float(item.get("lexical_score", 0.0)) for item in results)
        return (
            best_retrieval < self.min_context_score
            and best_vector < 0.2
            and best_lexical < 0.08
        )
