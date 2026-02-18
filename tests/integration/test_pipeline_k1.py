"""Integration test: full pipeline YAML → registry → decorator → K1 gate.

Task 3a.8 — Validate that the complete processing chain works end-to-end:

1. Load architecture.yaml via ArchitectureRegistry
2. Register an ICD JSON Schema in SchemaRegistry
3. Decorate a function with @kernel_boundary(gate_id="K1", icd_schema=...)
4. Call the decorated function with valid and invalid payloads
5. Assert: valid passes through, invalid raises ValidationError

This proves the four independently-built subsystems (parser → registry →
decorator → kernel gate) integrate correctly at their boundaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from holly.arch.decorators import get_holly_meta, kernel_boundary
from holly.arch.registry import ArchitectureRegistry
from holly.kernel.exceptions import (
    PayloadTooLargeError,
    SchemaNotFoundError,
    ValidationError,
)
from holly.kernel.schema_registry import SchemaRegistry

# ── Repo root & SAD path ───────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARCH_YAML = _REPO_ROOT / "docs" / "architecture.yaml"
_SAD_FILE = _REPO_ROOT / "docs" / "architecture" / "SAD_0.1.0.5.mermaid"

# ── ICD-006 test schema (Core ↔ Kernel boundary) ──────────────────────

ICD_006_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "payload": {"type": "object"},
    },
    "required": ["name", "version"],
    "additionalProperties": False,
}

# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registries() -> Any:
    """Reset both registries before and after each test."""
    SchemaRegistry.clear()
    ArchitectureRegistry.reset()
    yield
    SchemaRegistry.clear()
    ArchitectureRegistry.reset()


@pytest.fixture()
def loaded_arch_registry() -> ArchitectureRegistry:
    """Load the real architecture.yaml into the ArchitectureRegistry."""
    if not _ARCH_YAML.exists():
        pytest.skip("architecture.yaml not found — run extraction first")
    ArchitectureRegistry.configure(_ARCH_YAML)
    return ArchitectureRegistry.get()


@pytest.fixture()
def icd_006_registered() -> str:
    """Register ICD-006 test schema and return the schema_id."""
    schema_id = "ICD-006"
    SchemaRegistry.register(schema_id, ICD_006_SCHEMA)
    return schema_id


# ── Decorated endpoint under test ─────────────────────────────────────


def _make_k1_endpoint(schema_id: str) -> Any:
    """Create a @kernel_boundary decorated function enforcing K1.

    Returns a decorated function that validates its first argument
    against the given ICD schema via the K1 gate.
    """

    @kernel_boundary(
        gate_id="K1",
        invariant="schema_validation",
        icd_schema=schema_id,
        icd_field=0,
        validate=False,  # skip component_id check for unit-level wiring
    )
    def process_message(message: dict[str, Any]) -> dict[str, Any]:
        """Example endpoint: accepts a validated message, returns it."""
        return {"status": "processed", "input": message}

    return process_message


# ══════════════════════════════════════════════════════════════════════
# AC1: Valid schema passes through decorated endpoint
# ══════════════════════════════════════════════════════════════════════


class TestValidPayloadPassesK1:
    """Acceptance criterion 1: valid payloads pass through the full pipeline."""

    def test_valid_message_returns_result(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        valid_msg = {"name": "test-event", "version": "1.0.0"}

        result = endpoint(valid_msg)

        assert result["status"] == "processed"
        assert result["input"] == valid_msg

    def test_valid_message_with_optional_payload(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        valid_msg = {
            "name": "config-update",
            "version": "2.1.0",
            "payload": {"key": "value"},
        }

        result = endpoint(valid_msg)

        assert result["status"] == "processed"
        assert result["input"]["payload"] == {"key": "value"}

    def test_decorator_attaches_k1_metadata(
        self, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        meta = get_holly_meta(endpoint)

        assert meta is not None
        assert meta["kind"] == "kernel_boundary"
        assert meta["gate_id"] == "K1"
        assert meta["invariant"] == "schema_validation"
        assert meta["icd_schema"] == "ICD-006"

    def test_pipeline_with_real_architecture_yaml(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        """Prove the full chain: real YAML → registry → decorator → K1."""
        # Verify architecture loaded successfully
        reg = ArchitectureRegistry.get()
        assert reg.document.component_count >= 48

        # Verify schema registry has our ICD
        assert SchemaRegistry.has("ICD-006")

        # Invoke the decorated endpoint
        endpoint = _make_k1_endpoint(icd_006_registered)
        result = endpoint({"name": "full-chain-test", "version": "0.0.1"})

        assert result["status"] == "processed"


# ══════════════════════════════════════════════════════════════════════
# AC2: Invalid payload raises ValidationError
# ══════════════════════════════════════════════════════════════════════


class TestInvalidPayloadRaisesValidationError:
    """Acceptance criterion 2: invalid payloads raise ValidationError."""

    def test_missing_required_field_raises(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # Missing "version" (required)
        invalid_msg: dict[str, Any] = {"name": "test-event"}

        with pytest.raises(ValidationError) as exc_info:
            endpoint(invalid_msg)

        assert exc_info.value.schema_id == "ICD-006"
        assert len(exc_info.value.errors) >= 1
        assert any("version" in e["message"] for e in exc_info.value.errors)

    def test_wrong_type_raises(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # "version" should be string, not int
        invalid_msg = {"name": "test-event", "version": 42}

        with pytest.raises(ValidationError) as exc_info:
            endpoint(invalid_msg)

        assert exc_info.value.schema_id == "ICD-006"

    def test_additional_properties_rejected(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # "extra" is not in schema, additionalProperties=False
        invalid_msg = {
            "name": "test-event",
            "version": "1.0.0",
            "extra": "not_allowed",
        }

        with pytest.raises(ValidationError):
            endpoint(invalid_msg)

    def test_empty_name_rejected(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # "name" has minLength=1
        invalid_msg = {"name": "", "version": "1.0.0"}

        with pytest.raises(ValidationError):
            endpoint(invalid_msg)

    def test_malformed_version_rejected(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # version must match ^\d+\.\d+\.\d+$
        invalid_msg = {"name": "test", "version": "not-a-version"}

        with pytest.raises(ValidationError):
            endpoint(invalid_msg)

    def test_validation_error_includes_payload_hash(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        invalid_msg: dict[str, Any] = {"name": "test"}

        with pytest.raises(ValidationError) as exc_info:
            endpoint(invalid_msg)

        # payload_hash should be a non-empty hex string
        assert len(exc_info.value.payload_hash) == 64  # SHA-256


# ══════════════════════════════════════════════════════════════════════
# Edge cases: schema not registered, payload too large
# ══════════════════════════════════════════════════════════════════════


class TestPipelineEdgeCases:
    """Edge cases that exercise error paths in the full pipeline."""

    def test_unregistered_schema_raises_not_found(
        self, loaded_arch_registry: Any
    ) -> None:
        # Don't register any schema — decorator references missing ICD
        endpoint = _make_k1_endpoint("ICD-MISSING")
        msg = {"name": "test", "version": "1.0.0"}

        with pytest.raises(SchemaNotFoundError) as exc_info:
            endpoint(msg)

        assert exc_info.value.schema_id == "ICD-MISSING"

    def test_deeply_nested_payload_raises_too_large(
        self, loaded_arch_registry: Any, icd_006_registered: str
    ) -> None:
        endpoint = _make_k1_endpoint(icd_006_registered)
        # Build a payload that exceeds max nesting depth (default 20)
        deep: dict[str, Any] = {"name": "deep", "version": "1.0.0"}
        current = deep
        for _ in range(25):
            inner: dict[str, Any] = {}
            current["nested"] = inner
            current = inner

        with pytest.raises(PayloadTooLargeError):
            endpoint(deep)

    def test_oversized_payload_raises_too_large(
        self, icd_006_registered: str
    ) -> None:
        from holly.kernel.k1 import k1_validate

        # Directly call k1_validate with a small max_bytes to test the guard
        # without allocating a huge payload (default limit is 10MB)
        msg = {"name": "test", "version": "1.0.0"}

        with pytest.raises(PayloadTooLargeError):
            k1_validate(msg, icd_006_registered, max_bytes=10)
