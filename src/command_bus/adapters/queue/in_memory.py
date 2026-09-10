"""In-memory queue adapter for tests or in-process use."""

import warnings
from collections import deque
from typing import Any, List

from ...interfaces import QueueAdapter, TransmissibleBaseModel


class _InMemoryMessage:
    """Message wrapper with .body and .delete() for bus compatibility."""

    __slots__ = ("body",)

    def __init__(self, body: str) -> None:
        self.body = body

    def delete(self) -> None:
        """No-op: message already removed from queue when get_messages() popped it."""
        pass


class InMemoryQueueAdapter(QueueAdapter):
    """
    In-memory FIFO queue adapter. Useful for tests or single-process dispatch.
    delay_seconds is ignored (no native delay); messages are available immediately.
    """

    def __init__(self, queue_name: str = "default") -> None:
        self.queue_name = queue_name
        self._queue: deque[str] = deque()

    def enqueue(
        self,
        message_instance: TransmissibleBaseModel,
        delay_seconds: int = 0,
    ) -> None:
        """Append message to the queue. delay_seconds is ignored."""
        self._queue.append(str(message_instance))

    def dequeue(self, message_instance: Any) -> None:
        """No-op: message was already removed when get_messages() popped it."""
        if hasattr(message_instance, "delete"):
            message_instance.delete()

    def get_messages(
        self,
        max_messages: int = 1,
        wait_seconds: int = 0,
        **kwargs: Any,
    ) -> List[_InMemoryMessage]:
        """Pop up to max_messages from the queue. wait_seconds is ignored (no blocking)."""
        out: List[_InMemoryMessage] = []
        for _ in range(max_messages):
            try:
                body = self._queue.popleft()
            except IndexError:
                break
            out.append(_InMemoryMessage(body=body))
        return out

    def pending_message_count(self) -> int:
        """Return the number of messages waiting in this in-process queue."""
        return len(self._queue)

    def purge_messages(self) -> int:
        """Remove all pending messages without dispatching."""
        count = len(self._queue)
        self._queue.clear()
        return count


class InMemoryCommandBusAdapter(InMemoryQueueAdapter):
    """Deprecated alias for :class:`InMemoryQueueAdapter`."""

    def __init__(self, queue_name: str = "default") -> None:
        warnings.warn(
            "InMemoryCommandBusAdapter is deprecated; use InMemoryQueueAdapter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(queue_name=queue_name)
