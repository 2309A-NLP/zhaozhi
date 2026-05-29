"""Role schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=100)
    role_type: str = "friend"
    personality: Optional[str] = None
    language_style: Optional[str] = None
    constraints: Optional[str] = None
    system_prompt: Optional[str] = None
    knowledge_domains: Optional[List[str]] = None
    is_public: bool = False


class RoleOut(BaseModel):
    id: int
    user_id: int
    role_name: str
    role_type: str
    personality: Optional[str]
    language_style: Optional[str]
    constraints: Optional[str]
    knowledge_domains: Optional[List[str]]
    is_public: bool
