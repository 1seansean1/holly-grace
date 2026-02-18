"""Tests for holly.kernel.icd_schema_registry — Task 5.8.

Coverage:
    - ICDSchemaRegistry: register, resolve, has, registered_ids, validate,
      clear, evict_stale, set_ttl
    - TTL expiration and lazy eviction
    - Thread safety
    - Error paths: missing schema, duplicate, non-BaseModel, expired
    - Performance: resolution < 1ms
    - Property-based: arbitrary model registration roundtrip
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from holly.kernel.exceptions import SchemaNotFoundError
from holly.kernel.icd_schema_registry import (
    DEFAULT_TTL_SECONDS,
    ICDModelAlreadyRegisteredError,
    ICDSchemaRegistry,
    ICDValidationError,
)

# ── Fixtures ─────────────────────────────────────────────


class SampleModel(BaseModel):
    """Minimal test model."""

    name: str
    value: int


class AnotherModel(BaseModel):
    """Second test model."""

    x: float
    y: float


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    """Ensure clean registry state for each test."""
    ICDSchemaRegistry.clear()
    yield
    ICDSchemaRegistry.clear()


# ── TestRegisterAndResolve ───────────────────────────────


class TestRegisterAndResolve:
    """AC: Resolves schema_id to Pydantic model for all 49 ICDs."""

    def test_register_and_resolve(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        result = ICDSchemaRegistry.resolve("ICD-001")
        assert result is SampleModel

    def test_register_multiple_schemas(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        ICDSchemaRegistry.register("ICD-002", AnotherModel)
        assert ICDSchemaRegistry.resolve("ICD-001") is SampleModel
        assert ICDSchemaRegistry.resolve("ICD-002") is AnotherModel

    def test_has_registered(self) -> None:
        ICDSchemaRegistry.register("ICD-010", SampleModel)
        assert ICDSchemaRegistry.has("ICD-010") is True
        assert ICDSchemaRegistry.has("ICD-999") is False

    def test_registered_ids(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        ICDSchemaRegistry.register("ICD-002", AnotherModel)
        ids = ICDSchemaRegistry.registered_ids()
        assert ids == frozenset({"ICD-001", "ICD-002"})

    def test_resolve_missing_raises(self) -> None:
        with pytest.raises(SchemaNotFoundError, match="ICD-999"):
            ICDSchemaRegistry.resolve("ICD-999")

    def test_duplicate_registration_raises(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        with pytest.raises(ICDModelAlreadyRegisteredError, match="ICD-001"):
            ICDSchemaRegistry.register("ICD-001", AnotherModel)

    def test_register_non_basemodel_raises(self) -> None:
        with pytest.raises(TypeError, match="Expected BaseModel subclass"):
            ICDSchemaRegistry.register("ICD-001", dict)  # type: ignore[arg-type]

    def test_register_instance_raises(self) -> None:
        """Must pass the class, not an instance."""
        with pytest.raises(TypeError, match="Expected BaseModel subclass"):
            ICDSchemaRegistry.register("ICD-001", SampleModel(name="a", value=1))  # type: ignore[arg-type]

    def test_clear_removes_all(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        ICDSchemaRegistry.clear()
        assert ICDSchemaRegistry.has("ICD-001") is False
        assert ICDSchemaRegistry.registered_ids() == frozenset()


# ── TestTTLCache ─────────────────────────────────────────


class TestTTLCache:
    """AC: Schema caching with 1h TTL."""

    def test_default_ttl_is_one_hour(self) -> None:
        assert DEFAULT_TTL_SECONDS == 3600.0

    def test_set_ttl(self) -> None:
        ICDSchemaRegistry.set_ttl(7200.0)
        assert ICDSchemaRegistry.get_ttl() == 7200.0

    def test_set_ttl_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ICDSchemaRegistry.set_ttl(-1.0)

    def test_set_ttl_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            ICDSchemaRegistry.set_ttl(0.0)

    def test_expired_entry_evicted_on_resolve(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        time.sleep(0.02)
        with pytest.raises(SchemaNotFoundError, match="ICD-001"):
            ICDSchemaRegistry.resolve("ICD-001")

    def test_expired_entry_evicted_on_has(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        time.sleep(0.02)
        assert ICDSchemaRegistry.has("ICD-001") is False

    def test_expired_entry_excluded_from_registered_ids(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        ICDSchemaRegistry.register("ICD-002", AnotherModel, ttl=600.0)
        time.sleep(0.02)
        ids = ICDSchemaRegistry.registered_ids()
        assert "ICD-001" not in ids
        assert "ICD-002" in ids

    def test_evict_stale_returns_count(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        ICDSchemaRegistry.register("ICD-002", AnotherModel, ttl=0.01)
        ICDSchemaRegistry.register("ICD-003", SampleModel, ttl=600.0)
        time.sleep(0.02)
        evicted = ICDSchemaRegistry.evict_stale()
        assert evicted == 2
        assert ICDSchemaRegistry.has("ICD-003") is True

    def test_reregister_after_expiry(self) -> None:
        """After TTL expires, the same schema_id can be re-registered."""
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        time.sleep(0.02)
        # Should not raise - old entry expired
        ICDSchemaRegistry.register("ICD-001", AnotherModel)
        assert ICDSchemaRegistry.resolve("ICD-001") is AnotherModel

    def test_per_entry_ttl_override(self) -> None:
        ICDSchemaRegistry.set_ttl(0.01)
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=600.0)
        time.sleep(0.02)
        # Global TTL is tiny but per-entry override keeps it alive
        assert ICDSchemaRegistry.has("ICD-001") is True


# ── TestValidate ─────────────────────────────────────────


class TestValidate:
    """Validate payload against Pydantic model."""

    def test_valid_payload_returns_model_instance(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        result = ICDSchemaRegistry.validate("ICD-001", {"name": "test", "value": 42})
        assert isinstance(result, SampleModel)
        assert result.name == "test"
        assert result.value == 42

    def test_invalid_payload_raises_icd_validation_error(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        with pytest.raises(ICDValidationError, match="ICD-001") as exc_info:
            ICDSchemaRegistry.validate("ICD-001", {"name": "test", "value": "not_int"})
        assert len(exc_info.value.errors) >= 1
        assert exc_info.value.schema_id == "ICD-001"

    def test_missing_required_field(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel)
        with pytest.raises(ICDValidationError) as exc_info:
            ICDSchemaRegistry.validate("ICD-001", {"name": "test"})
        locs = [e["loc"] for e in exc_info.value.errors]
        assert any("value" in loc for loc in locs)

    def test_validate_unregistered_raises_not_found(self) -> None:
        with pytest.raises(SchemaNotFoundError):
            ICDSchemaRegistry.validate("ICD-999", {"name": "test", "value": 1})

    def test_validate_expired_raises_not_found(self) -> None:
        ICDSchemaRegistry.register("ICD-001", SampleModel, ttl=0.01)
        time.sleep(0.02)
        with pytest.raises(SchemaNotFoundError):
            ICDSchemaRegistry.validate("ICD-001", {"name": "test", "value": 1})


# ── TestPerformance ──────────────────────────────────────


class TestPerformance:
    """AC: Per ICD resolution time < 1ms (p99)."""

    def test_resolution_under_1ms(self) -> None:
        ICDSchemaRegistry.register("ICD-006", SampleModel)
        # Warm up
        ICDSchemaRegistry.resolve("ICD-006")

        timings: list[float] = []
        for _ in range(1000):
            start = time.perf_counter_ns()
            ICDSchemaRegistry.resolve("ICD-006")
            elapsed_ns = time.perf_counter_ns() - start
            timings.append(elapsed_ns)

        timings.sort()
        p99_ns = timings[int(len(timings) * 0.99)]
        p99_ms = p99_ns / 1_000_000
        assert p99_ms < 1.0, f"p99 resolution time {p99_ms:.3f}ms exceeds 1ms budget"

    def test_resolution_stable_with_many_entries(self) -> None:
        """Resolution should stay fast even with 49+ entries (all ICDs)."""
        for i in range(1, 50):
            ICDSchemaRegistry.register(f"ICD-{i:03d}", SampleModel)

        timings: list[float] = []
        for _ in range(500):
            start = time.perf_counter_ns()
            ICDSchemaRegistry.resolve("ICD-049")
            elapsed_ns = time.perf_counter_ns() - start
            timings.append(elapsed_ns)

        timings.sort()
        p99_ns = timings[int(len(timings) * 0.99)]
        p99_ms = p99_ns / 1_000_000
        assert p99_ms < 1.0, f"p99 resolution time {p99_ms:.3f}ms with 49 entries"


# ── TestThreadSafety ─────────────────────────────────────


class TestThreadSafety:
    """Concurrent access must not corrupt state."""

    def test_concurrent_register_and_resolve(self) -> None:
        errors: list[Exception] = []

        def register_batch(start: int) -> None:
            try:
                for i in range(start, start + 10):
                    ICDSchemaRegistry.register(f"T-{i:03d}", SampleModel)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register_batch, args=(i * 10,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        ids = ICDSchemaRegistry.registered_ids()
        assert len(ids) == 50


# ── TestAll49ICDs ────────────────────────────────────────


class TestAll49ICDs:
    """Simulate registering all 49 ICDs to verify capacity."""

    def test_register_all_49_icds(self) -> None:
        for i in range(1, 50):
            model = type(f"ICD{i:03d}Model", (BaseModel,), {"__annotations__": {"data": str}})
            ICDSchemaRegistry.register(f"ICD-{i:03d}", model)

        ids = ICDSchemaRegistry.registered_ids()
        assert len(ids) == 49
        for i in range(1, 50):
            assert ICDSchemaRegistry.has(f"ICD-{i:03d}")

    def test_resolve_each_of_49(self) -> None:
        models: dict[str, type[BaseModel]] = {}
        for i in range(1, 50):
            model = type(f"ICD{i:03d}Model", (BaseModel,), {"__annotations__": {"data": str}})
            schema_id = f"ICD-{i:03d}"
            ICDSchemaRegistry.register(schema_id, model)
            models[schema_id] = model

        for schema_id, expected_model in models.items():
            assert ICDSchemaRegistry.resolve(schema_id) is expected_model


# ── TestPropertyBased ────────────────────────────────────


class TestPropertyBased:
    """Hypothesis property-based tests for invariants."""

    @given(
        schema_id=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-"),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=50)
    def test_register_resolve_roundtrip(self, schema_id: str) -> None:
        """Registering then resolving returns the same model class."""
        ICDSchemaRegistry.clear()
        ICDSchemaRegistry.register(schema_id, SampleModel)
        assert ICDSchemaRegistry.resolve(schema_id) is SampleModel

    @given(
        schema_id=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-"),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=50)
    def test_has_matches_resolve(self, schema_id: str) -> None:
        """has() agrees with resolve() on existence."""
        ICDSchemaRegistry.clear()
        assert ICDSchemaRegistry.has(schema_id) is False
        ICDSchemaRegistry.register(schema_id, SampleModel)
        assert ICDSchemaRegistry.has(schema_id) is True

    @given(
        name=st.text(min_size=1, max_size=50),
        value=st.integers(),
    )
    @settings(max_examples=30)
    def test_validate_roundtrip(self, name: str, value: int) -> None:
        """Valid payloads always produce a valid model instance."""
        ICDSchemaRegistry.clear()
        ICDSchemaRegistry.register("TEST", SampleModel)
        result = ICDSchemaRegistry.validate("TEST", {"name": name, "value": value})
        assert result.name == name
        assert result.value == value
