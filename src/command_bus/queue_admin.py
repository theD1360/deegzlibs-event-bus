"""Queue inspection and maintenance helpers for the CLI."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from .adapters.queue.file import FileQueueAdapter
from .adapters.queue.in_memory import InMemoryQueueAdapter
from .adapters.queue.in_memory_pubsub import InMemoryPubSubAdapter
from .adapters.queue.rabbitmq import RabbitMqQueueAdapter
from .adapters.queue.redis import RedisQueueAdapter
from .adapters.queue.sqs import SqsQueueAdapter
from .bus import CommandBus
from .command_bus_group import BusGroup, CommandBusGroup, resolve_bus_attr_on_module
from .event_bus import EventBus
from .interfaces import QueueAdapter
from .worker_app import WorkerApp

BusTarget = Union[CommandBus, EventBus, WorkerApp, BusGroup, CommandBusGroup]


@dataclass(frozen=True)
class QueueDescriptor:
    """One consumable queue exposed by a CLI target."""

    label: str
    bus_kind: str
    adapter_type: str
    adapter_queue_name: str
    adapter: QueueAdapter


class QueueAdminError(Exception):
    """Base error for queue admin operations."""


class UnsupportedQueueOperation(QueueAdminError):
    """Raised when an adapter cannot perform the requested operation."""


def parse_target(spec: str) -> Tuple[str, str]:
    """Parse ``module`` or ``module:attribute`` (default attribute ``bus``)."""
    spec = spec.strip()
    if not spec:
        raise QueueAdminError("Target must be a non-empty module path or module:attribute")
    if ":" in spec:
        mod_part, _, attr = spec.rpartition(":")
        mod_part = mod_part.strip()
        attr = attr.strip()
        if not mod_part or not attr:
            raise QueueAdminError(
                f"Invalid target {spec!r}; use dotted.module:attribute"
            )
        return mod_part, attr
    return spec, "bus"


def load_target(spec: str) -> Tuple[object, str, BusTarget]:
    """Import ``spec`` and return ``(module, attr_name, target_object)``."""
    module_name, attr_name = parse_target(spec)
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise QueueAdminError(f"Failed to import {module_name!r}: {e}") from e
    target = getattr(module, attr_name, None)
    if target is None:
        raise QueueAdminError(f"Module {module_name!r} has no attribute {attr_name!r}")
    if not isinstance(target, (CommandBus, EventBus, WorkerApp, BusGroup, CommandBusGroup)):
        raise QueueAdminError(
            f"Attribute {attr_name!r} must be a CommandBus, EventBus, WorkerApp, or BusGroup "
            f"(got {type(target).__name__})"
        )
    return module, attr_name, target


def resolve_queues(module: object, attr_name: str, target: BusTarget) -> List[QueueDescriptor]:
    """Expand a CLI target into queue descriptors."""
    if isinstance(target, WorkerApp):
        descriptors: List[QueueDescriptor] = []
        for entry in target.queues.values():
            bus = entry.bus
            kind = "command" if isinstance(bus, CommandBus) else "event"
            adapter = bus.queue_adapter
            descriptors.append(
                QueueDescriptor(
                    label=entry.name,
                    bus_kind=kind,
                    adapter_type=type(adapter).__name__,
                    adapter_queue_name=getattr(adapter, "queue_name", entry.name),
                    adapter=adapter,
                )
            )
        return descriptors

    if isinstance(target, (BusGroup, CommandBusGroup)):
        target.validate(module)
        descriptors = []
        for cfg in target.configs:
            bus = cfg.bus
            label = resolve_bus_attr_on_module(module, bus)
            kind = "command" if isinstance(bus, CommandBus) else "event"
            adapter = bus.queue_adapter
            descriptors.append(
                QueueDescriptor(
                    label=label,
                    bus_kind=kind,
                    adapter_type=type(adapter).__name__,
                    adapter_queue_name=getattr(adapter, "queue_name", label),
                    adapter=adapter,
                )
            )
        return descriptors

    kind = "command" if isinstance(target, CommandBus) else "event"
    adapter = target.queue_adapter
    return [
        QueueDescriptor(
            label=attr_name,
            bus_kind=kind,
            adapter_type=type(adapter).__name__,
            adapter_queue_name=getattr(adapter, "queue_name", attr_name),
            adapter=adapter,
        )
    ]


def select_queues(
    descriptors: Sequence[QueueDescriptor],
    queue_name: Optional[str],
) -> List[QueueDescriptor]:
    if queue_name is None:
        return list(descriptors)
    matches = [d for d in descriptors if d.label == queue_name]
    if not matches:
        labels = sorted(d.label for d in descriptors)
        raise QueueAdminError(
            f"No queue named {queue_name!r} (available: {labels})"
        )
    return matches


def get_message_count(adapter: QueueAdapter) -> Optional[int]:
    """
    Return pending message count when available.

    ``None`` means the adapter does not expose a count (typical for live pub/sub).
    """
    if isinstance(adapter, InMemoryQueueAdapter):
        return adapter.pending_message_count()
    if isinstance(adapter, InMemoryPubSubAdapter):
        return adapter.pending_message_count()
    if isinstance(adapter, RedisQueueAdapter):
        return int(adapter.pending_message_count())
    if isinstance(adapter, SqsQueueAdapter):
        attrs = adapter.sqs_queue.attributes
        visible = int(attrs.get("ApproximateNumberOfMessages", 0))
        not_visible = int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0))
        delayed = int(attrs.get("ApproximateNumberOfMessagesDelayed", 0))
        return visible + not_visible + delayed
    if isinstance(adapter, FileQueueAdapter):
        return adapter.pending_message_count()
    if isinstance(adapter, RabbitMqQueueAdapter):
        channel = adapter._ensure_connection()
        result = channel.queue_declare(queue=adapter.queue_name, passive=True)
        return int(result.method.message_count)
    return None


def drain_queue(adapter: QueueAdapter, *, batch_size: int = 10) -> int:
    """
    Remove messages without dispatching handlers.

    Uses ``get_messages`` + ``dequeue`` in a loop. Works for work-queue adapters.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    removed = 0
    while True:
        messages = adapter.get_messages(max_messages=batch_size)
        if not messages:
            break
        for message in messages:
            adapter.dequeue(message)
            removed += 1
    return removed


def purge_queue(adapter: QueueAdapter) -> int:
    """Clear the queue using a native purge when possible, otherwise drain."""
    if isinstance(adapter, InMemoryQueueAdapter):
        return adapter.purge_messages()
    if isinstance(adapter, InMemoryPubSubAdapter):
        return adapter.purge_messages()
    if isinstance(adapter, RedisQueueAdapter):
        return adapter.purge_messages()
    if isinstance(adapter, SqsQueueAdapter):
        count = get_message_count(adapter) or 0
        adapter.sqs_queue.purge()
        return count
    if isinstance(adapter, FileQueueAdapter):
        return adapter.purge_messages()
    if isinstance(adapter, RabbitMqQueueAdapter):
        channel = adapter._ensure_connection()
        result = channel.queue_purge(queue=adapter.queue_name)
        return int(result.method.message_count)
    count = get_message_count(adapter)
    if count is None:
        raise UnsupportedQueueOperation(
            f"{type(adapter).__name__} does not support purge; try drain instead"
        )
    return drain_queue(adapter)
