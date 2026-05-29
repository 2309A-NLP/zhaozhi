"""角色 API 层."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.mysql_client import get_db
from ..database.models import User
from ..dependencies.auth import get_current_user
from ..schemas.role import RoleCreate, RoleOut
from ..services.role_service import RoleService


router = APIRouter()


@router.post("/", response_model=RoleOut)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建role相关逻辑。

    参数：
        role_data: 调用方传入的、已校验角色数据。
        current_user: 当前请求对应的已认证用户。
        db: 当前函数使用的异步数据库会话。
    """
    return await RoleService(db).create_role(role_data, current_user)


@router.get("/", response_model=list[RoleOut])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_public: bool = True,
):
    """列出roles相关逻辑。

    参数：
        current_user: 当前请求对应的已认证用户。
        db: 当前函数使用的异步数据库会话。
        include_public: 是否包含公开共享数据。
    """
    return await RoleService(db).list_roles(current_user, include_public)


@router.get("/{role_id}", response_model=RoleOut)
async def get_role(role_id: int, db: AsyncSession = Depends(get_db)):
    """获取role相关逻辑。

    参数：
        role_id: 当前函数使用的角色 ID。
        db: 当前函数使用的异步数据库会话。
    """
    return await RoleService(db).get_role(role_id)


@router.put("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新role相关逻辑。

    参数：
        role_id: 当前函数使用的角色 ID。
        role_data: 调用方传入的、已校验角色数据。
        current_user: 当前请求对应的已认证用户。
        db: 当前函数使用的异步数据库会话。
    """
    return await RoleService(db).update_role(role_id, role_data, current_user)


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除role相关逻辑。

    参数：
        role_id: 当前函数使用的角色 ID。
        current_user: 当前请求对应的已认证用户。
        db: 当前函数使用的异步数据库会话。
    """
    return await RoleService(db).delete_role(role_id, current_user)
