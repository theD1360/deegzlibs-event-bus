"""Generic event bus: coordinates an adapter and registry."""

import asyncio
import logging
import time
import uuid
from typing import Any, Optional, Type

from .interfaces import EventBusAdapter, EventBusInterface, EventMessage, ResponseStore
from .parsers import MessageParserBase, ReprMessageParser
from .registry import EventBusRegistry

logger = logging.getLogger(__name__)


class EventBus(EventBusInterface):
    """
    Generic event bus that uses any EventBusAdapter for queue operations
    and an EventBusRegistry for handler lookup. Use with SqsEventBusAdapter,
    RabbitMqEventBusAdapter, or any custom adapter.

    event_registry is optional; if omitted, a new EventBusRegistry() is used.
    You can still use EventBusRegistry independently and pass it in when you
    want to share or preconfigure it.

    response_store is optional; when set, the bus can store handler return values
    keyed by correlation_id so clients can use execute_and_wait() to get results.
    """

    def __init__(
        self,
        queue_adapter: EventBusAdapter,
        event_registry: Optional[EventBusRegistry] = None,
        message_parser_class: Optional[Type[MessageParserBase]] = None,
        response_store: Optional[ResponseStore] = None,
        response_ttl_seconds: int = 60,
    ) -> None:
        self.queue_adapter = queue_adapter
        self.registry = (
            event_registry if event_registry is not None else EventBusRegistry()
        )
        self.message_parser_class = message_parser_class or ReprMessageParser
        self.response_store = response_store
        self.response_ttl_seconds = response_ttl_seconds

    def _enqueue(
        self,
        message_instance: EventMessage,
        delay_seconds: int = 0,
    ) -> None:
        """Enqueue an event (internal)."""
        matched_handlers = self.registry.get_handlers_for_message(message_instance)
        if not matched_handlers:
            raise ValueError(f"No handler found for {message_instance}")
        self.queue_adapter.enqueue(message_instance, delay_seconds=delay_seconds)

    async def execute(
        self,
        message_instance: EventMessage,
        delay_seconds: Optional[int] = None,
        wait: Optional[bool] = None,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        response_ttl_seconds: Optional[int] = None,
    ) -> Any:
        """
        Enqueue the event and optionally wait for a response.

        When a response_store is set, default is wait=True (enqueue with correlation_id
        and return the handler result). Pass wait=False for fire-and-forget.
        When no response_store is set, wait is ignored and the event is only enqueued.

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
        message_instance: EventMessage,
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

    async def dispatch(self, raw_message: str) -> None:
        """Parse the raw message (using the configured parser), then run all registered handlers."""
        parser = self.message_parser_class(raw_message)
        event_instance = parser.initialize()
        registry_entries = self.registry.get_handlers_for_message(event_instance)
        logger.info("%d handlers found", len(registry_entries))

        last_result: Any = None
        for entry in registry_entries:
            handler = entry.handler_instance()
            result = await handler(event_instance)
            if result is not None:
                last_result = result
            logger.info(
                "Dispatched event %s to %s handler",
                event_instance,
                entry.handler_class,
            )

        if (
            event_instance.correlation_id
            and self.response_store is not None
            and last_result is not None
        ):
            self.response_store.set(
                event_instance.correlation_id,
                last_result,
                ttl_seconds=self.response_ttl_seconds,
            )

    async def work(self) -> None:
        """Poll the queue and dispatch each message to its handlers."""
        messages = self.queue_adapter.get_messages()
        for message in messages:
            await self.dispatch(message.body)
            self.queue_adapter.dequeue(message)
