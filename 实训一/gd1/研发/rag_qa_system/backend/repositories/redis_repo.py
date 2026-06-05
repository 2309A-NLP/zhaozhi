"""Redis-backed cache repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


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
