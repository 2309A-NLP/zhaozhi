"""Core RAG pipeline: retrieve, rerank, build context, and generate."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.milvus_client import MilvusClient
from ..database.models import Document, MilvusIndex
from ..prompts.templates import get_role_prompt
from .embedding import BGEEmbeddingService
from .llm_client import LLMClient
from .memory import MemoryService
from .reranker import BGERerankerService


DocCandidate = Dict[str, Any]


class RAGEngine:
    """一个简约的RAG引擎，具备检索、回退检索和生成功能"""

    def __init__(self, current_config):
        self.config = current_config
        self.embedding = BGEEmbeddingService(
            current_config.BGE_EMBEDDING_MODEL,
            dim=current_config.EMBEDDING_DIM,
        )
        self.reranker = BGERerankerService(current_config.BGE_RERANKER_MODEL)
        self.milvus = MilvusClient(current_config.MILVUS_HOST, current_config.MILVUS_PORT)
        self.memory = MemoryService(
            current_config.REDIS_HOST,
            current_config.REDIS_PORT,
            current_config.REDIS_PASSWORD,
        )
        self.llm = LLMClient(
            current_config.LLM_BASE_URL,
            current_config.LLM_API_KEY,
            current_config.LLM_MODEL,
            timeout=current_config.LLM_TIMEOUT_SECONDS,
        )

    async def chat(  # 对外提供的核心对话方法，完成一次完整的 RAG 问答
        self,
        user_id: int,
        role_id: int,
        session_id: str,
        role_config: dict,
        user_message: str,
        db: AsyncSession,
        allowed_doc_ids: List[int] | None = None,
    ) -> dict:
        # 从会话记忆（可能是 Redis 或数据库）里取出该用户在当前会话中最近的 N 条历史消息，用于理解上下文
        recent_messages = await self.memory.get_recent_messages(user_id,role_id,session_id,self.config.SHORT_TERM_MAX_LEN,)

        # 把“当前用户消息 + 历史对话”压缩/改写成一个适合扔给搜索引擎或向量数据库的查询字符串。这一步是为了提高检索质量，让查出来的文档更贴近真实意图
        search_query = self._build_search_query(user_message, recent_messages)

        # 异步访问知识库（数据库或向量库），根据搜索查询、角色配置规定允许的知识领域、以及可选的允许文档白名单，查出一批可能相关的文档片段
        retrieved_docs = await self._retrieve_documents(  # 混合检索
            db=db,
            search_query=search_query,
            role_config=role_config,
            allowed_doc_ids=allowed_doc_ids,
        )

        # 用更精确的重排序模型，根据与用户问题的语义相关性，对粗检出来的文档进行“优中选优”，把真正有用的文档排在前面
        reranked_docs = self._rerank_documents(user_message, retrieved_docs)

        # 将系统提示（角色配置）、对话历史、用户问题、检索到的文档片段组装成一个大模型的输入格式
        messages = self._build_messages(role_config, user_message, reranked_docs, recent_messages)

        # 调用大语言模型（LLM），让它基于给定的上下文生成最终的自然语言回答
        assistant_response = await self._generate_response(messages, user_message, reranked_docs)

        # 保证下次同一会话继续对话时能拿到完整历史
        await self.memory.push_message(
            user_id,
            role_id,
            session_id,
            user_message,
            assistant_response,
            self.config.SHORT_TERM_MAX_LEN,
        )
        await self.memory.set_ttl(user_id, role_id, session_id, self.config.SHORT_TERM_TTL)


        return {
            "response": assistant_response,  # 大模型生成的回答文本
            "retrieved_docs": reranked_docs, # 最终采用的文档片段列表（就是 ChatResponse 里的那个）
            "session_id": session_id,  # 会话ID，保持对话连续性
       }

    async def _retrieve_documents( # 混合检索（稠密向量 + 稀疏向量）获得候选文档。
        self,
        *,  # * 作为分隔符，表示其后的参数必须使用关键字传递，不能按位置传入
        db: AsyncSession,
        search_query: str,
        role_config: dict,
        allowed_doc_ids: List[int] | None,
    ) -> List[DocCandidate]:
        if allowed_doc_ids == []:
            return []
        # 双路，一路是dense_vec，二路是sparse_vec
        dense_vec = self.embedding.encode_dense([search_query], is_query=True)[0]  # 稠密向量， 语义相似度检索
        sparse_vec = self.embedding.encode_sparse([search_query])[0]  # 稀疏向量，关键词检索
        # 召回是同时传入
        try:
            docs = self.milvus.hybrid_search(
                dense_vec.tolist(),
                sparse_vec,
                domains=role_config.get("knowledge_domains") or None,
                doc_ids=allowed_doc_ids,
                top_k=self.config.RETRIEVAL_TOP_K,
            )
        except Exception:
            docs = []

        if docs:
            return docs
        return await self._local_search(db, allowed_doc_ids or [], self.config.RETRIEVAL_TOP_K)

    def _rerank_documents( # 调用重排序服务对候选文档按相关性精排
            self, user_message: str, docs: List[DocCandidate]) -> List[DocCandidate]:
        return self.reranker.rerank_with_docs(
            user_message,
            docs,
            self.config.RERANK_TOP_K,
        )

    def _build_messages(# 构造发送给 LLM 的消息列表
        self,
        role_config: dict,  # 角色配置字典，包含角色名称、描述等信息，用于生成系统提示。
        user_message: str,  # 用户当前发送的消息文本。
        docs: List[DocCandidate],  # 经过重排序后的候选文档列表
        recent_messages: List[Dict[str, Any]],  # 最近的对话历史列表，每个元素是带有 role 和 content 的字典
    ) -> List[Dict[str, str]]:
        context = self._build_context(docs, recent_messages)
        user_content = context
        if user_content:
            user_content = f"{user_content}\n\n用户最新消息：{user_message}"
        else:
            user_content = f"用户最新消息：{user_message}"
        return [
            {"role": "system", "content": get_role_prompt(role_config)},
            {"role": "user", "content": user_content},
        ]

    @staticmethod
    def _build_doc_candidate( # 静态工厂方法，创建一个标准的文档候选字典
            doc_id: int, text: str, knowledge_domain: str | None) -> DocCandidate:
        return {
            "id": None,
            "doc_id": doc_id,
            "text": text,
            "score": 0.0,
            "domain": knowledge_domain or "general",
        }

    @staticmethod
    def _history_lines( # 将历史消息列表格式化为可读文本行
            recent_messages: List[Dict[str, Any]], limit: int) -> List[str]:  # 将已有的历史消息格式化成可读文本行
        lines: List[str] = []   # 创建一个空列表
        for message in recent_messages[-limit:]:
            lines.append(f"用户：{message['user']}")  # 添加用户
            lines.append(f"助手：{message['assistant']}") # 添加助手
        return lines

    def _build_search_query( # 生成用于检索的搜索查询字符串
            self, user_message: str, recent_messages: List[Dict[str, Any]]) -> str:
        if not recent_messages:
            return user_message
        history = "\n".join(self._history_lines(recent_messages, 3))
        # 得到一个包含最多最近 3 条消息的可迭代对象，
        # 每条消息被格式化为一行文本，"\n" 将这些行连接成一个多行字符串
        # 作用是：将历史记录转换为一个可读性较好的文本块，供后续拼接到搜索查询中。限制 3 条是为了避免上下文过长干扰搜索效果

        return f"{history}\n\n当前问题：{user_message}"

    def _build_context( # 构建 LLM 的上下文文本
            self, docs: List[DocCandidate], recent_messages: List[Dict[str, Any]]) -> str:
        parts: List[str] = []   # parts 是一个元素类型为字符串的空列表
        if docs:
            parts.append("【相关知识】")
            parts.extend(
                f"{index}. {doc['text'][:self.config.CONTEXT_DOC_CHAR_LIMIT]}"
                for index, doc in enumerate(docs, start=1)  # start指定序号从几开始计数
            )  # 将一系列带编号的文档摘要（或文档开头部分）依次添加到 parts 列表的末尾
        if recent_messages:
            parts.append("【对话历史】")
            parts.extend(self._history_lines(recent_messages, 5))
        return "\n".join(parts).strip()

    async def _local_search( # 本地数据库检索
        self,
        db: AsyncSession, # 异步执行数据库操作
        allowed_doc_ids: List[int], # 文档 ID 范围内检索
        top_k: int,
    ) -> List[DocCandidate]:
        if not allowed_doc_ids: # 快捷判断allowed_doc_ids是否为空列表
            return []

        chunk_stmt = ( # 构建一个sql查询语句
            select(MilvusIndex.doc_id, MilvusIndex.chunk_text, Document.knowledge_domain)
            # 查询文档 ID、分块文本内容、文档所属的知识领域
            .join(Document, Document.id == MilvusIndex.doc_id)
            # 将 MilvusIndex 表与 Document 表进行内连接，连接条件是 Document.id 等于 MilvusIndex.doc_id
            .where(MilvusIndex.doc_id.in_(allowed_doc_ids))
            # 添加过滤条件：只查询 doc_id 在 allowed_doc_ids 列表中的记录。
            .order_by(MilvusIndex.doc_id, MilvusIndex.chunk_index)
            # 按 doc_id 升序排列，同一文档内按 chunk_index（分块序号）升序排列。
        ) # 构建分块查询语句
        chunk_rows = (await db.execute(chunk_stmt)).all() # 异步铲鲟执行查询并获取所有行
        chunk_candidates = [ # 开始构建候选结果列表，使用列表推导式遍历每一行查询结果
            self._build_doc_candidate(doc_id, chunk_text, knowledge_domain) # 将三个字段生成一个 DocCandidate 对象
            for doc_id, chunk_text, knowledge_domain in chunk_rows # 解包每一行数据为三个变量，并迭代。
            if chunk_text # 仅当 chunk_text 非空（即分块文本存在）时才将该候选加入列表，避免无意义的空文本
        ] # 构建候选对象列表
        if chunk_candidates: #  判断分块候选列表是否非空
            return chunk_candidates[:top_k]  # 若已有分块候选，直接返回前 k 个

        document_stmt = select(Document.id, Document.content, Document.knowledge_domain).where(
            # 如果分块表中没有数据（例如该文档尚未进行分块处理），则改用文档表进行检索。
            # 构建一个新的查询语句，选择文档 ID、文档内容、知识领域。
            Document.id.in_(allowed_doc_ids)
            # 只查询 id 在 allowed_doc_ids 中的文档
        )
        document_rows = (await db.execute(document_stmt)).all()  # 异步执行文档查询，并获取所有结果行
        document_candidates: List[DocCandidate] = []  #  初始化一个空列表，用于存放从文档内容动态分块生成的候选对象
        for doc_id, content, knowledge_domain in document_rows: # 解包每一行数据为三个变量，并迭代。
            for chunk in self.embedding.chunk_text( # 对当前文档的内容进行动态分块，该方法将文本按指定大小和重叠度切分成多个块，并返回迭代器
                content or "",  #  如果文档内容为 None，则使用空字符串，避免分块函数出错
                chunk_size=self.config.CHUNK_SIZE, # 分块大小
                overlap=self.config.CHUNK_OVERLAP, # 重叠度
            ):
                document_candidates.append(
                    self._build_doc_candidate(doc_id, chunk, knowledge_domain)
                ) # 传入文档 ID、分块文本、知识领域，生成一个 DocCandidate 对象。
                if len(document_candidates) >= top_k: # 判断每次追加后的列表长度是否超过top_k,是则返回列表
                    return document_candidates
        return document_candidates # 当所有文档的分块都处理完毕，但候选总数仍不足 top_k 时，返回整个候选列表

    async def _generate_response(  # 异步调用 LLM 生成回答，带超时和重试机制
        self,
        messages: List[Dict[str, str]],  # 对话历史
        user_message: str,  # 用户当前发送的消息原文
        reranked_docs: List[DocCandidate],  # 重排序后的文档候选列表
    ) -> str:
        try:
            result = await asyncio.wait_for(
                # asyncio.wait_for 会在给定超时时间内等待内部的协程/可等待对象完成，超时则抛出 asyncio.TimeoutError
                # asyncio.TimeoutError 的含义是在异步操作等待超时后引发的异常，用于表示某个异步任务未能在规定时间内完成
                asyncio.to_thread(  # 将同步阻塞函数放到独立线程中执行
                    self.llm.chat_with_retry,  # 一个同步的 LLM 调用函数，内部可能包含重试逻辑
                    messages,  # 对话历史、
                    self.config.LLM_MAX_RETRIES, # 最大重试次数、
                    self.config.LLM_TEMPERATURE, # 温度参数
                    self.config.LLM_MAX_TOKENS, # 最大生成 token 数。
                ),
                timeout=self.config.LLM_HARD_TIMEOUT_SECONDS,  # 为 asyncio.wait_for 指定超时时间
            )  # 闭合 asyncio.wait_for 的括号，await 这里会得到 chat_with_retry 的返回值（正常情况是 LLM 生成的字符串）。
            if result:
                return result
        except (asyncio.TimeoutError, Exception):
            pass
        return self._build_timeout_fallback(user_message, reranked_docs)
    # 如果上面的 try 块中没有成功返回（无论是异常还是 result 为空），则调用 _build_timeout_fallback 方法，
    # 传入原始用户消息和重排序文档，构建一个“超时/错误”时的兜底回复并返回

    def _build_timeout_fallback( # 当 LLM 调用超时或失败时，构造一个友好的降级回复。
            self, user_message: str, docs: List[DocCandidate]) -> str:
        if not docs:
            return (
                f"我暂时没能在时限内完成生成，但已收到你的问题：{user_message}。"
                "请稍后重试，或把问题问得更具体一些。"
            )

        lines = [f"我暂时没能在时限内完成完整生成。根据当前检索到的资料，关于“{user_message}”可先参考这些要点："]
        for index, doc in enumerate(docs[:3], start=1):
            snippet = " ".join(doc.get("text", "").split())
            lines.append(f"{index}. {snippet[:140]}")
        lines.append("如果你愿意，我可以继续基于这些资料回答更具体的问题。")
        return "\n".join(lines)
