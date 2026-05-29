"""聊天 API 层."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
# APIRouter，把路由分组管理的工具 ， Depends：依赖注入工具 ， HTTPException，抛出一个 HTTP 错误响应
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import config
from ..database.mysql_client import get_db
from ..database.models import User
from ..dependencies.auth import get_current_user
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.chat_service import ChatService
from ..services.rag_engine import RAGEngine


router = APIRouter()
_rag_engine: Optional[RAGEngine] = None

# 这是一个懒加载，整个项目，无论调用多少次这个函数，RAGEngine只会实例化一次
def get_rag_engine() -> RAGEngine:
    """获取ragengine相关逻辑。
    """
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine(config)
    return _rag_engine


# response_model=ChatResponse 表示返回结果会用 ChatResponse 这个 Pydantic 模型进行序列化和校验
@router.post("/", response_model=ChatResponse)

# 它就是“聊天接口”的逻辑实现，把请求 → 验证 → 对话 → 响应的链路串了起来。
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """处理一次聊天相关操作。

    参数：
        request: 当前操作使用的、已校验请求数据。
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    try:
        return await ChatService(db, get_rag_engine()).chat(request, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
