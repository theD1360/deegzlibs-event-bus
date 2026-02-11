"""Tests for JsonMessageParser."""

import json

import pytest
from event_bus import EventMessage, JsonMessageParser


class OrderCreated(EventMessage):
    order_id: str
    amount_cents: int


class NestedMessage(EventMessage):
    name: str
    count: int


def test_json_parser_initialize():
    payload = {
        "__type__": "tests.test_json_parser.OrderCreated",
        "order_id": "ord-123",
        "amount_cents": 1999,
    }
    parser = JsonMessageParser(json.dumps(payload))
    msg = parser.initialize()
    assert isinstance(msg, OrderCreated)
    assert msg.order_id == "ord-123"
    assert msg.amount_cents == 1999


def test_json_parser_custom_type_key():
    payload = {
        "type": "tests.test_json_parser.OrderCreated",
        "order_id": "ord-456",
        "amount_cents": 5000,
    }
    parser = JsonMessageParser(json.dumps(payload), type_key="type")
    msg = parser.initialize()
    assert msg.order_id == "ord-456"
    assert msg.amount_cents == 5000


def test_json_parser_missing_type_key_raises():
    parser = JsonMessageParser(json.dumps({"order_id": "x", "amount_cents": 100}))
    with pytest.raises(ValueError, match="__type__"):
        parser.initialize()


def test_json_parser_type_not_string_raises():
    parser = JsonMessageParser(
        json.dumps({"__type__": 123, "order_id": "x", "amount_cents": 100})
    )
    with pytest.raises(ValueError, match="must be a string"):
        parser.initialize()


def test_json_parser_type_not_fully_qualified_raises():
    parser = JsonMessageParser(
        json.dumps({"__type__": "OrderCreated", "order_id": "x", "amount_cents": 100})
    )
    with pytest.raises(ValueError, match="fully qualified"):
        parser.initialize()


def test_json_parser_invalid_class_raises():
    parser = JsonMessageParser(
        json.dumps(
            {
                "__type__": "tests.test_json_parser.NonexistentMessage",
                "order_id": "x",
            }
        )
    )
    with pytest.raises((AttributeError, ValueError)):
        parser.initialize()


def test_json_parser_not_event_message_class_raises():
    # Builtin type is not an EventMessage subclass
    parser = JsonMessageParser(json.dumps({"__type__": "builtins.dict", "x": 1}))
    with pytest.raises(ValueError, match="not an EventMessage subclass"):
        parser.initialize()
