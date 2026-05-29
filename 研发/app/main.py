"""创建 FastAPI 应用，注册 API 路由，并托管静态前端页面"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, chat, documents, roles
from .config import config
from .database.mysql_client import mysql_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    """管理应用启动与关闭阶段的生命周期逻辑。

    参数：
        _: 框架传入但当前未使用的参数，保留是为了兼容接口定义。
    """
    await mysql_client.init_db()
    yield


app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])  # 作用是把认证模块的路由注册到主应用上
app.include_router(chat.router, prefix="/api/chat", tags=["聊天"])  # 作用是把聊天模块的路由注册到主应用上
app.include_router(documents.router, prefix="/api/documents", tags=["知识库"])  # 作用是把知识库模块的路由注册到主应用上
app.include_router(roles.router, prefix="/api/roles", tags=["角色"])  # 作用是把角色模块的路由注册到主应用上

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
async def root():
    """返回根路径响应。
    """
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": f"{config.APP_NAME} API", "version": config.APP_VERSION}


@app.get("/health")
async def health():
    """返回健康检查结果。
    """
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}
