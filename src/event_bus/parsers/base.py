"""Abstract base for message parsers. Implement this to support different message formats."""

from abc import ABC, abstractmethod

from ..interfaces import EventMessage


class MessageParserBase(ABC):
    """
    Interface for parsing a raw message (e.g. string or bytes) into an EventMessage.
    Implement this to support different serialization formats (repr-style, JSON, etc.).
    """

    @abstractmethod
    def initialize(self) -> EventMessage:
        """Parse the raw message and return an EventMessage instance."""
        ...
