"""Prompt assembly service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from rag_qa_system.backend.utils.text_utils import best_matching_excerpt, normalize_text


@dataclass
class PromptService:
    context_doc_char_limit: int = 400

    def build_messages(self, question: str, contexts: List[Dict[str, object]]) -> List[Dict[str, str]]:
        system_prompt = (
            "你是企业知识库问答助手。"
            "必须优先依据给定片段回答，不要编造事实。"
            "如果证据不足，请明确写出“无法根据知识库确认”，并说明还缺什么信息。"
            "回答使用简体中文，先给结论，再补充1到3条依据。"
            "只有片段中明确出现的数字、时间、姓名和结论，才允许直接引用。"
        )
        context_blocks = [self._format_context(question, item, index) for index, item in enumerate(contexts, start=1)]
        context_text = "\n\n".join(context_blocks) if context_blocks else "未检索到可用片段。"
        user_prompt = (
            "请根据以下片段回答用户问题。\n\n"
            f"{context_text}\n\n"
            "输出要求：\n"
            "1. 先给出直接答案。\n"
            "2. 如果证据不足，明确写“无法根据知识库确认”。\n"
            "3. 简要列出所依据的片段编号。\n"
            "4. 不要使用片段之外的常识补全事实。\n\n"
            f"用户问题: {question}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _format_context(self, question: str, item: Dict[str, object], index: int) -> str:
        text = normalize_text(str(item.get("text", "")))
        excerpt_limit = min(220, max(140, self.context_doc_char_limit // 2))
        excerpt = best_matching_excerpt(question, text, max_chars=excerpt_limit)
        body_limit = max(0, self.context_doc_char_limit - len(excerpt) - 24)
        body = text[:body_limit] if body_limit else ""
        if excerpt and body and excerpt not in body:
            content = f"相关句子: {excerpt}\n连续上下文: {body}"
        else:
            content = body or excerpt or "无可用文本"
        return "\n".join(
            [
                f"[片段{index}]",
                f"文档: {item.get('document_name', '')}",
                f"分数: {item.get('score', '')}",
                f"内容: {content}",
            ]
        )
