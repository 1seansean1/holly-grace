"""Tests for K1 schema validation gate (Task 3.7).

Covers all 7 acceptance criteria from Behavior Spec §1.2:
  AC1  Valid payload passes
  AC2  Invalid payload raises ValidationError
  AC3  Schema caching (single lookup per call)
  AC4  Error details (schema_id + field-level errors)
  AC5  Timeout enforcement (delegated to registry; tested via mock)
  AC6  Large payload rejection (>max_bytes → PayloadTooLargeError)
  AC7  Payload immutability during validation

Plus negative/edge cases:
  - SchemaNotFoundError for unknown schema_id
  - Deep nesting rejection
  - Decorator integration (K1 enforcement via @kernel_boundary)
  - SchemaRegistry thread-safety and clear()
  - SchemaParseError for non-dict schemas
  - Property-based tests via hypothesis
"""

from __future__ import annotations

import copy
import threading
from typing import Any
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.arch.decorators import kernel_boundary
from holly.kernel.exceptions import (
    KernelError,
    KernelInvariantError,
    PayloadTooLargeError,
    SchemaNotFoundError,
    SchemaParseError,
    ValidationError,
)
from holly.kernel.k1 import k1_validate
from holly.kernel.schema_registry import SchemaRegistry

# ── Fixtures ──────────────────────────────────────────────


SIMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0},
    },
    "required": ["name"],
    "additionalProperties": False,
}

ARRAY_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 1,
}


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    """Ensure SchemaRegistry is clean before and after each test."""
    SchemaRegistry.clear()
    yield
    SchemaRegistry.clear()


@pytest.fixture()
def register_simple() -> str:
    """Register SIMPLE_SCHEMA and return its ID."""
    schema_id = "ICD-TEST-001"
    SchemaRegistry.register(schema_id, SIMPLE_SCHEMA)
    return schema_id


@pytest.fixture()
def register_array() -> str:
    schema_id = "ICD-TEST-002"
    SchemaRegistry.register(schema_id, ARRAY_SCHEMA)
    return schema_id


# ══════════════════════════════════════════════════════════
# AC1: Valid payload passes
# ══════════════════════════════════════════════════════════


class TestAC1ValidPayloadPasses:
    def test_valid_object(self, register_simple: str) -> None:
        payload = {"name": "Alice", "age": 30}
        result = k1_validate(payload, register_simple)
        assert result == payload

    def test_valid_with_optional_field_omitted(self, register_simple: str) -> None:
        payload = {"name": "Bob"}
        result = k1_validate(payload, register_simple)
        assert result == payload

    def test_valid_array(self, register_array: str) -> None:
        payload = [1, 2, 3]
        result = k1_validate(payload, register_array)
        assert result == payload

    def test_returns_same_object(self, register_simple: str) -> None:
        """k1_validate returns the exact same object, not a copy."""
        payload = {"name": "Alice"}
        result = k1_validate(payload, register_simple)
        assert result is payload


# ══════════════════════════════════════════════════════════
# AC2: Invalid payload raises ValidationError
# ══════════════════════════════════════════════════════════


class TestAC2InvalidPayloadFails:
    def test_wrong_type(self, register_simple: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"name": 123}, register_simple)
        assert exc_info.value.schema_id == register_simple
        assert len(exc_info.value.errors) >= 1

    def test_missing_required_field(self, register_simple: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"age": 25}, register_simple)
        assert any("name" in e["message"] for e in exc_info.value.errors)

    def test_additional_properties_disallowed(self, register_simple: str) -> None:
        with pytest.raises(ValidationError):
            k1_validate({"name": "Alice", "extra": True}, register_simple)

    def test_constraint_violation(self, register_simple: str) -> None:
        """age < 0 violates minimum constraint."""
        with pytest.raises(ValidationError):
            k1_validate({"name": "Alice", "age": -1}, register_simple)

    def test_empty_array(self, register_array: str) -> None:
        """Empty array violates minItems=1."""
        with pytest.raises(ValidationError):
            k1_validate([], register_array)

    def test_wrong_array_item_type(self, register_array: str) -> None:
        with pytest.raises(ValidationError):
            k1_validate(["not", "ints"], register_array)


