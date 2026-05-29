"""文档应用服务."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.models import Document, MilvusIndex, User
from ..repositories.document_repository import DocumentRepository
from ..schemas.document import DocumentOut
from .document_ingestion import get_milvus, save_document


def serialize_document(document: Document) -> DocumentOut:
    """序列化document相关逻辑。

    参数：
        document: 当前函数处理的文档实体。
    """
    return DocumentOut(
        id=document.id,
        title=document.title,
        knowledge_domain=document.knowledge_domain,
        user_id=document.user_id,
        chunk_count=document.chunk_count or 0,
        source=document.source,
        created_at=document.created_at.isoformat() if document.created_at else None,
    )


def ensure_document_access(document: Optional[Document], current_user: User) -> Document:
    """确保documentaccess相关逻辑。

    参数：
        document: 当前函数处理的文档实体。
        current_user: 当前请求对应的已认证用户。
    """
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该文档")
    return document


async def read_uploaded_content(file: UploadFile) -> bytes:
    """读取uploadedcontent相关逻辑。

    参数：
        file: 当前函数处理的上传文件对象。
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")
    return content


def remove_file_if_exists(file_path: Optional[str]) -> None:
    """移除fileifexists相关逻辑。

    参数：
        file_path: 当前函数处理的本地文件路径。
    """
    if not file_path:
        return
    path = Path(file_path)
    if path.exists():
        path.unlink()


class DocumentService:
    def __init__(self, db: AsyncSession):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
        """
        self.db = db
        self.documents = DocumentRepository(db)

    async def list_documents(self, current_user: User) -> list[DocumentOut]:
        """列出documents相关逻辑。

        参数：
            current_user: 当前请求对应的已认证用户。
        """
        items = await self.documents.list_by_user(current_user.id)
        return [serialize_document(item) for item in items]

    async def get_document(self, doc_id: int, current_user: User) -> DocumentOut:
        """获取document相关逻辑。

        参数：
            doc_id: 当前函数使用的文档 ID。
            current_user: 当前请求对应的已认证用户。
        """
        document = ensure_document_access(await self.documents.get_by_id(doc_id), current_user)
        return serialize_document(document)

    async def upload_document(
        self,
        *,
        file: UploadFile,
        knowledge_domain: str,
        current_user: User,
    ) -> DocumentOut:
        """处理upload_document相关逻辑。

        参数：
            file: 当前函数处理的上传文件对象。
            knowledge_domain: 用于存储或过滤的知识领域标签。
            current_user: 当前请求对应的已认证用户。
        """
        try:
            document = await save_document(
                db=self.db,
                user_id=current_user.id,
                filename=file.filename or "document.txt",
                content=await read_uploaded_content(file),
                knowledge_domain=knowledge_domain,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return serialize_document(document)

    async def update_document(
        self,
        *,
        doc_id: int,
        file: UploadFile,
        knowledge_domain: str,
        current_user: User,
    ) -> DocumentOut:
        """更新document相关逻辑。

        参数：
            doc_id: 当前函数使用的文档 ID。
            file: 当前函数处理的上传文件对象。
            knowledge_domain: 用于存储或过滤的知识领域标签。
            current_user: 当前请求对应的已认证用户。
        """
        existing = ensure_document_access(await self.documents.get_by_id(doc_id), current_user)
        try:
            document = await save_document(
                db=self.db,
                user_id=current_user.id,
                filename=file.filename or existing.title,
                content=await read_uploaded_content(file),
                knowledge_domain=knowledge_domain,
                existing_document=existing,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return serialize_document(document)

    async def delete_document(self, doc_id: int, current_user: User) -> dict:
        """删除document相关逻辑。

        参数：
            doc_id: 当前函数使用的文档 ID。
            current_user: 当前请求对应的已认证用户。
        """
        document = ensure_document_access(await self.documents.get_by_id(doc_id), current_user)
        get_milvus().delete_by_doc_id(doc_id)
        await self.db.execute(delete(MilvusIndex).where(MilvusIndex.doc_id == doc_id))
        remove_file_if_exists(document.file_path)
        await self.db.delete(document)
        await self.db.commit()
        return {"status": "deleted", "doc_id": doc_id}
