#!/usr/bin/env python3
"""
WorkerApp multi-queue demo: mount CommandBus + EventBus on one app.

Run from the repo root:

    PYTHONPATH=src python examples/worker_app_multi_queue_demo.py

CLI (all queues):

    PYTHONPATH=src command-bus-worker examples.worker_app_multi_queue_demo:app

CLI (one queue only):

    PYTHONPATH=src command-bus-worker examples.worker_app_multi_queue_demo:app --queue orders
    PYTHONPATH=src command-bus-worker examples.worker_app_multi_queue_demo:app --queue events
"""

from __future__ import annotations

import asyncio

from command_bus import CommandBus, EventBus, Router, WorkerApp
from command_bus.adapters import InMemoryPubSubAdapter, InMemoryQueueAdapter
from command_bus.adapters.queue.in_memory_pubsub import _reset_in_memory_pubsub_broker

_reset_in_memory_pubsub_broker()

orders_router = Router()
events_router = Router()


@orders_router.command()
def process_order(order_id: str) -> str:
    print(f"  [orders] processed {order_id}")
    return f"ok:{order_id}"


@events_router.event()
def on_order_created(order_id: str) -> None:
    print(f"  [events] saw order_created {order_id}")


orders = CommandBus(
    queue_adapter=InMemoryQueueAdapter(queue_name="demo-orders"),
    command_router=orders_router,
)
events = EventBus(
    queue_adapter=InMemoryPubSubAdapter(queue_name="demo-events"),
    command_router=events_router,
)

app = WorkerApp(create_default_bus=False)
app.register(orders, name="orders", workers=1, concurrency=2)
app.register(events, name="events", workers=1, concurrency=2)


async def main() -> None:
    worker = asyncio.create_task(app.run(poll_interval=0.01))
    await asyncio.sleep(0.02)

    await orders.execute(process_order(order_id="ord-1"), wait=False)
    await events.publish(on_order_created(order_id="ord-1"))
    await asyncio.sleep(0.05)

    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
