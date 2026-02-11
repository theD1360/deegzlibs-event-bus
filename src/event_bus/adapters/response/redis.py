"""Redis-backed response store for request/response over the event bus."""

import json
from typing import Any, Optional

from ...interfaces import ResponseStore


def _serialize(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, default=str)


def _deserialize(raw: Optional[bytes]) -> Optional[Any]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


class RedisResponseStore(ResponseStore):
    """
    Store handler results in Redis keyed by correlation_id.
    Use with EventBus(response_store=...) and execute_and_wait() on the client.
    Values are JSON-serialized; Pydantic models are stored via model_dump().
    """

    def __init__(
        self,
        redis_client: Any,  # e.g. redis.Redis() with .set(key, value, ex=ttl), .get(key), .delete(key)
        key_prefix: str = "event_bus:response:",
        default_ttl_seconds: int = 60,
    ) -> None:
        self._redis = redis_client
        self._prefix = key_prefix
        self._default_ttl = default_ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def set(self, key: str, value: Any, ttl_seconds: int = 0) -> None:
        full_key = self._key(key)
        payload = _serialize(value)
        if ttl_seconds <= 0:
            ttl_seconds = self._default_ttl
        self._redis.set(full_key, payload, ex=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        full_key = self._key(key)
        raw = self._redis.get(full_key)
        return _deserialize(raw)

    def delete(self, key: str) -> None:
        self._redis.delete(self._key(key))
