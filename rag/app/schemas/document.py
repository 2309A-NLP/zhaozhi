"""Document schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    knowledge_domain: Optional[str] = None
    user_id: int
    chunk_count: int
    source: Optional[str] = None
    created_at: Optional[str] = None
