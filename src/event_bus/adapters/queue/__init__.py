"""Queue adapters for the event bus (SQS, RabbitMQ, Redis, in-memory, etc.)."""

from .in_memory import InMemoryEventBusAdapter
from .sqs import SqsEventBusAdapter

__all__ = ["InMemoryEventBusAdapter", "SqsEventBusAdapter"]

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
