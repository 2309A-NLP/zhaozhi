from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from gd.ledger_formatting import format_decimal

# 新增记录只允许这一种插入模板，防止模型生成任意 SQL
EXPECTED_INSERT_SQL = (
    "INSERT INTO transactions "
    "(transaction_date, member_name, item, transaction_type, amount, currency, original_text) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
)

# 用于从原始文本里推断收入
INCOME_HINTS = (
    "收入",
    "工资",
    "薪水",
    "奖金",
    "分红",
    "到账",
    "入账",
    "收款",
    "收到",
    "卖了",
    "卖出",
    "退款",
    "报销",
)

# 用于从原始文本里推断支出
EXPENSE_HINTS = (
    "支出",
    "花了",
    "花费",
    "买了",
    "购买",
    "交了",
    "付了",
    "支付",
    "消费",
    "扣款",
    "转给",
    "打车",
    "吃饭",
    "买菜",
    "买药",
    "充值",
)


def validate_record(record: dict[str, Any], original_text: str) -> dict[str, str]:
    # 统一校验一条新增账目记录，返回规范化后的字典
    transaction_date = validate_date(record.get("date"))
    member_name = validate_text(record.get("member_name"), "成员", 64)
    item = validate_text(record.get("item"), "事项", 255)
    transaction_type = resolve_transaction_type(record.get("transaction_type"), original_text)
    amount = normalize_signed_amount(record.get("amount"), transaction_type)
    currency = validate_currency(record.get("currency"))

    return {
        "date": transaction_date,
        "member_name": member_name,
        "item": item,
        "transaction_type": transaction_type,
        "amount": amount,
        "currency": currency,
        "original_text": original_text,
    }


def resolve_transaction_type(raw_value: Any, original_text: str) -> str:
    # 先看用户有没有明确给 income/expense
    value = str(raw_value or "").strip().lower()
    if value in {"income", "expense"}:
        return value

    # 没有明确给出时，尝试从原始文本推断
    inferred = infer_transaction_type(original_text)
    if inferred:
        return inferred
    raise ValueError("transaction_type must be income or expense.")


def infer_transaction_type(text: str) -> str | None:
    # 根据关键词粗略判断这笔账是收入还是支出
    normalized = str(text).strip().lower()
    for hint in INCOME_HINTS:
        if hint in normalized:
            return "income"
    for hint in EXPENSE_HINTS:
        if hint in normalized:
            return "expense"
    return None


def normalize_signed_amount(raw_value: Any, transaction_type: str) -> str:
    # 先保证金额是合法正数，再根据类型决定正负号
    amount = validate_amount(raw_value)
    decimal_amount = Decimal(amount)
    if transaction_type == "expense":
        decimal_amount = -abs(decimal_amount)
    else:
        decimal_amount = abs(decimal_amount)
    return format_decimal(decimal_amount)


