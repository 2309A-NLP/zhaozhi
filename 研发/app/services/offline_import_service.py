"""Offline import application service."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from .document_ingestion import upsert_local_file


class OfflineImportService:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db

    async def import_file(self, *, file_path: Path, user_id: int, knowledge_domain: str):
        """导入file相关逻辑。

        参数：
            file_path: 当前函数处理的本地文件路径。
            user_id: 当前函数使用的用户 ID。
            knowledge_domain: 用于存储或过滤的知识领域标签。
        """
        return await upsert_local_file(
            db=self.db,
            file_path=file_path,
            user_id=user_id,
            knowledge_domain=knowledge_domain,
        )
