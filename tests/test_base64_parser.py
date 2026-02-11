"""Tests for Base64MessageParser."""

import base64
import gzip
import json

import pytest
from event_bus import Base64MessageParser, EventMessage, JsonMessageParser


class Command(EventMessage):
    name: str
    value: int


def test_base64_parser_repr_format():
    """Decode base64 then parse as repr-style (default inner parser)."""
    payload = "tests.test_base64_parser.Command(name='ping', value=42)"
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    parser = Base64MessageParser(encoded)
    msg = parser.initialize()
    assert isinstance(msg, Command)
    assert msg.name == "ping"
    assert msg.value == 42


def test_base64_parser_repr_format_compressed():
    """Decode base64, decompress gzip, then parse as repr-style."""
    payload = "tests.test_base64_parser.Command(name='pong', value=99)"
    compressed = gzip.compress(payload.encode("utf-8"))
    encoded = base64.b64encode(compressed).decode("ascii")
    parser = Base64MessageParser(encoded, decompress=True)
    msg = parser.initialize()
    assert msg.name == "pong"
    assert msg.value == 99


def test_base64_parser_json_inner():
    """Decode base64 then parse as JSON via inner_parser_class."""
    payload = {
        "__type__": "tests.test_base64_parser.Command",
        "name": "json-cmd",
        "value": 1,
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    parser = Base64MessageParser(encoded, inner_parser_class=JsonMessageParser)
    msg = parser.initialize()
    assert isinstance(msg, Command)
    assert msg.name == "json-cmd"
    assert msg.value == 1


def test_base64_parser_json_inner_with_kwargs():
    """Inner parser can receive extra kwargs (e.g. type_key)."""
    payload = {
        "type": "tests.test_base64_parser.Command",
        "name": "custom-key",
        "value": 2,
    }
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    parser = Base64MessageParser(
        encoded,
        inner_parser_class=JsonMessageParser,
        inner_parser_kwargs={"type_key": "type"},
    )
    msg = parser.initialize()
    assert msg.name == "custom-key"


def test_base64_parser_invalid_base64_raises():
    parser = Base64MessageParser("not-valid-base64!!!")
    with pytest.raises(Exception):  # binascii.Error or ValueError
        parser.initialize()


def test_base64_parser_decompress_non_gzip_raises():
    """If decompress=True but payload isn't gzip, we get an error."""
    payload = b"plain bytes"
    encoded = base64.b64encode(payload).decode("ascii")
    parser = Base64MessageParser(encoded, decompress=True)
    with pytest.raises(Exception):  # gzip.BadGzipFile or OSError
        parser.initialize()
