"""FastAPI-style facade for command-bus workers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Optional

from .adapters.queue.in_memory import InMemoryQueueAdapter
from .bus import CommandBus
from .interfaces import CommandMessage, QueueAdapter, ResponseStore
from .registry import Router

logger = logging.getLogger(__name__)


class WorkerApp:
    """
    Single entry point for a command worker (like ``FastAPI()`` for HTTP).

    Owns a :class:`Router`, :class:`CommandBus`, and queue adapter. Use
    ``@app.command()`` to register handlers and ``command-bus-worker module:app``
    as the CLI target.
    """

    def __init__(
        self,
        *,
        queue_adapter: Optional[QueueAdapter] = None,
        queue_name: str = "default",
        concurrency: int = 1,
        response_store: Optional[ResponseStore] = None,
        response_ttl_seconds: int = 60,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.concurrency = concurrency
        self.router = Router()
        adapter = queue_adapter or InMemoryQueueAdapter(queue_name=queue_name)
        self._bus = CommandBus(
            queue_adapter=adapter,
            command_router=self.router,
            response_store=response_store,
            response_ttl_seconds=response_ttl_seconds,
        )

    @property
    def bus(self) -> CommandBus:
        """Underlying :class:`CommandBus` for advanced configuration."""
        return self._bus

    @property
    def queue_adapter(self) -> QueueAdapter:
        return self._bus.queue_adapter

    def command(self) -> Callable[..., Any]:
        """Decorator: register a command handler (delegates to the internal router)."""
        return self.router.command()

    def event(self) -> Callable[..., Any]:
        """Decorator: register an event handler (delegates to the internal router)."""
        return self.router.event()

    async def execute(
        self,
        message_instance: CommandMessage,
        delay_seconds: Optional[int] = None,
        wait: Optional[bool] = None,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        response_ttl_seconds: Optional[int] = None,
    ) -> Any:
        """Enqueue a command (delegates to the internal bus)."""
        return await self._bus.execute(
            message_instance,
            delay_seconds=delay_seconds,
            wait=wait,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            response_ttl_seconds=response_ttl_seconds,
        )

    async def work(self, *, concurrency: Optional[int] = None) -> int:
        """Poll the queue once and dispatch up to ``concurrency`` messages in parallel."""
        n = self.concurrency if concurrency is None else concurrency
        return await self._bus.work(concurrency=n)

    async def run(self, *, poll_interval: float = 0.05) -> None:
        """Dev-friendly infinite worker loop (like a hand-written ``while True: await work()``)."""
        while True:
            try:
                handled = await self.work()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("WorkerApp.work() failed")
                handled = 0
            if handled == 0:
                if poll_interval > 0:
                    deadline = time.monotonic() + poll_interval
                    while time.monotonic() < deadline:
                        await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
                else:
                    await asyncio.sleep(0)
