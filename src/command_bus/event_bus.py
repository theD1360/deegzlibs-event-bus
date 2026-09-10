"""Pub/sub event bus: publish fans out to all subscribers."""

import asyncio
import logging
from typing import Any, MutableSequence, Optional, Type

from .interfaces import (
    EventBusInterface,
    EventMessage,
    QueueAdapter,
)
from .middleware import DispatchContext, Middleware, run_middleware_stack
from .parsers import MessageParserBase, ReprMessageParser
from .registry import Router

logger = logging.getLogger(__name__)


class EventBus(EventBusInterface):
    """
    Event bus for fan-out pub/sub. Uses any QueueAdapter that broadcasts on
    enqueue (e.g. InMemoryPubSubAdapter, RedisPubSubAdapter, RabbitMqFanoutAdapter).

    Unlike CommandBus, publish does not require a local handler, and there is no
    response store / wait semantics.
    """

    def __init__(
        self,
        queue_adapter: QueueAdapter,
        command_router: Optional[Router] = None,
        message_parser_class: Optional[Type[MessageParserBase]] = None,
        middleware: Optional[MutableSequence[Middleware]] = None,
        dispatch_context_app: Any = None,
    ) -> None:
        self.queue_adapter = queue_adapter
        self.registry = (
            command_router if command_router is not None else Router()
        )
        self.message_parser_class = message_parser_class or ReprMessageParser
        self._middleware = middleware if middleware is not None else []
        self.dispatch_context_app = dispatch_context_app
        if hasattr(queue_adapter, "bind_message_parser"):
            queue_adapter.bind_message_parser(self.message_parser_class)

    async def publish(
        self,
        message_instance: EventMessage,
        delay_seconds: Optional[int] = None,
    ) -> None:
        """Publish an event to all subscribers. delay_seconds depends on the adapter."""
        delay = 0 if delay_seconds is None else delay_seconds
        self.queue_adapter.enqueue(message_instance, delay_seconds=delay)

    async def _dispatch_parsed(self, event_instance: EventMessage) -> None:
        """Run registered handlers for a parsed event (no-op if none)."""
        registry_entries = self.registry.get_handlers_for_message(event_instance)
        logger.info("%d handlers found", len(registry_entries))

        if not registry_entries:
            logger.info("No handlers for %s; acknowledging", event_instance)
            return

        for entry in registry_entries:
            handler = entry.handler_instance()
            await handler(event_instance)
            logger.info(
                "Dispatched event %s to %s handler",
                event_instance,
                entry.handler_class,
            )

    async def dispatch(self, raw_message: str) -> None:
        """Parse the raw message and run all registered handlers (no-op if none)."""
        ctx = DispatchContext(
            raw_message=raw_message,
            app=self.dispatch_context_app,
        )

        async def core(current_ctx: DispatchContext) -> None:
            parser = self.message_parser_class(current_ctx.raw_message)
            current_ctx.parsed_message = parser.initialize()
            await self._dispatch_parsed(current_ctx.parsed_message)

        if self._middleware:
            await run_middleware_stack(ctx, core, self._middleware)
        else:
            await core(ctx)

    async def work(self, *, concurrency: int = 1) -> int:
        """Poll the subscription and dispatch messages (up to ``concurrency`` in parallel)."""
        messages = self.queue_adapter.get_messages(max_messages=max(1, concurrency))
        if not messages:
            return 0

        async def _handle(message: Any) -> None:
            try:
                await self.dispatch(message.body)
            finally:
                self.queue_adapter.dequeue(message)

        await asyncio.gather(*(_handle(m) for m in messages))
        return len(messages)
