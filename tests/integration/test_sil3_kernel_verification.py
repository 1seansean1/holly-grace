"""SIL-3 Kernel Verification: K1-K8 Behavioral Acceptance Criteria.

Traces to: docs/Component_Behavior_Specs_SIL3.md §1.2-1.9
Task 21.2 — Execute SIL-3 verification.

Each test class covers one K gate and maps every test to the specific
Behavior Spec AC number it validates.  Hypothesis property tests provide
≥3 invariant checks per K gate per SIL-3 requirements (formal evidence
record for TLC / property-based / unit / integration methods).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.kernel.budget_registry import BudgetRegistry
from holly.kernel.context import KernelContext
from holly.kernel.exceptions import (
    ApprovalTimeout,
    BoundsExceeded,
    CanonicalizeError,
    ConfidenceError,
    EvalError,
    EvalGateFailure,
    ExpiredTokenError,
    JWTError,
    OperationRejected,
    PayloadTooLargeError,
    PermissionDeniedError,
    PredicateNotFoundError,
    RevocationCacheError,
    TenantContextError,
    UsageTrackingError,
    ValidationError,
    WALWriteError,
)
from holly.kernel.k1 import MAX_PAYLOAD_BYTES, k1_validate
from holly.kernel.k2 import FailRevocationCache, NullRevocationCache, k2_check_permissions
from holly.kernel.k3 import FailUsageTracker, InMemoryUsageTracker, k3_check_bounds
from holly.kernel.k4 import k4_inject_trace
from holly.kernel.k5 import k5_generate_key
from holly.kernel.k6 import InMemoryWALBackend, WALEntry, k6_write_entry
from holly.kernel.k7 import (
    ApprovalRequest,
    FailConfidenceEvaluator,
    FixedConfidenceEvaluator,
    FixedThresholdConfig,
    InMemoryApprovalChannel,
    MappedThresholdConfig,
    k7_check_confidence,
    k7_gate,
)
from holly.kernel.k8 import k8_evaluate
from holly.kernel.permission_registry import PermissionRegistry
from holly.kernel.predicate_registry import PredicateRegistry
from holly.kernel.schema_registry import SchemaRegistry

# ── Module-level constants ───────────────────────────────────────────────────

_K1_SCHEMA_ID = "sil3:K1:test"
_K1_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
}

_K2_ROLE = "sil3:reader"
_K2_PERM = "sil3:read:data"

_K3_TENANT = "sil3:t1"
_K3_RESOURCE = "sil3:tokens"
_K3_BUDGET = 10_000

_K7_OP = "sil3:classify"
_K7_PAYLOAD: dict[str, Any] = {"input": "test-value"}

# ── K7 helper classes ────────────────────────────────────────────────────────


class _AutoApproveChannel(InMemoryApprovalChannel):
    """Injects an approval for every emitted request (AC3 approval-path tests)."""

    def emit(self, request: ApprovalRequest) -> None:
        super().emit(request)
        self.inject_approve(request.request_id, reviewer_id="sil3-reviewer")


class _AutoRejectChannel(InMemoryApprovalChannel):
    """Injects a rejection for every emitted request (AC4 rejection tests)."""

    def emit(self, request: ApprovalRequest) -> None:
        super().emit(request)
        self.inject_reject(request.request_id, reviewer_id="sil3-reviewer")


async def _run_k7(
    *,
    score: float,
    threshold: float,
    channel: InMemoryApprovalChannel,
    op: str = _K7_OP,
    timeout: float = 1.0,
) -> KernelContext:
    """Run a k7_gate through a full KernelContext lifecycle."""
    gate = k7_gate(
        operation_type=op,
        payload=_K7_PAYLOAD,
        evaluator=FixedConfidenceEvaluator(score),
        threshold_config=FixedThresholdConfig(threshold),
        approval_channel=channel,
        timeout_seconds=timeout,
    )
    ctx = KernelContext(gates=[gate])
    async with ctx:
        pass
    return ctx


# ── K1 — Schema Validation (§1.2) ───────────────────────────────────────────


class TestK1SIL3Verification:
    """K1 schema validation gate — Behavior Spec §1.2 AC1-AC7."""

    def setup_method(self) -> None:
        SchemaRegistry.clear()
        SchemaRegistry.register(_K1_SCHEMA_ID, _K1_SCHEMA)

    def teardown_method(self) -> None:
        SchemaRegistry.clear()

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_valid_payload_passes(self) -> None:
        """AC1: Payload conforming to registered schema passes; returned unchanged."""
        payload: dict[str, Any] = {"name": "alice"}
        result = k1_validate(payload, _K1_SCHEMA_ID)
        assert result == {"name": "alice"}

    # AC2 (property) ──────────────────────────────────────────────────────

    @given(
        st.one_of(
            st.integers(),
            st.text(),
            st.lists(st.integers(), max_size=5),
            st.booleans(),
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_ac2_invalid_payload_always_fails_property(self, payload: Any) -> None:
        """AC2 (property): Non-object types always raise ValidationError."""
        with pytest.raises(ValidationError):
            k1_validate(payload, _K1_SCHEMA_ID)

    # AC3 ─────────────────────────────────────────────────────────────────

    def test_ac3_schema_caching_returns_same_object(self) -> None:
        """AC3: SchemaRegistry returns the identical schema object on repeated calls."""
        s1 = SchemaRegistry.get(_K1_SCHEMA_ID)
        s2 = SchemaRegistry.get(_K1_SCHEMA_ID)
        assert s1 is s2

    # AC4 ─────────────────────────────────────────────────────────────────

    def test_ac4_error_details_include_path_and_message(self) -> None:
        """AC4: ValidationError exposes field path and validator message."""
        with pytest.raises(ValidationError) as exc_info:
            k1_validate({"name": 42}, _K1_SCHEMA_ID)  # name must be str
        err = exc_info.value
        assert err.errors
        first = err.errors[0]
        assert "path" in first
        assert "message" in first

    # AC6 ─────────────────────────────────────────────────────────────────

    def test_ac6_large_payload_rejected(self) -> None:
        """AC6: Payload > MAX_PAYLOAD_BYTES raises PayloadTooLargeError."""
        big_value = "x" * (MAX_PAYLOAD_BYTES + 1)
        with pytest.raises(PayloadTooLargeError):
            k1_validate({"name": big_value}, _K1_SCHEMA_ID)

    # AC7 (property) ──────────────────────────────────────────────────────

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_ac7_payload_immutability_property(self, name: str) -> None:
        """AC7 (property): k1_validate never mutates the input payload."""
        payload: dict[str, Any] = {"name": name}
        snapshot = dict(payload)
        k1_validate(payload, _K1_SCHEMA_ID)
        assert payload == snapshot

    # Extra property ──────────────────────────────────────────────────────

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, deadline=None)
    def test_valid_name_string_always_passes_property(self, name: str) -> None:
        """Property: Any non-empty string satisfies the 'name' field requirement."""
        result = k1_validate({"name": name}, _K1_SCHEMA_ID)
        assert result["name"] == name


# ── K2 — Permission Gate (§1.3) ─────────────────────────────────────────────


class TestK2SIL3Verification:
    """K2 permission gate — Behavior Spec §1.3 AC1-AC8."""

    def setup_method(self) -> None:
        PermissionRegistry.clear()
        PermissionRegistry.register_role(_K2_ROLE, {_K2_PERM})

    def teardown_method(self) -> None:
        PermissionRegistry.clear()

    def _valid_claims(self) -> dict[str, Any]:
        return {"sub": "sil3-user", "roles": [_K2_ROLE]}

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_valid_claims_pass(self) -> None:
        """AC1: Valid claims with required permissions pass without exception."""
        k2_check_permissions(
            self._valid_claims(),
            frozenset({_K2_PERM}),
            revocation_cache=NullRevocationCache(),
        )

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_none_claims_raises_jwt_error(self) -> None:
        """AC2: None claims (missing/malformed JWT) raise JWTError."""
        with pytest.raises(JWTError):
            k2_check_permissions(None, frozenset({_K2_PERM}))

    @given(st.none())
    @settings(max_examples=10, deadline=None)
    def test_ac2_none_claims_always_fails_property(self, claims: None) -> None:
        """AC2 (property): None claims always raises JWTError."""
        with pytest.raises(JWTError):
            k2_check_permissions(claims, frozenset({_K2_PERM}))

    # AC3 ─────────────────────────────────────────────────────────────────

    def test_ac3_expired_token_raises(self) -> None:
        """AC3: Claims with a past exp timestamp raise ExpiredTokenError."""
        past_exp = int(time.time()) - 3600
        claims = {**self._valid_claims(), "exp": past_exp}
        with pytest.raises(ExpiredTokenError):
            k2_check_permissions(claims, frozenset({_K2_PERM}))

    @given(st.integers(min_value=1, max_value=86_400 * 365))
    @settings(max_examples=50, deadline=None)
    def test_ac3_any_past_exp_always_rejected_property(self, seconds_ago: int) -> None:
        """AC3 (property): Any exp in the past always raises ExpiredTokenError."""
        past_exp = int(time.time()) - seconds_ago - 1
        claims = {"sub": "u1", "roles": [_K2_ROLE], "exp": past_exp}
        with pytest.raises(ExpiredTokenError):
            k2_check_permissions(claims, frozenset({_K2_PERM}))

    # AC5 ─────────────────────────────────────────────────────────────────

    def test_ac5_insufficient_permissions_raises(self) -> None:
        """AC5: Missing required permission raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            k2_check_permissions(
                self._valid_claims(),
                frozenset({"sil3:write:data"}),  # reader role lacks this
                revocation_cache=NullRevocationCache(),
            )

    # AC7 ─────────────────────────────────────────────────────────────────

    def test_ac7_fail_safe_deny_on_cache_error(self) -> None:
        """AC7: Unavailable revocation cache raises RevocationCacheError (fail-safe deny)."""
        claims = {**self._valid_claims(), "jti": "tok-sil3-001"}
        with pytest.raises(RevocationCacheError):
            k2_check_permissions(
                claims,
                frozenset({_K2_PERM}),
                revocation_cache=FailRevocationCache(),
            )

    # Extra property ──────────────────────────────────────────────────────

    @given(st.booleans())
    @settings(max_examples=50, deadline=None)
    def test_missing_sub_always_fails_property(self, sub_present: bool) -> None:
        """Property: Claims without 'sub' always raise JWTError."""
        claims: dict[str, Any] = {"roles": [_K2_ROLE]}
        if sub_present:
            claims["sub"] = "u1"
            # Valid claims — should not raise
            k2_check_permissions(claims, frozenset({_K2_PERM}))
        else:
            with pytest.raises(JWTError):
                k2_check_permissions(claims, frozenset({_K2_PERM}))


