from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from gd.ledger_service import LedgerService


class AddTransactionInput(BaseModel):
    # 新增账目时，agent 必须填完整这些字段
    date: str = Field(..., description="交易日期，格式必须为 YYYY-MM-DD。")
    member_name: str = Field(..., description="家庭成员名称。")
    item: str = Field(..., description="事项名称，例如买菜、工资。")
    transaction_type: str = Field(..., description="只能是 income 或 expense。")
    amount: str = Field(..., description="正数金额，不带负号。")
    currency: str = Field(default="CNY", description="币种，默认 CNY。")
    original_text: str = Field(default="", description="用户原始描述，用于审计和推断。")


class QueryTransactionsInput(BaseModel):
    # 查询账目时的筛选条件
    start_date: str | None = Field(default=None, description="开始日期，格式 YYYY-MM-DD。")
    end_date: str | None = Field(default=None, description="结束日期，格式 YYYY-MM-DD。")
    member_name: str | None = Field(default=None, description="家庭成员名称。")
    transaction_type: str | None = Field(default=None, description="income 或 expense。")
    keyword: str | None = Field(default=None, description="事项关键词，例如 买菜。")
    limit: int = Field(default=20, description="最多返回多少条记录，建议不超过 100。")


class DeleteTransactionInput(BaseModel):
    # 删除账目时的筛选条件
    date: str | None = Field(default=None, description="日期，格式 YYYY-MM-DD。")
    member_name: str | None = Field(default=None, description="家庭成员名称。")
    transaction_type: str | None = Field(default=None, description="income 或 expense。")
    item: str | None = Field(default=None, description="要删除的事项名称。")
    amount: str | None = Field(default=None, description="正数金额，不带负号。")
    limit: int = Field(default=20, description="本次最多删除多少条记录。")


class AddTransactionTool(BaseTool):
    # 新增账目工具，agent 在确认字段齐全后调用
    name: str = "add_transaction"
    description: str = (
        "当用户明确要新增一笔或多笔账目时使用。"
        "必须先从用户输入中提取完整字段：date、member_name、item、transaction_type、amount。"
        "如果任何关键字段不明确，不要调用这个工具，而是先追问。"
    )
    args_schema: Type[BaseModel] = AddTransactionInput

    def _run(
        self,
        date: str,
        member_name: str,
        item: str,
        transaction_type: str,
        amount: str,
        currency: str = "CNY",
        original_text: str = "",
    ) -> str:
        # 调用业务层新增记录，并返回给用户看的中文消息
        return LedgerService().add_transaction(
            date=date,
            member_name=member_name,
            item=item,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            original_text=original_text,
        ).user_message


class QueryTransactionsTool(BaseTool):
    # 查询账目工具
    name: str = "query_transactions"
    description: str = (
        "当用户要查询账目、查看最近记录、按日期或成员筛选时使用。"
        "如果没有给筛选条件，也可以用来查看最近记录。"
    )
    args_schema: Type[BaseModel] = QueryTransactionsInput

    def _run(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        member_name: str | None = None,
        transaction_type: str | None = None,
        keyword: str | None = None,
        limit: int = 20,
    ) -> str:
        # 调用业务层查询记录，并返回中文列表
        return LedgerService().query_transactions(
            start_date=start_date,
            end_date=end_date,
            member_name=member_name,
            transaction_type=transaction_type,
            keyword=keyword,
            limit=limit,
        ).user_message


class DeleteTransactionTool(BaseTool):
    # 删除账目工具
    name: str = "delete_transaction"
    description: str = (
        "当用户明确要求删除账目时使用。"
        "删除前至少要有一个明确筛选条件，例如日期、成员、事项或金额。"
        "如果条件模糊，不要调用这个工具，而是先追问。"
    )
    args_schema: Type[BaseModel] = DeleteTransactionInput

    def _run(
        self,
        date: str | None = None,
        member_name: str | None = None,
        transaction_type: str | None = None,
        item: str | None = None,
        amount: str | None = None,
        limit: int = 20,
    ) -> str:
        # 调用业务层删除记录，并返回删除结果说明
        return LedgerService().delete_transactions(
            date=date,
            member_name=member_name,
            transaction_type=transaction_type,
            item=item,
            amount=amount,
            limit=limit,
        ).user_message
