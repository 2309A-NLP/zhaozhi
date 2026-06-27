"""Prompt assembly service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PromptService:
    context_doc_char_limit: int = 400

    def build_messages(self, question: str, contexts: List[Dict[str, object]]) -> List[Dict[str, str]]:
        system_prompt = (
            "你是一个基于知识库的问答助手。"
            "你必须优先依据检索到的片段回答，不能编造事实。"
            "如果知识库中的内容不足以支持结论，需要明确说明信息不足。"
            "回答尽量简洁，并在引用事实时对应到检索片段。"
        )
        context_blocks: List[str] = []
        for index, item in enumerate(contexts, start=1):
            text = str(item.get("text", ""))[: self.context_doc_char_limit]
            context_blocks.append(
                "\n".join(
                    [
                        f"[片段{index}]",
                        f"文档: {item.get('document_name', '')}",
                        f"得分: {item.get('score', '')}",
                        f"内容: {text}",
                    ]
                )
            )
        user_prompt = (
            "请根据以下检索片段回答用户问题。\n\n"
            f"{chr(10).join(context_blocks) if context_blocks else '未检索到任何片段。'}\n\n"
            f"用户问题: {question}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