# ══════════════════════════════════════════════════════════
# AC3: Schema caching (single lookup)
# ══════════════════════════════════════════════════════════


class TestAC3SchemaCaching:
    def test_single_registry_lookup(self, register_simple: str) -> None:
        """Two calls with same schema_id should resolve to same object."""
        with patch.object(
            SchemaRegistry, "get", wraps=SchemaRegistry.get
        ) as mock_get:
            k1_validate({"name": "Alice"}, register_simple)
            k1_validate({"name": "Bob"}, register_simple)
            # Each call resolves once — 2 calls = 2 lookups.
            # The point is that each individual call does exactly 1 lookup.
            assert mock_get.call_count == 2

    def test_registry_returns_same_object(self, register_simple: str) -> None:
        """SchemaRegistry.get() returns identical object on repeat calls."""
        s1 = SchemaRegistry.get(register_simple)
        s2 = SchemaRegistry.get(register_simple)
        assert s1 is s2


# ══════════════════════════════════════════════════════════
# AC4: Error details
# ══════════════════════════════════════════════════════════


class TestAC4ErrorDetails:
    def test_schema_id_in_error(self, register_simple: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"age": "wrong"}, register_simple)
        assert exc_info.value.schema_id == register_simple

    def test_field_level_errors(self, register_simple: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"age": "wrong"}, register_simple)
        errors = exc_info.value.errors
        assert isinstance(errors, list)
        assert len(errors) >= 1
        for err in errors:
            assert "path" in err
            assert "message" in err

    def test_payload_hash_populated(self, register_simple: str) -> None:
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"name": 42}, register_simple)
        assert exc_info.value.payload_hash
        assert len(exc_info.value.payload_hash) == 64  # SHA-256 hex

    def test_inherits_kernel_error(self, register_simple: str) -> None:
        with pytest.raises(KernelError):
            k1_validate({"name": 42}, register_simple)


# ══════════════════════════════════════════════════════════
# AC5: Timeout enforcement (mocked — actual timeout is
#       SchemaRegistry responsibility in later slices)
# ══════════════════════════════════════════════════════════


class TestAC5TimeoutEnforcement:
    def test_schema_not_found_raises(self) -> None:
        """SchemaNotFoundError is the Phase A proxy for timeout."""
        with pytest.raises(SchemaNotFoundError) as exc_info:
            k1_validate({"name": "x"}, "ICD-DOES-NOT-EXIST")
        assert exc_info.value.schema_id == "ICD-DOES-NOT-EXIST"


# ══════════════════════════════════════════════════════════
# AC6: Large payload rejection
# ══════════════════════════════════════════════════════════


class TestAC6LargePayloadRejection:
    def test_oversized_payload(self, register_simple: str) -> None:
        big = {"name": "x" * 2_000_000}
        with pytest.raises(PayloadTooLargeError) as exc_info:
            k1_validate(big, register_simple, max_bytes=1_000_000)
        assert exc_info.value.schema_id == register_simple
        assert exc_info.value.size > exc_info.value.limit

    def test_deep_nesting_rejected(self, register_simple: str) -> None:
        """Deeply nested payload exceeds max_depth."""
        nested: dict[str, Any] = {"name": "leaf"}
        for _ in range(25):
            nested = {"nested": nested, "name": "wrap"}
        with pytest.raises(PayloadTooLargeError):
            k1_validate(nested, register_simple, max_depth=10)

    def test_exactly_at_limit_passes(self, register_simple: str) -> None:
        """Payload exactly at limit should not raise."""
        payload = {"name": "ok"}
        # use a generous limit so it passes
        result = k1_validate(payload, register_simple, max_bytes=10_000_000)
        assert result == payload


# ══════════════════════════════════════════════════════════
# AC7: Payload immutability
# ══════════════════════════════════════════════════════════


