"""Parser for base64-encoded (and optionally compressed) message payloads."""

import base64
import gzip
from typing import Any, Dict, Optional, Type

from ..interfaces import EventMessage
from .base import MessageParserBase
from .repr_parser import ReprMessageParser


class Base64MessageParser(MessageParserBase):
    """
    Parses base64-encoded strings into EventMessage instances.

    Decodes the input from base64, optionally decompresses with gzip, then
    delegates to an inner parser (e.g. ReprMessageParser or JsonMessageParser).
    Useful when sending compressed or encoded commands over the event bus.

    Example (repr format, compressed):
        raw = base64.b64encode(gzip.compress(b"mymodule.OrderCreated(order_id='x')")).decode()
        parser = Base64MessageParser(raw, decompress=True)
        msg = parser.initialize()

    Example (JSON format, no compression):
        raw = base64.b64encode(b'{"__type__": "mymodule.OrderCreated", "order_id": "x"}').decode()
        parser = Base64MessageParser(raw, inner_parser_class=JsonMessageParser)
        msg = parser.initialize()
    """

    def __init__(
        self,
        message_string: str,
        inner_parser_class: Type[MessageParserBase] = ReprMessageParser,
        decompress: bool = False,
        inner_parser_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._encoded = message_string
        self._inner_parser_class = inner_parser_class
        self._decompress = decompress
        self._inner_parser_kwargs = inner_parser_kwargs or {}

    def initialize(self) -> EventMessage:
        """Decode (and optionally decompress), then parse with the inner parser."""
        decoded_bytes = base64.b64decode(self._encoded)
        if self._decompress:
            decoded_bytes = gzip.decompress(decoded_bytes)
        decoded_str = decoded_bytes.decode("utf-8")
        inner = self._inner_parser_class(decoded_str, **self._inner_parser_kwargs)
        return inner.initialize()