# ── K3 — Bounds Checking Gate (§1.4) ────────────────────────────────────────


class TestK3SIL3Verification:
    """K3 bounds gate — Behavior Spec §1.4 AC1-AC7."""

    def setup_method(self) -> None:
        BudgetRegistry.clear()
        BudgetRegistry.register(_K3_TENANT, _K3_RESOURCE, _K3_BUDGET)
        self._tracker = InMemoryUsageTracker()

    def teardown_method(self) -> None:
        BudgetRegistry.clear()

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_within_budget_passes_and_increments(self) -> None:
        """AC1: Request within budget passes and atomically increments usage."""
        k3_check_bounds(_K3_TENANT, _K3_RESOURCE, 500, usage_tracker=self._tracker)
        assert self._tracker.get_usage(_K3_TENANT, _K3_RESOURCE) == 500

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_budget_exceeded_raises(self) -> None:
        """AC2: Request that pushes usage over budget raises BoundsExceeded."""
        k3_check_bounds(_K3_TENANT, _K3_RESOURCE, 9_500, usage_tracker=self._tracker)
        with pytest.raises(BoundsExceeded):
            k3_check_bounds(_K3_TENANT, _K3_RESOURCE, 600, usage_tracker=self._tracker)

    # AC3 (property) ──────────────────────────────────────────────────────

    @given(
        amounts=st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=5)
    )
    @settings(max_examples=50, deadline=None)
    def test_ac3_atomicity_sequential_increments_property(
        self, amounts: list[int]
    ) -> None:
        """AC3 (property): Sequential requests atomically track usage; total = Σ amounts."""
        tracker = InMemoryUsageTracker()
        budget = sum(amounts) + 1
        tenant = f"sil3:k3:hyp:{uuid.uuid4().hex}"
        BudgetRegistry.register(tenant, "tokens", budget)
        running = 0
        for amount in amounts:
            k3_check_bounds(tenant, "tokens", amount, usage_tracker=tracker)
            running += amount
            assert tracker.get_usage(tenant, "tokens") == running

    # AC4 ─────────────────────────────────────────────────────────────────

    def test_ac4_tenant_isolation(self) -> None:
        """AC4: Budget exhaustion in tenant A does not affect tenant B."""
        tenant_b = "sil3:t2:iso"
        BudgetRegistry.register(tenant_b, _K3_RESOURCE, 500)
        tracker_b = InMemoryUsageTracker()
        # Exhaust tenant A
        k3_check_bounds(
            _K3_TENANT, _K3_RESOURCE, _K3_BUDGET, usage_tracker=self._tracker
        )
        # Tenant B still has full capacity
        k3_check_bounds(tenant_b, _K3_RESOURCE, 250, usage_tracker=tracker_b)
        assert tracker_b.get_usage(tenant_b, _K3_RESOURCE) == 250

    # AC6 ─────────────────────────────────────────────────────────────────

    def test_ac6_fail_tracker_raises_usage_tracking_error(self) -> None:
        """AC6: Unavailable usage tracker triggers fail-safe deny (UsageTrackingError)."""
        with pytest.raises(UsageTrackingError):
            k3_check_bounds(
                _K3_TENANT, _K3_RESOURCE, 100, usage_tracker=FailUsageTracker()
            )

    # Extra properties ────────────────────────────────────────────────────

    @given(
        requested=st.integers(min_value=_K3_BUDGET + 1, max_value=_K3_BUDGET * 2)
    )
    @settings(max_examples=50, deadline=None)
    def test_over_budget_always_raises_property(self, requested: int) -> None:
        """Property: Any request > budget with empty tracker always raises BoundsExceeded."""
        tracker = InMemoryUsageTracker()
        with pytest.raises(BoundsExceeded):
            k3_check_bounds(
                _K3_TENANT, _K3_RESOURCE, requested, usage_tracker=tracker
            )

    @given(
        budget=st.integers(min_value=1, max_value=1000),
        current=st.integers(min_value=0, max_value=1000),
        requested=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=80, deadline=None)
    def test_bounds_check_semantics_property(
        self, budget: int, current: int, requested: int
    ) -> None:
        """Property: BoundsExceeded raised ↔ current + requested > budget."""
        if current > budget:
            return  # cannot pre-fill beyond budget; skip
        tracker = InMemoryUsageTracker()
        tenant = f"sil3:k3:sem:{uuid.uuid4().hex}"
        BudgetRegistry.register(tenant, "cpu", budget)
        if current > 0:
            k3_check_bounds(tenant, "cpu", current, usage_tracker=tracker)
        should_exceed = (current + requested) > budget
        if should_exceed:
            with pytest.raises(BoundsExceeded):
                k3_check_bounds(tenant, "cpu", requested, usage_tracker=tracker)
        else:
            k3_check_bounds(tenant, "cpu", requested, usage_tracker=tracker)
            assert tracker.get_usage(tenant, "cpu") == current + requested


