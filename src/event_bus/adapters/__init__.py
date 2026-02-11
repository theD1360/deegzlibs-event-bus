"""Queue and response adapters for the event bus."""

from .queue import FileQueueAdapter, InMemoryEventBusAdapter, SqsEventBusAdapter

__all__ = ["InMemoryEventBusAdapter", "SqsEventBusAdapter", "FileQueueAdapter"]

try:
    from .queue import RabbitMqEventBusAdapter

    __all__ += ["RabbitMqEventBusAdapter"]
except ImportError:
    pass

try:
    from .queue import RedisEventBusAdapter

    __all__ += ["RedisEventBusAdapter"]
except ImportError:
    pass

from .response import FileResponseStore, InMemoryResponseStore

__all__ += ["InMemoryResponseStore", "FileResponseStore"]

try:
    from .response import RedisResponseStore

    __all__ += ["RedisResponseStore"]
except ImportError:
    pass
