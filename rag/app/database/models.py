"""应用程序的 SQLAlchemy 模型."""

from __future__ import annotations
"""
SQLAlchemy 模型是帮你用面向对象的方式操作数据库结构（建表、查询、插入、更新、删除）的工具，可以连接多种数据库，
但数据库的高级管理（权限、备份等）不是它的职责。如果你需要管理多个数据库的表结构变化，建议配合 Alembic
"""
from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func


Base = declarative_base()


def _timestamp_column(**kwargs):
    """处理_timestamp_column相关逻辑。

    参数：
        kwargs: 当前函数透传的额外关键字参数。
    """
    return Column(TIMESTAMP, **kwargs)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100))
    avatar = Column(String(255))
    created_at = _timestamp_column(server_default=func.current_timestamp())
    updated_at = _timestamp_column(
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (Index("idx_username", "username"),)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_name = Column(String(100), nullable=False)
    role_type = Column(String(100), default="friend")
    personality = Column(Text)
    language_style = Column(Text)
    constraints = Column(Text)
    system_prompt = Column(Text)
    knowledge_domains = Column(JSON)
    is_public = Column(Boolean, default=False)
    created_at = _timestamp_column(server_default=func.current_timestamp())
    updated_at = _timestamp_column(
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index("idx_role_user_id", "user_id"),
        Index("idx_role_type", "role_type"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text)
    retrieved_docs = Column(JSON)
    timestamp = _timestamp_column(server_default=func.current_timestamp())

    __table_args__ = (
        Index("idx_conversation_session", "session_id"),
        Index("idx_conversation_timestamp", "timestamp"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    file_path = Column(String(500))
    source = Column(String(100))
    knowledge_domain = Column(String(50))
    user_id = Column(Integer, nullable=False)
    milvus_ids = Column(JSON)
    chunk_count = Column(Integer, default=0)
    created_at = _timestamp_column(server_default=func.current_timestamp())
    updated_at = _timestamp_column(
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index("idx_document_domain", "knowledge_domain"),
        Index("idx_document_user", "user_id"),
    )


class MilvusIndex(Base):
    __tablename__ = "milvus_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    milvus_id = Column(String(255), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text)

    __table_args__ = (Index("idx_milvus_id", "milvus_id"),)
