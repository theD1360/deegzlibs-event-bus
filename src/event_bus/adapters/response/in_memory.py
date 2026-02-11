"""In-memory response store for tests or in-process request/response."""

from typing import Any, Optional

from ...interfaces import ResponseStore


class InMemoryResponseStore(ResponseStore):
    """Minimal in-memory store. Useful for tests or single-process use."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        self._store[key] = value

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
