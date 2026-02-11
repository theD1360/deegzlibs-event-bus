"""Utility for dynamic module/class loading used by the message parser."""

import importlib
import sys
from typing import Type, TypeVar

T = TypeVar("T")


class ModuleImporter:
    """Imports a module by path and provides access to its classes by name."""

    def __init__(self, module_path: str) -> None:
        self._module_path = module_path
        try:
            self._module = importlib.import_module(module_path)
        except ImportError as e:
            # Provide helpful error message for __main__ module issues
            if module_path == "__main__":
                raise ImportError(
                    f"Cannot import '{module_path}'. This usually happens when "
                    "using @registry.event() in a script run as __main__. "
                    "Solution: Define your event handlers in a shared module "
                    "and import them in both client and worker scripts. "
                    "See docs/client-and-worker.md for examples."
                ) from e
            raise

    def get_class(self, class_name: str) -> Type[T]:
        """Return the class named class_name from the module."""
        try:
            return getattr(self._module, class_name)
        except AttributeError:
            # If module is __main__ and class not found, provide helpful error
            if self._module_path == "__main__":
                raise AttributeError(
                    f"Class '{class_name}' not found in module '{self._module_path}'. "
                    "This usually happens when client and worker are separate scripts. "
                    "Solution: Define event handlers in a shared module that both "
                    "client and worker import. See docs/client-and-worker.md"
                )
            raise AttributeError(
                f"Class '{class_name}' not found in module '{self._module_path}'. "
                f"Available attributes: {[x for x in dir(self._module) if not x.startswith('_')]}"
            )
