from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from gd.settings import load_project_env, read_env

# 模块导入时先加载 .env，保证数据库连接参数可用
load_project_env()


@dataclass(frozen=True)
class MySQLSettings:
    # 保存连接 MySQL 所需的配置
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "MySQLSettings":
        # 从环境变量读取数据库配置
        return cls(
            host=read_env("MYSQL_HOST"),
            port=int(read_env("MYSQL_PORT")),
            user=read_env("MYSQL_USER"),
            password=read_env("MYSQL_PASSWORD"),
            database=read_env("MYSQL_DATABASE"),
        )


class MySQLLedgerRepository:
    # 数据访问层，所有真正的写库/查库操作都在这里完成
    def __init__(self, settings: MySQLSettings | None = None):
        self.settings = settings or MySQLSettings.from_env()

    def _connect(self):
        # 建立一个 PyMySQL 连接，并使用字典游标，方便按字段名读结果
        return pymysql.connect(
            host=self.settings.host,
            port=self.settings.port,
            user=self.settings.user,
            password=self.settings.password,
            database=self.settings.database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=DictCursor,
        )

    @contextmanager
    def connection(self) -> Iterator[Any]:
        # 用上下文管理连接，统一处理提交、回滚和关闭
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        # 启动时确保 transactions 表存在
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS transactions (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            transaction_date DATE NOT NULL,
            member_name VARCHAR(64) NOT NULL,
            item VARCHAR(255) NOT NULL,
            transaction_type ENUM('income', 'expense') NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            currency VARCHAR(8) NOT NULL DEFAULT 'CNY',
            original_text TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_transaction_date (transaction_date),
            INDEX idx_member_name (member_name),
            INDEX idx_transaction_type (transaction_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_table_sql)

    def insert_transaction(self, sql: str, params: list[Any]) -> int:
        # 插入单条记录，并返回自增 ID
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return int(cursor.lastrowid)

    def insert_transactions(self, statements: list[tuple[str, list[Any]]]) -> list[int]:
        # 批量插入多条记录，并返回所有新记录 ID
        inserted_ids: list[int] = []
        with self.connection() as conn:
            with conn.cursor() as cursor:
                for sql, params in statements:
                    cursor.execute(sql, params)
                    inserted_ids.append(int(cursor.lastrowid))
        return inserted_ids

    def fetch_transactions(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        # 查询多条账目记录
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())

    def count_transactions(self, sql: str, params: list[Any]) -> int:
        # 查询命中记录数量，删除前会先走这里
        with self.connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()
                return int(row["total"]) if row else 0

    def delete_transactions(self, sql: str, params: list[Any]) -> int:
        # 执行删除，并返回受影响行数
        with self.connection() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                return int(affected)
