"""Tests for event_bus interfaces and base types."""

import pytest
from event_bus import EventMessage, EventMessageHandler, TransmissibleBaseModel


def test_transmissible_base_model_str():
    """str() of a message yields module-qualified repr."""

    class M(TransmissibleBaseModel):
        x: int

    m = M(x=1)
    s = str(m)
    assert "M" in s
    assert "x=1" in s or "1" in s
    assert m.__module__ in s


def test_event_message_is_pydantic_model():
    """EventMessage subclasses can define fields."""

    class E(EventMessage):
        id: str

    e = E(id="abc")
    assert e.id == "abc"


def test_event_message_handler_abstract():
    """EventMessageHandler cannot be instantiated without process()."""
    with pytest.raises(TypeError):
        EventMessageHandler()
