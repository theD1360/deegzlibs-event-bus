"""RabbitMQ-backed event bus adapter."""

from typing import Any, List, Optional

import pika
from pika.adapters.blocking_connection import BlockingChannel

from ...interfaces import EventBusAdapter, EventMessage


class _RabbitMQMessage:
    """Wrapper so RabbitMQ messages have .body and .delete() like SQS messages."""

    __slots__ = ("body", "_channel", "_delivery_tag")

    def __init__(self, body: str, channel: BlockingChannel, delivery_tag: int) -> None:
        self.body = body
        self._channel = channel
        self._delivery_tag = delivery_tag

    def delete(self) -> None:
        self._channel.basic_ack(self._delivery_tag)


class RabbitMqEventBusAdapter(EventBusAdapter):
    """EventBus adapter using RabbitMQ for queue operations (via pika)."""

    def __init__(
        self,
        queue_name: str,
        connection_url: Optional[str] = None,
        connection_params: Optional[pika.ConnectionParameters] = None,
    ) -> None:
        if not connection_url and not connection_params:
            raise ValueError("Provide either connection_url or connection_params")
        self.queue_name = queue_name
        self._connection_url = connection_url
        self._connection_params = connection_params
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None

    def _ensure_connection(self) -> BlockingChannel:
        if self._channel is None or self._channel.is_closed:
            if self._connection_url:
                self._connection = pika.BlockingConnection(
                    pika.URLParameters(self._connection_url)
                )
            else:
                self._connection = pika.BlockingConnection(self._connection_params)
            self._channel = self._connection.channel()
            self._channel.queue_declare(queue=self.queue_name, durable=True)
        return self._channel

    def _connection_for_publish(self) -> tuple:
        """Short-lived connection for publishing (no shared state)."""
        if self._connection_url:
            conn = pika.BlockingConnection(pika.URLParameters(self._connection_url))
        else:
            conn = pika.BlockingConnection(self._connection_params)
        ch = conn.channel()
        ch.queue_declare(queue=self.queue_name, durable=True)
        return conn, ch

    def enqueue(
        self,
        message_instance: EventMessage,
        delay_seconds: int = 0,
    ) -> None:
        """Add a message to the queue. (delay_seconds is ignored; use a delayed-exchange plugin for delays.)"""
        conn, ch = self._connection_for_publish()
        try:
            ch.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=str(message_instance),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )
        finally:
            conn.close()

    def dequeue(self, message_instance: Any) -> None:
        """Ack the message (remove from queue after successful processing)."""
        if hasattr(message_instance, "delete"):
            message_instance.delete()
        else:
            raise TypeError(
                "message_instance must be a _RabbitMQMessage with .delete()"
            )

    def get_messages(
        self,
        max_messages: int = 1,
        **kwargs: Any,
    ) -> List[_RabbitMQMessage]:
        """Fetch messages from the queue. Uses a shared connection/channel for acks."""
        channel = self._ensure_connection()
        out: List[_RabbitMQMessage] = []
        for _ in range(max_messages):
            method_frame, _, body = channel.basic_get(queue=self.queue_name)
            if method_frame is None:
                break
            body_str = body.decode("utf-8") if isinstance(body, bytes) else body
            out.append(
                _RabbitMQMessage(
                    body=body_str,
                    channel=channel,
                    delivery_tag=method_frame.delivery_tag,
                )
            )
        return out

    def close(self) -> None:
        """Close the consumer connection (optional; call when done with get_messages)."""
        if self._channel and not self._channel.is_closed:
            self._channel.close()
        if self._connection and self._connection.is_open:
            self._connection.close()
        self._channel = None
        self._connection = None
