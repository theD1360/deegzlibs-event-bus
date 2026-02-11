"""Tests for message parsers (parsers package)."""

import pytest
from event_bus import EventMessage, MessageParser, MessageParserBase, ReprMessageParser


class SimpleMessage(EventMessage):
    x: int
    y: str


def test_get_message_components():
    module_path, class_name, param_string = ReprMessageParser.get_message_components(
        "tests.test_parser.SimpleMessage(1, 'hello')"
    )
    assert module_path == "tests.test_parser"
    assert class_name == "SimpleMessage"
    assert param_string == "1, 'hello'"


def test_parser_initialize_with_kwargs():
    parser = MessageParser("tests.test_parser.SimpleMessage(x=1, y='hello')")
    msg = parser.initialize()
    assert isinstance(msg, SimpleMessage)
    assert msg.x == 1
    assert msg.y == "hello"


def test_parser_parse_args_positional():
    """parse_args correctly parses positional args (caller may map to model fields)."""
    parser = MessageParser("tests.test_parser.SimpleMessage(0, '')")
    args, kwargs = parser.parse_args("1, 'hello'")
    assert args == [1, "hello"]
    assert kwargs == {}


def test_parser_initialize_kwargs():
    parser = MessageParser("tests.test_parser.SimpleMessage(x=1, y='hello')")
    msg = parser.initialize()
    assert msg.x == 1
    assert msg.y == "hello"


def test_parser_parse_args_none_true_false():
    parser = MessageParser("tests.test_parser.SimpleMessage(0, '')")
    args, kwargs = parser.parse_args("None, True, False, x=1")
    assert args == [None, True, False]
    assert kwargs == {"x": 1}


def test_parser_parse_args_list_dict():
    parser = MessageParser("tests.test_parser.SimpleMessage(0, '')")
    args, kwargs = parser.parse_args("[1, 2], {'a': 3}")
    assert args == [[1, 2], {"a": 3}]


def test_message_parser_is_repr_parser():
    """MessageParser is the default repr-style parser (backward compat)."""
    assert MessageParser is ReprMessageParser


def test_custom_parser_implements_base():
    """A custom parser can implement MessageParserBase for other formats."""

    class SimpleParser(MessageParserBase):
        def __init__(self, raw: str) -> None:
            self.raw = raw

        def initialize(self) -> EventMessage:
            return SimpleMessage(x=0, y=self.raw)

    parser = SimpleParser("hello")
    msg = parser.initialize()
    assert msg.y == "hello"
    assert isinstance(msg, SimpleMessage)
