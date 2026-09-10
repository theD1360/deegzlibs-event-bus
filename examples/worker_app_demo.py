#!/usr/bin/env python3
"""
WorkerApp demo with InMemoryQueueAdapter (single process).

Producer and consumer share one in-memory queue in the same process.
InMemoryQueueAdapter is process-local — use SQS/Redis/RabbitMQ for
multi-process ``command-bus-worker --workers N``.

Run from the repo root:

    PYTHONPATH=src python examples/worker_app_demo.py
"""

from __future__ import annotations

import asyncio

from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter, InMemoryResponseStore

adapter = InMemoryQueueAdapter(queue_name="demo")
app = WorkerApp(
    queue_adapter=adapter,
    concurrency=3,
    response_store=InMemoryResponseStore(),
)


@app.command()
async def add(a: int, b: int) -> int:
    return a + b


@app.command()
def greet(name: str) -> str:
    return f"Hello, {name}!"


async def main() -> None:
    worker = asyncio.create_task(app.run(poll_interval=0.01))

    total = await app.execute(add(a=10, b=32), wait=True)
    msg = await app.execute(greet(name="WorkerApp"), wait=True)
    print(f"add -> {total}")
    print(f"greet -> {msg!r}")

    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
