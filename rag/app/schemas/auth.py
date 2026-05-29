"""Auth request and response schemas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import config


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERNAME_MIN_LENGTH = 3
PASSWORD_MIN_LENGTH = 6


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    uid: Optional[int] = None
    typ: str = "access"
    exp: Optional[int] = None


def normalize_username(username: str) -> str:
    """规范化username相关逻辑。

    参数：
        username: 当前函数使用的输入参数。
    """
    return username.strip()


def normalize_optional_text(value: Optional[str]) -> Optional[str]:
    """规范化optionaltext相关逻辑。

    参数：
        value: 当前函数要规范化或校验的输入值。
    """
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=USERNAME_MIN_LENGTH, max_length=50)
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)
    email: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """处理validate_username相关逻辑。

        参数：
            value: 当前函数要规范化或校验的输入值。
        """
        normalized = normalize_username(value)
        if len(normalized) < USERNAME_MIN_LENGTH:
            raise ValueError("用户名长度不能少于 3 个字符")
        if " " in normalized:
            raise ValueError("用户名不能包含空格")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """处理validate_password相关逻辑。

        参数：
            value: 当前函数要规范化或校验的输入值。
        """
        normalized = value.strip()
        if len(normalized) < PASSWORD_MIN_LENGTH:
            raise ValueError("密码长度不能少于 6 个字符")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        """处理validate_email相关逻辑。

        参数：
            value: 当前函数要规范化或校验的输入值。
        """
        normalized = normalize_optional_text(value)
        if normalized is None:
            return None
        if "@" not in normalized:
            raise ValueError("邮箱格式不正确")
        return normalized


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None


def build_auth_exception(detail: str = "无效的认证凭证") -> HTTPException:
    """构建authexception相关逻辑。

    参数：
        detail: 当前函数使用的错误详情或消息文本。
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验password相关逻辑。

    参数：
        plain_password: 当前函数处理的明文密码。
        hashed_password: 当前函数处理的已存储密码哈希。
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取passwordhash相关逻辑。

    参数：
        password: 当前函数处理的密码值。
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建accesstoken相关逻辑。

    参数：
        data: 当前函数使用的输入参数。
        expires_delta: 创建令牌时使用的可选过期时长。
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = data.copy()
    payload.update({"typ": "access", "exp": expire})
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """解码accesstoken相关逻辑。

    参数：
        token: 调用方传入的认证令牌。
    """
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        token_payload = TokenPayload(**payload)
        if token_payload.typ != "access":
            raise build_auth_exception()
        return token_payload
    except (JWTError, ValueError) as exc:
        raise build_auth_exception() from exc
