from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from gd.db import MySQLLedgerRepository
from gd.ledger_formatting import (
    display_transaction_type,
    format_decimal,
    format_create_message,
    format_delete_message,
    format_query_message,
    serialize_row,
)
from gd.ledger_validation import (
    EXPECTED_INSERT_SQL,
    build_delete_sql,
    build_query_sql,
    extract_json_object,
    infer_transaction_type,
    normalize_params,
    normalize_insert_params,
    normalize_signed_amount,
    optional_amount,
    optional_date,
    optional_limit,
    optional_text,
    optional_transaction_type,
    resolve_transaction_type,
    validate_amount,
    validate_currency,
    validate_date,
    validate_insert_sql,
    validate_record,
    validate_text,
    validate_transaction_type,
)

OPENING_MESSAGE = (
    "您好，欢迎使用家庭记账助手。"
    "请直接告诉我需要新增、查询或删除哪笔账，例如："
    "“2026年6月3日，妈妈买菜花了30元”。"
)


class LedgerCrewResponse(BaseModel):
    # status 表示本次处理是否成功，还是需要追问
    status: Literal["success", "clarify", "error"]
    # intent 表示本次用户请求的核心意图
    intent: Literal["create", "query", "delete", "clarify"]
    # user_message 是最终返回给用户看的中文结果
    user_message: str = Field(..., description="面向用户的中文回复。")
    # data 保存结构化结果，方便后续程序继续处理
    data: dict[str, Any] = Field(default_factory=dict, description="本次处理的附加结构化数据。")


@dataclass
class LedgerResult:
    # 业务层内部统一使用的返回结构
    status: str
    intent: str
    user_message: str
    data: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        # 把 dataclass 转成普通字典，便于序列化
        return {
            "status": self.status,
            "intent": self.intent,
            "user_message": self.user_message,
            "data": self.data,
        }


