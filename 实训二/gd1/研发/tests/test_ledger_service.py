# gd1 的单元测试，覆盖记账校验、金额规则、删除逻辑、时间工具
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from gd.ledger_service import EXPECTED_INSERT_SQL, LedgerService
from gd.ledger_validation import build_query_sql, validate_record
from gd.time_utils import get_beijing_time_context


class LedgerServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.service = LedgerService.__new__(LedgerService)

    def test_extract_json_object_from_markdown_block(self):
        raw = '```json\n{"intent":"clarify","needs_clarification":true}\n```'
        parsed = self.service._extract_json_object(raw)
        self.assertEqual(parsed["intent"], "clarify")
        self.assertTrue(parsed["needs_clarification"])

    def test_validate_insert_sql_accepts_only_whitelisted_template(self):
        sql = """
        INSERT INTO transactions
        (transaction_date, member_name, item, transaction_type, amount, currency, original_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        self.assertEqual(self.service._validate_insert_sql(sql), EXPECTED_INSERT_SQL)

    def test_expense_amount_is_saved_as_negative(self):
        record = {
            "date": "2026-06-12",
            "member_name": "妈妈",
            "item": "买菜",
            "transaction_type": "expense",
            "amount": "30",
            "currency": "cny",
        }
        validated = self.service._validate_record(record, "妈妈买菜花了30元")
        self.assertEqual(validated["amount"], "-30.00")
        self.assertEqual(validated["currency"], "CNY")

    def test_income_amount_is_saved_as_positive(self):
        record = {
            "date": "2026-06-12",
            "member_name": "爸爸",
            "item": "工资",
            "transaction_type": "income",
            "amount": "12000",
            "currency": "cny",
        }
        validated = self.service._validate_record(record, "今天爸爸工资到账12000元")
        self.assertEqual(validated["amount"], "12000.00")

    def test_insert_params_convert_expense_amount_to_negative(self):
        params = [
            "2026-06-12",
            "女儿",
            "登山鞋",
            "expense",
            "499.00",
            "CNY",
            "今天女儿买了双登山鞋499元",
        ]
        normalized = self.service._normalize_insert_params(params, "expense")
        self.assertEqual(normalized[4], "-499.00")

    def test_infer_expense_when_user_does_not_explicitly_say_expense(self):
        inferred = self.service._infer_transaction_type("今天女儿买了双登山鞋499元")
        self.assertEqual(inferred, "expense")

    def test_infer_income_when_user_does_not_explicitly_say_income(self):
        inferred = self.service._infer_transaction_type("今天爸爸工资到账12000元")
        self.assertEqual(inferred, "income")

    def test_delete_without_confirmation_can_continue_if_filters_are_present(self):
        plan = {
            "delete_filters": {
                "member_name": "女儿",
                "item": "旅游团",
                "confirmed": False,
            }
        }

        captured = {}

        def fake_build_delete_sql(filters):
            captured["filters"] = filters
            return (
                "SELECT COUNT(*) AS total FROM transactions WHERE member_name = %s",
                ["女儿"],
                "DELETE FROM transactions WHERE member_name = %s LIMIT %s",
                ["女儿", 20],
            )

        class DummyRepo:
            def count_transactions(self, sql, params):
                return 1

            def delete_transactions(self, sql, params):
                return 1

        self.service.repository = DummyRepo()
        self.service._build_delete_sql = fake_build_delete_sql
        result = self.service._handle_delete(plan)

        self.assertEqual(captured["filters"]["member_name"], "女儿")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.intent, "delete")

    def test_beijing_time_context_has_expected_shape(self):
        context = get_beijing_time_context()
        self.assertEqual(context.timezone_name, "Asia/Shanghai")
        self.assertRegex(context.date, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(context.time, r"^\d{2}:\d{2}:\d{2}$")
        self.assertRegex(context.iso_datetime, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_validation_module_builds_query_sql_with_keyword_filter(self):
        sql, params = build_query_sql({"keyword": "买菜", "limit": 5})
        self.assertIn("item LIKE %s", sql)
        self.assertEqual(params, ["%买菜%", 5])

    def test_validation_module_rejects_missing_member_name(self):
        with self.assertRaises(ValueError):
            validate_record(
                {
                    "date": "2026-06-12",
                    "member_name": "",
                    "item": "买菜",
                    "transaction_type": "expense",
                    "amount": "30",
                    "currency": "CNY",
                },
                "买菜花了30元",
            )


if __name__ == "__main__":
    unittest.main()
