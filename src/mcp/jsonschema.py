"""Limited JSON Schema -> Pydantic model conversion for MCP tool inputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, create_model


def _primitive_type(type_name: str) -> type:
    if type_name == "string":
        return str
    if type_name == "number":
        return float
    if type_name == "integer":
        return int
    if type_name == "boolean":
        return bool
    return Any


def _schema_to_type(schema: dict[str, Any]) -> type:
    t = schema.get("type")

    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        values: list[Any] = []
        for v in enum:
            try:
                hash(v)
                values.append(v)
            except Exception:
                pass
        if values:
            return Literal[tuple(values)]  # type: ignore[misc]

    if t == "array":
        items = schema.get("items") or {}
        item_t = _schema_to_type(items) if isinstance(items, dict) else Any
        return list[item_t]  # type: ignore[valid-type]

    if isinstance(t, str):
        return _primitive_type(t)

    return Any


def jsonschema_to_pydantic_model(model_name: str, schema: dict[str, Any] | None) -> type[BaseModel]:
    """Convert a subset of JSON schema into a pydantic model class.

    Supported:
    - type=object with properties + required
    - primitives: string, number, integer, boolean
    - arrays of primitives
    - enum -> Literal
    """
    schema = schema or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    fields: dict[str, tuple[type, Any]] = {}
    if isinstance(props, dict):
        for name, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                continue

            py_type = _schema_to_type(prop_schema)
            desc = prop_schema.get("description", "")
            default = prop_schema.get("default")

            if name in required:
                fields[name] = (py_type, Field(..., description=desc))
            else:
                if default is None:
                    fields[name] = (py_type | None, Field(None, description=desc))
                else:
                    fields[name] = (py_type | None, Field(default, description=desc))

    if not fields:
        return create_model(model_name, __base__=BaseModel)  # type: ignore[call-arg]

    return create_model(model_name, __base__=BaseModel, **fields)  # type: ignore[call-arg]

