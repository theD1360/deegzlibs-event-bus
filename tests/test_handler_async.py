"""Tests for async handler dispatch."""

import pytest
from event_bus import EventBusRegistry, EventMessage, EventMessageHandler, MessageParser


class AsyncMessage(EventMessage):
    name: str


class AsyncHandler(EventMessageHandler):
    async def process(self, message: EventMessage):
        return f"ok:{message.name}"


@pytest.mark.asyncio
async def test_dispatch_calls_async_handler():
    registry = EventBusRegistry()
    registry.register(AsyncMessage, AsyncHandler)
    parser = MessageParser("tests.test_handler_async.AsyncMessage(name='test')")
    msg = parser.initialize()
    entries = registry.get_handlers_for_message(msg)
    assert len(entries) == 1
    handler = entries[0].handler_instance()
    result = await handler(msg)
    assert result == "ok:test"
