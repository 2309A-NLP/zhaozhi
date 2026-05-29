"""Chat schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from ..config import config


class RoleConfigOverride(BaseModel):
    # 定义角色配置的可选覆盖参数
    role_name: str = config.DEFAULT_ROLE_NAME  # 角色名称
    role_type: str = config.DEFAULT_ROLE_TYPE  # 角色名称
    personality: Optional[str] = None  # 角色的性格
    language_style: Optional[str] = None  # 角色语言风格
    constraints: Optional[str] = None  # 角色约束条件
    system_prompt: Optional[str] = None
    knowledge_domains: List[str] = Field(default_factory=list)  # 限定该角色使用的知识领域列表
    is_public: bool = False  # 是否将此临时配置设为公开可见


class ChatRequest(BaseModel):
    # 客户端向聊天接口发送请求时，需要按此模型提供数据
    role_id: int = 0  # 指定使用哪个预定义角色
    session_id: Optional[str] = None  # 会话ID，用于多轮对话上下文关联；为空时可能新建会话
    message: str  # 用户输入的当前消息
    role_config_override: Optional[RoleConfigOverride] = None  # 用于动态调整当前对话的角色行为


class RetrievedDoc(BaseModel):
    # 表示检索到的文档片段
    id: Optional[int] = None  # 片段ID
    doc_id: Optional[int] = None  # 原始文档ID
    text: str  # 文档片段的文本内容
    score: Optional[float] = None  # 原始检索得分
    domain: Optional[str] = None  # 该文档所属的知识领域
    rerank_score: Optional[float] = None  # 重排序后的得分，用于更精准的相关性排序


class ChatResponse(BaseModel):
    # 定义聊天回复的响应结构
    response: str  # 模型生成的回答文本
    session_id: str  # 当前对话的会话ID
    retrieved_docs_count: int  # 本次检索到的文档数量
    retrieved_docs: List[RetrievedDoc] = Field(default_factory=list)  # 检索到的文档片段列表，元素是 RetrievedDoc，可用于前端展示引用或更多信息。
