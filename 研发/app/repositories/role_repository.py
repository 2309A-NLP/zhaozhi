"""Role repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Role


class RoleRepository:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db

    async def get_by_id(self, role_id: int) -> Optional[Role]:
        """获取byid相关逻辑。

        参数：
            role_id: 当前函数使用的角色 ID。
        """
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: int) -> int:
        """统计byuser相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
        """
        result = await self.db.execute(select(Role).where(Role.user_id == user_id))
        return len(result.scalars().all())

    async def list_for_user(self, *, user_id: int, include_public: bool) -> List[Role]:
        """列出foruser相关逻辑。

        参数：
            user_id: 当前函数使用的用户 ID。
            include_public: 是否包含公开共享数据。
        """
        stmt = select(Role)
        if include_public:
            stmt = stmt.where(or_(Role.user_id == user_id, Role.is_public.is_(True)))
        else:
            stmt = stmt.where(Role.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save(self, role: Role) -> Role:
        """处理save相关逻辑。

        参数：
            role: 当前函数处理的角色实体。
        """
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def delete(self, role: Role) -> None:
        """处理delete相关逻辑。

        参数：
            role: 当前函数处理的角色实体。
        """
        await self.db.delete(role)
        await self.db.commit()
