from __future__ import annotations

from gd2.database import ExecutionResult
from gd2.schemas import ScheduleSqlPlan


def format_query_rows(rows: list[dict]) -> str:
    if not rows:
        return "查询结果：mysql 里面没有符合条件的日程。"

    lines = ["查询结果："]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. id={row['id']} | {row['schedule_time']} | {row['title']} | {row['normalized_request']}"
        )
    return "\n".join(lines)


def format_result(plan: ScheduleSqlPlan, execution: ExecutionResult, beijing_now: str) -> str:
    if plan.action == "query":
        return (
            f"生成的 SQL：{execution.sql}\n"
            f"SQL 参数：{plan.params}\n"
            f"{plan.summary}\n"
            f"当前北京时间：{beijing_now}\n"
            f"操作结果：已经从 mysql 里面查询完成\n"
            f"目标库表：{execution.database}.{execution.table}\n"
            f"{format_query_rows(execution.rows)}"
        )

    if plan.action == "add":
        action_text = "已经保存到 mysql 里面"
    elif plan.action == "delete_by_id":
        action_text = "已经按查询序号对应的日程从 mysql 里面删除"
    else:
        action_text = "已经从 mysql 里面删除"

    return (
        f"生成的 SQL：{execution.sql}\n"
        f"SQL 参数：{plan.params}\n"
        f"{plan.summary}\n"
        f"当前北京时间：{beijing_now}\n"
        f"操作结果：{action_text}\n"
        f"目标库表：{execution.database}.{execution.table}\n"
        f"日程标题：{execution.title}\n"
        f"日程时间：{execution.schedule_time}\n"
        f"影响行数：{execution.affected_rows}"
    )
