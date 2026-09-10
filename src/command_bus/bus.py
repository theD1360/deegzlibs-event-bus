"""Generic command bus: coordinates an adapter and router."""

import asyncio
import logging
import time
import uuid
from typing import Any, MutableSequence, Optional, Type

from .interfaces import QueueAdapter, CommandBusInterface, CommandMessage, ResponseStore
from .middleware import DispatchContext, Middleware, run_middleware_stack
from .parsers import MessageParserBase, ReprMessageParser
from .registry import Router

logger = logging.getLogger(__name__)


class CommandBus(CommandBusInterface):
    """
    Generic command bus that uses any QueueAdapter for queue operations
    and a Router for handler lookup. Use with SqsQueueAdapter,
    RabbitMqQueueAdapter, or any custom adapter.

    command_router is optional; if omitted, a new Router() is used.
    You can still use Router independently and pass it in when you
    want to share or preconfigure it.

    response_store is optional; when set, the bus can store handler return values
    keyed by correlation_id so clients can use execute_and_wait() to get results.
    """

    def __init__(
        self,
        queue_adapter: QueueAdapter,
        command_router: Optional[Router] = None,
        message_parser_class: Optional[Type[MessageParserBase]] = None,
        response_store: Optional[ResponseStore] = None,
        response_ttl_seconds: int = 60,
        middleware: Optional[MutableSequence[Middleware]] = None,
        dispatch_context_app: Any = None,
    ) -> None:
        self.queue_adapter = queue_adapter
        self.registry = (
            command_router if command_router is not None else Router()
        )
        self.message_parser_class = message_parser_class or ReprMessageParser
        self.response_store = response_store
        self.response_ttl_seconds = response_ttl_seconds
        self._middleware = middleware if middleware is not None else []
        self.dispatch_context_app = dispatch_context_app

    def _enqueue(
        self,
        message_instance: CommandMessage,
        delay_seconds: int = 0,
    ) -> None:
        """Enqueue a command (internal)."""
        matched_handlers = self.registry.get_handlers_for_message(message_instance)
        if not matched_handlers:
            raise ValueError(f"No handler found for {message_instance}")
        self.queue_adapter.enqueue(message_instance, delay_seconds=delay_seconds)

    async def execute(
        self,
        message_instance: CommandMessage,
        delay_seconds: Optional[int] = None,
        wait: Optional[bool] = None,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        response_ttl_seconds: Optional[int] = None,
    ) -> Any:
        """
        Enqueue the command and optionally wait for a response.

        When a response_store is set, default is wait=True (enqueue with correlation_id
        and return the handler result). Pass wait=False for fire-and-forget.
        When no response_store is set, wait is ignored and the command is only enqueued.

        Returns the handler result when wait=True, None otherwise.
        """
        delay = 0 if delay_seconds is None else delay_seconds
        if wait is None:
            wait = self.response_store is not None

        if wait:
            if self.response_store is None:
                raise ValueError(
                    "execute(..., wait=True) requires a response_store on the bus"
                )
            correlation_id = str(uuid.uuid4())
            message_with_id = message_instance.model_copy(
                update={"correlation_id": correlation_id}
            )
            self._enqueue(message_with_id, delay_seconds=delay)
            ttl = (
                response_ttl_seconds
                if response_ttl_seconds is not None
                else self.response_ttl_seconds
            )
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                result = self.response_store.get(correlation_id)
                if result is not None:
                    return result
                await asyncio.sleep(poll_interval_seconds)
            raise TimeoutError(
                f"No response for correlation_id {correlation_id} within {timeout_seconds}s"
            )
        self._enqueue(message_instance, delay_seconds=delay)
        return None

    async def execute_and_wait(
        self,
        message_instance: CommandMessage,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        response_ttl_seconds: Optional[int] = None,
        delay_seconds: Optional[int] = None,
    ) -> Any:
        """Enqueue and wait for handler result. Convenience for execute(..., wait=True)."""
        return await self.execute(
            message_instance,
            delay_seconds=delay_seconds,
            wait=True,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            response_ttl_seconds=response_ttl_seconds,
        )

    async def _dispatch_parsed(self, command_instance: CommandMessage) -> None:
        """Run registered handlers for a parsed command and store response if configured."""
        registry_entries = self.registry.get_handlers_for_message(command_instance)
        logger.info("%d handlers found", len(registry_entries))

        last_result: Any = None
        for entry in registry_entries:
            handler = entry.handler_instance()
            result = await handler(command_instance)
            if result is not None:
                last_result = result
            logger.info(
                "Dispatched command %s to %s handler",
                command_instance,
                entry.handler_class,
            )

        if (
            command_instance.correlation_id
            and self.response_store is not None
            and last_result is not None
        ):
            self.response_store.set(
                command_instance.correlation_id,
                last_result,
                ttl_seconds=self.response_ttl_seconds,
            )

    async def dispatch(self, raw_message: str) -> None:
        """Parse the raw message (using the configured parser), then run all registered handlers."""
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
        """Poll the queue and dispatch messages to handlers (up to ``concurrency`` in parallel)."""
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