class LedgerService:
    # LedgerService 是业务核心层，负责新增、查询、删除账目
    def __init__(self, repository: MySQLLedgerRepository | None = None):
        # 允许外部传入仓储对象，测试时可以替换成假仓储
        self.repository = repository or MySQLLedgerRepository()
        # 启动时自动确保数据表存在，避免首次运行报表不存在
        self.repository.ensure_schema()

    def add_transaction(
        self,
        *,
        date: Any,
        member_name: Any,
        item: Any,
        transaction_type: Any,
        amount: Any,
        currency: Any = "CNY",
        original_text: Any = "",
    ) -> LedgerResult:
        # original_text 保留原始输入，便于审计和兜底推断
        source_text = str(original_text or "").strip()
        validated = self._validate_record(
            {
                "date": date,
                "member_name": member_name,
                "item": item,
                "transaction_type": transaction_type,
                "amount": amount,
                "currency": currency,
            },
            source_text or f"{member_name} {item} {amount}",
        )
        # 插入参数顺序必须和白名单 SQL 完全一致
        params = [
            validated["date"],
            validated["member_name"],
            validated["item"],
            validated["transaction_type"],
            validated["amount"],
            validated["currency"],
            validated["original_text"],
        ]
        inserted_id = self.repository.insert_transaction(EXPECTED_INSERT_SQL, params)
        return LedgerResult(
            status="success",
            intent="create",
            user_message=format_create_message(validated),
            data={"inserted_id": inserted_id, "record": validated},
        )

    def query_transactions(
        self,
        *,
        start_date: Any = None,
        end_date: Any = None,
        member_name: Any = None,
        transaction_type: Any = None,
        keyword: Any = None,
        limit: Any = 20,
    ) -> LedgerResult:
        # 根据筛选条件生成安全 SQL 和参数
        sql, params = self._build_query_sql(
            {
                "start_date": start_date,
                "end_date": end_date,
                "member_name": member_name,
                "transaction_type": transaction_type,
                "keyword": keyword,
                "limit": limit,
            }
        )
        rows = self.repository.fetch_transactions(sql, params)
        # 把数据库里的 Decimal、日期等类型转成更易展示的格式
        normalized_rows = [self._serialize_row(row) for row in rows]
        if not normalized_rows:
            return LedgerResult(
                status="success",
                intent="query",
                user_message=format_query_message(normalized_rows),
                data={"rows": []},
            )

        return LedgerResult(
            status="success",
            intent="query",
            user_message=format_query_message(normalized_rows),
            data={"rows": normalized_rows},
        )

    def delete_transactions(
        self,
        *,
        date: Any = None,
        member_name: Any = None,
        transaction_type: Any = None,
        item: Any = None,
        amount: Any = None,
        limit: Any = 20,
    ) -> LedgerResult:
        # 先生成 count SQL 和 delete SQL，删除前先确认有多少条命中
        count_sql, count_params, delete_sql, delete_params = self._build_delete_sql(
            {
                "date": date,
                "member_name": member_name,
                "transaction_type": transaction_type,
                "item": item,
                "amount": amount,
                "limit": limit,
            }
        )
        matched_count = self.repository.count_transactions(count_sql, count_params)
        if matched_count == 0:
            return LedgerResult(
                status="success",
                intent="delete",
                user_message="没有找到需要删除的记录。",
                data={"deleted_count": 0, "matched_count": 0},
            )

        deleted_count = self.repository.delete_transactions(delete_sql, delete_params)
        return LedgerResult(
            status="success",
            intent="delete",
            user_message=format_delete_message(deleted_count),
            data={"deleted_count": deleted_count, "matched_count": matched_count},
        )

    def _handle_delete(self, plan: dict[str, Any]) -> LedgerResult:
        # 从计划字典中抽取删除过滤条件，并复用标准删除逻辑
        filters = plan.get("delete_filters") or {}
        return self.delete_transactions(
            date=filters.get("date"),
            member_name=filters.get("member_name"),
            transaction_type=filters.get("transaction_type"),
            item=filters.get("item"),
            amount=filters.get("amount"),
            limit=filters.get("limit", 20),
        )

    def _validate_record(self, record: dict[str, Any], original_text: str) -> dict[str, str]:
        # 校验并规范化一条新增记录
        return validate_record(record, original_text)

    def _resolve_transaction_type(self, raw_value: Any, original_text: str) -> str:
        # 如果用户没明确写 income / expense，就尝试根据原文推断
        return resolve_transaction_type(raw_value, original_text)

    def _infer_transaction_type(self, text: str) -> str | None:
        # 根据关键词粗略判断是收入还是支出
        return infer_transaction_type(text)

    def _display_transaction_type(self, transaction_type: str) -> str:
        # 把内部枚举值转换成用户更容易理解的中文
        return display_transaction_type(transaction_type)

    def _normalize_signed_amount(self, raw_value: Any, transaction_type: str) -> str:
        # 统一金额符号规则：收入为正，支出为负
        return normalize_signed_amount(raw_value, transaction_type)

    def _build_query_sql(self, filters: dict[str, Any]) -> tuple[str, list[Any]]:
        # 根据查询条件组装安全 SQL
        return build_query_sql(filters)

    def _build_delete_sql(
        self, filters: dict[str, Any]
    ) -> tuple[str, list[Any], str, list[Any]]:
        # 根据删除条件同时生成 count SQL 和 delete SQL
        return build_delete_sql(filters)

    def _validate_insert_sql(self, sql: Any) -> str:
        # 只允许白名单中的 INSERT 模板，防止模型生成任意写库 SQL
        return validate_insert_sql(sql)

    def _normalize_params(self, params: Any) -> list[Any]:
        # 统一规范 SQL 参数类型和字符串格式
        return normalize_params(params)

    def _normalize_insert_params(self, params: Any, transaction_type: str) -> list[Any]:
        # 针对新增场景额外处理 amount 的正负号
        return normalize_insert_params(params, transaction_type)

    def _validate_date(self, raw_value: Any) -> str:
        # 校验日期格式是否是 YYYY-MM-DD
        return validate_date(raw_value)

    def _validate_text(self, raw_value: Any, field_name: str, limit: int) -> str:
        # 校验文本字段是否非空、是否超长
        return validate_text(raw_value, field_name, limit)

    def _validate_transaction_type(self, raw_value: Any) -> str:
        # 校验 transaction_type 只能是 income 或 expense
        return validate_transaction_type(raw_value)

    def _validate_amount(self, raw_value: Any) -> str:
        # 校验金额必须是正数，并标准化成两位小数
        return validate_amount(raw_value)

    def _validate_currency(self, raw_value: Any) -> str:
        # 校验币种格式，例如 CNY、USD
        return validate_currency(raw_value)

    def _optional_date(self, raw_value: Any) -> str | None:
        # 查询/删除场景中，允许日期为空
        return optional_date(raw_value)

    def _optional_text(self, raw_value: Any) -> str | None:
        # 查询/删除场景中，允许文本条件为空
        return optional_text(raw_value)

    def _optional_transaction_type(self, raw_value: Any) -> str | None:
        # 查询/删除场景中，允许类型条件为空
        return optional_transaction_type(raw_value)

    def _optional_amount(self, raw_value: Any) -> str | None:
        # 查询/删除场景中，允许金额条件为空
        return optional_amount(raw_value)

    def _optional_limit(self, raw_value: Any, default: int, maximum: int) -> int:
        # limit 为空或非法时回退默认值，并限制最大值
        return optional_limit(raw_value, default, maximum)

    def _format_decimal(self, amount):
        # 把 Decimal 统一格式化成两位小数字符串
        return format_decimal(amount)

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        # 把数据库返回的一行记录转成可直接展示的字典
        return serialize_row(row)

    def _extract_json_object(self, raw_content: str) -> dict[str, Any]:
        # 从模型输出的文本中提取 JSON 对象
        return extract_json_object(raw_content)