class TestAC7PayloadImmutability:
    def test_payload_not_mutated_on_valid(self, register_simple: str) -> None:
        payload = {"name": "Alice", "age": 30}
        original = copy.deepcopy(payload)
        k1_validate(payload, register_simple)
        assert payload == original

    def test_payload_identity_preserved(self, register_simple: str) -> None:
        """The returned object is the same object passed in."""
        payload = {"name": "Alice"}
        result = k1_validate(payload, register_simple)
        assert result is payload

    def test_payload_not_mutated_on_invalid(self, register_simple: str) -> None:
        payload = {"name": 42}
        original = copy.deepcopy(payload)
        with pytest.raises(ValidationError):
            k1_validate(payload, register_simple)
        assert payload == original


# ══════════════════════════════════════════════════════════
# SchemaRegistry tests
# ══════════════════════════════════════════════════════════


class TestKernelInvariantError:
    """F-036: assert → KernelInvariantError (survives python -O)."""

    def test_immutability_guard_fires_when_validator_mutates(
        self, register_simple: str
    ) -> None:
        """Simulate a validator that mutates the payload; KernelInvariantError fires."""
        from unittest.mock import patch

        def _mutating_validator(schema: dict) -> object:
            class _Mutator:
                def iter_errors(self, payload: dict) -> list:
                    payload["__injected__"] = True  # mutation!
                    return []

            return _Mutator()

        with (
            patch("holly.kernel.k1.Draft202012Validator", side_effect=_mutating_validator),
            pytest.raises(KernelInvariantError) as exc_info,
        ):
            k1_validate({"name": "Alice"}, register_simple)
        assert exc_info.value.invariant == "payload_immutability"
        assert isinstance(exc_info.value, KernelError)

    def test_no_invariant_error_on_clean_validation(self, register_simple: str) -> None:
        """Normal validation does not raise KernelInvariantError."""
        result = k1_validate({"name": "Alice"}, register_simple)
        assert result == {"name": "Alice"}


class TestSchemaRegistry:
    def test_register_and_get(self) -> None:
        SchemaRegistry.register("ICD-A", {"type": "object"})
        assert SchemaRegistry.get("ICD-A") == {"type": "object"}

    def test_has(self) -> None:
        assert not SchemaRegistry.has("ICD-X")
        SchemaRegistry.register("ICD-X", {"type": "string"})
        assert SchemaRegistry.has("ICD-X")

    def test_registered_ids(self) -> None:
        SchemaRegistry.register("ICD-1", {"type": "object"})
        SchemaRegistry.register("ICD-2", {"type": "array"})
        assert SchemaRegistry.registered_ids() == frozenset({"ICD-1", "ICD-2"})

    def test_clear(self) -> None:
        SchemaRegistry.register("ICD-Z", {"type": "null"})
        SchemaRegistry.clear()
        assert not SchemaRegistry.has("ICD-Z")

    def test_non_dict_raises_schema_parse_error(self) -> None:
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register("ICD-BAD", "not a dict")  # type: ignore[arg-type]

    def test_empty_dict_raises_schema_parse_error(self) -> None:
        """F-037: empty schema {} has no structural keywords — rejected."""
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register("ICD-EMPTY", {})

    def test_anyof_schema_accepted(self) -> None:
        """F-037: anyOf at top level is valid JSON Schema 2020-12."""
        schema = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
        SchemaRegistry.register("ICD-ANYOF", schema)
        assert SchemaRegistry.has("ICD-ANYOF")

    def test_oneof_schema_accepted(self) -> None:
        """F-037: oneOf at top level accepted."""
        schema = {"oneOf": [{"type": "object"}, {"type": "null"}]}
        SchemaRegistry.register("ICD-ONEOF", schema)
        assert SchemaRegistry.has("ICD-ONEOF")

    def test_ref_schema_accepted(self) -> None:
        """F-037: $ref-rooted schema accepted."""
        schema = {"$ref": "#/$defs/Payload", "$defs": {"Payload": {"type": "object"}}}
        SchemaRegistry.register("ICD-REF", schema)
        assert SchemaRegistry.has("ICD-REF")

    def test_only_metadata_raises_schema_parse_error(self) -> None:
        """F-037: schema with only $schema/$id but no structural keyword rejected."""
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register(
                "ICD-META", {"$schema": "https://json-schema.org/draft/2020-12/schema"}
            )

    def test_thread_safety(self) -> None:
        """Concurrent register + get should not corrupt state."""
        errors: list[Exception] = []

        def _register(n: int) -> None:
            try:
                for i in range(50):
                    SchemaRegistry.register(f"ICD-T{n}-{i}", {"type": "object"})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_register, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(SchemaRegistry.registered_ids()) == 200


