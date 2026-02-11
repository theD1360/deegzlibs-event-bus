"""Response store adapters for request/response over the event bus (Redis, in-memory, etc.)."""

from .in_memory import InMemoryResponseStore

__all__ = ["InMemoryResponseStore"]

try:
    from .redis import RedisResponseStore

    __all__ += ["RedisResponseStore"]
except ImportError:
    pass
