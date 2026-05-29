"""认证应用服务（或 身份验证应用服务）."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import User
from ..repositories.user_repository import UserRepository
from .default_role_service import ensure_user_default_roles
from ..schemas.auth import (
    UserCreate,
    build_auth_exception,
    create_access_token,
    decode_access_token,
    get_password_hash,
    normalize_username,
    verify_password,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db
        self.users = UserRepository(db)

    async def register_user(self, user_data: UserCreate) -> User:
        """处理register_user相关逻辑。

        参数：
            user_data: 调用方传入的、已校验用户数据。
        """
        existing = await self.users.get_by_username(user_data.username)
        if existing:
            raise build_auth_exception("用户名已存在")
        user = await self.users.create(
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            email=user_data.email,
        )
        await ensure_user_default_roles(self.db, user.id)
        return user

    async def authenticate(self, username: str, password: str) -> User | None:
        """认证相关逻辑。

        参数：
            username: 当前函数使用的输入参数。
            password: 当前函数处理的密码值。
        """
        user = await self.users.get_by_username(normalize_username(username))
        if user and verify_password(password, user.password_hash):
            return user
        return None

    async def login(self, username: str, password: str) -> str:
        """执行登录认证流程并返回结果。

        参数：
            username: 当前函数使用的输入参数。
            password: 当前函数处理的密码值。
        """
        user = await self.authenticate(username, password)
        if user is None:
            raise build_auth_exception("用户名或密码错误")
        return create_access_token(data={"sub": user.username, "uid": user.id})

# 负责把客户端传过来的令牌转换成具体的用户实例，实现了基于 JWT 的用户认证。
    async def get_current_user_from_token(self, token: str) -> User:
        """ 将token转化成系统中的用户对象

        参数：
            token: 调用方传入的认证令牌。
        """
        payload = decode_access_token(token) # 检查签名是否正确，过期时间，如果都通过，返回令牌里存的信息（payload）
        # 签名（Signature）：用服务端的密钥（不是用户密码）生成，用来防止令牌被篡改，这是令牌的“防伪标签”
        # 过期时间，服务端在签发 Token 时自己设置的
        #
        user = await self.users.get_by_username(payload.sub)
        if user is None:
            raise build_auth_exception()
        return user
