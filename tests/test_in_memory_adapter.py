"""Tests for in-memory queue adapter."""

import pytest
from event_bus import EventBus, EventBusRegistry, EventMessage, EventMessageHandler
from event_bus.adapters import InMemoryEventBusAdapter
from event_bus.adapters.queue.in_memory import _InMemoryMessage


class DummyMessage(EventMessage):
    id: str


def test_in_memory_message_wrapper():
    m = _InMemoryMessage(body="hello")
    assert m.body == "hello"
    m.delete()  # no-op, no error


def test_in_memory_adapter_enqueue_and_get_messages():
    adapter = InMemoryEventBusAdapter(queue_name="q")
    msg = DummyMessage(id="x")
    adapter.enqueue(msg, delay_seconds=0)
    adapter.enqueue(DummyMessage(id="y"))
    messages = adapter.get_messages(max_messages=2)
    assert len(messages) == 2
    assert (
        "id='x'" in messages[0].body
        or '"id":"x"' in messages[0].body
        or "x" in messages[0].body
    )
    assert "id='y'" in messages[1].body or "y" in messages[1].body
    # Queue is now empty
    assert adapter.get_messages(max_messages=1) == []


def test_in_memory_adapter_fifo():
    adapter = InMemoryEventBusAdapter()
    adapter.enqueue(DummyMessage(id="1"))
    adapter.enqueue(DummyMessage(id="2"))
    one = adapter.get_messages(max_messages=1)[0]
    two = adapter.get_messages(max_messages=1)[0]
    assert "1" in one.body
    assert "2" in two.body


@pytest.mark.asyncio
async def test_in_memory_event_bus_execute_and_work():
    adapter = InMemoryEventBusAdapter(queue_name="events")
    registry = EventBusRegistry()
    received: list[str] = []

    class Handler(EventMessageHandler):
        def process(self, message: EventMessage):
            received.append(message.id)

    registry.register(DummyMessage, Handler)
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    await bus.execute(DummyMessage(id="a"), wait=False)
    await bus.execute(DummyMessage(id="b"), wait=False)
    await bus.work()  # processes one message (default max_messages=1)
    await bus.work()  # processes the second
    assert received == ["a", "b"]
