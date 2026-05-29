"""Conversation repository."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db

    async def create(
        self,
        *,
        user_id: int,
        role_id: int | None,
        session_id: str,
        message: str,
        response: str,
        retrieved_docs,
    ) -> Conversation:
        """处理create相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
            role_id: 当前函数使用的角色 ID。
            session_id: 当前函数使用的会话 ID。
            message: 当前函数使用的输入参数。
            response: 当前函数处理的响应内容。
            retrieved_docs: 当前函数处理的已检索文档元数据。
        """
        item = Conversation(
            user_id=user_id,
            role_id=role_id,
            session_id=session_id,
            message=message,
            response=response,
            retrieved_docs=retrieved_docs,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item
