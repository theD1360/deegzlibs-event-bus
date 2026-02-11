"""Tests for response store and execute_and_wait."""

import asyncio
from unittest.mock import MagicMock

import pytest
from event_bus import EventBus, EventBusRegistry, EventMessage, EventMessageHandler
from event_bus.adapters import InMemoryResponseStore, SqsEventBusAdapter


class GetPrice(EventMessage):
    product_id: str


class PriceHandler(EventMessageHandler):
    def process(self, message: EventMessage):
        return {"price_cents": 999, "product_id": message.product_id}


def test_event_message_has_correlation_id():
    m = GetPrice(product_id="x")
    assert m.correlation_id is None
    m2 = GetPrice(product_id="y", correlation_id="abc")
    assert m2.correlation_id == "abc"


def test_execute_and_wait_raises_without_response_store():
    adapter = MagicMock(spec=SqsEventBusAdapter)
    bus = EventBus(queue_adapter=adapter, event_registry=EventBusRegistry())
    bus.registry.register(GetPrice, PriceHandler)

    with pytest.raises(ValueError, match="response_store"):
        asyncio.run(bus.execute(GetPrice(product_id="x"), wait=True))


@pytest.mark.asyncio
async def test_execute_and_wait_returns_result_when_stored():
    adapter = MagicMock()
    store = InMemoryResponseStore()
    registry = EventBusRegistry()
    registry.register(GetPrice, PriceHandler)
    bus = EventBus(queue_adapter=adapter, event_registry=registry, response_store=store)

    # Run execute_and_wait in a task; after a short delay simulate worker storing the result
    # (using the correlation_id from the enqueued message)
    async def run_client():
        return await bus.execute_and_wait(
            GetPrice(product_id="p1"),
            timeout_seconds=2,
            poll_interval_seconds=0.05,
        )

    async def simulate_worker():
        await asyncio.sleep(0.15)
        enqueued = adapter.enqueue.call_args[0][0]
        store.set(enqueued.correlation_id, {"price_cents": 123}, ttl_seconds=60)

    client_task = asyncio.create_task(run_client())
    await simulate_worker()
    result = await client_task
    assert result == {"price_cents": 123}


@pytest.mark.asyncio
async def test_execute_and_wait_times_out_when_not_stored():
    adapter = MagicMock()
    store = InMemoryResponseStore()
    registry = EventBusRegistry()
    registry.register(GetPrice, PriceHandler)
    bus = EventBus(queue_adapter=adapter, event_registry=registry, response_store=store)

    with pytest.raises(TimeoutError, match="No response"):
        await bus.execute_and_wait(
            GetPrice(product_id="p1"),
            timeout_seconds=0.2,
            poll_interval_seconds=0.05,
        )


@pytest.mark.asyncio
async def test_dispatch_stores_handler_result_when_correlation_id_and_response_store_set():
    """When event has correlation_id and bus has response_store, dispatch stores last handler return."""
    store = InMemoryResponseStore()
    registry = EventBusRegistry()
    registry.register(GetPrice, PriceHandler)
    # Use real parser and adapter that we don't need to call (we only call dispatch with a string)
    from event_bus.parsers import ReprMessageParser

    adapter = MagicMock()
    bus = EventBus(
        queue_adapter=adapter,
        event_registry=registry,
        response_store=store,
        message_parser_class=ReprMessageParser,
    )
    msg_str = (
        "tests.test_response_store.GetPrice(product_id='p99', correlation_id='resp-1')"
    )
    await bus.dispatch(msg_str)
    assert store.get("resp-1") == {"price_cents": 999, "product_id": "p99"}


def test_redis_response_store_mock():
    """RedisResponseStore set/get/delete with mocked redis client."""
    from event_bus.adapters.response.redis import RedisResponseStore

    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    store = RedisResponseStore(redis_mock, key_prefix="test:", default_ttl_seconds=30)
    store.set("k1", {"a": 1}, ttl_seconds=60)
    redis_mock.set.assert_called_once()
    call = redis_mock.set.call_args
    assert call[0][0] == "test:k1"
    assert "1" in call[0][1] and "a" in call[0][1]
    assert call[1]["ex"] == 60

    redis_mock.get.return_value = b'{"b": 2}'
    assert store.get("k2") == {"b": 2}
    redis_mock.get.assert_called_with("test:k2")

    store.delete("k3")
    redis_mock.delete.assert_called_with("test:k3")
