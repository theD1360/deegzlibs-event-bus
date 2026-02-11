"""In-memory response store for tests or in-process request/response."""

import json
import time
from typing import Any, Dict, Optional

from ...interfaces import ResponseStore


class InMemoryResponseStore(ResponseStore):
    """Simple in-memory response store."""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self._store: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self._default_ttl = default_ttl_seconds

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Store a response value with optional TTL."""
        # Serialize if not already a string
        if not isinstance(value, str):
            value = json.dumps(value)
        # Use default TTL if 0 is provided (matching interface behavior)
        ttl = ttl_seconds if ttl_seconds > 0 else self._default_ttl
        self._store[key] = (value, time.time() + ttl)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a response value if it exists and hasn't expired."""
        if key not in self._store:
            return None
        value, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            return None
        # Try to deserialize JSON, return as-is if it fails
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def delete(self, key: str) -> None:
        """Delete a response value."""
        self._store.pop(key, None)
