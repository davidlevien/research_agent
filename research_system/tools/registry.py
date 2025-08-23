from typing import Any, Callable, Dict, get_origin, get_args, List, Optional, Type
from pydantic import BaseModel

Model = BaseModel

class ToolSpec(BaseModel):
    name: str
    fn: Callable[..., Any]
    input_model: Optional[Type[BaseModel]] = None
    output_model: Optional[Any] = None
    description: str = ""

class Registry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool name: {spec.name}")
        self._tools[spec.name] = spec

    def execute(self, name: str, payload: Dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool '{name}'")
        spec = self._tools[name]
        kwargs = payload or {}
        if spec.input_model:
            kwargs = spec.input_model(**kwargs).model_dump()

        result = spec.fn(**kwargs)

        if spec.output_model is not None:
            origin = get_origin(spec.output_model)
            if origin in (list, List):
                (inner,) = get_args(spec.output_model)
                if not isinstance(result, list):
                    raise TypeError(f"Tool '{name}' expected list output")
                for i, item in enumerate(result):
                    if not isinstance(item, inner):
                        raise TypeError(f"Tool '{name}' list item {i} not of type {inner}")
            else:
                if not isinstance(result, spec.output_model):
                    raise TypeError(f"Tool '{name}' returned {type(result)}; expected {spec.output_model}")

        return result

# ---- Compatibility: export ToolRegistry alias for backward compatibility ----
ToolRegistry = Registry

# ---- Compatibility shim for tests that expect a global registry ----
tool_registry = Registry()

def register_tool(spec: ToolSpec) -> None:
    tool_registry.register(spec)