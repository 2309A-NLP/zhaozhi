"""处理文档入库、切块与索引写入流程。"""  # 说明当前模块或代码块的用途。
from __future__ import annotations  # 从 __future__ 中导入所需对象。

import time  # 导入所需的模块或对象：time。
from pathlib import Path  # 从 pathlib 中导入所需对象。
from typing import Optional  # 从 typing 中导入所需对象。

from sqlalchemy import delete, select  # 从 sqlalchemy 中导入所需对象。
from sqlalchemy.ext.asyncio import AsyncSession  # 从 sqlalchemy.ext.asyncio 中导入所需对象。

from ..config import config  # 从 ..config 中导入所需对象。
from ..database.milvus_client import MilvusClient  # 从 ..database.milvus_client 中导入所需对象。
from ..database.models import Document, MilvusIndex  # 从 ..database.models 中导入所需对象。
from .document_parser import extract_text  # 从 .document_parser 中导入所需对象。
from .embedding import BGEEmbeddingService  # 从 .embedding 中导入所需对象。


_embedding: Optional[BGEEmbeddingService] = None  # 执行这一行代码，完成当前逻辑。
_milvus: Optional[MilvusClient] = None  # 执行这一行代码，完成当前逻辑。


def get_embedding() -> BGEEmbeddingService:  # 定义函数 get_embedding，用于封装可复用的逻辑。
    """获取embedding相关逻辑。
    """
    global _embedding  # 执行这一行代码，完成当前逻辑。
    if _embedding is None:  # 根据条件决定是否执行下面的代码块。
        _embedding = BGEEmbeddingService(config.BGE_EMBEDDING_MODEL, dim=config.EMBEDDING_DIM)  # 调用 BGEEmbeddingService 并把结果保存到 _embedding 中。
    return _embedding  # 返回当前函数计算出的结果。


def get_milvus() -> MilvusClient:  # 定义函数 get_milvus，用于封装可复用的逻辑。
    """获取milvus相关逻辑。
    """
    global _milvus  # 执行这一行代码，完成当前逻辑。
    if _milvus is None:  # 根据条件决定是否执行下面的代码块。
        _milvus = MilvusClient(config.MILVUS_HOST, config.MILVUS_PORT)  # 调用 MilvusClient 并把结果保存到 _milvus 中。
    return _milvus  # 返回当前函数计算出的结果。


def build_saved_path(user_id: int, filename: str) -> Path:  # 定义函数 build_saved_path，用于封装可复用的逻辑。
    """构建savedpath相关逻辑。

    参数：
        user_id: 当前函数使用的用户 ID。
        filename: 当前函数处理的文件名。
    """
    safe_name = Path(filename).name or "document.txt"  # 调用 Path 并把结果保存到 safe_name 中。
    return config.DOCUMENTS_DIR / f"{user_id}_{time.time_ns()}_{safe_name}"  # 返回当前函数计算出的结果。


def _get_document_source(filename: str) -> str:  # 定义函数 _get_document_source，用于封装可复用的逻辑。
    """处理_get_document_source相关逻辑。

    参数：
        filename: 当前函数处理的文件名。
    """
    return Path(filename).suffix.lower().lstrip(".") or "text"  # 返回当前函数计算出的结果。


