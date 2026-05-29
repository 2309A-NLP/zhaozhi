"""User repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db

    async def get_by_username(self, username: str) -> Optional[User]:
        """获取byusername相关逻辑。

        参数：
            username: 当前函数使用的输入参数。
        """
        stmt = select(User).where(func.lower(User.username) == username.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, *, username: str, password_hash: str, email: Optional[str]) -> User:
        """处理create相关逻辑。

        参数：
            username: 当前函数使用的输入参数。
            password_hash: 当前函数处理的密码哈希值。
            email: 当前函数使用的输入参数。
        """
        user = User(username=username, password_hash=password_hash, email=email)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
