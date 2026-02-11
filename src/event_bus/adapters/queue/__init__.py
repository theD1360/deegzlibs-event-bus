"""Queue adapters for the event bus (SQS, RabbitMQ, Redis, in-memory, file, etc.)."""

from .file import FileQueueAdapter
from .in_memory import InMemoryEventBusAdapter
from .sqs import SqsEventBusAdapter

__all__ = ["InMemoryEventBusAdapter", "SqsEventBusAdapter", "FileQueueAdapter"]

try:
    from .rabbitmq import RabbitMqEventBusAdapter

    __all__ += ["RabbitMqEventBusAdapter"]
except ImportError:
    pass

try:
    from .redis import RedisEventBusAdapter

    __all__ += ["RedisEventBusAdapter"]
except ImportError:
    pass
