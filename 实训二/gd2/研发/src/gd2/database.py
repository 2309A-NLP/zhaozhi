from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from gd2.schemas import ScheduleSqlPlan
from gd2.settings import AppSettings
from gd2.time_utils import BEIJING_TIMEZONE


INSERT_SQL = (
    "INSERT INTO gd2 "
    "(title, schedule_time, raw_request, normalized_request, timezone) "
    "VALUES (%s, %s, %s, %s, %s) "
    "ON DUPLICATE KEY UPDATE "
    "raw_request = VALUES(raw_request), "
    "normalized_request = VALUES(normalized_request), "
    "timezone = VALUES(timezone), "
    "updated_at = CURRENT_TIMESTAMP"
)

DELETE_SQL = "DELETE FROM gd2 WHERE title = %s AND schedule_time = %s"
DELETE_BY_ID_SQL = "DELETE FROM gd2 WHERE id = %s"
QUERY_DAY_SQL = (
    "SELECT id, title, schedule_time, normalized_request, timezone, created_at, updated_at "
    "FROM gd2 WHERE DATE(schedule_time) = %s ORDER BY schedule_time ASC"
)
QUERY_ALL_SQL = (
    "SELECT id, title, schedule_time, normalized_request, timezone, created_at, updated_at "
    "FROM gd2 ORDER BY schedule_time ASC"
)


@dataclass(frozen=True)
class ExecutionResult:
    action: str
    title: str
    schedule_time: str
    affected_rows: int
    database: str
    table: str
    sql: str
    rows: list[dict[str, Any]]


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.replace("\n", " ").replace("\t", " ").strip().rstrip(";").split())


def _ensure_valid_schedule_time(schedule_time: str) -> str:
    datetime.strptime(schedule_time, "%Y-%m-%d %H:%M:%S")
    return schedule_time


def _derive_query_day(schedule_time: str) -> str:
    validated = _ensure_valid_schedule_time(schedule_time)
    return validated.split(" ")[0]


def validate_sql_plan(plan: ScheduleSqlPlan, raw_request: str) -> tuple[str, list[str]]:
    """Validate the LLM SQL plan and return the canonical SQL plus params."""

    title = plan.title.strip()
    normalized_request = plan.normalized_request.strip()
    raw_request = raw_request.strip()

    if not normalized_request:
        raise ValueError("解析出的规范化请求为空，无法执行。")
    if not raw_request:
        raise ValueError("原始请求为空，无法执行。")

    if plan.action == "add":
        schedule_time = _ensure_valid_schedule_time(plan.schedule_time)
        if not title:
            raise ValueError("解析出的日程标题为空，无法入库。")
        expected_sql = INSERT_SQL
        expected_params = [
            title,
            schedule_time,
            raw_request,
            normalized_request,
            BEIJING_TIMEZONE,
        ]
    elif plan.action == "delete":
        schedule_time = _ensure_valid_schedule_time(plan.schedule_time)
        if not title:
            raise ValueError("解析出的日程标题为空，无法删除。")
        expected_sql = DELETE_SQL
        expected_params = [title, schedule_time]
    elif plan.action == "delete_by_id":
        if not plan.params:
            raise ValueError("缺少要取消的日程编号。")
        expected_sql = DELETE_BY_ID_SQL
        expected_params = [str(int(plan.params[0]))]
    else:
        if plan.schedule_time.strip():
            expected_sql = QUERY_DAY_SQL
            expected_params = [_derive_query_day(plan.schedule_time)]
        else:
            expected_sql = QUERY_ALL_SQL
            expected_params = []

    if _normalize_sql(plan.sql) != _normalize_sql(expected_sql):
        raise ValueError("大模型生成的 SQL 不符合允许的模板，已拒绝执行。")

    if plan.params != expected_params:
        raise ValueError("大模型生成的 SQL 参数与程序校验结果不一致，已拒绝执行。")

    return expected_sql, expected_params


class MySQLScheduleRepository:
    """Persist schedules into the MySQL database declared in .env."""

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def _connect_server(self):
        import pymysql

        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            charset="utf8mb4",
            autocommit=False,
        )

    def _connect_database(self):
        import pymysql

        return pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def ensure_schema(self) -> None:
        server_connection = self._connect_server()
        try:
            cursor = server_connection.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.settings.mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
            )
            server_connection.commit()
        finally:
            server_connection.close()

        database_connection = self._connect_database()
        try:
            cursor = database_connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gd2 (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    title VARCHAR(255) NOT NULL,
                    schedule_time DATETIME NOT NULL,
                    raw_request TEXT NOT NULL,
                    normalized_request TEXT NOT NULL,
                    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_schedule (title, schedule_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            database_connection.commit()
        finally:
            database_connection.close()

    def execute_plan(self, plan: ScheduleSqlPlan, raw_request: str) -> ExecutionResult:
        self.ensure_schema()
        sql, params = validate_sql_plan(plan, raw_request)

        connection = self._connect_database()
        try:
            cursor = connection.cursor()
            cursor.execute(sql, params)
            rows: list[dict[str, Any]] = []
            if plan.action == "query":
                rows = list(cursor.fetchall())
                connection.commit()
                return ExecutionResult(
                    action=plan.action,
                    title=plan.title.strip(),
                    schedule_time=plan.schedule_time.strip(),
                    affected_rows=len(rows),
                    database=self.settings.mysql_database,
                    table="gd2",
                    sql=sql,
                    rows=rows,
                )

            connection.commit()
            return ExecutionResult(
                action=plan.action,
                title=plan.title.strip(),
                schedule_time=plan.schedule_time.strip(),
                affected_rows=cursor.rowcount,
                database=self.settings.mysql_database,
                table="gd2",
                sql=sql,
                rows=rows,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
