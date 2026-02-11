"""In-memory event bus adapter for tests or in-process use."""

from collections import deque
from typing import Any, List

from ...interfaces import EventBusAdapter, EventMessage


class _InMemoryMessage:
    """Message wrapper with .body and .delete() for bus compatibility."""

    __slots__ = ("body",)

    def __init__(self, body: str) -> None:
        self.body = body

    def delete(self) -> None:
        """No-op: message already removed from queue when get_messages() popped it."""
        pass


class InMemoryEventBusAdapter(EventBusAdapter):
    """
    In-memory FIFO queue adapter. Useful for tests or single-process event dispatch.
    delay_seconds is ignored (no native delay); messages are available immediately.
    """

    def __init__(self, queue_name: str = "default") -> None:
        self.queue_name = queue_name
        self._queue: deque[str] = deque()

    def enqueue(
        self,
        message_instance: EventMessage,
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
