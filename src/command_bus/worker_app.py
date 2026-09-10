"""FastAPI-style orchestration shell for command and event workers."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Type, TypeVar, Union

from .adapters.queue.in_memory import InMemoryQueueAdapter
from .bus import CommandBus
from .event_bus import EventBus
from .interfaces import CommandMessage, QueueAdapter, ResponseStore
from .lifecycle import LifecycleHandler, run_shutdown_handlers, run_startup_handlers
from .middleware import Middleware
from .registry import Router

logger = logging.getLogger(__name__)

_MiddlewareClass = TypeVar("_MiddlewareClass", bound=type)
BusInstance = Union[CommandBus, EventBus]


@dataclass(frozen=True)
class RegisteredBus:
    """A :class:`CommandBus` or :class:`EventBus` mounted on a :class:`WorkerApp`."""

    name: str
    bus: BusInstance
    workers: Optional[int] = None
    concurrency: Optional[int] = None


class WorkerApp:
    """
    Orchestration entry point for worker processes (like ``FastAPI()`` for HTTP).

    Mount existing :class:`CommandBus` / :class:`EventBus` instances with
    :meth:`register`, or use the constructor shortcut for a single default command
    queue (``@app.command()``, ``app.execute()``, ``app.work()``).

    Point the worker CLI at ``module:app`` — optionally ``--queue NAME`` for one
    registered bus only.
    """

    def __init__(
        self,
        *,
        queue_adapter: Optional[QueueAdapter] = None,
        queue_name: str = "default",
        concurrency: int = 1,
        response_store: Optional[ResponseStore] = None,
        response_ttl_seconds: int = 60,
        create_default_bus: bool = True,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self.concurrency = concurrency
        self._middleware: List[Middleware] = []
        self._startup_handlers: List[LifecycleHandler] = []
        self._shutdown_handlers: List[LifecycleHandler] = []
        self._started = False
        self._registered: Dict[str, RegisteredBus] = {}
        self._primary_name: Optional[str] = None

        if create_default_bus:
            adapter = queue_adapter or InMemoryQueueAdapter(queue_name=queue_name)
            router = Router()
            bus = CommandBus(
                queue_adapter=adapter,
                command_router=router,
                response_store=response_store,
                response_ttl_seconds=response_ttl_seconds,
                middleware=self._middleware,
                dispatch_context_app=self,
            )
            self.register(bus, name="default", primary=True)

    @property
    def queues(self) -> Mapping[str, RegisteredBus]:
        """Registered buses by name."""
        return self._registered

    @property
    def router(self) -> Router:
        """Router on the primary (default) command bus."""
        entry = self._primary_entry()
        if not isinstance(entry.bus, CommandBus):
            raise RuntimeError("Primary registered bus is not a CommandBus")
        return entry.bus.registry

    @property
    def bus(self) -> CommandBus:
        """Primary :class:`CommandBus` (default queue shortcut)."""
        entry = self._primary_entry()
        if not isinstance(entry.bus, CommandBus):
            raise RuntimeError("Primary registered bus is not a CommandBus")
        return entry.bus

    @property
    def queue_adapter(self) -> QueueAdapter:
        """Queue adapter on the primary bus."""
        return self._primary_entry().bus.queue_adapter

    def get(self, name: str) -> RegisteredBus:
        """Return a registered bus entry by name."""
        try:
            return self._registered[name]
        except KeyError as e:
            raise KeyError(f"No registered bus named {name!r}") from e

    def register(
        self,
        bus: BusInstance,
        *,
        name: Optional[str] = None,
        workers: Optional[int] = None,
        concurrency: Optional[int] = None,
        primary: bool = False,
    ) -> RegisteredBus:
        """
        Mount a :class:`CommandBus` or :class:`EventBus` for CLI/work orchestration.

        ``name`` defaults to ``bus.queue_adapter.queue_name`` when available.
        """
        if not isinstance(bus, (CommandBus, EventBus)):
            raise TypeError(
                f"register() expects CommandBus or EventBus (got {type(bus).__name__})"
            )
        if name is None:
            name = getattr(bus.queue_adapter, "queue_name", None) or f"bus-{len(self._registered)}"
        if name in self._registered:
            raise ValueError(f"Bus name {name!r} is already registered")
        if workers is not None and workers < 1:
            raise ValueError("workers must be >= 1")
        if concurrency is not None and concurrency < 1:
            raise ValueError("concurrency must be >= 1")

        bus.dispatch_context_app = self
        bus._middleware = self._middleware

        entry = RegisteredBus(
            name=name,
            bus=bus,
            workers=workers,
            concurrency=concurrency,
        )
        self._registered[name] = entry
        if primary or self._primary_name is None:
            self._primary_name = name
        return entry

    def iter_jobs(
        self,
        default_workers: int,
        *,
        queue_name: Optional[str] = None,
        workers_override: Optional[int] = None,
    ) -> List[Tuple[str, int]]:
        """
        Return ``(queue_name, worker_index)`` for each worker process to spawn.

        When ``queue_name`` is set, only that registered bus is included.
        """
        if default_workers < 1:
            raise ValueError("default_workers must be >= 1")
        if not self._registered:
            raise ValueError("WorkerApp has no registered buses")

        if queue_name is not None:
            if queue_name not in self._registered:
                raise ValueError(
                    f"Unknown queue {queue_name!r}; registered: {sorted(self._registered)}"
                )
            entries = [self._registered[queue_name]]
        else:
            entries = list(self._registered.values())

        jobs: List[Tuple[str, int]] = []
        for entry in entries:
            if workers_override is not None:
                n = workers_override
            else:
                n = entry.workers if entry.workers is not None else default_workers
            if n < 1:
                raise ValueError(f"workers must be >= 1 for queue {entry.name!r}, got {n}")
            for w in range(1, n + 1):
                jobs.append((entry.name, w))
        return jobs

    def concurrency_for_queue(
        self,
        queue_name: str,
        cli_concurrency: Optional[int],
    ) -> int:
        """Resolve in-process concurrency for a registered queue."""
        if cli_concurrency is not None:
            return cli_concurrency
        entry = self.get(queue_name)
        if entry.concurrency is not None:
            return entry.concurrency
        return self.concurrency

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
        """Decorator: register a command handler on the primary bus router."""
        return self.router.command()

    def event(self) -> Callable[..., Any]:
        """Decorator: register an event handler on the primary bus router."""
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
        """Enqueue a command on the primary command bus."""
        return await self.bus.execute(
            message_instance,
            delay_seconds=delay_seconds,
            wait=wait,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            response_ttl_seconds=response_ttl_seconds,
        )

    async def work(
        self,
        *,
        concurrency: Optional[int] = None,
        queue_name: Optional[str] = None,
    ) -> int:
        """
        Poll registered queue(s) once.

        With ``queue_name``, only that bus is polled. Otherwise all registered buses
        are polled sequentially. For the default single-bus app, this matches the
        previous ``WorkerApp.work()`` behavior when one queue is registered.
        """
        if queue_name is not None:
            entry = self.get(queue_name)
            n = concurrency if concurrency is not None else self.concurrency_for_queue(
                queue_name, None
            )
            return await entry.bus.work(concurrency=n)

        total = 0
        for entry in self._registered.values():
            n = concurrency if concurrency is not None else self.concurrency_for_queue(
                entry.name, None
            )
            total += await entry.bus.work(concurrency=n)
        return total

    async def run(self, *, poll_interval: float = 0.05) -> None:
        """Dev-friendly infinite worker loop for all registered buses."""
        await self.startup()
        try:
            if len(self._registered) <= 1:
                entry = next(iter(self._registered.values()), None)
                if entry is None:
                    raise RuntimeError("WorkerApp has no registered buses")
                await self._poll_loop(entry, poll_interval)
            else:
                await asyncio.gather(
                    *[
                        self._poll_loop(entry, poll_interval)
                        for entry in self._registered.values()
                    ]
                )
        finally:
            await self.shutdown()

    async def _poll_loop(self, entry: RegisteredBus, poll_interval: float) -> None:
        concurrency = self.concurrency_for_queue(entry.name, None)
        while True:
            try:
                handled = await entry.bus.work(concurrency=concurrency)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("WorkerApp poll loop failed for queue %r", entry.name)
                handled = 0
            if handled == 0:
                if poll_interval > 0:
                    deadline = time.monotonic() + poll_interval
                    while time.monotonic() < deadline:
                        await asyncio.sleep(
                            min(0.05, max(0.0, deadline - time.monotonic()))
                        )
                else:
                    await asyncio.sleep(0)

    def _primary_entry(self) -> RegisteredBus:
        if self._primary_name is None:
            raise RuntimeError("WorkerApp has no registered buses")
        return self._registered[self._primary_name]