# ── K4 — Trace Injection Gate (§1.5) ────────────────────────────────────────


class TestK4SIL3Verification:
    """K4 trace injection gate — Behavior Spec §1.5 AC1-AC7."""

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_tenant_id_extracted_from_claims(self) -> None:
        """AC1: tenant_id is extracted from JWT claims and returned."""
        claims: dict[str, Any] = {"tenant_id": "acme-corp", "sub": "user-1"}
        _, tenant = k4_inject_trace(claims)
        assert tenant == "acme-corp"

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_context_correlation_propagated(self) -> None:
        """AC2: Existing context corr_id propagates when no override is supplied."""
        existing = str(uuid.uuid4())
        claims: dict[str, Any] = {"tenant_id": "t1", "sub": "u1"}
        corr_id, _ = k4_inject_trace(claims, context_corr_id=existing)
        assert corr_id == existing

    # AC3 ─────────────────────────────────────────────────────────────────

    def test_ac3_generates_fresh_uuid4_when_none_provided(self) -> None:
        """AC3: Fresh UUID4 correlation_id generated when no context or override given."""
        claims: dict[str, Any] = {"tenant_id": "t1", "sub": "u1"}
        corr_id, _ = k4_inject_trace(claims)
        parsed = uuid.UUID(corr_id)
        assert parsed.version == 4

    # AC4 ─────────────────────────────────────────────────────────────────

    def test_ac4_caller_provided_correlation_used_verbatim(self) -> None:
        """AC4: Caller-supplied UUID is returned as-is without modification."""
        provided = str(uuid.uuid4())
        claims: dict[str, Any] = {"tenant_id": "t1", "sub": "u1"}
        corr_id, _ = k4_inject_trace(claims, provided_correlation_id=provided)
        assert corr_id == provided

    # AC6 ─────────────────────────────────────────────────────────────────

    def test_ac6_missing_tenant_id_raises(self) -> None:
        """AC6: Claims without tenant_id raise TenantContextError."""
        claims: dict[str, Any] = {"sub": "u1", "roles": ["reader"]}
        with pytest.raises(TenantContextError):
            k4_inject_trace(claims)

    def test_ac6_none_claims_raises(self) -> None:
        """AC6: None claims raise TenantContextError."""
        with pytest.raises(TenantContextError):
            k4_inject_trace(None)

    # AC7 (property) ──────────────────────────────────────────────────────

    @given(
        tenant=st.text(
            min_size=1,
            max_size=30,
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_ac7_tenant_id_always_preserved_property(self, tenant: str) -> None:
        """AC7 (property): Returned tenant_id always matches claims['tenant_id']."""
        claims: dict[str, Any] = {"tenant_id": tenant, "sub": "u1"}
        _, returned_tenant = k4_inject_trace(claims)
        assert returned_tenant == tenant

    @given(
        tenant=st.text(
            min_size=1, max_size=20, alphabet="abcdef0123456789-"
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_ac7_generated_corr_always_uuid4_property(self, tenant: str) -> None:
        """AC7 (property): Auto-generated corr_id is always a valid UUID4."""
        claims: dict[str, Any] = {"tenant_id": tenant, "sub": "u1"}
        corr_id, _ = k4_inject_trace(claims)
        parsed = uuid.UUID(corr_id)
        assert parsed.version == 4

    @given(valid_uuid=st.uuids(version=4).map(str))
    @settings(max_examples=50, deadline=None)
    def test_ac4_provided_uuid_always_returned_property(self, valid_uuid: str) -> None:
        """AC4 (property): Any caller-supplied UUID4 is always returned verbatim."""
        claims: dict[str, Any] = {"tenant_id": "t1", "sub": "u1"}
        corr_id, _ = k4_inject_trace(claims, provided_correlation_id=valid_uuid)
        assert corr_id == valid_uuid


# ── K5 — Idempotency Key Gate (§1.6) ────────────────────────────────────────


class TestK5SIL3Verification:
    """K5 idempotency key gate — Behavior Spec §1.6 AC1-AC7."""

    # AC1 (property) ──────────────────────────────────────────────────────

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet="abcdefghijklmn"),
            st.integers(min_value=-100, max_value=100),
            max_size=5,
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_ac1_deterministic_property(self, payload: dict[str, Any]) -> None:
        """AC1 (property): Same payload always produces the same idempotency key."""
        k1 = k5_generate_key(payload)
        k2 = k5_generate_key(payload)
        assert k1 == k2

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_field_order_independence(self) -> None:
        """AC2: Dicts with identical content in different insertion order yield same key."""
        p1 = {"a": 1, "b": 2, "c": 3}
        p2 = {"c": 3, "a": 1, "b": 2}
        p3 = {"b": 2, "c": 3, "a": 1}
        assert k5_generate_key(p1) == k5_generate_key(p2) == k5_generate_key(p3)

    # AC5 (property) ──────────────────────────────────────────────────────

    @given(
        p1=st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcdef"),
            st.integers(min_value=0, max_value=100),
            max_size=3,
        ),
        p2=st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcdef"),
            st.integers(min_value=0, max_value=100),
            max_size=3,
        ),
    )
    @settings(max_examples=200, deadline=None)
    def test_ac5_different_payloads_different_keys_property(
        self, p1: dict[str, Any], p2: dict[str, Any]
    ) -> None:
        """AC5 (property): Distinct payloads always yield distinct idempotency keys."""
        if p1 == p2:
            return  # equal payloads legitimately share a key; skip
        assert k5_generate_key(p1) != k5_generate_key(p2)

    # AC6 ─────────────────────────────────────────────────────────────────

    def test_ac6_non_json_serializable_raises(self) -> None:
        """AC6: Non-JSON-serializable payload raises CanonicalizeError."""
        from datetime import datetime as _dt

        with pytest.raises(CanonicalizeError):
            k5_generate_key({"ts": _dt.now()})

    # AC7 (property) ──────────────────────────────────────────────────────

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcdef"),
            st.integers(min_value=0, max_value=50),
            max_size=4,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_ac7_key_format_hex64_property(self, payload: dict[str, Any]) -> None:
        """AC7 (property): Generated key is always exactly 64 lowercase hex chars."""
        import re

        key = k5_generate_key(payload)
        assert re.fullmatch(r"[a-f0-9]{64}", key) is not None


# ── K6 — WAL Durability Gate (§1.7) ─────────────────────────────────────────


class TestK6SIL3Verification:
    """K6 WAL durability gate — Behavior Spec §1.7 AC1-AC7."""

    def _make_entry(
        self,
        *,
        tenant: str = "sil3:t1",
        corr: str = "sil3-corr-001",
        result: str | None = None,
    ) -> WALEntry:
        return WALEntry(
            id=str(uuid.uuid4()),
            tenant_id=tenant,
            correlation_id=corr,
            timestamp=datetime.now(timezone.utc),  # noqa: UP017
            boundary_crossing="sil3::test_boundary",
            caller_user_id="sil3-user",
            caller_roles=["sil3:reader"],
            exit_code=0,
            k1_valid=True,
            k2_authorized=True,
            k3_within_budget=True,
            operation_result=result,
        )

    # AC1 (property) ──────────────────────────────────────────────────────

    @given(n=st.integers(min_value=1, max_value=6))
    @settings(max_examples=30, deadline=None)
    def test_ac1_one_entry_per_crossing_property(self, n: int) -> None:
        """AC1 (property): Each k6_write_entry call appends exactly one WAL entry."""
        backend = InMemoryWALBackend()
        for _ in range(n):
            k6_write_entry(self._make_entry(), backend)
        assert len(backend.entries) == n

    # AC3 ─────────────────────────────────────────────────────────────────

    def test_ac3_redaction_applied_to_operation_result(self) -> None:
        """AC3: PII in operation_result is redacted before WAL persistence."""
        backend = InMemoryWALBackend()
        entry = self._make_entry(result="Contact user@example.com for auth details")
        k6_write_entry(entry, backend)
        persisted = backend.entries[0]
        assert "user@example.com" not in (persisted.operation_result or "")
        assert "[email hidden]" in (persisted.operation_result or "")

    # AC5 (property) ──────────────────────────────────────────────────────

    @given(n=st.integers(min_value=2, max_value=5))
    @settings(max_examples=20, deadline=None)
    def test_ac5_timestamp_ordering_property(self, n: int) -> None:
        """AC5 (property): Entries are ordered by insertion timestamp (non-decreasing)."""
        backend = InMemoryWALBackend()
        for _ in range(n):
            k6_write_entry(self._make_entry(), backend)
        timestamps = [e.timestamp for e in backend.entries]
        assert timestamps == sorted(timestamps)

    # AC6 ─────────────────────────────────────────────────────────────────

    def test_ac6_correlation_id_linked_in_entry(self) -> None:
        """AC6: correlation_id is preserved verbatim in the persisted WAL entry."""
        backend = InMemoryWALBackend()
        expected = "sil3-trace-xyz-789"
        k6_write_entry(self._make_entry(corr=expected), backend)
        assert backend.entries[0].correlation_id == expected

    # AC7 (property) ──────────────────────────────────────────────────────

    @given(fail=st.booleans())
    @settings(max_examples=20, deadline=None)
    def test_ac7_write_error_on_backend_failure_property(self, fail: bool) -> None:
        """AC7 (property): Backend failure always surfaces as WALWriteError."""
        backend = InMemoryWALBackend()
        backend._fail = fail
        if fail:
            with pytest.raises(WALWriteError):
                k6_write_entry(self._make_entry(), backend)
        else:
            k6_write_entry(self._make_entry(), backend)
            assert len(backend.entries) == 1


# ── K7 — HITL Gate (§1.8) ───────────────────────────────────────────────────


class TestK7SIL3Verification:
    """K7 HITL confidence gate — Behavior Spec §1.8 AC1-AC8."""

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_high_confidence_passes_without_approval(self) -> None:
        """AC1: score ≥ threshold passes gate immediately; no approval request emitted."""
        channel = InMemoryApprovalChannel()
        asyncio.run(_run_k7(score=0.95, threshold=0.85, channel=channel))
        assert len(channel.emitted) == 0

    # AC1 (property) ──────────────────────────────────────────────────────

    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=80, deadline=None)
    def test_ac1_confident_path_never_emits_property(
        self, score: float, threshold: float
    ) -> None:
        """AC1 (property): When score ≥ threshold, approval channel is never called."""
        if score < threshold:
            return  # uncertain path; not covered here
        channel = InMemoryApprovalChannel()
        asyncio.run(_run_k7(score=score, threshold=threshold, channel=channel))
        assert len(channel.emitted) == 0

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_low_confidence_emits_approval_request(self) -> None:
        """AC2: score < threshold causes an ApprovalRequest to be emitted."""
        channel = _AutoApproveChannel()
        asyncio.run(_run_k7(score=0.70, threshold=0.85, channel=channel))
        assert len(channel.emitted) == 1
        req = channel.emitted[0]
        assert req.operation_type == _K7_OP
        assert req.confidence_score == pytest.approx(0.70)
        assert req.threshold == pytest.approx(0.85)

    # AC3 ─────────────────────────────────────────────────────────────────

    def test_ac3_human_approval_passes_gate(self) -> None:
        """AC3: Human approval decision unblocks the gate; operation proceeds."""
        channel = _AutoApproveChannel()
        asyncio.run(_run_k7(score=0.50, threshold=0.85, channel=channel))
        assert len(channel.emitted) == 1

    # AC4 ─────────────────────────────────────────────────────────────────

    def test_ac4_human_rejection_raises_operation_rejected(self) -> None:
        """AC4: Human rejection decision raises OperationRejected."""

        async def _run() -> None:
            channel = _AutoRejectChannel()
            gate = k7_gate(
                operation_type=_K7_OP,
                payload=_K7_PAYLOAD,
                evaluator=FixedConfidenceEvaluator(0.50),
                threshold_config=FixedThresholdConfig(0.85),
                approval_channel=channel,
                timeout_seconds=1.0,
            )
            ctx = KernelContext(gates=[gate])
            async with ctx:
                pass

        with pytest.raises(OperationRejected):
            asyncio.run(_run())

    # AC5 ─────────────────────────────────────────────────────────────────

    def test_ac5_approval_timeout_raises(self) -> None:
        """AC5: No human decision within TTL raises ApprovalTimeout."""

        async def _run() -> None:
            channel = InMemoryApprovalChannel()
            channel.set_timeout_all(timeout=True)
            gate = k7_gate(
                operation_type=_K7_OP,
                payload=_K7_PAYLOAD,
                evaluator=FixedConfidenceEvaluator(0.50),
                threshold_config=FixedThresholdConfig(0.85),
                approval_channel=channel,
                timeout_seconds=1.0,
            )
            ctx = KernelContext(gates=[gate])
            async with ctx:
                pass

        with pytest.raises(ApprovalTimeout):
            asyncio.run(_run())

    # AC7 ─────────────────────────────────────────────────────────────────

    def test_ac7_fail_evaluator_raises_confidence_error(self) -> None:
        """AC7: ConfidenceEvaluator exception triggers fail-safe deny (ConfidenceError)."""

        async def _run() -> None:
            channel = InMemoryApprovalChannel()
            gate = k7_gate(
                operation_type=_K7_OP,
                payload=_K7_PAYLOAD,
                evaluator=FailConfidenceEvaluator(),
                threshold_config=FixedThresholdConfig(0.85),
                approval_channel=channel,
                timeout_seconds=1.0,
            )
            ctx = KernelContext(gates=[gate])
            async with ctx:
                pass

        with pytest.raises(ConfidenceError):
            asyncio.run(_run())

    # AC8 ─────────────────────────────────────────────────────────────────

    def test_ac8_per_operation_type_thresholds(self) -> None:
        """AC8: MappedThresholdConfig enforces distinct thresholds per operation type."""
        threshold_config = MappedThresholdConfig(
            {"op_strict": 0.95, "op_lenient": 0.40},
            default_threshold=0.80,
        )

        # op_strict: score 0.85 < threshold 0.95 → uncertain → timeout
        async def _run_strict() -> None:
            channel = InMemoryApprovalChannel()
            channel.set_timeout_all(timeout=True)
            gate = k7_gate(
                operation_type="op_strict",
                payload=_K7_PAYLOAD,
                evaluator=FixedConfidenceEvaluator(0.85),
                threshold_config=threshold_config,
                approval_channel=channel,
                timeout_seconds=1.0,
            )
            ctx = KernelContext(gates=[gate])
            async with ctx:
                pass

        with pytest.raises(ApprovalTimeout):
            asyncio.run(_run_strict())

        # op_lenient: score 0.85 ≥ threshold 0.40 → passes directly
        async def _run_lenient() -> None:
            channel = InMemoryApprovalChannel()
            gate = k7_gate(
                operation_type="op_lenient",
                payload=_K7_PAYLOAD,
                evaluator=FixedConfidenceEvaluator(0.85),
                threshold_config=threshold_config,
                approval_channel=channel,
                timeout_seconds=1.0,
            )
            ctx = KernelContext(gates=[gate])
            async with ctx:
                pass
            assert len(channel.emitted) == 0

        asyncio.run(_run_lenient())

    # k7_check_confidence pure-function properties ────────────────────────

    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200, deadline=None)
    def test_check_confidence_correctness_property(
        self, score: float, threshold: float
    ) -> None:
        """Property: k7_check_confidence returns True ↔ score ≥ threshold."""
        assert k7_check_confidence(score, threshold=threshold) == (score >= threshold)

    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200, deadline=None)
    def test_check_confidence_determinism_property(
        self, score: float, threshold: float
    ) -> None:
        """Property: k7_check_confidence is deterministic — same inputs, same output."""
        r1 = k7_check_confidence(score, threshold=threshold)
        r2 = k7_check_confidence(score, threshold=threshold)
        assert r1 == r2


