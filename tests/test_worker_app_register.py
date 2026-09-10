"""Tests for WorkerApp register/mount model."""

import asyncio

import pytest

from command_bus import CommandBus, EventBus, Router, WorkerApp
from command_bus.adapters import InMemoryPubSubAdapter, InMemoryQueueAdapter
from command_bus.adapters.queue.in_memory_pubsub import _reset_in_memory_pubsub_broker


@pytest.fixture(autouse=True)
def _clean_pubsub_broker():
    _reset_in_memory_pubsub_broker()
    yield
    _reset_in_memory_pubsub_broker()


@pytest.mark.asyncio
async def test_register_command_and_event_buses():
    orders_router = Router()
    events_router = Router()

    @orders_router.command()
    def process_order(order_id: str) -> str:
        return f"processed:{order_id}"

    @events_router.event()
    def on_order_created(order_id: str) -> None:
        pass

    orders = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="orders"),
        command_router=orders_router,
    )
    events = EventBus(
        queue_adapter=InMemoryPubSubAdapter(queue_name="events"),
        command_router=events_router,
    )

    app = WorkerApp(create_default_bus=False)
    app.register(orders, name="orders", workers=2, concurrency=2)
    app.register(events, name="events", workers=1, concurrency=3)

    assert set(app.queues) == {"orders", "events"}
    assert app.get("orders").bus is orders
    assert app.get("events").bus is events

    await orders.execute(process_order(order_id="1"), wait=False)
    assert await app.work(queue_name="orders") == 1

    await events.publish(on_order_created(order_id="evt-1"))
    assert await app.work(queue_name="events") == 1


@pytest.mark.asyncio
async def test_register_shares_middleware():
    order: list[str] = []
    app = WorkerApp(create_default_bus=False)

    orders = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="orders"),
        command_router=Router(),
    )
    app.register(orders, name="orders")

    @app.middleware
    async def trace(ctx, call_next):
        order.append("mw")
        await call_next(ctx)

    @orders.registry.command()
    def handle(tag: str) -> None:
        order.append("handler")

    await orders.execute(handle(tag="a"), wait=False)
    await app.work(queue_name="orders")
    assert order == ["mw", "handler"]


def test_iter_jobs_all_queues():
    app = WorkerApp(create_default_bus=False)
    orders = CommandBus(queue_adapter=InMemoryQueueAdapter(queue_name="orders"))
    events = EventBus(queue_adapter=InMemoryPubSubAdapter(queue_name="events"))
    app.register(orders, name="orders", workers=2)
    app.register(events, name="events", workers=1)

    assert app.iter_jobs(default_workers=1) == [
        ("orders", 1),
        ("orders", 2),
        ("events", 1),
    ]


def test_iter_jobs_single_queue():
    app = WorkerApp(create_default_bus=False)
    orders = CommandBus(queue_adapter=InMemoryQueueAdapter(queue_name="orders"))
    app.register(orders, name="orders", workers=4)

    assert app.iter_jobs(default_workers=1, queue_name="orders") == [
        ("orders", 1),
        ("orders", 2),
        ("orders", 3),
        ("orders", 4),
    ]


def test_iter_jobs_workers_override():
    app = WorkerApp(create_default_bus=False)
    orders = CommandBus(queue_adapter=InMemoryQueueAdapter(queue_name="orders"))
    app.register(orders, name="orders", workers=4)

    assert app.iter_jobs(
        default_workers=1,
        queue_name="orders",
        workers_override=2,
    ) == [("orders", 1), ("orders", 2)]


@pytest.mark.asyncio
async def test_run_polls_all_registered_queues():
    orders_router = Router()
    events_router = Router()
    seen_orders: list[str] = []
    seen_events: list[str] = []

    @orders_router.command()
    def process_order(order_id: str) -> None:
        seen_orders.append(order_id)

    @events_router.event()
    def on_created(order_id: str) -> None:
        seen_events.append(order_id)

    orders = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="orders-run"),
        command_router=orders_router,
    )
    events = EventBus(
        queue_adapter=InMemoryPubSubAdapter(queue_name="events-run"),
        command_router=events_router,
    )

    app = WorkerApp(create_default_bus=False)
    app.register(orders, name="orders")
    app.register(events, name="events")

    worker = asyncio.create_task(app.run(poll_interval=0.01))
    await asyncio.sleep(0.02)

    await orders.execute(process_order(order_id="o1"), wait=False)
    await events.publish(on_created(order_id="e1"))
    await asyncio.sleep(0.05)

    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker

    assert seen_orders == ["o1"]
    assert seen_events == ["e1"]
