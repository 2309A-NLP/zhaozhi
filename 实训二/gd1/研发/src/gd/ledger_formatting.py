from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def display_transaction_type(transaction_type: str) -> str:
    # 把内部值 income / expense 转成中文展示
    return "收入" if transaction_type == "income" else "支出"


def format_decimal(amount: Decimal) -> str:
    # 金额统一四舍五入保留两位小数
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    # 把数据库记录转成更适合输出的字典
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            normalized[key] = format_decimal(value)
        else:
            normalized[key] = str(value) if key in {"transaction_date", "created_at"} else value
    return normalized


def format_create_message(record: dict[str, str]) -> str:
    # 生成新增账目的中文提示
    type_label = display_transaction_type(record["transaction_type"])
    return (
        "已成功写入 1 条账目："
        f"日期 {record['date']}，成员 {record['member_name']}，事项 {record['item']}，"
        f"类型 {type_label}，金额 {record['amount']} 元。"
    )


def format_query_message(rows: list[dict[str, Any]]) -> str:
    # 生成查询结果的中文列表
    if not rows:
        return "没有查询到符合条件的账目记录。"

    lines = ["查询结果如下："]
    for row in rows:
        type_label = display_transaction_type(row["transaction_type"])
        lines.append(
            f"- ID {row['id']} | 日期：{row['transaction_date']} | 成员：{row['member_name']} | "
            f"事项：{row['item']} | 类型：{type_label} | 金额：{row['amount']} 元"
        )
    return "\n".join(lines)


def format_delete_message(deleted_count: int) -> str:
    # 生成删除结果的中文提示
    return f"已从 MySQL 数据库中删除 {deleted_count} 条账目记录。"
