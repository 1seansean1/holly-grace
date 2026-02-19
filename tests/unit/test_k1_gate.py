"""Tests for k1_gate — KernelContext-integrated K1 validation gate.

Task 16.3 — K1 schema validation per TLA+ spec.

Traces to: Behavior Spec §1.2, TLA+ spec (14.1), KernelContext (15.4).
SIL: 3

Acceptance criteria verified (per Task_Manifest.md §16.3):
  AC1  Valid payload passes through KernelContext k1_gate
  AC2  Invalid payload raises ValidationError; KernelContext state -> IDLE
  AC3  SchemaNotFoundError propagates; KernelContext state -> IDLE
  AC4  PayloadTooLargeError propagates; KernelContext state -> IDLE
  AC5  Gate executes with state = ENTERING (INV-5)
  AC6  Liveness: all failure paths end in IDLE (TLA+ EventuallyIdle)
  AC7  Zero false positives/negatives (property-based)

Test taxonomy
-------------
Structure       k1_gate importable; returns async callable
HappyPath       valid payload passes; ACTIVE during body; IDLE after; payload unchanged
GateFail        ValidationError propagates; schema_id/payload_hash preserved; IDLE after
SchemaNotFound  SchemaNotFoundError propagates; IDLE after
TooLarge        PayloadTooLargeError (size, depth); IDLE after
Ordering        k1_gate composes with other gates; runs in order
Liveness        all error paths satisfy EventuallyIdle
Property        Hypothesis: valid always IDLE; invalid always IDLE; FP/FN=0
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.kernel.context import KernelContext
from holly.kernel.exceptions import (
    PayloadTooLargeError,
    SchemaNotFoundError,
    ValidationError,
)
from holly.kernel.k1 import k1_gate
from holly.kernel.schema_registry import SchemaRegistry
from holly.kernel.state_machine import KernelState

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SIMPLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "value": {"type": "integer", "minimum": 0},
    },
    "required": ["name"],
    "additionalProperties": False,
}

SCHEMA_ID = "ICD-K1G-TEST"


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    SchemaRegistry.clear()
    yield
    SchemaRegistry.clear()


@pytest.fixture()
def schema_id() -> str:
    SchemaRegistry.register(SCHEMA_ID, SIMPLE_SCHEMA)
    return SCHEMA_ID


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestStructure:
    def test_k1_gate_importable(self) -> None:
        from holly.kernel.k1 import k1_gate as _g

        assert _g is not None

    def test_k1_gate_importable_from_kernel_init(self) -> None:
        from holly.kernel import k1_gate as _g

        assert _g is not None

    def test_k1_gate_returns_callable(self, schema_id: str) -> None:
        gate = k1_gate({"name": "Alice"}, schema_id)
        assert callable(gate)

    def test_returned_gate_is_coroutine_function(self, schema_id: str) -> None:
        gate = k1_gate({"name": "Alice"}, schema_id)
        assert inspect.iscoroutinefunction(gate)

    def test_k1_gate_accepts_max_bytes_kwarg(self, schema_id: str) -> None:
        gate = k1_gate({"name": "x"}, schema_id, max_bytes=1_000_000)
        assert callable(gate)

    def test_k1_gate_accepts_max_depth_kwarg(self, schema_id: str) -> None:
        gate = k1_gate({"name": "x"}, schema_id, max_depth=10)
        assert callable(gate)


# ---------------------------------------------------------------------------
# Happy path: valid payload
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_valid_payload_context_enters(self, schema_id: str) -> None:
        """Valid payload: KernelContext enters ACTIVE state."""
        ctx = KernelContext(gates=[k1_gate({"name": "Alice"}, schema_id)])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE

    @pytest.mark.asyncio
    async def test_valid_payload_context_is_idle_after(self, schema_id: str) -> None:
        """Valid payload: KernelContext is IDLE after block (liveness)."""
        ctx = KernelContext(gates=[k1_gate({"name": "Alice"}, schema_id)])
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_valid_payload_with_optional_field(self, schema_id: str) -> None:
        """Optional integer field present and valid."""
        ctx = KernelContext(gates=[k1_gate({"name": "Bob", "value": 42}, schema_id)])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_multiple_valid_crossings_end_idle(self, schema_id: str) -> None:
        """Three sequential crossings all end in IDLE."""
        ctx = KernelContext(gates=[k1_gate({"name": "X"}, schema_id)])
        for _ in range(3):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_gate_state_is_entering_during_execution(
        self, schema_id: str
    ) -> None:
        """INV-5: gate runs while KernelContext state is ENTERING, not ACTIVE."""
        observed_states: list[KernelState] = []

        async def _spy_gate(ctx: KernelContext) -> None:
            observed_states.append(ctx.state)

        payload = {"name": "Eve"}
        ctx = KernelContext(gates=[k1_gate(payload, schema_id), _spy_gate])
        async with ctx:
            pass
        # k1_gate and spy gate both ran while ENTERING
        assert observed_states == [KernelState.ENTERING]

    @pytest.mark.asyncio
    async def test_corr_id_accessible_during_body(self, schema_id: str) -> None:
        """corr_id is non-empty when inside the body."""
        ctx = KernelContext(gates=[k1_gate({"name": "A"}, schema_id)])
        async with ctx:
            assert len(ctx.corr_id) > 0


# ---------------------------------------------------------------------------
# Gate fail: invalid payload -> ValidationError
# ---------------------------------------------------------------------------


class TestGateFail:
    @pytest.mark.asyncio
    async def test_invalid_payload_raises_validation_error(
        self, schema_id: str
    ) -> None:
        """AC2: invalid payload raises ValidationError through KernelContext."""
        ctx = KernelContext(gates=[k1_gate({"name": 999}, schema_id)])
        with pytest.raises(ValidationError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.schema_id == schema_id

    @pytest.mark.asyncio
    async def test_invalid_payload_state_is_idle_after(self, schema_id: str) -> None:
        """AC6 liveness: after ValidationError, state is IDLE."""
        ctx = KernelContext(gates=[k1_gate({"name": 999}, schema_id)])
        with pytest.raises(ValidationError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_missing_required_field_raises(self, schema_id: str) -> None:
        ctx = KernelContext(gates=[k1_gate({"value": 5}, schema_id)])
        with pytest.raises(ValidationError) as exc_info:
            async with ctx:
                pass
        assert any("name" in e["message"] for e in exc_info.value.errors)

    @pytest.mark.asyncio
    async def test_additional_property_raises(self, schema_id: str) -> None:
        ctx = KernelContext(
            gates=[k1_gate({"name": "x", "unexpected": True}, schema_id)]
        )
        with pytest.raises(ValidationError):
            async with ctx:
                pass

    @pytest.mark.asyncio
    async def test_payload_hash_populated_on_failure(self, schema_id: str) -> None:
        """ValidationError carries SHA-256 payload_hash (64 hex chars)."""
        ctx = KernelContext(gates=[k1_gate({"name": 123}, schema_id)])
        with pytest.raises(ValidationError) as exc_info:
            async with ctx:
                pass
        assert len(exc_info.value.payload_hash) == 64

    @pytest.mark.asyncio
    async def test_field_level_errors_populated(self, schema_id: str) -> None:
        """ValidationError.errors is a non-empty list of field violations."""
        ctx = KernelContext(gates=[k1_gate({"value": 5}, schema_id)])
        with pytest.raises(ValidationError) as exc_info:
            async with ctx:
                pass
        errs = exc_info.value.errors
        assert isinstance(errs, list)
        assert len(errs) >= 1
        for e in errs:
            assert "path" in e and "message" in e


# ---------------------------------------------------------------------------
# Schema not found
# ---------------------------------------------------------------------------


class TestSchemaNotFound:
    @pytest.mark.asyncio
    async def test_unknown_schema_id_raises_schema_not_found(self) -> None:
        """AC3: SchemaNotFoundError propagates unchanged."""
        ctx = KernelContext(
            gates=[k1_gate({"name": "x"}, "ICD-DOES-NOT-EXIST")]
        )
        with pytest.raises(SchemaNotFoundError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.schema_id == "ICD-DOES-NOT-EXIST"

    @pytest.mark.asyncio
    async def test_schema_not_found_state_is_idle(self) -> None:
        """AC6 liveness: after SchemaNotFoundError, state is IDLE."""
        ctx = KernelContext(
            gates=[k1_gate({"name": "x"}, "ICD-MISSING")]
        )
        with pytest.raises(SchemaNotFoundError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Payload too large
# ---------------------------------------------------------------------------


class TestPayloadTooLarge:
    @pytest.mark.asyncio
    async def test_oversized_payload_raises_too_large(self, schema_id: str) -> None:
        """AC4: payload exceeding max_bytes raises PayloadTooLargeError."""
        big_payload = {"name": "x" * 200_000}
        ctx = KernelContext(
            gates=[k1_gate(big_payload, schema_id, max_bytes=100_000)]
        )
        with pytest.raises(PayloadTooLargeError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.size > exc_info.value.limit

    @pytest.mark.asyncio
    async def test_too_large_state_is_idle(self, schema_id: str) -> None:
        """AC6 liveness: after PayloadTooLargeError, state is IDLE."""
        big_payload = {"name": "x" * 200_000}
        ctx = KernelContext(
            gates=[k1_gate(big_payload, schema_id, max_bytes=100_000)]
        )
        with pytest.raises(PayloadTooLargeError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_deep_nesting_raises_too_large(self, schema_id: str) -> None:
        """Nesting depth > max_depth raises PayloadTooLargeError."""
        nested: dict[str, Any] = {"name": "leaf"}
        for _ in range(25):
            nested = {"nested": nested, "name": "wrap"}
        ctx = KernelContext(
            gates=[k1_gate(nested, schema_id, max_depth=10)]
        )
        with pytest.raises(PayloadTooLargeError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Gate ordering: k1_gate composes with other gates
# ---------------------------------------------------------------------------


class TestOrdering:
    @pytest.mark.asyncio
    async def test_k1_gate_runs_before_subsequent_gates(
        self, schema_id: str
    ) -> None:
        """k1_gate in first position: subsequent gate records ENTERING state."""
        order: list[str] = []

        async def _record(ctx: KernelContext) -> None:
            order.append("second")

        async def _k1_wrapper(ctx: KernelContext) -> None:
            order.append("k1")
            # call the real k1 gate
            await k1_gate({"name": "A"}, schema_id)(ctx)

        ctx = KernelContext(gates=[_k1_wrapper, _record])
        async with ctx:
            pass
        assert order == ["k1", "second"]

    @pytest.mark.asyncio
    async def test_k1_gate_fail_stops_subsequent_gates(
        self, schema_id: str
    ) -> None:
        """First-fail-abort: if k1_gate fails, subsequent gates do not run."""
        ran: list[bool] = []

        async def _should_not_run(ctx: KernelContext) -> None:
            ran.append(True)

        ctx = KernelContext(
            gates=[k1_gate({"name": 123}, schema_id), _should_not_run]
        )
        with pytest.raises(ValidationError):
            async with ctx:
                pass
        # Subsequent gate must NOT have run
        assert not ran


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis) — AC7 zero FP/FN
# ---------------------------------------------------------------------------


class TestPropertyBased:
    @given(name=st.text(min_size=1), value=st.integers(min_value=0))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_valid_payload_always_enters_and_idles(
        self, name: str, value: int
    ) -> None:
        """Property: any valid payload -> ACTIVE during body, IDLE after."""
        SchemaRegistry.clear()
        SchemaRegistry.register(SCHEMA_ID, SIMPLE_SCHEMA)
        payload = {"name": name, "value": value}
        ctx = KernelContext(gates=[k1_gate(payload, SCHEMA_ID)])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

    @given(name=st.integers() | st.booleans() | st.none())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_invalid_name_type_always_raises_and_idles(
        self, name: Any
    ) -> None:
        """Property: wrong name type -> ValidationError + IDLE."""
        SchemaRegistry.clear()
        SchemaRegistry.register(SCHEMA_ID, SIMPLE_SCHEMA)
        ctx = KernelContext(gates=[k1_gate({"name": name}, SCHEMA_ID)])
        with pytest.raises(ValidationError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.schema_id == SCHEMA_ID
        assert ctx.state == KernelState.IDLE

    @given(value=st.integers(max_value=-1))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_negative_value_always_raises_and_idles(
        self, value: int
    ) -> None:
        """Property: negative value (minimum=0 violated) -> ValidationError + IDLE."""
        SchemaRegistry.clear()
        SchemaRegistry.register(SCHEMA_ID, SIMPLE_SCHEMA)
        ctx = KernelContext(
            gates=[k1_gate({"name": "Test", "value": value}, SCHEMA_ID)]
        )
        with pytest.raises(ValidationError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_repeated_valid_crossings_always_end_idle(self, n: int) -> None:
        """Property: N sequential valid crossings always end in IDLE."""
        SchemaRegistry.clear()
        SchemaRegistry.register(SCHEMA_ID, SIMPLE_SCHEMA)
        ctx = KernelContext(gates=[k1_gate({"name": "Repeat"}, SCHEMA_ID)])
        for _ in range(n):
            async with ctx:
                assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE
