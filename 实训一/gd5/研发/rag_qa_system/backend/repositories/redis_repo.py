"""Redis-backed cache and conversation repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RedisRepository:
    host: str
    port: int
    password: str = ""
    db: int = 0

    def __post_init__(self) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis package is required for Redis access") from exc

        self._client = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password or None,
            db=self.db,
            decode_responses=True,
        )
        self._client.ping()

    def get(self, key: str) -> Optional[Any]:
        value = self._client.get(key)
        if value is None:
            return None
        return json.loads(value)

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        self._client.set(name=key, value=json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

    def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        if not session_id:
            return []
        key = self._conversation_key(session_id)
        values = self._client.lrange(key, 0, -1)
        return [json.loads(item) for item in values]

    def append_conversation_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        ttl_seconds: int,
        max_messages: int,
    ) -> None:
        if not session_id or not messages:
            return
        key = self._conversation_key(session_id)
        payloads = [json.dumps(message, ensure_ascii=False) for message in messages]
        pipeline = self._client.pipeline()
        pipeline.rpush(key, *payloads)
        if max_messages > 0:
            pipeline.ltrim(key, -max_messages, -1)
        if ttl_seconds > 0:
            pipeline.expire(key, ttl_seconds)
        pipeline.execute()

    def clear_conversation(self, session_id: str) -> None:
        if not session_id:
            return
        self._client.delete(self._conversation_key(session_id))

    def _conversation_key(self, session_id: str) -> str:
        return f"conversation:{session_id}"
