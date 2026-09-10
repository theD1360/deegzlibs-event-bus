"""FastAPI-style facade for command-bus workers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, List, Optional, Type, TypeVar

from .adapters.queue.in_memory import InMemoryQueueAdapter
from .bus import CommandBus
from .interfaces import CommandMessage, QueueAdapter, ResponseStore
from .lifecycle import LifecycleHandler, run_shutdown_handlers, run_startup_handlers
from .middleware import Middleware
from .registry import Router

logger = logging.getLogger(__name__)

_MiddlewareClass = TypeVar("_MiddlewareClass", bound=type)


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
        self._middleware: List[Middleware] = []
        self._startup_handlers: List[LifecycleHandler] = []
        self._shutdown_handlers: List[LifecycleHandler] = []
        self._started = False
        adapter = queue_adapter or InMemoryQueueAdapter(queue_name=queue_name)
        self._bus = CommandBus(
            queue_adapter=adapter,
            command_router=self.router,
            response_store=response_store,
            response_ttl_seconds=response_ttl_seconds,
            middleware=self._middleware,
            dispatch_context_app=self,
        )

    @property
    def bus(self) -> CommandBus:
        """Underlying :class:`CommandBus` for advanced configuration."""
        return self._bus

    @property
    def queue_adapter(self) -> QueueAdapter:
        return self._bus.queue_adapter

    def middleware(self, mw: Middleware) -> Middleware:
        """Register dispatch middleware (first registered = outermost)."""
        self._middleware.append(mw)
        return mw

    def add_middleware(self, middleware_class: _MiddlewareClass, **kwargs: Any) -> None:
        """Instantiate and register a class-based middleware."""
        self._middleware.append(middleware_class(**kwargs))

    def on_startup(self, func: LifecycleHandler) -> LifecycleHandler:
        """Decorator: run before the worker loop starts."""
        self._startup_handlers.append(func)
        return func

    def on_shutdown(self, func: LifecycleHandler) -> LifecycleHandler:
        """Decorator: run after the worker loop stops (reverse order)."""
        self._shutdown_handlers.append(func)
        return func

    async def startup(self) -> None:
        """Run all startup handlers in registration order."""
        await run_startup_handlers(self._startup_handlers)
        self._started = True

    async def shutdown(self) -> None:
        """Run all shutdown handlers in reverse registration order."""
        if not self._started:
            return
        await run_shutdown_handlers(self._shutdown_handlers)
        self._started = False

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
        await self.startup()
        try:
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
        finally:
            await self.shutdown()
