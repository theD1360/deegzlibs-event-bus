"""Tests for SQS adapter (mocked)."""

from unittest.mock import MagicMock

import pytest
from event_bus import EventBus, EventBusRegistry, EventMessage
from event_bus.adapters import SqsEventBusAdapter
from event_bus.parsers import JsonMessageParser, ReprMessageParser


class DummyMessage(EventMessage):
    id: str


def test_sqs_adapter_enqueue_dequeue():
    """Enqueue and dequeue call through to the mock SQS queue."""
    queue = MagicMock()
    queue.receive_messages.return_value = []
    client = MagicMock()
    client.get_queue_by_name.return_value = queue
    adapter = SqsEventBusAdapter(queue_name="test", sqs_client=client)

    msg = DummyMessage(id="x")
    adapter.enqueue(msg, delay_seconds=0)
    queue.send_message.assert_called_once()
    call = queue.send_message.call_args
    assert "x" in str(call.kwargs["MessageBody"]) or "id" in str(
        call.kwargs["MessageBody"]
    )
    assert call.kwargs["DelaySeconds"] == 0

    message_handle = MagicMock()
    adapter.dequeue(message_handle)
    message_handle.delete.assert_called_once()


@pytest.mark.asyncio
async def test_sqs_event_bus_execute_raises_when_no_handler():
    adapter = MagicMock(spec=SqsEventBusAdapter)
    registry = EventBusRegistry()
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    msg = DummyMessage(id="y")

    with pytest.raises(ValueError, match="No handler found"):
        await bus.execute(msg, wait=False)


@pytest.mark.asyncio
async def test_sqs_event_bus_execute_enqueues_when_handler_registered():
    adapter = MagicMock(spec=SqsEventBusAdapter)
    registry = EventBusRegistry()

    class DummyHandler:
        def process(self, message):
            pass

    registry.register(DummyMessage, DummyHandler)
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    msg = DummyMessage(id="z")

    await bus.execute(msg, delay_seconds=5, wait=False)
    adapter.enqueue.assert_called_once_with(msg, delay_seconds=5)


def test_event_bus_default_registry():
    """EventBus uses a new EventBusRegistry when event_registry is omitted."""
    queue = MagicMock()
    client = MagicMock()
    client.get_queue_by_name.return_value = queue
    adapter = SqsEventBusAdapter(queue_name="q", sqs_client=client)
    bus = EventBus(queue_adapter=adapter)
    assert bus.registry is not None
    assert isinstance(bus.registry, EventBusRegistry)
    assert bus.registry.get_handlers_for_message(DummyMessage(id="x")) == []


def test_sqs_event_bus_message_parser_class():
    """Bus accepts message_parser_class and uses it for dispatch; default is ReprMessageParser."""
    queue = MagicMock()
    client = MagicMock()
    client.get_queue_by_name.return_value = queue
    adapter = SqsEventBusAdapter(queue_name="q", sqs_client=client)
    registry = EventBusRegistry()
    bus = EventBus(
        queue_adapter=adapter,
        event_registry=registry,
        message_parser_class=JsonMessageParser,
    )
    assert bus.message_parser_class is JsonMessageParser

    bus_default = EventBus(queue_adapter=adapter, event_registry=registry)
    assert bus_default.message_parser_class is ReprMessageParser