def build_query_sql(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    # 根据可选条件拼出查询 SQL，所有条件都通过参数绑定
    conditions = []
    params: list[Any] = []

    start_date = optional_date(filters.get("start_date"))
    end_date = optional_date(filters.get("end_date"))
    member_name = optional_text(filters.get("member_name"))
    transaction_type = optional_transaction_type(filters.get("transaction_type"))
    keyword = optional_text(filters.get("keyword"))
    limit = optional_limit(filters.get("limit"), default=20, maximum=100)

    if start_date:
        conditions.append("transaction_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("transaction_date <= %s")
        params.append(end_date)
    if member_name:
        conditions.append("member_name = %s")
        params.append(member_name)
    if transaction_type:
        conditions.append("transaction_type = %s")
        params.append(transaction_type)
    if keyword:
        conditions.append("item LIKE %s")
        params.append(f"%{keyword}%")

    where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = (
        "SELECT id, transaction_date, member_name, item, transaction_type, amount, currency, created_at "
        f"FROM transactions{where_sql} "
        "ORDER BY transaction_date DESC, id DESC "
        "LIMIT %s"
    )
    params.append(limit)
    return sql, params


def build_delete_sql(filters: dict[str, Any]) -> tuple[str, list[Any], str, list[Any]]:
    # 删除前先生成 count SQL，再生成 delete SQL，避免误删
    conditions = []
    params: list[Any] = []

    target_date = optional_date(filters.get("date"))
    member_name = optional_text(filters.get("member_name"))
    transaction_type = optional_transaction_type(filters.get("transaction_type"))
    item = optional_text(filters.get("item"))
    amount = optional_amount(filters.get("amount"))
    limit = optional_limit(filters.get("limit"), default=20, maximum=50)

    if target_date:
        conditions.append("transaction_date = %s")
        params.append(target_date)
    if member_name:
        conditions.append("member_name = %s")
        params.append(member_name)
    if transaction_type:
        conditions.append("transaction_type = %s")
        params.append(transaction_type)
    if item:
        conditions.append("item = %s")
        params.append(item)
    if amount:
        conditions.append("amount = %s")
        params.append(amount)

    if not conditions:
        raise ValueError("Delete requests must include at least one specific filter.")

    where_sql = " AND ".join(conditions)
    count_sql = f"SELECT COUNT(*) AS total FROM transactions WHERE {where_sql}"
    delete_sql = f"DELETE FROM transactions WHERE {where_sql} LIMIT %s"
    delete_params = [*params, limit]
    return count_sql, params, delete_sql, delete_params


def validate_insert_sql(sql: Any) -> str:
    # 只允许完全匹配预定义插入模板
    normalized = re.sub(r"\s+", " ", str(sql).strip()).strip().lower()
    expected = EXPECTED_INSERT_SQL.lower()
    if normalized != expected:
        raise ValueError("The generated SQL is not an approved INSERT statement.")
    return EXPECTED_INSERT_SQL


def normalize_params(params: Any) -> list[Any]:
    # 把各种参数统一转成适合 SQL 绑定的格式
    if not isinstance(params, list):
        raise ValueError("SQL params must be a list.")

    normalized: list[Any] = []
    for value in params:
        if isinstance(value, float):
            normalized.append(format_decimal(Decimal(str(value))))
        elif isinstance(value, Decimal):
            normalized.append(format_decimal(value))
        elif value is None:
            normalized.append("")
        else:
            normalized.append(str(value).strip())
    return normalized


def normalize_insert_params(params: Any, transaction_type: str) -> list[Any]:
    # 新增参数固定 7 个，其中第 5 个是金额，需要额外处理正负号
    normalized = normalize_params(params)
    if len(normalized) != 7:
        raise ValueError("INSERT params must contain exactly 7 values.")
    normalized[4] = normalize_signed_amount(normalized[4], transaction_type)
    return normalized


def validate_date(raw_value: Any) -> str:
    # 日期必须严格是 YYYY-MM-DD
    value = str(raw_value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Date must be in YYYY-MM-DD format.")
    return value


def validate_text(raw_value: Any, field_name: str, limit: int) -> str:
    # 文本字段不能为空，并且不能超出长度限制
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required.")
    if len(value) > limit:
        raise ValueError(f"{field_name} is too long.")
    return value


def validate_transaction_type(raw_value: Any) -> str:
    # 交易类型只能是 income 或 expense
    value = str(raw_value or "").strip().lower()
    if value not in {"income", "expense"}:
        raise ValueError("transaction_type must be income or expense.")
    return value


def validate_amount(raw_value: Any) -> str:
    # 金额必须是正数，并统一保留两位小数
    try:
        amount = Decimal(str(raw_value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Amount must be a number.") from exc
    if amount <= 0:
        raise ValueError("Amount must be positive.")
    return format_decimal(amount)


def validate_currency(raw_value: Any) -> str:
    # 币种默认 CNY，并限制为字母格式
    value = str(raw_value or "CNY").strip().upper()
    if not re.fullmatch(r"[A-Z]{3,8}", value):
        raise ValueError("Currency format is invalid.")
    return value


def optional_date(raw_value: Any) -> str | None:
    # 可选日期：空值直接返回 None，否则校验格式
    value = str(raw_value or "").strip()
    return validate_date(value) if value else None


def optional_text(raw_value: Any) -> str | None:
    # 可选文本：空值返回 None
    value = str(raw_value or "").strip()
    return value or None


def optional_transaction_type(raw_value: Any) -> str | None:
    # 可选交易类型：空值返回 None，否则校验合法性
    value = str(raw_value or "").strip().lower()
    if not value:
        return None
    return validate_transaction_type(value)


def optional_amount(raw_value: Any) -> str | None:
    # 可选金额：空值返回 None，否则校验为正数
    value = str(raw_value or "").strip()
    return validate_amount(value) if value else None


def optional_limit(raw_value: Any, default: int, maximum: int) -> int:
    # limit 既要有默认值，也要限制最大值，避免查太多或删太多
    try:
        limit = int(raw_value)
    except (TypeError, ValueError):
        return default
    return min(max(limit, 1), maximum)


def extract_json_object(raw_content: str) -> dict[str, Any]:
    # 从模型输出中提取 JSON，兼容代码块包裹的情况
    cleaned = raw_content.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The model response does not contain a valid JSON object.")
    return json.loads(cleaned[start : end + 1])
