"""Prompt assembly service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from rag_qa_system.backend.utils.text_utils import best_matching_excerpt


@dataclass
class PromptService:
    context_doc_char_limit: int = 400

    def build_messages(self, question: str, contexts: List[Dict[str, object]]) -> List[Dict[str, str]]:
        system_prompt = (
            "你是一个基于企业知识库的问答助手。"
            "必须优先依据给定检索片段作答，不要编造事实。"
            "如果证据不足，明确说明信息不足，并指出缺失点。"
            "回答使用简体中文，先给结论，再用简短条目列出依据。"
            "只有在片段中能找到依据时，才给出数字、时间、姓名或结论。"
        )
        context_blocks: List[str] = []
        for index, item in enumerate(contexts, start=1):
            excerpt = best_matching_excerpt(
                query=question,
                text=str(item.get("text", "")),
                max_chars=self.context_doc_char_limit,
            )
            context_blocks.append(
                "\n".join(
                    [
                        f"[片段{index}]",
                        f"文档: {item.get('document_name', '')}",
                        f"分数: {item.get('score', '')}",
                        f"内容: {excerpt}",
                    ]
                )
            )

        context_text = "\n\n".join(context_blocks) if context_blocks else "未检索到可用片段。"
        user_prompt = (
            "请仅根据以下片段回答用户问题。\n\n"
            f"{context_text}\n\n"
            "输出要求：\n"
            "1. 先给出直接答案。\n"
            "2. 如果证据不足，明确写“无法根据知识库确认”。\n"
            "3. 简要列出所依据的片段编号。\n\n"
            f"用户问题: {question}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
