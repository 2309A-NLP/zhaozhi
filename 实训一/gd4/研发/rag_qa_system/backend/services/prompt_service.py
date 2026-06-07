"""Prompt assembly service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PromptService:
    context_doc_char_limit: int = 1600

    def build_messages(self, question: str, contexts: List[Dict[str, object]]) -> List[Dict[str, str]]:
        system_prompt = (
            "你是一个严格依赖检索片段作答的知识库问答助手。\n"
            "请只根据给出的片段回答，不要使用常识补全，不要猜测，不要沿用历史对话中的信息。\n"
            "回答规则：\n"
            "1. 只有片段明确支持的内容才能写进答案。\n"
            "2. 如果问题涉及“几个、哪些、由什么构成、下设什么、增长率最快、负增长、最高、最低、占比、比例”等比较或统计，请逐段核对名称、数量、层级和数值。\n"
            "3. 如果片段的内容类型是 chart，优先使用其中明确列出的结构关系、增长率数据、极值结论和节点关系。\n"
            "4. 对组织结构问题，只有在片段明确出现“下设、由…构成、上级=、A -> B、组织结构关系”等层级信息时，才能认定上下级关系。\n"
            "5. 对增长率问题，只有在片段明确出现行业名称和对应百分比，或明确写出“增长率最快/负增长”时，才能下结论；不能凭图表标题或上下文猜测。\n"
            "6. 多个片段互相补充时，请合并后给出最终答案；如果片段冲突，优先采用更直接、更完整的片段，并简短说明存在冲突。\n"
            "7. 如果片段不足以支持问题的某一部分，只回答能确认的部分，并明确说明哪一部分信息不足。\n"
            "8. 不要输出“依据如下”“片段1/片段2”等字样，不要解释检索过程。"
        )
        context_blocks: List[str] = []
        for index, item in enumerate(contexts, start=1):
            limit = self.context_doc_char_limit
            if str(item.get("content_type", "text")) == "chart":
                limit = max(limit, 4000)
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

        user_prompt = (
            "请从以下检索片段中直接抽取答案。\n"
            "如果问题有两个子问，请分别回答；如果片段不足，请明确说“检索片段未提供足够信息”。\n\n"
            f"{chr(10).join(context_blocks) if context_blocks else '未检索到任何片段。'}\n\n"
            f"用户问题: {question}\n\n"
            "请直接作答。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
