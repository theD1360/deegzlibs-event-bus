#!/usr/bin/env python3
"""
WorkerApp demo: lifecycle hooks and dispatch middleware.

Shows @app.on_startup / @app.on_shutdown and @app.middleware wrapping
each message dispatch. Single-process in-memory queue.

Run from the repo root:

    PYTHONPATH=src python examples/worker_app_lifecycle_middleware_demo.py

For production, the worker module exposes ``app`` only; the CLI runs
``command-bus-worker myapp.worker:app`` and does not call ``main()``.
"""

from __future__ import annotations

import asyncio
import logging
import time

from command_bus import DispatchContext, WorkerApp
from command_bus.adapters import InMemoryQueueAdapter, InMemoryResponseStore

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("demo")

# Simulated resource opened in startup, closed in shutdown.
_cache: dict[str, str] = {}

queue = InMemoryQueueAdapter(queue_name="lifecycle-demo")
app = WorkerApp(
    queue_adapter=queue,
    response_store=InMemoryResponseStore(),
)


@app.on_startup
def warm_cache():
    _cache["status"] = "ready"
    log.info("startup: cache warmed (%s)", _cache["status"])


@app.on_shutdown
def clear_cache():
    _cache.clear()
    log.info("shutdown: cache cleared")


@app.middleware
async def log_and_time(ctx: DispatchContext, call_next):
    started = time.monotonic()
    log.info("middleware: dispatching %r", ctx.raw_message[:60])
    await call_next(ctx)
    elapsed_ms = (time.monotonic() - started) * 1000
    log.info(
        "middleware: done %r (%.1f ms, cache=%s)",
        ctx.parsed_message,
        elapsed_ms,
        _cache.get("status", "missing"),
    )


@app.command()
def greet(name: str) -> str:
    return f"Hello, {name}! (cache={_cache.get('status')})"


async def main() -> None:
    # app.run() calls startup → poll loop → shutdown on exit
    worker = asyncio.create_task(app.run(poll_interval=0.01))

    reply = await app.execute(greet(name="WorkerApp"), wait=True)
    print(f"reply -> {reply!r}")

    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
