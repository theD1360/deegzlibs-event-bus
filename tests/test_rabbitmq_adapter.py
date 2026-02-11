"""Tests for RabbitMQ adapter (mocked)."""

import pytest

pytest.importorskip("pika")

from unittest.mock import MagicMock, patch

from event_bus import EventBus, EventBusRegistry, EventMessage
from event_bus.adapters.queue.rabbitmq import RabbitMqEventBusAdapter, _RabbitMQMessage


class DummyMessage(EventMessage):
    id: str


def test_rabbitmq_adapter_requires_connection():
    with pytest.raises(ValueError, match="connection_url or connection_params"):
        RabbitMqEventBusAdapter(queue_name="q")


def test_rabbitmq_message_wrapper_delete_acks():
    channel = MagicMock()
    msg = _RabbitMQMessage(body='{"x": 1}', channel=channel, delivery_tag=7)
    msg.delete()
    channel.basic_ack.assert_called_once_with(7)


@patch("event_bus.adapters.queue.rabbitmq.pika")
def test_rabbitmq_adapter_enqueue(pika_mock):
    conn = MagicMock()
    ch = MagicMock()
    pika_mock.BlockingConnection.return_value = conn
    conn.channel.return_value = ch

    adapter = RabbitMqEventBusAdapter(
        queue_name="test-q", connection_url="amqp://localhost/"
    )
    msg = DummyMessage(id="x")
    adapter.enqueue(msg, delay_seconds=0)

    ch.queue_declare.assert_called_once()
    ch.basic_publish.assert_called_once()
    call_kw = ch.basic_publish.call_args[1]
    assert call_kw["routing_key"] == "test-q"
    assert "x" in call_kw["body"] or "id" in call_kw["body"]
    conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_rabbitmq_event_bus_execute_raises_when_no_handler():
    adapter = MagicMock()
    registry = EventBusRegistry()
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    with pytest.raises(ValueError, match="No handler found"):
        await bus.execute(DummyMessage(id="y"), wait=False)


@pytest.mark.asyncio
async def test_rabbitmq_event_bus_execute_enqueues_when_handler_registered():
    adapter = MagicMock()
    registry = EventBusRegistry()

    class DummyHandler:
        def process(self, message):
            pass

    registry.register(DummyMessage, DummyHandler)
    bus = EventBus(queue_adapter=adapter, event_registry=registry)
    await bus.execute(DummyMessage(id="z"), delay_seconds=0, wait=False)
    adapter.enqueue.assert_called_once()
