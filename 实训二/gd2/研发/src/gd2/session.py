from __future__ import annotations

import re
from dataclasses import dataclass, field

from gd2.database import DELETE_BY_ID_SQL
from gd2.schemas import ScheduleSqlPlan


CANCEL_INDEX_PATTERN = re.compile(r"^(取消|删除)日程\s*[:：]?\s*(\d+)\s*$")


@dataclass
class SessionState:
    last_query_rows: list[dict] = field(default_factory=list)

    def build_delete_by_index_plan(self, user_request: str) -> ScheduleSqlPlan | None:
        match = CANCEL_INDEX_PATTERN.match(user_request.strip())
        if not match:
            return None

        if not self.last_query_rows:
            raise ValueError("请先执行一次查询日程，再使用“取消日程 1”这种序号删除。")

        index = int(match.group(2))
        if index < 1 or index > len(self.last_query_rows):
            raise ValueError(f"当前查询结果只有 {len(self.last_query_rows)} 条，无法取消第 {index} 条。")

        row = self.last_query_rows[index - 1]
        return ScheduleSqlPlan(
            action="delete_by_id",
            title=str(row.get("title", "")),
            schedule_time=str(row.get("schedule_time", "")),
            normalized_request=f"取消查询结果中的第 {index} 条日程，数据库 id 为 {row['id']}",
            sql=DELETE_BY_ID_SQL,
            params=[str(row["id"])],
            summary=f"已定位到查询结果中的第 {index} 条日程，准备删除。",
        )

    def remember_query_rows(self, rows: list[dict]) -> None:
        self.last_query_rows = list(rows)
