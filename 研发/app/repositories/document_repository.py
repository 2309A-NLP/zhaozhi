"""Document repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db

    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        """获取byid相关逻辑。

        参数：
            doc_id: 当前函数使用的文档 ID。
        """
        result = await self.db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> List[Document]:
        """列出byuser相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
        """
        stmt = select(Document).where(Document.user_id == user_id).order_by(desc(Document.created_at))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_doc_ids_by_user_and_domains(
        self,
        *,
        user_id: int,
        knowledge_domains: List[str],
    ) -> List[int]:
        """列出docidsbyuseranddomains相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
            knowledge_domains: 用于存储或过滤的知识领域标签列表。
        """
        stmt = select(Document.id).where(Document.user_id == user_id)
        if knowledge_domains:
            stmt = stmt.where(Document.knowledge_domain.in_(knowledge_domains))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
