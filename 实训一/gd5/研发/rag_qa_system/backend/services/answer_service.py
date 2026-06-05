"""Answer orchestration service."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List

from rag_qa_system.backend.models.llm_client import LLMClient
from rag_qa_system.backend.repositories.mysql_repo import MysqlRepository
from rag_qa_system.backend.repositories.redis_repo import RedisRepository
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
    redis_repo: RedisRepository
    top_k: int = 5
    min_context_score: float = 0.2
    conversation_ttl_seconds: int = 3600
    conversation_max_messages: int = 12
    _log_executor: ThreadPoolExecutor = field(
        init=False,
        repr=False,
        default_factory=lambda: ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-log"),
    )

    def answer(self, question: str, session_id: str = "", document_id: str = "") -> Dict[str, Any]:
        started_at = time.perf_counter()
        active_session_id = session_id.strip() or uuid.uuid4().hex
        try:
            history = self._load_conversation_history(active_session_id)
            results = self.retrieval_service.retrieve(question=question, top_k=self.top_k, document_id=document_id)
            if self._should_short_circuit(results):
                answer = "无法根据当前知识库内容确认该问题，建议补充更相关的文档或提供更具体的问题。"
            else:
                messages = self.prompt_service.build_messages(
                    question=question,
                    contexts=results,
                    conversation_history=history,
                )
                answer = self.llm_client.chat(messages)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            payload = {
                "session_id": active_session_id,
                "question": question,
                "answer": answer,
                "sources": results,
                "source_count": len(results),
                "duration_ms": duration_ms,
                "history_count": len(history),
                "document_id": document_id,
            }
            self._append_conversation_turn(active_session_id, question, answer)
            self._save_qa_log_async(payload)
            LOGGER.info(
                "qa_success | session_id=%s | question=%r | duration_ms=%s | source_count=%s",
                active_session_id,
                question,
                duration_ms,
                len(results),
            )
            return payload
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            LOGGER.exception(
                "qa_failed | session_id=%s | question=%r | duration_ms=%s",
                active_session_id,
                question,
                duration_ms,
            )
            raise

    def get_conversation(self, session_id: str) -> Dict[str, Any]:
        active_session_id = session_id.strip()
        if not active_session_id:
            return {"error": "session_id is required"}
        messages = self.redis_repo.get_conversation(active_session_id)
        return {
            "session_id": active_session_id,
            "messages": messages,
        }

    def clear_conversation(self, session_id: str) -> Dict[str, Any]:
        active_session_id = session_id.strip()
        if not active_session_id:
            return {"error": "session_id is required"}
        self.redis_repo.clear_conversation(active_session_id)
        return {
            "session_id": active_session_id,
            "cleared": True,
        }

    def _save_qa_log_async(self, payload: Dict[str, object]) -> None:
        def worker() -> None:
            try:
                self.mysql_repo.save_qa_log(payload)
            except Exception:
                LOGGER.exception("qa_log_save_failed | question=%r", payload.get("question", ""))

        self._log_executor.submit(worker)

    def _should_short_circuit(self, results: List[Dict[str, object]]) -> bool:
        if not results:
            return True
        best_score = max(float(item.get("score", 0.0)) for item in results)
        return best_score < self.min_context_score

    def _load_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        history = self.redis_repo.get_conversation(session_id)
        return [
            {
                "role": str(item.get("role", "")).strip(),
                "content": str(item.get("content", "")).strip(),
            }
            for item in history
            if str(item.get("role", "")).strip() in {"user", "assistant"} and str(item.get("content", "")).strip()
        ]

    def _append_conversation_turn(self, session_id: str, question: str, answer: str) -> None:
        self.redis_repo.append_conversation_messages(
            session_id=session_id,
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
            ttl_seconds=self.conversation_ttl_seconds,
            max_messages=self.conversation_max_messages,
        )
