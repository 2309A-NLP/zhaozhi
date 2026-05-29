"""文档 API 层"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.mysql_client import get_db
from ..database.models import User
from ..dependencies.auth import get_current_user
from ..schemas.document import DocumentOut
from ..services.document_service import DocumentService


router = APIRouter()


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    knowledge_domain: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """处理upload_document相关逻辑。

    参数：
        file: 当前函数处理的上传文件对象。
        knowledge_domain: 用于存储或过滤的知识领域标签。
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    return await DocumentService(db).upload_document(
        file=file,
        knowledge_domain=knowledge_domain,
        current_user=current_user,
    )


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出documents相关逻辑。

    参数：
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    return await DocumentService(db).list_documents(current_user)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取document相关逻辑。

    参数：
        doc_id: 当前函数使用的文档 ID。
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    return await DocumentService(db).get_document(doc_id, current_user)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除document相关逻辑。

    参数：
        doc_id: 当前函数使用的文档 ID。
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    return await DocumentService(db).delete_document(doc_id, current_user)


@router.put("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: int,
    file: UploadFile = File(...),
    knowledge_domain: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新document相关逻辑。

    参数：
        doc_id: 当前函数使用的文档 ID。
        file: 当前函数处理的上传文件对象。
        knowledge_domain: 用于存储或过滤的知识领域标签。
        db: 当前函数使用的异步数据库会话。
        current_user: 当前请求对应的已认证用户。
    """
    return await DocumentService(db).update_document(
        doc_id=doc_id,
        file=file,
        knowledge_domain=knowledge_domain,
        current_user=current_user,
    )