def _build_milvus_payload(  # 定义函数 _build_milvus_payload，用于封装可复用的逻辑。
    document: Document,  # 执行这一行代码，完成当前逻辑。
    chunks: list[str],  # 执行这一行代码，完成当前逻辑。
    dense_vecs,  # 把这一项加入当前的导入、参数或数据列表中。
    sparse_vecs,  # 把这一项加入当前的导入、参数或数据列表中。
) -> list[dict]:  # 开始一个新的代码块。
    """处理_build_milvus_payload相关逻辑。

    参数：
        # 定义函数 _build_milvus_payload，用于封装可复用的逻辑。     document: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     chunks: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     dense_vecs: 当前函数使用的输入参数。
        # 把这一项加入当前的导入、参数或数据列表中。     sparse_vecs: 当前函数使用的输入参数。
        # 把这一项加入当前的导入、参数或数据列表中。: 当前函数使用的输入参数。
    """
    return [  # 返回当前函数计算出的结果。
        {  # 执行这一行代码，完成当前逻辑。
            "doc_id": document.id,  # 设置键 doc_id 对应的值。
            "chunk_text": chunk,  # 设置键 chunk_text 对应的值。
            "knowledge_domain": document.knowledge_domain or "general",  # 设置键 knowledge_domain 对应的值。
            "dense_vector": dense_vecs[index].tolist(),  # 设置键 dense_vector 对应的值。
            "sparse_vector": sparse_vecs[index],  # 设置键 sparse_vector 对应的值。
        }  # 结束当前列表、字典、元组、调用或代码块。
        for index, chunk in enumerate(chunks)  # 遍历目标数据中的每一项。
    ]  # 结束当前列表、字典、元组、调用或代码块。


async def replace_local_chunks(  # 定义异步函数 replace_local_chunks，用于封装可复用的异步逻辑。
    db: AsyncSession,  # 执行这一行代码，完成当前逻辑。
    document: Document,  # 执行这一行代码，完成当前逻辑。
    chunks: list[str],  # 执行这一行代码，完成当前逻辑。
    milvus_ids: list[int],  # 执行这一行代码，完成当前逻辑。
) -> None:  # 开始一个新的代码块。
    """处理replace_local_chunks相关逻辑。

    参数：
        # 定义异步函数 replace_local_chunks，用于封装可复用的异步逻辑。     db: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     document: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     chunks: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     milvus_ids: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。: 当前函数使用的输入参数。
    """
    await db.execute(delete(MilvusIndex).where(MilvusIndex.doc_id == document.id))  # 等待异步操作完成后再继续执行。
    if not chunks:  # 根据条件决定是否执行下面的代码块。
        return  # 结束当前函数并返回空结果。

    db.add_all(  # 开始调用 db.add_all，后面继续传入参数。
        [  # 执行这一行代码，完成当前逻辑。
            MilvusIndex(  # 开始调用 MilvusIndex，后面继续传入参数。
                doc_id=document.id,  # 设置 doc_id 的值，供后续逻辑使用。
                milvus_id=str(milvus_ids[index]) if index < len(milvus_ids) else f"local-{document.id}-{index}",  # 调用 str 并把结果保存到 milvus_id 中。
                chunk_index=index,  # 设置 chunk_index 的值，供后续逻辑使用。
                chunk_text=chunk,  # 设置 chunk_text 的值，供后续逻辑使用。
            )  # 结束当前列表、字典、元组、调用或代码块。
            for index, chunk in enumerate(chunks)  # 遍历目标数据中的每一项。
        ]  # 结束当前列表、字典、元组、调用或代码块。
    )  # 结束当前列表、字典、元组、调用或代码块。


async def index_document(document: Document) -> tuple[list[str], list[int]]:  # 定义异步函数 index_document，用于封装可复用的异步逻辑。
    """处理index_document相关逻辑。

    参数：
        document: 当前函数处理的文档实体。
    """
    embedding = get_embedding()  # 调用 get_embedding 并把结果保存到 embedding 中。
    milvus = get_milvus()  # 调用 get_milvus 并把结果保存到 milvus 中。
    chunks = embedding.chunk_text(  # 调用 embedding.chunk_text 并把结果保存到 chunks 中。
        document.content,  # 执行这一行代码，完成当前逻辑。
        chunk_size=config.CHUNK_SIZE,  # 设置 chunk_size 的值，供后续逻辑使用。
        overlap=config.CHUNK_OVERLAP,  # 设置 overlap 的值，供后续逻辑使用。
    )  # 结束当前列表、字典、元组、调用或代码块。
    if not chunks:  # 根据条件决定是否执行下面的代码块。
        return [], []  # 返回当前函数计算出的结果。

    try:  # 开始尝试执行可能出错的代码。
        milvus.delete_by_doc_id(document.id)  # 调用 milvus.delete_by_doc_id 处理当前这一步逻辑。
        dense_vecs, sparse_vecs = embedding.encode_full(chunks)  # 执行这一行代码，完成当前逻辑。
        return chunks, milvus.upsert(_build_milvus_payload(document, chunks, dense_vecs, sparse_vecs))  # 返回当前函数计算出的结果。
    except Exception:  # 捕获并处理前面代码抛出的异常。
        return chunks, []  # 返回当前函数计算出的结果。


