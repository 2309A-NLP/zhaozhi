"""Persist conversation records into a dedicated Milvus collection."""
from __future__ import annotations

from typing import Optional

from ..config import config
from ..database.milvus_client import MilvusClient
from ..database.models import Conversation
from .embedding import BGEEmbeddingService


_embedding: Optional[BGEEmbeddingService] = None
_milvus: Optional[MilvusClient] = None


def get_embedding() -> BGEEmbeddingService:
    """获取embedding相关逻辑。
    """
    global _embedding
    if _embedding is None:
        _embedding = BGEEmbeddingService(config.BGE_EMBEDDING_MODEL, dim=config.EMBEDDING_DIM)
    return _embedding


def get_milvus() -> MilvusClient:
    """获取milvus相关逻辑。
    """
    global _milvus
    if _milvus is None:
        _milvus = MilvusClient(
            config.MILVUS_HOST,
            config.MILVUS_PORT,
            collection_name=config.MILVUS_CONVERSATION_COLLECTION_NAME,
        )
    return _milvus


def _build_conversation_text(conversation: Conversation) -> str:
    """处理_build_conversation_text相关逻辑。

    参数：
        conversation: 当前函数处理的会话实体。
    """
    timestamp = conversation.timestamp.isoformat() if conversation.timestamp else ""
    role_id = conversation.role_id if conversation.role_id is not None else 0
    return (
        f"conversation_id: {conversation.id}\n"
        f"user_id: {conversation.user_id}\n"
        f"role_id: {role_id}\n"
        f"session_id: {conversation.session_id}\n"
        f"timestamp: {timestamp}\n"
        f"user: {conversation.message}\n"
        f"assistant: {conversation.response or ''}"
    )


async def save_conversation(conversation: Conversation) -> list[int]:
    """保存conversation相关逻辑。

    参数：
        conversation: 当前函数处理的会话实体。
    """
    text = _build_conversation_text(conversation)
    embedding = get_embedding()
    milvus = get_milvus()
    chunks = embedding.chunk_text(
        text,
        chunk_size=config.CHUNK_SIZE,
        overlap=config.CHUNK_OVERLAP,
    )
    if not chunks:
        return []

    dense_vecs, sparse_vecs = embedding.encode_full(chunks)
    payload = [
        {
            "doc_id": conversation.id,
            "chunk_text": chunk,
            "knowledge_domain": "chat_history",
            "dense_vector": dense_vecs[index].tolist(),
            "sparse_vector": sparse_vecs[index],
        }
        for index, chunk in enumerate(chunks)
    ]
    milvus.delete_by_doc_id(conversation.id)
    return milvus.upsert(payload)
