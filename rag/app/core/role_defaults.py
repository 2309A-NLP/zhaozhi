"""Shared role defaults and role config builders."""
from __future__ import annotations

from typing import Any, Dict, List


ROLE_DEFAULT_PROFILES: Dict[str, Dict[str, Any]] = {
    "assistant": {
        "role_name": "通用助手",
        "personality": "专业、可靠、清晰",
        "language_style": "简洁、礼貌、自然",
        "constraints": "回答必须基于已有信息、检索结果和上下文，不编造事实。",
        "knowledge_domains": ["general"],
    },
    "friend": {
        "role_name": "虚拟朋友",
        "personality": "温和、真诚、善于倾听",
        "language_style": "自然、轻松、有陪伴感",
        "constraints": "保持虚拟朋友的陪伴感，先理解用户情绪，再结合知识和上下文回应，不编造事实。",
        "knowledge_domains": ["general"],
    },
    "doctor": {
        "role_name": "医生",
        "personality": "严谨、耐心、专业",
        "language_style": "清晰、审慎、易理解",
        "constraints": "优先基于医疗知识库回答，不能替代线下诊疗；遇到危险信号时要明确建议及时就医。",
        "knowledge_domains": ["medical"],
    },
}

FALLBACK_ROLE_PROFILE = ROLE_DEFAULT_PROFILES["assistant"]

ROLE_DEFAULT_KNOWLEDGE_DOMAINS = {
    role_type: profile["knowledge_domains"][:]
    for role_type, profile in ROLE_DEFAULT_PROFILES.items()
}


def get_role_profile(role_type: str) -> Dict[str, Any]:
    """获取roleprofile相关逻辑。

    参数：
        role_type: 当前函数处理的角色类型。
    """
    return ROLE_DEFAULT_PROFILES.get(role_type, FALLBACK_ROLE_PROFILE)


def build_default_role_config(
    *,
    role_id: int,
    default_role_name: str,
    default_role_type: str,
) -> Dict[str, Any]:
    """构建defaultroleconfig相关逻辑。

    参数：
        role_id: 当前函数使用的角色 ID。
        default_role_name: 没有明确值时使用的默认角色名称。
        default_role_type: 没有明确值时使用的默认角色类型。
    """
    profile = get_role_profile(default_role_type)
    return {
        "role_id": role_id,
        "role_name": default_role_name or profile["role_name"],
        "role_type": default_role_type,
        "personality": profile["personality"],
        "language_style": profile["language_style"],
        "constraints": profile["constraints"],
        "system_prompt": None,
        "knowledge_domains": profile["knowledge_domains"][:],
        "is_public": True,
    }


def build_effective_knowledge_domains(
    role_config: Dict[str, Any],
    *,
    default_role_type: str,
) -> List[str]:
    """构建effectiveknowledgedomains相关逻辑。

    参数：
        role_config: 当前函数使用的最终角色配置。
        default_role_type: 没有明确值时使用的默认角色类型。
    """
    domains = [
        item.strip()
        for item in role_config.get("knowledge_domains") or []
        if item and item.strip()
    ]
    if domains:
        return domains
    return ROLE_DEFAULT_KNOWLEDGE_DOMAINS.get(
        role_config.get("role_type", default_role_type),
        ROLE_DEFAULT_KNOWLEDGE_DOMAINS.get(default_role_type, ["general"]),
    ).copy()
