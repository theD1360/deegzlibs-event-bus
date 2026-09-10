"""Dispatch middleware stack for CommandBus and EventBus."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, MutableSequence, Protocol, Union

CallNext = Callable[["DispatchContext"], Awaitable[None]]


@dataclass
class DispatchContext:
    """Per-message context passed through the middleware stack."""

    raw_message: str
    parsed_message: Any | None = None
    app: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)


class MiddlewareProtocol(Protocol):
    async def __call__(self, ctx: DispatchContext, call_next: CallNext) -> None: ...


Middleware = Union[
    MiddlewareProtocol,
    Callable[[DispatchContext, CallNext], Awaitable[None]],
]


async def _invoke_middleware(mw: Middleware, ctx: DispatchContext, call_next: CallNext) -> None:
    result = mw(ctx, call_next)
    if inspect.isawaitable(result):
        await result


async def run_middleware_stack(
    ctx: DispatchContext,
    call_next: CallNext,
    middlewares: MutableSequence[Middleware],
) -> None:
    """
    Run middleware in registration order (first registered = outermost).

    Each middleware receives ``call_next`` to invoke the next layer; the innermost
    layer runs ``call_next`` which executes the core dispatch logic.
    """
    async def call_at(index: int, current_ctx: DispatchContext) -> None:
        if index >= len(middlewares):
            await call_next(current_ctx)
            return

        async def next_layer(next_ctx: DispatchContext) -> None:
            await call_at(index + 1, next_ctx)

        await _invoke_middleware(middlewares[index], current_ctx, next_layer)

    await call_at(0, ctx)
