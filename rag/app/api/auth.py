"""认证 API 层."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.mysql_client import get_db
from ..database.models import User
from ..dependencies.auth import get_current_user
from ..schemas.auth import Token, UserCreate, UserOut
from ..services.auth_service import AuthService


router = APIRouter()


@router.post(
    "/register",
    response_model=UserOut,
    response_model_exclude_none=True,
    status_code=201,
)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """执行注册流程并创建新用户。

    参数：
        user_data: 调用方传入的、已校验用户数据。
        db: 当前函数使用的异步数据库会话。
    """
    return await AuthService(db).register_user(user_data)


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),  # 它会自动从请求的 表单数据,中提取 username 和 password
    db: AsyncSession = Depends(get_db), # 获得一个异步数据库会话，用于在数据库里查询用户、校验密码等。
):
    """ 执行登录认证流程并返回结果。

    参数：
        form_data: 当前函数处理的表单数据对象。
        db: 当前函数使用的异步数据库会话。
    """
    access_token = await AuthService(db).login(form_data.username, form_data.password)
    # 传入form_data获取的username 和 password，检验是否正确，正确就可以登录了
    return Token(access_token=access_token)
    # 生成的令牌包装成 Token 模型，Token 模型本身是一个 Python 类（Pydantic 模型），不是 JSON格式，但它最终会被 FastAPI 自动转换成 JSON 格式返回给客户端


@router.get("/me", response_model=UserOut, response_model_exclude_none=True)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """读取usersme相关逻辑。

    参数：
        current_user: 当前请求对应的已认证用户。
    """
    return current_user
