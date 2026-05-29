"""认证依赖 或 认证依赖项."""
from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import User
from ..database.mysql_client import get_db
from ..services.auth_service import AuthService

# OAuth2PasswordBearer 是 FastAPI 自带的安全工具类，专门用来处理 OAuth2 密码模式（Password Flow） 的身份认证
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")



async def get_current_user(
    token: str = Depends(oauth2_scheme),  # 从请求中提取 Token（Bearer 令牌）,
    db: AsyncSession = Depends(get_db),  # 这个db通常情况下和chat里面的作用是一样的
) -> User:
    """获取currentuser相关逻辑。

    参数：
        token: 调用方传入的认证令牌。
        db: 当前函数使用的异步数据库会话。
    """
    return await AuthService(db).get_current_user_from_token(token)
