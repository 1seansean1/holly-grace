from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.mcp.jsonschema import jsonschema_to_pydantic_model


def test_jsonschema_to_pydantic_required_and_optional():
    Model = jsonschema_to_pydantic_model(
        "X",
        {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient"},
                "count": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["to"],
        },
    )

    ok = Model(to="a@example.com", count=2, tags=["x", "y"])
    assert ok.to == "a@example.com"
    assert ok.count == 2
    assert ok.tags == ["x", "y"]

    with pytest.raises(ValidationError):
        Model(count=1)


def test_jsonschema_enum_literal():
    Model = jsonschema_to_pydantic_model(
        "EnumModel",
        {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["low", "high"]}},
            "required": ["mode"],
        },
    )
    ok = Model(mode="low")
    assert ok.mode == "low"
    with pytest.raises(ValidationError):
        Model(mode="medium")