# ── K8 — Eval Gate (§1.9) ───────────────────────────────────────────────────


class TestK8SIL3Verification:
    """K8 eval gate — Behavior Spec §1.9 AC1-AC7."""

    def setup_method(self) -> None:
        PredicateRegistry.clear()

    def teardown_method(self) -> None:
        PredicateRegistry.clear()

    # AC1 ─────────────────────────────────────────────────────────────────

    def test_ac1_predicate_true_passes(self) -> None:
        """AC1: Predicate returning True passes; k8_evaluate returns True."""
        PredicateRegistry.register("sil3:k8:allow_all", lambda o: True)
        assert k8_evaluate({"x": 1}, "sil3:k8:allow_all") is True

    # AC2 ─────────────────────────────────────────────────────────────────

    def test_ac2_predicate_false_raises_eval_gate_failure(self) -> None:
        """AC2: Predicate returning False raises EvalGateFailure."""
        PredicateRegistry.register("sil3:k8:deny_all", lambda o: False)
        with pytest.raises(EvalGateFailure):
            k8_evaluate({"x": 1}, "sil3:k8:deny_all")

    # AC5 ─────────────────────────────────────────────────────────────────

    def test_ac5_missing_predicate_raises_not_found(self) -> None:
        """AC5: Unknown predicate_id raises PredicateNotFoundError."""
        with pytest.raises(PredicateNotFoundError):
            k8_evaluate({"x": 1}, "sil3:k8:does_not_exist")

    # AC6 (property) ──────────────────────────────────────────────────────

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcde"),
            st.integers(min_value=0, max_value=10),
            max_size=3,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_ac6_deterministic_evaluation_property(
        self, output: dict[str, Any]
    ) -> None:
        """AC6 (property): k8_evaluate is deterministic — same output → same result."""
        PredicateRegistry.clear()
        PredicateRegistry.register("sil3:k8:always_pass", lambda o: True)
        r1 = k8_evaluate(output, "sil3:k8:always_pass")
        r2 = k8_evaluate(output, "sil3:k8:always_pass")
        assert r1 == r2 is True

    # AC7 ─────────────────────────────────────────────────────────────────

    def test_ac7_predicate_exception_raises_eval_error(self) -> None:
        """AC7: Exception inside predicate raises EvalError (fail-safe block)."""

        def _bad_pred(o: Any) -> bool:
            raise RuntimeError("predicate internal failure")

        PredicateRegistry.register("sil3:k8:bad_pred", _bad_pred)
        with pytest.raises(EvalError):
            k8_evaluate({"x": 1}, "sil3:k8:bad_pred")

    # Extra properties ────────────────────────────────────────────────────

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcde"),
            st.integers(min_value=0, max_value=10),
            max_size=3,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_deny_predicate_always_raises_property(
        self, output: dict[str, Any]
    ) -> None:
        """Property: A predicate returning False always raises EvalGateFailure."""
        PredicateRegistry.clear()
        PredicateRegistry.register("sil3:k8:deny", lambda o: False)
        with pytest.raises(EvalGateFailure):
            k8_evaluate(output, "sil3:k8:deny")

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet="abcde"),
            st.integers(min_value=0, max_value=10),
            max_size=3,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_allow_predicate_always_returns_true_property(
        self, output: dict[str, Any]
    ) -> None:
        """Property: A predicate returning True always allows the output to pass."""
        PredicateRegistry.clear()
        PredicateRegistry.register("sil3:k8:allow", lambda o: True)
        assert k8_evaluate(output, "sil3:k8:allow") is True
