"""Redis-backed cache repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.redis")


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
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            LOGGER.warning("redis_invalid_json | key=%s", key)
            self._client.delete(key)
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        self._client.set(name=key, value=json.dumps(value, ensure_ascii=False), ex=ttl_seconds)

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        for key in self._client.scan_iter(match=f"{prefix}*"):
            deleted += int(self._client.delete(key) or 0)
        return deleted
