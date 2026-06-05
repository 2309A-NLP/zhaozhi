"""Prompt assembly service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PromptService:
    context_doc_char_limit: int = 1000

    def build_messages(self, question: str, contexts: List[Dict[str, object]]) -> List[Dict[str, str]]:
        context_blocks: List[str] = []
        for index, item in enumerate(contexts, start=1):
            limit = self.context_doc_char_limit
            if str(item.get("content_type", "text")) == "chart":
                limit = max(limit, 2500)
            text = str(item.get("text", ""))[:limit]
            context_blocks.append(
                "\n".join(
                    [
                        f"[片段{index}]",
                        f"片段ID: {item.get('chunk_id', '')}",
                        f"文档: {item.get('document_name', '')}",
                        f"页码: {item.get('page_number', '')}",
                        f"内容类型: {item.get('content_type', 'text')}",
                        f"得分: {item.get('score', '')}",
                        f"内容: {text}",
                    ]
                )
            )

        user_prompt = "\n\n".join(
            [
                f"知识库检索片段:\n{chr(10).join(context_blocks) if context_blocks else ''}",
                f"用户问题: {question}",
            ]
        )
        return [
            {"role": "user", "content": user_prompt},
        ]
