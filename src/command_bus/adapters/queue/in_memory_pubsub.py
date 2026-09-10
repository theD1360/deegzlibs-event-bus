"""In-memory pub/sub adapter: one publish copies to every subscriber."""

from collections import defaultdict, deque
from threading import Lock
from typing import Any, Deque, Dict, List, Set

from ...interfaces import QueueAdapter, TransmissibleBaseModel


class _InMemoryPubSubMessage:
    """Message wrapper with .body and .delete() for bus compatibility."""

    __slots__ = ("body",)

    def __init__(self, body: str) -> None:
        self.body = body

    def delete(self) -> None:
        """No-op: message already removed from the subscriber queue when popped."""
        pass


# Shared broker state: topic -> set of subscriber queue ids
_broker_lock = Lock()
_topic_subscribers: Dict[str, Set[int]] = defaultdict(set)
_subscriber_queues: Dict[int, Deque[str]] = {}
_next_subscriber_id = 1


class InMemoryPubSubAdapter(QueueAdapter):
    """
    In-memory fan-out adapter. Each instance is one subscriber on ``queue_name``
    (topic). ``enqueue`` copies the message body to every subscriber's local queue.
    Useful for tests and single-process multi-worker simulation.
    """

    def __init__(self, queue_name: str = "events") -> None:
        global _next_subscriber_id
        self.queue_name = queue_name
        with _broker_lock:
            self._subscriber_id = _next_subscriber_id
            _next_subscriber_id += 1
            _subscriber_queues[self._subscriber_id] = deque()
            _topic_subscribers[queue_name].add(self._subscriber_id)

    def enqueue(
        self,
        message_instance: TransmissibleBaseModel,
        delay_seconds: int = 0,
    ) -> None:
        """Broadcast message to all subscribers of this topic. delay_seconds ignored."""
        body = str(message_instance)
        with _broker_lock:
            for sid in list(_topic_subscribers.get(self.queue_name, ())):
                q = _subscriber_queues.get(sid)
                if q is not None:
                    q.append(body)

    def dequeue(self, message_instance: Any) -> None:
        """No-op: message was already removed when get_messages() popped it."""
        if hasattr(message_instance, "delete"):
            message_instance.delete()

    def get_messages(
        self,
        max_messages: int = 1,
        wait_seconds: int = 0,
        **kwargs: Any,
    ) -> List[_InMemoryPubSubMessage]:
        """Pop up to max_messages from this subscriber's queue."""
        out: List[_InMemoryPubSubMessage] = []
        with _broker_lock:
            q = _subscriber_queues.get(self._subscriber_id)
            if q is None:
                return out
            for _ in range(max_messages):
                try:
                    body = q.popleft()
                except IndexError:
                    break
                out.append(_InMemoryPubSubMessage(body=body))
        return out

    def pending_message_count(self) -> int:
        """Return messages waiting in this subscriber's local buffer."""
        with _broker_lock:
            q = _subscriber_queues.get(self._subscriber_id)
            return len(q) if q is not None else 0

    def purge_messages(self) -> int:
        """Remove all pending messages from this subscriber's local buffer."""
        with _broker_lock:
            q = _subscriber_queues.get(self._subscriber_id)
            if q is None:
                return 0
            count = len(q)
            q.clear()
            return count

    def close(self) -> None:
        """Unregister this subscriber from the topic."""
        with _broker_lock:
            _topic_subscribers[self.queue_name].discard(self._subscriber_id)
            _subscriber_queues.pop(self._subscriber_id, None)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _reset_in_memory_pubsub_broker() -> None:
    """Test helper: clear shared broker state."""
    global _next_subscriber_id
    with _broker_lock:
        _topic_subscribers.clear()
        _subscriber_queues.clear()
        _next_subscriber_id = 1
