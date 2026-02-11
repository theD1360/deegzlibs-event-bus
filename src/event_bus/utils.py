"""Utility for dynamic module/class loading used by the message parser."""

import importlib
from typing import Type, TypeVar

T = TypeVar("T")


class ModuleImporter:
    """Imports a module by path and provides access to its classes by name."""

    def __init__(self, module_path: str) -> None:
        self._module = importlib.import_module(module_path)

    def get_class(self, class_name: str) -> Type[T]:
        """Return the class named class_name from the module."""
        return getattr(self._module, class_name)