async def save_document(
    *,
    db: AsyncSession,
    user_id: int,
    filename: str,
    content: bytes,
    knowledge_domain: str,
    existing_document: Optional[Document] = None,
) -> Document:

    text = extract_text(filename, content)
    if not text.strip():
        raise ValueError("文件中未解析到有效文本")

    saved_path = build_saved_path(user_id, filename)
    saved_path.write_bytes(content)

    document = existing_document
    if document is None:
        document = Document(
            title=filename or "untitled",
            content=text,
            file_path=str(saved_path),
            source=_get_document_source(filename),
            knowledge_domain=knowledge_domain,
            user_id=user_id,
            milvus_ids=[],
            chunk_count=0,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
    else:
        old_path = Path(document.file_path) if document.file_path else None
        document.title = filename or document.title
        document.content = text
        document.file_path = str(saved_path)
        document.source = _get_document_source(filename)
        document.knowledge_domain = knowledge_domain
        document.user_id = user_id
        if old_path and old_path.exists() and old_path != saved_path:
            old_path.unlink()

    chunks, milvus_ids = await index_document(document)
    await replace_local_chunks(db, document, chunks, milvus_ids)
    document.milvus_ids = milvus_ids
    document.chunk_count = len(chunks)
    await db.commit()
    await db.refresh(document)
    return document


async def upsert_local_file(  # 定义异步函数 upsert_local_file，用于封装可复用的异步逻辑。
    *,  # 执行这一行代码，完成当前逻辑。
    db: AsyncSession,  # 执行这一行代码，完成当前逻辑。
    file_path: Path,  # 执行这一行代码，完成当前逻辑。
    user_id: int,  # 执行这一行代码，完成当前逻辑。
    knowledge_domain: str,  # 执行这一行代码，完成当前逻辑。
) -> Document:  # 开始一个新的代码块。
    """插入或更新localfile相关逻辑。

    参数：
        # 定义异步函数 upsert_local_file，用于封装可复用的异步逻辑。     *: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     db: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     file_path: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     user_id: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。     knowledge_domain: 当前函数使用的输入参数。
        # 执行这一行代码，完成当前逻辑。: 当前函数使用的输入参数。
    """
    result = await db.execute(  # 设置 result 的值，供后续逻辑使用。
        select(Document).where(  # 开始书写一个函数调用或表达式。
            Document.user_id == user_id,  # 执行这一行代码，完成当前逻辑。
            Document.title == file_path.name,  # 执行这一行代码，完成当前逻辑。
        )  # 结束当前列表、字典、元组、调用或代码块。
    )  # 结束当前列表、字典、元组、调用或代码块。
    return await save_document(  # 返回当前函数计算出的结果。
        db=db,  # 设置 db 的值，供后续逻辑使用。
        user_id=user_id,  # 设置 user_id 的值，供后续逻辑使用。
        filename=file_path.name,  # 设置 filename 的值，供后续逻辑使用。
        content=file_path.read_bytes(),  # 调用 file_path.read_bytes 并把结果保存到 content 中。
        knowledge_domain=knowledge_domain,  # 设置 knowledge_domain 的值，供后续逻辑使用。
        existing_document=result.scalar_one_or_none(),  # 调用 result.scalar_one_or_none 并把结果保存到 existing_document 中。
    )  # 结束当前列表、字典、元组、调用或代码块。
