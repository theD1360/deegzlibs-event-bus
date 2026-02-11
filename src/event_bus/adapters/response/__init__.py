"""Response store adapters for request/response over the event bus (Redis, in-memory, file, etc.)."""

from .file import FileResponseStore
from .in_memory import InMemoryResponseStore

__all__ = ["InMemoryResponseStore", "FileResponseStore"]

try:
    from .redis import RedisResponseStore

    __all__ += ["RedisResponseStore"]
except ImportError:
    pass
