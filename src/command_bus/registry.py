"""Router for mapping message types to handlers."""

from __future__ import annotations

import inspect
import sys
import warnings
from typing import Any, Callable, List, Optional, Union, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model

from .interfaces import (
    CommandHandler,
    Handler,
    CommandMessage,
    EventMessage,
    RouterInterface,
    TransmissibleBaseModel,
)


def get_qual_name(obj: Union[type, object]) -> str:
    """Return the qualified name (module + class name) for a class or instance."""
    if inspect.isclass(obj):
        return obj.__module__ + "." + obj.__name__
    return type(obj).__module__ + "." + type(obj).__name__


def _message_class_from_signature(
    func: Callable[..., Any],
    base: type = CommandMessage,
    model_name: Optional[str] = None,
) -> type:
    """Build a message subclass (CommandMessage or EventMessage) from function parameters."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    fields: dict[str, tuple[type, Any]] = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        ann = hints.get(name, Any)
        if param.default is inspect.Parameter.empty:
            fields[name] = (ann, ...)
        else:
            fields[name] = (ann, Field(default=param.default))
    name = model_name or f"{func.__name__}Message"
    model = create_model(name, __base__=base, **fields)
    module_name = getattr(func, "__module__", "__main__")
    model.__module__ = module_name
    # Register on the module so repr-based parsers can resolve the class by name
    mod = inspect.getmodule(func)
    if mod is not None:
        setattr(mod, name, model)
        # Also register in sys.modules if module is __main__ to help with cross-process imports
        # Note: This is a fallback; the recommended approach is to use a shared module
        if module_name == "__main__" and "__main__" in sys.modules:
            main_module = sys.modules["__main__"]
            if not hasattr(main_module, name):
                setattr(main_module, name, model)
    return model


def _command_message_class_from_signature(
    func: Callable[..., Any],
    model_name: Optional[str] = None,
) -> type:
    """Build a CommandMessage subclass whose fields match the function's parameters."""
    return _message_class_from_signature(func, base=CommandMessage, model_name=model_name)


class RouterEntry(BaseModel):
    """A single router entry binding a message type to a handler class."""

    handler_class: type
    message_class: type

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def message_qual_name(self) -> str:
        return get_qual_name(self.message_class)

    def is_message_match(
        self,
        message_instance_or_class: Union[TransmissibleBaseModel, type, str],
    ) -> bool:
        if isinstance(message_instance_or_class, str):
            return self.message_qual_name == message_instance_or_class
        return self.message_qual_name == get_qual_name(message_instance_or_class)

    def handler_instance(self) -> Handler:
        """Return an instance of the handler."""
        return self.handler_class()


class CommandBusRouterEntry(RouterEntry):
    """Deprecated alias for :class:`RouterEntry`."""

    def __init__(self, **data: Any) -> None:
        warnings.warn(
            "CommandBusRouterEntry is deprecated; use RouterEntry instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(**data)


class Router(RouterInterface):
    """Default in-memory router of message types to handlers."""

    def __init__(
        self,
        command_handlers: Optional[List[RouterEntry]] = None,
    ) -> None:
        self.handlers: List[RouterEntry] = command_handlers or []

    def get_handlers_for_message(
        self,
        message_class: Union[TransmissibleBaseModel, type],
    ) -> List[RouterEntry]:
        """Return all router entries that handle this message type."""
        return [
            entry for entry in self.handlers if entry.is_message_match(message_class)
        ]

    def register(
        self,
        message_class: type,
        handler_class: type,
    ) -> None:
        """Register a handler for a message class."""
        entry = RouterEntry(
            message_class=message_class,
            handler_class=handler_class,
        )
        if entry not in self.handlers:
            self.handlers.append(entry)

    def deregister(
        self,
        message_class: type,
        handler_class: type,
    ) -> None:
        """Remove a handler registration."""
        entry = RouterEntry(
            message_class=message_class,
            handler_class=handler_class,
        )
        for i, v in enumerate(self.handlers):
            if v == entry:
                self.handlers.pop(i)
                return

    def _handler_decorator(self, base: type):
        """Shared decorator factory for command() and event()."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            message_class = _message_class_from_signature(func, base=base)
            sig = inspect.signature(func)
            param_names = [name for name, p in sig.parameters.items() if name != "self"]

            def process(self: Any, message: TransmissibleBaseModel) -> Any:
                dump = message.model_dump()
                kwargs = {k: dump[k] for k in param_names if k in dump}
                return func(**kwargs)

            handler_class = type(
                f"{func.__name__}_Handler",
                (Handler,),
                {"process": process},
            )
            self.register(message_class, handler_class)

            def message_factory(*args: Any, **kwargs: Any) -> TransmissibleBaseModel:
                # Map positional args to param names so message_class(**kwargs) works
                kwargs_from_args = dict(zip(param_names, args))
                return message_class(**{**kwargs_from_args, **kwargs})

            message_factory.__name__ = func.__name__
            message_factory._command_message_class = message_class  # type: ignore[attr-defined]
            message_factory._handler_func = func  # type: ignore[attr-defined]
            return message_factory

        return decorator

    def command(self):
        """
        Decorator that creates a CommandMessage from the function's parameters,
        registers a handler that calls the function when the message is dispatched,
        and returns a callable that builds the message instance. So you can do:
          bus.execute(on_order_created(order_id="x", amount_cents=10), wait=False)
        """
        return self._handler_decorator(CommandMessage)

    def event(self):
        """
        Decorator that creates an EventMessage from the function's parameters,
        registers a handler for pub/sub dispatch, and returns a message factory:
          await event_bus.publish(on_order_created(order_id="x", amount_cents=10))
        """
        return self._handler_decorator(EventMessage)


class CommandBusRouter(Router):
    """Deprecated alias for :class:`Router`."""

    def __init__(
        self,
        command_handlers: Optional[List[RouterEntry]] = None,
    ) -> None:
        warnings.warn(
            "CommandBusRouter is deprecated; use Router instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(command_handlers=command_handlers)
