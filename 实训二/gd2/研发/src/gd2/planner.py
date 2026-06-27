from __future__ import annotations

import json

from gd2.schemas import ScheduleSqlPlan


def parse_plan_text(raw_text: str) -> ScheduleSqlPlan:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()

    try:
        return ScheduleSqlPlan.model_validate(json.loads(cleaned))
    except Exception as exc:
        raise ValueError(f"CrewAI 返回的内容不是有效 JSON：{cleaned}") from exc


def extract_plan(result) -> ScheduleSqlPlan:
    if isinstance(result.pydantic, ScheduleSqlPlan):
        return result.pydantic

    for task_output in reversed(result.tasks_output):
        if isinstance(task_output.pydantic, ScheduleSqlPlan):
            return task_output.pydantic
        if task_output.raw:
            return parse_plan_text(task_output.raw)

    if result.raw:
        return parse_plan_text(result.raw)

    raise ValueError("CrewAI 没有返回可执行的结构化 SQL 方案。")
