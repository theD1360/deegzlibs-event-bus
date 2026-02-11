"""Tests for registry.event() + bus.execute() with the constructed EventMessage class."""

import asyncio
from unittest.mock import MagicMock

import pytest
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import (
    InMemoryEventBusAdapter,
    InMemoryResponseStore,
    SqsEventBusAdapter,
)


@pytest.mark.asyncio
async def test_registry_event_call_returns_message_for_bus_execute():
    """Calling the decorated function returns the message; pass it to bus.execute()."""
    adapter = MagicMock(spec=SqsEventBusAdapter)
    registry = EventBusRegistry()
    bus = EventBus(queue_adapter=adapter, event_registry=registry)

    @registry.event()
    def on_created(order_id: str, amount_cents: int):
        return {"order_id": order_id}

    await bus.execute(on_created(order_id="ord-1", amount_cents=2000), wait=False)
    assert adapter.enqueue.called
    (msg,) = adapter.enqueue.call_args[0]
    assert msg.order_id == "ord-1"
    assert msg.amount_cents == 2000


@pytest.mark.asyncio
async def test_registry_event_message_class_works_with_execute_and_wait():
    """get_price(...) returns the message; pass to execute(wait=True)."""
    adapter = MagicMock()
    store = InMemoryResponseStore()
    registry = EventBusRegistry()
    bus = EventBus(
        queue_adapter=adapter,
        event_registry=registry,
        response_store=store,
    )

    @registry.event()
    def get_price(product_id: str) -> dict:
        return {"price_cents": 99, "product_id": product_id}

    async def run_client():
        return await bus.execute(
            get_price(product_id="p1"), timeout_seconds=2, poll_interval_seconds=0.05
        )

    async def simulate_worker():
        await asyncio.sleep(0.1)
        enqueued = adapter.enqueue.call_args[0][0]
        store.set(
            enqueued.correlation_id,
            {"price_cents": 99, "product_id": "p1"},
            ttl_seconds=60,
        )

    client_task = asyncio.create_task(run_client())
    await simulate_worker()
    result = await client_task
    assert result == {"price_cents": 99, "product_id": "p1"}


@pytest.mark.asyncio
async def test_registry_event_then_bus_execute_and_work():
    """Full flow: bus.execute(on_created(...), wait=False) and bus.work()."""
    adapter = InMemoryEventBusAdapter(queue_name="events")
    registry = EventBusRegistry()
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    received: list[str] = []

    @registry.event()
    def on_created(order_id: str, amount_cents: int):
        received.append(order_id)

    await bus.execute(on_created(order_id="a", amount_cents=1), wait=False)
    await bus.execute(on_created(order_id="b", amount_cents=2), wait=False)
    await bus.work()
    await bus.work()
    assert received == ["a", "b"]
