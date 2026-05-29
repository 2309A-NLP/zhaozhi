"""聊天应用服务."""
from __future__ import annotations

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import config
from ..core.role_defaults import (
    build_default_role_config,
    build_effective_knowledge_domains,
)
from ..database.models import User
from ..repositories.conversation_repository import ConversationRepository
from ..repositories.document_repository import DocumentRepository
from ..repositories.role_repository import RoleRepository
from ..schemas.chat import ChatRequest, ChatResponse
from .conversation_ingestion import save_conversation
from .rag_engine import RAGEngine


def apply_role_response_rules(role_config: Dict[str, Any], response: str) -> str:
    """应用roleresponserules相关逻辑。

    参数：
        role_config: 当前函数使用的最终角色配置。
        response: 当前函数处理的响应内容。
    """
    return response


class ChatService:
    def __init__(self, db: AsyncSession, rag_engine: RAGEngine):
        """初始化对象，准备后续逻辑所需的依赖。

        参数：
            db: 当前函数使用的异步数据库会话。
            rag_engine: 当前函数使用的输入参数。
        """
        self.db = db
        self.rag_engine = rag_engine
        self.roles = RoleRepository(db)
        self.documents = DocumentRepository(db)
        self.conversations = ConversationRepository(db)

    async def _get_role_config(self, *, role_id: int, user_id: int) -> Dict[str, Any] | None:
        """处理_get_role_config相关逻辑。
        根据 role_id 和当前用户，拿到“这次聊天最终要用的角色基础配置

        参数：
            role_id: 当前函数使用的角色 ID。
            user_id: 当前函数使用的用户 ID。
        """
        if role_id <= 0:
            return None
        role = await self.roles.get_by_id(role_id)
        if not role:
            return None
        if role.user_id != user_id and not role.is_public:
            raise PermissionError("无权使用该角色")
        role_type = role.role_type or config.DEFAULT_ROLE_TYPE
        default_profile = build_default_role_config(
            role_id=role.id,
            default_role_name=role.role_name,
            default_role_type=role_type,
        )
        default_profile.update(
            {
                "personality": role.personality or default_profile["personality"],
                "language_style": role.language_style or default_profile["language_style"],
                "constraints": role.constraints or default_profile["constraints"],
                "system_prompt": role.system_prompt,
                "knowledge_domains": role.knowledge_domains or default_profile["knowledge_domains"][:],
                "is_public": role.is_public,
            }
        )
        return default_profile

    async def chat(self, request: ChatRequest, current_user: User) -> ChatResponse:
        """处理一次聊天相关操作。
            把这次聊天所需的角色、权限、文档范围准备好，然后交给 rag_engine这个py文件 去真正检索和生成。”
        参数：
            request: 当前操作使用的、已校验请求数据。
            current_user: 当前请求对应的已认证用户。
        """
        session_id = request.session_id or f"session_{current_user.id}_{request.role_id}_{int(time.time())}"
        role_config = await self._get_role_config(role_id=request.role_id, user_id=current_user.id)
        if role_config is None:
            role_config = build_default_role_config(
                role_id=request.role_id,
                default_role_name=config.DEFAULT_ROLE_NAME,
                default_role_type=config.DEFAULT_ROLE_TYPE,
            )
        if request.role_config_override:
            role_config.update(request.role_config_override.model_dump())

        effective_domains = build_effective_knowledge_domains(
            role_config,
            default_role_type=config.DEFAULT_ROLE_TYPE,
        )
        role_config["knowledge_domains"] = effective_domains
        allowed_doc_ids = await self.documents.list_doc_ids_by_user_and_domains(
            user_id=current_user.id,
            knowledge_domains=effective_domains,
        )

        result = await self.rag_engine.chat(
            user_id=current_user.id,
            role_id=request.role_id,
            session_id=session_id,
            role_config=role_config,
            user_message=request.message,
            db=self.db,
            allowed_doc_ids=allowed_doc_ids,
        )
        result["response"] = apply_role_response_rules(role_config, result["response"])

        conversation = await self.conversations.create(
            user_id=current_user.id,
            role_id=request.role_id or None,
            session_id=session_id,
            message=request.message,
            response=result["response"],
            retrieved_docs=result.get("retrieved_docs", []),
        )
        try:
            await save_conversation(conversation)
        except Exception:
            pass

        retrieved_docs: List[Dict[str, Any]] = result.get("retrieved_docs", [])
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            retrieved_docs_count=len(retrieved_docs),
            retrieved_docs=retrieved_docs,
        ) # 返回到schemas\chat.py
