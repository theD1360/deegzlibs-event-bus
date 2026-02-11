"""Parser for repr-style message strings: module.path.ClassName(args)."""

import ast
from typing import Any, Dict, List, Tuple

from ..interfaces import EventMessage
from ..utils import ModuleImporter
from .base import MessageParserBase


class ReprMessageParser(MessageParserBase):
    """
    Parses event message strings in the form:
    mymodule.MyMessage(1, x=2)
    into EventMessage instances.
    """

    def __init__(self, message_string: str) -> None:
        (
            self.module_path,
            self.class_name,
            self.param_string,
        ) = self.get_message_components(message_string)
        self.module_importer = ModuleImporter(self.module_path)

    @staticmethod
    def get_message_components(message_string: str) -> Tuple[str, str, str]:
        """
        Split message string into (module_path, class_name, param_string).
        """

        def strip_last_parens(s: str) -> str:
            pos = s.rfind(")")
            if pos != -1:
                s = s[:pos] + s[pos + 1 :]
            return s

        module_name, param_string = strip_last_parens(message_string).split("(", 1)
        module_parts = module_name.split(".")
        class_name = module_parts.pop(-1)
        module_path = ".".join(module_parts)
        return module_path, class_name, param_string

    def initialize(self) -> EventMessage:
        """Create an instance of the message class with its parameters."""
        args, kwargs = self.parse_args(self.param_string)
        return self.module_importer.get_class(self.class_name)(*args, **kwargs)

    def parse_args(self, args: str) -> Tuple[List[Any], Dict[str, Any]]:
        """Parse a string of Python arguments into args and kwargs."""
        args_str = "f({})".format(args)
        tree = ast.parse(args_str)
        funccall = tree.body[0].value

        parsed_args = [self._eval_arg(arg) for arg in funccall.args]
        parsed_kwargs = {
            arg.arg: self._eval_arg(arg.value) for arg in funccall.keywords
        }
        return parsed_args, parsed_kwargs

    def _eval_arg(self, arg: ast.AST) -> Any:
        """Convert an AST argument node to a Python value."""
        if isinstance(arg, ast.Name):
            if arg.id == "None":
                return None
            if arg.id == "True":
                return True
            if arg.id == "False":
                return False
            if arg.id == "nan":
                return None
            raise ValueError(f"Unsupported name: {arg.id}")

        try:
            return ast.literal_eval(arg)
        except (ValueError, SyntaxError):
            if isinstance(arg, ast.Call):
                module_name, _, class_str = arg.func.id.partition(".")
                try:
                    module_importer = ModuleImporter(module_name)
                    class_ = module_importer.get_class(class_str)
                except ImportError:
                    class_ = self.module_importer.get_class(module_name)

                call_args = [self._eval_arg(a) for a in arg.args]
                call_kwargs = {k.arg: self._eval_arg(k.value) for k in arg.keywords}
                return class_(*call_args, **call_kwargs)
            if isinstance(arg, ast.List):
                return [self._eval_arg(a) for a in arg.elts]
            if isinstance(arg, ast.Dict):
                return {
                    self._eval_arg(k): self._eval_arg(v)
                    for k, v in zip(arg.keys, arg.values)
                }
            raise ValueError(f"Unsupported arg type: {type(arg)}")
