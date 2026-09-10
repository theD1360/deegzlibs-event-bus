"""Lifecycle handler runner for WorkerApp startup and shutdown."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, List, Union

LifecycleHandler = Union[
    Callable[[], Any],
    Callable[[], Awaitable[Any]],
]


async def run_lifecycle_handlers(handlers: List[LifecycleHandler]) -> None:
    """Run lifecycle handlers in order (async and sync supported)."""
    for handler in handlers:
        result = handler()
        if inspect.isawaitable(result):
            await result


async def run_startup_handlers(handlers: List[LifecycleHandler]) -> None:
    await run_lifecycle_handlers(handlers)


async def run_shutdown_handlers(handlers: List[LifecycleHandler]) -> None:
    await run_lifecycle_handlers(list(reversed(handlers)))
