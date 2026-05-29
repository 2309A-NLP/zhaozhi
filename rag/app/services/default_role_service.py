"""Ensure built-in roles exist for each user."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.role_defaults import ROLE_DEFAULT_PROFILES
from ..database.models import Role
from ..repositories.role_repository import RoleRepository


async def ensure_user_default_roles(db: AsyncSession, user_id: int) -> None:
    """确保userdefaultroles相关逻辑。

    参数：
        db: 当前函数使用的异步数据库会话。
        user_id: 当前函数使用的用户 ID。
    """
    roles = RoleRepository(db)
    existing_roles = await roles.list_for_user(user_id=user_id, include_public=False)
    existing_types = {str(role.role_type).strip() for role in existing_roles if role.role_type}

    missing_roles = []
    for role_type, profile in ROLE_DEFAULT_PROFILES.items():
        if role_type in existing_types:
            continue
        missing_roles.append(
            Role(
                user_id=user_id,
                role_name=profile["role_name"],
                role_type=role_type,
                personality=profile["personality"],
                language_style=profile["language_style"],
                constraints=profile["constraints"],
                system_prompt=None,
                knowledge_domains=profile["knowledge_domains"][:],
                is_public=False,
            )
        )

    if not missing_roles:
        return

    db.add_all(missing_roles)
    await db.commit()
