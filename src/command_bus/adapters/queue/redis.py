"""Redis-backed queue adapter using Redis Lists (LPUSH/BRPOP)."""

import warnings
from typing import Any, List

from ...interfaces import QueueAdapter, TransmissibleBaseModel


class _RedisMessage:
    """Wrapper so Redis messages have .body and .delete() like SQS/RabbitMQ. Message already popped, so delete is no-op."""

    __slots__ = ("body",)

    def __init__(self, body: str) -> None:
        self.body = body

    def delete(self) -> None:
        """No-op: message was already removed from the list when we BRPOP'd."""
        pass


class RedisQueueAdapter(QueueAdapter):
    """
    Queue adapter using a Redis List for queue operations (LPUSH to enqueue, BRPOP to consume).
    FIFO: producers LPUSH, workers BRPOP. delay_seconds is not supported (use a delayed-queue pattern separately if needed).
    """

    def __init__(self, redis_client: Any, queue_name: str) -> None:
        self._redis = redis_client
        self.queue_name = queue_name

    def enqueue(
        self,
        message_instance: TransmissibleBaseModel,
        delay_seconds: int = 0,
    ) -> None:
        """Add a message to the queue. delay_seconds is ignored (Redis List has no native delay)."""
        self._redis.lpush(self.queue_name, str(message_instance))

    def dequeue(self, message_instance: Any) -> None:
        """No-op: message was already removed when get_messages() used BRPOP."""
        if hasattr(message_instance, "delete"):
            message_instance.delete()

    def get_messages(
        self,
        max_messages: int = 1,
        wait_seconds: int = 0,
        **kwargs: Any,
    ) -> List[_RedisMessage]:
        """Fetch messages from the queue. Uses BRPOP (blocking) when wait_seconds > 0, else RPOP (non-blocking)."""
        out: List[_RedisMessage] = []
        timeout = max(0, wait_seconds)
        for i in range(max_messages):
            if timeout > 0 and i == 0:
                result = self._redis.brpop(self.queue_name, timeout=timeout)
            else:
                result = self._redis.rpop(self.queue_name)
            if result is None:
                break
            # brpop returns (key, value); rpop returns value only
            if isinstance(result, (list, tuple)):
                _, raw = result
            else:
                raw = result
            body = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            out.append(_RedisMessage(body=body))
        return out

    def pending_message_count(self) -> int:
        """Return the number of messages waiting in the Redis list."""
        return int(self._redis.llen(self.queue_name))

    def purge_messages(self) -> int:
        """Delete the Redis list key and return how many messages were removed."""
        count = self.pending_message_count()
        if count:
            self._redis.delete(self.queue_name)
        return count


class RedisCommandBusAdapter(RedisQueueAdapter):
    """Deprecated alias for :class:`RedisQueueAdapter`."""

    def __init__(self, redis_client: Any, queue_name: str) -> None:
        warnings.warn(
            "RedisCommandBusAdapter is deprecated; use RedisQueueAdapter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(redis_client=redis_client, queue_name=queue_name)
