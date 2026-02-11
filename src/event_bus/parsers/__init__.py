"""
Message parsers: pluggable parsers for different message formats.

Use MessageParser (repr-style) by default, JsonMessageParser for JSON,
Base64MessageParser for base64-encoded (optionally compressed) payloads,
or implement MessageParserBase for other formats.
"""

from .base import MessageParserBase
from .base64_parser import Base64MessageParser
from .json_parser import JsonMessageParser
from .repr_parser import ReprMessageParser

# Default / backward-compatible name for the repr-style parser
MessageParser = ReprMessageParser

__all__ = [
    "Base64MessageParser",
    "JsonMessageParser",
    "MessageParser",
    "MessageParserBase",
    "ReprMessageParser",
]
