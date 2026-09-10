"""Tests for dispatch middleware."""

import pytest

from command_bus import CommandBus, CommandHandler, CommandMessage, DispatchContext, Router
from command_bus.adapters import InMemoryQueueAdapter
from command_bus.event_bus import EventBus
from command_bus.interfaces import EventMessage


class PingCommand(CommandMessage):
    value: str


class PingHandler(CommandHandler):
    def process(self, message: CommandMessage):
        assert isinstance(message, PingCommand)
        return message.value.upper()


class PingEvent(EventMessage):
    value: str


@pytest.mark.asyncio
async def test_middleware_runs_before_and_after_handler():
    order: list[str] = []
    middleware: list = []

    async def record_mw(ctx: DispatchContext, call_next):
        order.append("before")
        await call_next(ctx)
        order.append("after")
        assert ctx.parsed_message is not None

    middleware.append(record_mw)
    router = Router()
    router.register(PingCommand, PingHandler)
    bus = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="mw-test"),
        command_router=router,
        middleware=middleware,
    )

    await bus.dispatch(str(PingCommand(value="hi")))
    assert order == ["before", "after"]


@pytest.mark.asyncio
async def test_middleware_order_outermost_first():
    order: list[str] = []
    middleware: list = []

    async def mw1(ctx, call_next):
        order.append("mw1_before")
        await call_next(ctx)
        order.append("mw1_after")

    async def mw2(ctx, call_next):
        order.append("mw2_before")
        await call_next(ctx)
        order.append("mw2_after")

    middleware.extend([mw1, mw2])
    router = Router()

    @router.command()
    def handle(value: str) -> None:
        order.append("handler")

    bus = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="order-test"),
        command_router=router,
        middleware=middleware,
    )

    await bus.dispatch(str(handle(value="x")))
    assert order == ["mw1_before", "mw2_before", "handler", "mw2_after", "mw1_after"]


@pytest.mark.asyncio
async def test_empty_middleware_matches_direct_dispatch():
    received: list[str] = []

    class H(CommandHandler):
        def process(self, message: CommandMessage):
            received.append(message.value)

    router = Router()
    router.register(PingCommand, H)
    bus = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="empty-mw"),
        command_router=router,
    )
    await bus.dispatch(str(PingCommand(value="ok")))
    assert received == ["ok"]


@pytest.mark.asyncio
async def test_event_bus_middleware():
    order: list[str] = []
    middleware: list = []

    async def mw(ctx, call_next):
        order.append("event_mw")
        await call_next(ctx)

    middleware.append(mw)
    router = Router()

    class H(CommandHandler):
        def process(self, message: EventMessage):
            order.append("handled")

    router.register(PingEvent, H)
    bus = EventBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="event-mw"),
        command_router=router,
        middleware=middleware,
    )
    await bus.dispatch(str(PingEvent(value="e")))
    assert order == ["event_mw", "handled"]
