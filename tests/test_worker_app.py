"""Tests for WorkerApp."""

import asyncio

import pytest

from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter, InMemoryResponseStore


@pytest.mark.asyncio
async def test_worker_app_command_decorator_registers_handler():
    app = WorkerApp()

    @app.command()
    async def handle(tag: str) -> str:
        return f"ok:{tag}"

    await app.execute(handle(tag="a"), wait=False)
    assert await app.work() == 1


@pytest.mark.asyncio
async def test_worker_app_execute_and_work():
    app = WorkerApp(response_store=InMemoryResponseStore())

    @app.command()
    def double(n: int) -> int:
        return n * 2

    await app.execute(double(n=5), wait=False)
    assert await app.work() == 1

    worker = asyncio.create_task(app.run(poll_interval=0.01))
    await asyncio.sleep(0.02)
    result = await app.execute(double(n=3), wait=True)
    assert result == 6
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker


@pytest.mark.asyncio
async def test_worker_app_concurrent_work():
    adapter = InMemoryQueueAdapter(queue_name="concurrent")
    app = WorkerApp(queue_adapter=adapter, concurrency=3)
    seen: list[int] = []

    @app.command()
    async def record(value: int) -> None:
        seen.append(value)

    for i in range(5):
        await app.execute(record(value=i), wait=False)

    assert await app.work() == 3
    assert await app.work() == 2
    assert sorted(seen) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_worker_app_run_processes_until_idle():
    app = WorkerApp(response_store=InMemoryResponseStore())

    @app.command()
    def increment(n: int) -> int:
        return n + 1

    worker = asyncio.create_task(app.run(poll_interval=0.01))
    await asyncio.sleep(0.02)
    result = await app.execute(increment(n=41), wait=True)
    assert result == 42
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker


@pytest.mark.asyncio
async def test_worker_app_bus_property():
    app = WorkerApp()
    assert app.bus is app._bus
    assert app.bus.registry is app.router


def test_worker_app_invalid_concurrency():
    with pytest.raises(ValueError, match="concurrency must be >= 1"):
        WorkerApp(concurrency=0)


@pytest.mark.asyncio
async def test_worker_app_lifecycle_startup_shutdown():
    events: list[str] = []
    app = WorkerApp()

    @app.on_startup
    async def start():
        events.append("startup")

    @app.on_shutdown
    def stop():
        events.append("shutdown")

    await app.startup()
    await app.shutdown()
    assert events == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_worker_app_run_calls_lifecycle():
    events: list[str] = []
    app = WorkerApp()

    @app.on_startup
    def start():
        events.append("startup")

    @app.on_shutdown
    def stop():
        events.append("shutdown")

    worker = asyncio.create_task(app.run(poll_interval=0.01))
    await asyncio.sleep(0.02)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert events == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_worker_app_middleware():
    order: list[str] = []
    app = WorkerApp()

    @app.middleware
    async def log_mw(ctx, call_next):
        order.append("mw")
        await call_next(ctx)

    @app.command()
    def handle(tag: str) -> None:
        order.append("handler")

    await app.execute(handle(tag="a"), wait=False)
    await app.work()
    assert order == ["mw", "handler"]


@pytest.mark.asyncio
async def test_worker_app_dispatch_context_has_app():
    seen_app = []

    app = WorkerApp()

    @app.middleware
    async def capture_app(ctx, call_next):
        seen_app.append(ctx.app)
        await call_next(ctx)

    @app.command()
    def handle(tag: str) -> None:
        pass

    await app.execute(handle(tag="a"), wait=False)
    await app.work()
    assert seen_app == [app]
