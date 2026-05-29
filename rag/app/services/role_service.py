"""Role application service."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Role, User
from ..repositories.role_repository import RoleRepository
from ..schemas.role import RoleCreate, RoleOut
from .default_role_service import ensure_user_default_roles


def normalize_role_type(role_type: str) -> str:
    """规范化roletype相关逻辑。

    参数：
        role_type: 当前函数处理的角色类型。
    """
    normalized = (role_type or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="角色类型不能为空")
    return normalized


def serialize_role(role: Role) -> RoleOut:
    """序列化role相关逻辑。

    参数：
        role: 当前函数处理的角色实体。
    """
    return RoleOut(
        id=role.id,
        user_id=role.user_id,
        role_name=role.role_name,
        role_type=role.role_type,
        personality=role.personality,
        language_style=role.language_style,
        constraints=role.constraints,
        knowledge_domains=role.knowledge_domains,
        is_public=role.is_public,
    )


def ensure_role_owner(role: Optional[Role], current_user: User, detail: str) -> Role:
    """确保roleowner相关逻辑。

    参数：
        role: 当前函数处理的角色实体。
        current_user: 当前请求对应的已认证用户。
        detail: 当前函数使用的错误详情或消息文本。
    """
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=detail)
    return role


def apply_role_data(role: Role, role_data: RoleCreate, role_type: str) -> Role:
    """应用roledata相关逻辑。

    参数：
        role: 当前函数处理的角色实体。
        role_data: 调用方传入的、已校验角色数据。
        role_type: 当前函数处理的角色类型。
    """
    role.role_name = role_data.role_name.strip()
    role.role_type = role_type
    role.personality = role_data.personality
    role.language_style = role_data.language_style
    role.constraints = role_data.constraints
    role.system_prompt = role_data.system_prompt
    role.knowledge_domains = role_data.knowledge_domains or []
    role.is_public = role_data.is_public
    return role


class RoleService:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db
        self.roles = RoleRepository(db)

    async def create_role(self, role_data: RoleCreate, current_user: User) -> RoleOut:
        """创建role相关逻辑。

        参数：
            role_data: 调用方传入的、已校验角色数据。
            current_user: 当前请求对应的已认证用户。
        """
        if await self.roles.count_by_user(current_user.id) >= 10:
            raise HTTPException(status_code=400, detail="每个用户最多创建 10 个角色")
        role = apply_role_data(Role(user_id=current_user.id), role_data, normalize_role_type(role_data.role_type))
        return serialize_role(await self.roles.save(role))

    async def list_roles(self, current_user: User, include_public: bool) -> list[RoleOut]:
        """列出roles相关逻辑。

        参数：
            current_user: 当前请求对应的已认证用户。
            include_public: 是否包含公开共享数据。
        """
        await ensure_user_default_roles(self.db, current_user.id)
        items = await self.roles.list_for_user(user_id=current_user.id, include_public=include_public)
        return [serialize_role(item) for item in items]

    async def get_role(self, role_id: int) -> RoleOut:
        """获取role相关逻辑。

        参数：
            role_id: 当前函数使用的角色 ID。
        """
        role = await self.roles.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")
        return serialize_role(role)

    async def update_role(self, role_id: int, role_data: RoleCreate, current_user: User) -> RoleOut:
        """更新role相关逻辑。

        参数：
            role_id: 当前函数使用的角色 ID。
            role_data: 调用方传入的、已校验角色数据。
            current_user: 当前请求对应的已认证用户。
        """
        role = ensure_role_owner(await self.roles.get_by_id(role_id), current_user, "无权修改该角色")
        apply_role_data(role, role_data, normalize_role_type(role_data.role_type))
        return serialize_role(await self.roles.save(role))

    async def delete_role(self, role_id: int, current_user: User) -> dict:
        """删除role相关逻辑。

        参数：
            role_id: 当前函数使用的角色 ID。
            current_user: 当前请求对应的已认证用户。
        """
        role = ensure_role_owner(await self.roles.get_by_id(role_id), current_user, "无权删除该角色")
        await self.roles.delete(role)
        return {"detail": "角色已删除"}
