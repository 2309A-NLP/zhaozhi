import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from gd2.database import DELETE_SQL, INSERT_SQL, validate_sql_plan
from gd2.schemas import ScheduleSqlPlan
from gd2.session import SessionState


class ValidateSqlPlanTests(unittest.TestCase):
    def test_add_plan_matches_canonical_sql(self):
        raw_request = "添加日程，2026 年 6 月 16 日 15 时要做开会"
        plan = ScheduleSqlPlan(
            action="add",
            title="开会",
            schedule_time="2026-06-16 15:00:00",
            normalized_request="添加日程，2026 年 06 月 16 日 15 时 00 分要做开会",
            sql=INSERT_SQL,
            params=[
                "开会",
                "2026-06-16 15:00:00",
                raw_request,
                "添加日程，2026 年 06 月 16 日 15 时 00 分要做开会",
                "Asia/Shanghai",
            ],
            summary="已准备新增日程。",
        )

        sql, params = validate_sql_plan(plan, raw_request)

        self.assertEqual(sql, INSERT_SQL)
        self.assertEqual(params[0], "开会")

    def test_delete_plan_matches_canonical_sql(self):
        plan = ScheduleSqlPlan(
            action="delete",
            title="开会",
            schedule_time="2026-06-16 15:00:00",
            normalized_request="删除日程，2026 年 06 月 16 日 15 时 00 分要做开会",
            sql=DELETE_SQL,
            params=["开会", "2026-06-16 15:00:00"],
            summary="已准备删除日程。",
        )

        sql, params = validate_sql_plan(plan, "删除日程，2026 年 6 月 16 日 15 时要做开会")

        self.assertEqual(sql, DELETE_SQL)
        self.assertEqual(params, ["开会", "2026-06-16 15:00:00"])

    def test_rejects_non_canonical_sql(self):
        plan = ScheduleSqlPlan(
            action="delete",
            title="开会",
            schedule_time="2026-06-16 15:00:00",
            normalized_request="删除日程，2026 年 06 月 16 日 15 时 00 分要做开会",
            sql="DELETE FROM other_table WHERE id = %s",
            params=["开会", "2026-06-16 15:00:00"],
            summary="已准备删除日程。",
        )

        with self.assertRaises(ValueError):
            validate_sql_plan(plan, "删除日程，2026 年 6 月 16 日 15 时要做开会")


class SessionStateTests(unittest.TestCase):
    def test_build_delete_by_index_plan_uses_last_query_rows(self):
        state = SessionState(
            last_query_rows=[
                {
                    "id": 42,
                    "title": "开会",
                    "schedule_time": "2026-06-16 15:00:00",
                }
            ]
        )

        plan = state.build_delete_by_index_plan("取消日程 1")

        self.assertIsNotNone(plan)
        self.assertEqual(plan.action, "delete_by_id")
        self.assertEqual(plan.params, ["42"])

    def test_build_delete_by_index_plan_rejects_missing_query_context(self):
        state = SessionState()

        with self.assertRaises(ValueError):
            state.build_delete_by_index_plan("取消日程 1")


if __name__ == "__main__":
    unittest.main()
