from abc import ABC, abstractmethod
from asyncio import iscoroutine
from typing import Any, Coroutine, List, Optional, Type, Union

from pydantic import BaseModel


class TransmissibleBaseModel(BaseModel):
    def __str__(self) -> str:
        return self.__module__ + "." + repr(self)


class CommandMessage(TransmissibleBaseModel):
    """Base for command payloads. Set correlation_id when using execute_and_wait for responses."""

    correlation_id: Optional[str] = None


class EventMessage(TransmissibleBaseModel):
    """Base for pub/sub event payloads. Fire-and-forget; no response-store semantics."""


class Handler(ABC):
    @abstractmethod
    def process(
        self, message: TransmissibleBaseModel
    ) -> Union[Any, Coroutine[Any, Any, Any]]:
        pass

    async def __call__(self, message: TransmissibleBaseModel) -> Any:
        res = self.process(message=message)
        if iscoroutine(res):
            return await res
        return res


class CommandHandler(Handler):
    """Deprecated alias for :class:`Handler`."""


class ResponseStore(ABC):
    """Store for response values keyed by correlation_id (e.g. Redis)."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Store a value for key. Overwrites existing. ttl_seconds 0 = no expiry."""
        ...

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Return the value for key, or None if missing or expired."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the key from the store."""
        ...


class QueueAdapter(ABC):
    @abstractmethod
    def enqueue(
        self, message_instance: TransmissibleBaseModel, delay_seconds: int = 0
    ) -> None:
        pass

    @abstractmethod
    def dequeue(self, message_instance: Any) -> None:
        pass

    @abstractmethod
    def get_messages(self, *args: Any, **kwargs: Any) -> Any:
        pass


class CommandBusAdapter(QueueAdapter):
    """Deprecated alias for :class:`QueueAdapter`."""


class RouterInterface(ABC):
    @abstractmethod
    def get_handlers_for_message(
        self,
        message_class: Union[TransmissibleBaseModel, Type[TransmissibleBaseModel]],
    ) -> List[Any]:
        pass

    @abstractmethod
    def register(
        self,
        message_class: Type[TransmissibleBaseModel],
        handler_class: Type[Handler],
    ) -> None:
        pass

    @abstractmethod
    def deregister(
        self,
        message_class: Type[TransmissibleBaseModel],
        handler_class: Type[Handler],
    ) -> None:
        pass


class CommandBusRouterInterface(RouterInterface):
    """Deprecated alias for :class:`RouterInterface`."""


class CommandBusInterface(ABC):
    queue_name: str
    registry: RouterInterface

    @abstractmethod
    async def execute(
        self,
        message_instance: CommandMessage,
        delay_seconds: Optional[int] = None,
        wait: Optional[bool] = None,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        response_ttl_seconds: Optional[int] = None,
    ) -> Any:
        """Enqueue command; when wait=True (default if response_store set), return handler result."""
        pass

    @abstractmethod
    async def dispatch(self, message_string: str) -> None:
        pass

    @abstractmethod
    async def work(self, *, concurrency: int = 1) -> int:
        pass


class EventBusInterface(ABC):
    """Pub/sub event bus: publish fans out; workers poll and dispatch."""

    registry: RouterInterface

    @abstractmethod
    async def publish(
        self,
        message_instance: EventMessage,
        delay_seconds: Optional[int] = None,
    ) -> None:
        """Publish an event to all subscribers (fire-and-forget)."""
        pass

    @abstractmethod
    async def dispatch(self, message_string: str) -> None:
        pass

    @abstractmethod
    async def work(self, *, concurrency: int = 1) -> int:
        pass