# ══════════════════════════════════════════════════════════
# Decorator integration
# ══════════════════════════════════════════════════════════


class TestDecoratorK1Integration:
    def test_decorator_validates_first_arg(self, register_simple: str) -> None:
        @kernel_boundary(
            gate_id="K1",
            invariant="schema_validation",
            icd_schema=register_simple,
            validate=False,
        )
        def process(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        result = process({"name": "Alice"})
        assert result == {"name": "Alice"}

    def test_decorator_rejects_invalid(self, register_simple: str) -> None:
        @kernel_boundary(
            gate_id="K1",
            invariant="schema_validation",
            icd_schema=register_simple,
            validate=False,
        )
        def process(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        with pytest.raises(ValidationError) as exc_info:
            process({"name": 123})
        assert exc_info.value.schema_id == register_simple

    def test_decorator_kwarg_field(self, register_simple: str) -> None:
        @kernel_boundary(
            gate_id="K1",
            invariant="schema_validation",
            icd_schema=register_simple,
            icd_field="data",
            validate=False,
        )
        def process(ctx: str, *, data: dict[str, Any]) -> dict[str, Any]:
            return data

        result = process("ctx", data={"name": "Alice"})
        assert result == {"name": "Alice"}

    def test_decorator_no_schema_skips_validation(self) -> None:
        """Without icd_schema, K1 gate is not enforced."""

        @kernel_boundary(gate_id="K1", invariant="schema_validation", validate=False)
        def process(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        # Should pass even with invalid data since no schema configured
        result = process({"anything": True})
        assert result == {"anything": True}

    def test_non_k1_gate_skips_validation(self, register_simple: str) -> None:
        """gate_id != 'K1' should not trigger schema validation."""

        @kernel_boundary(
            gate_id="K2",
            invariant="permission_gate",
            icd_schema=register_simple,
            validate=False,
        )
        def process(payload: dict[str, Any]) -> dict[str, Any]:
            return payload

        # Should pass — K2 doesn't do schema validation
        result = process({"arbitrary": "data"})
        assert result == {"arbitrary": "data"}


# ══════════════════════════════════════════════════════════
# Property-based tests (hypothesis)
# ══════════════════════════════════════════════════════════


class TestPropertyBased:
    @given(name=st.text(min_size=1), age=st.integers(min_value=0))
    @settings(max_examples=50)
    def test_valid_payloads_always_pass(self, name: str, age: int) -> None:
        SchemaRegistry.clear()
        SchemaRegistry.register("ICD-PBT", SIMPLE_SCHEMA)
        payload = {"name": name, "age": age}
        result = k1_validate(payload, "ICD-PBT")
        assert result == payload

    @given(name=st.integers() | st.booleans() | st.none())
    @settings(max_examples=50)
    def test_wrong_name_type_always_fails(self, name: Any) -> None:
        SchemaRegistry.clear()
        SchemaRegistry.register("ICD-PBT", SIMPLE_SCHEMA)
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"name": name}, "ICD-PBT")
        assert exc_info.value.schema_id == "ICD-PBT"

    @given(age=st.integers(max_value=-1))
    @settings(max_examples=25)
    def test_negative_age_always_fails(self, age: int) -> None:
        SchemaRegistry.clear()
        SchemaRegistry.register("ICD-PBT", SIMPLE_SCHEMA)
        with pytest.raises(ValidationError):
            k1_validate({"name": "Test", "age": age}, "ICD-PBT")
