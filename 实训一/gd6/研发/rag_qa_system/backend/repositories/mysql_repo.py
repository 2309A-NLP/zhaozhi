"""MySQL-backed metadata repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.mysql")


@dataclass
class MysqlRepository:
    host: str
    port: int
    user: str
    password: str
    database: str

    def __post_init__(self) -> None:
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("pymysql is required for MySQL access") from exc

        self._pymysql = pymysql
        self._ensure_database()
        self._ensure_tables()

    def save_document_chunk(self, chunk: Dict[str, Any]) -> None:
        sql = """
        INSERT INTO document_chunks (chunk_id, document_id, document_name, source_path, chunk_text)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            document_name = VALUES(document_name),
            source_path = VALUES(source_path),
            chunk_text = VALUES(chunk_text)
        """
        self._execute(
            sql,
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["document_name"],
                chunk["source_path"],
                chunk["text"],
            ),
        )

    def save_document(self, document: Dict[str, Any]) -> None:
        sql = """
        INSERT INTO documents (document_id, document_name, source_path, chunk_count, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            document_name = VALUES(document_name),
            source_path = VALUES(source_path),
            chunk_count = VALUES(chunk_count),
            updated_at = NOW()
        """
        self._execute(
            sql,
            (
                document["document_id"],
                document["document_name"],
                document["source_path"],
                document["chunk_count"],
            ),
        )

    def replace_document_chunks(self, document_id: str, chunks: List[Dict[str, Any]]) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
                if chunks:
                    cursor.executemany(
                        """
                        INSERT INTO document_chunks (chunk_id, document_id, document_name, source_path, chunk_text)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            (
                                chunk["chunk_id"],
                                chunk["document_id"],
                                chunk["document_name"],
                                chunk["source_path"],
                                chunk["text"],
                            )
                            for chunk in chunks
                        ],
                    )
            conn.commit()

    def list_documents(self) -> List[Dict[str, Any]]:
        rows = self._query_all(
            """
            SELECT document_id, document_name, source_path, chunk_count, updated_at
            FROM documents
            ORDER BY updated_at DESC, document_name ASC
            """
        )
        return [
            {
                "document_id": row["document_id"],
                "document_name": row["document_name"],
                "source_path": row["source_path"],
                "chunk_count": row["chunk_count"],
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]

    def count_chunks(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS count FROM document_chunks")
        return int(row["count"]) if row else 0

    def list_document_chunks(self, document_id: str = "") -> List[Dict[str, Any]]:
        scoped_document_id = document_id.strip()
        if scoped_document_id:
            rows = self._query_all(
                """
                SELECT chunk_id, document_id, document_name, source_path, chunk_text
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY document_id ASC, chunk_id ASC
                """,
                (scoped_document_id,),
            )
        else:
            rows = self._query_all(
                """
                SELECT chunk_id, document_id, document_name, source_path, chunk_text
                FROM document_chunks
                ORDER BY document_id ASC, chunk_id ASC
                """
            )
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "document_name": row["document_name"],
                "source_path": row["source_path"],
                "text": row["chunk_text"],
            }
            for row in rows
        ]

    def save_qa_log(self, record: Dict[str, Any]) -> None:
        payload = dict(record)
        sql = """
        INSERT INTO qa_logs (question, answer, sources_json, source_count, duration_ms, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        self._execute(
            sql,
            (
                payload.get("question", ""),
                payload.get("answer", ""),
                json.dumps(payload.get("sources", []), ensure_ascii=False),
                payload.get("source_count", 0),
                payload.get("duration_ms", 0.0),
                datetime.utcnow(),
            ),
        )

    def _ensure_database(self) -> None:
        connection = self._pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset="utf8mb4",
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        finally:
            connection.close()

    def _ensure_tables(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id VARCHAR(64) PRIMARY KEY,
                document_name VARCHAR(255) NOT NULL,
                source_path TEXT NOT NULL,
                chunk_count INT NOT NULL DEFAULT 0,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id VARCHAR(80) PRIMARY KEY,
                document_id VARCHAR(64) NOT NULL,
                document_name VARCHAR(255) NOT NULL,
                source_path TEXT NOT NULL,
                chunk_text MEDIUMTEXT NOT NULL,
                KEY idx_document_chunks_document_id (document_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS qa_logs (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                question TEXT NOT NULL,
                answer MEDIUMTEXT NOT NULL,
                sources_json JSON NOT NULL,
                source_count INT NOT NULL DEFAULT 0,
                duration_ms DOUBLE NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            conn.commit()

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
            conn.commit()

    def _query_all(self, sql: str, params: tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())

    def _query_one(self, sql: str, params: tuple[Any, ...] = ()) -> Dict[str, Any] | None:
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()

    def _connection(self):
        return self._pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            autocommit=False,
            cursorclass=self._pymysql.cursors.DictCursor,
        )
