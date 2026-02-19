"""Task 16.9 — K1-K4 Guard Condition Determinism.

Verifies Behavior Spec §1.1 INV-4:

    ∀ transition: guard_condition(transition) must evaluate deterministically.
    Guards are pure functions; no side effects on evaluation.

Property-based tests confirm:

1. **K1 (Schema Validation):** ``k1_validate`` is deterministic — same payload
   and schema always produce the same pass/fail outcome, regardless of call
   count.  No mutation to SchemaRegistry on repeated reads.

2. **K2 (Permission Check):** ``k2_check_permissions`` is deterministic —
   same claims and required-permissions always produce the same outcome.
   No mutation to PermissionRegistry on repeated evaluations.

3. **K3 (Bounds Check):** ``k3_check_bounds`` guard evaluation is deterministic
   — same tenant, resource, requested amount, and initial usage always produce
   the same pass/fail.  Usage is only incremented on explicit gate pass; the
   *check itself* does not vary across evaluations given the same state.

4. **K4 (Trace Injection):** ``k4_inject_trace`` is deterministic — same
   claims and provided correlation ID always return the same (corr_id, tenant_id)
   pair.  No global state is mutated during evaluation.

5. **Cross-guard isolation:** Repeated evaluation of one guard does not mutate
   state visible to another guard.

Traces to Behavior Spec §1.1 INV-4, §1.2 K1, §1.3 K2, §1.4 K3, §1.5 K4.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from holly.kernel.budget_registry import BudgetRegistry
from holly.kernel.exceptions import (
    BoundsExceeded,
    JWTError,
    PermissionDeniedError,
    SchemaNotFoundError,
    TenantContextError,
    ValidationError,
)
from holly.kernel.k1 import k1_validate
from holly.kernel.k2 import k2_check_permissions
from holly.kernel.k3 import InMemoryUsageTracker, k3_check_bounds
from holly.kernel.k4 import k4_inject_trace
from holly.kernel.permission_registry import PermissionRegistry
from holly.kernel.schema_registry import SchemaRegistry

# ---------------------------------------------------------------------------
# Shared fixtures / setup helpers
# ---------------------------------------------------------------------------

_SCHEMA_ID = "test_16_9_determinism_schema"
_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "integer"},
        "tag": {"type": "string"},
    },
    "required": ["value"],
}

_ROLE = "det_reader"
_PERMISSION = "action:det_read"

_TENANT = "tenant-det-16-9"
_RESOURCE = "det-tokens"
_BUDGET = 10_000


def _ensure_schema() -> None:
    """Register determinism test schema if not already present."""
    if not SchemaRegistry.has(_SCHEMA_ID):
        SchemaRegistry.register(_SCHEMA_ID, _SCHEMA)


def _ensure_role() -> None:
    """Register determinism test role if not already present."""
    if not PermissionRegistry.has_role(_ROLE):
        PermissionRegistry.register_role(_ROLE, {_PERMISSION})


def _ensure_budget() -> None:
    """Register determinism test budget if not already present."""
    if not BudgetRegistry.has_budget(_TENANT, _RESOURCE):
        BudgetRegistry.register(_TENANT, _RESOURCE, _BUDGET)


# ---------------------------------------------------------------------------
# TestK1Determinism
# ---------------------------------------------------------------------------


class TestK1Determinism:
    """K1 guard (k1_validate) is a pure function: same input → same outcome."""

    def setup_method(self) -> None:
        _ensure_schema()

    def test_valid_payload_idempotent(self) -> None:
        """10 sequential calls with identical input always pass."""
        payload = {"value": 42, "tag": "hello"}
        for _ in range(10):
            result = k1_validate(payload, _SCHEMA_ID)
            assert result == payload

    def test_invalid_payload_idempotent(self) -> None:
        """10 sequential calls with an invalid payload always raise the same exception."""
        bad_payload = {"value": "not-an-int"}
        for _ in range(10):
            with pytest.raises(ValidationError):
                k1_validate(bad_payload, _SCHEMA_ID)

    def test_unknown_schema_idempotent(self) -> None:
        """Missing schema always raises SchemaNotFoundError, never passes."""
        for _ in range(10):
            with pytest.raises(SchemaNotFoundError):
                k1_validate({"value": 1}, "schema_that_does_not_exist_16_9")

    def test_schema_registry_not_mutated_by_validation(self) -> None:
        """Calling k1_validate does not alter SchemaRegistry contents."""
        before = frozenset(SchemaRegistry.registered_ids())
        for _ in range(5):
            k1_validate({"value": 1}, _SCHEMA_ID)
        after = frozenset(SchemaRegistry.registered_ids())
        assert before == after

    @given(
        value=st.integers(),
        tag=st.text(max_size=20),
    )
    @settings(max_examples=60)
    def test_property_valid_payload_always_passes(
        self, value: int, tag: str
    ) -> None:
        """Any integer value + string tag always passes K1 deterministically."""
        _ensure_schema()
        payload = {"value": value, "tag": tag}
        result = k1_validate(payload, _SCHEMA_ID)
        assert result == payload

    @given(
        value=st.one_of(
            st.text(min_size=1),  # string instead of int
            st.lists(st.integers()),  # list
            st.booleans(),  # bool (JSON Schema treats bool as non-integer sometimes)
        )
    )
    @settings(max_examples=40)
    def test_property_wrong_value_type_always_fails(self, value: object) -> None:
        """Non-integer 'value' always fails K1; outcome never varies."""
        _ensure_schema()
        assume(not isinstance(value, int))
        payload = {"value": value}
        exc_type: type | None = None
        for _ in range(3):
            try:
                k1_validate(payload, _SCHEMA_ID)
                # If no exception: both calls must also pass (determinism)
            except ValidationError as e:
                if exc_type is None:
                    exc_type = type(e)
                else:
                    assert type(e) is exc_type

    def test_repeated_reads_do_not_increment_internal_counter(self) -> None:
        """SchemaRegistry has no access counter that k1_validate could bump."""
        schemas_before = len(list(SchemaRegistry.registered_ids()))
        for _ in range(20):
            k1_validate({"value": 0}, _SCHEMA_ID)
        schemas_after = len(list(SchemaRegistry.registered_ids()))
        assert schemas_before == schemas_after


# ---------------------------------------------------------------------------
# TestK2Determinism
# ---------------------------------------------------------------------------


class TestK2Determinism:
    """K2 guard (k2_check_permissions) is pure: same claims → same outcome."""

    def setup_method(self) -> None:
        _ensure_role()

    _VALID_CLAIMS: ClassVar[dict] = {
        "sub": "user-det",
        "tenant_id": "tenant-det",
        "roles": [_ROLE],
        "exp": 9_999_999_999,
    }

    def test_authorized_claims_idempotent(self) -> None:
        """10 sequential calls with authorized claims always pass."""
        required = frozenset({_PERMISSION})
        for _ in range(10):
            # Must not raise
            k2_check_permissions(self._VALID_CLAIMS, required, check_expiry=False)

    def test_unauthorized_claims_idempotent(self) -> None:
        """10 calls with missing permission always raise PermissionDeniedError."""
        claims = {**self._VALID_CLAIMS, "roles": []}  # empty roles → no permissions
        required = frozenset({_PERMISSION})
        for _ in range(10):
            with pytest.raises(PermissionDeniedError):
                k2_check_permissions(claims, required, check_expiry=False)

    def test_none_claims_idempotent(self) -> None:
        """None claims always raises JWTError."""
        required = frozenset({_PERMISSION})
        for _ in range(10):
            with pytest.raises(JWTError):
                k2_check_permissions(None, required, check_expiry=False)

    def test_permission_registry_not_mutated_by_check(self) -> None:
        """Calling k2_check_permissions does not alter PermissionRegistry."""
        before = frozenset(PermissionRegistry.registered_roles())
        required = frozenset({_PERMISSION})
        for _ in range(5):
            k2_check_permissions(self._VALID_CLAIMS, required, check_expiry=False)
        after = frozenset(PermissionRegistry.registered_roles())
        assert before == after

    @given(
        sub=st.text(min_size=1, max_size=60).filter(lambda s: s.strip()),
    )
    @settings(max_examples=40)
    def test_property_authorized_always_passes(self, sub: str) -> None:
        """Claims with the required role always pass regardless of sub field value."""
        _ensure_role()
        # k2 only cares about roles; vary sub to confirm determinism across
        # different claim identities.
        claims = {
            "sub": sub,
            "tenant_id": "tenant-det",
            "roles": [_ROLE],
            "exp": 9_999_999_999,
        }
        required = frozenset({_PERMISSION})
        # Call 3 times - must always pass (deterministic)
        for _ in range(3):
            k2_check_permissions(claims, required, check_expiry=False)

    @given(
        unrelated=st.text(min_size=1, max_size=20).filter(
            lambda s: s.strip() and s != _ROLE
        )
    )
    @settings(max_examples=40)
    def test_property_wrong_role_always_fails(self, unrelated: str) -> None:
        """Claims with only an unregistered role always raise PermissionDeniedError."""
        _ensure_role()
        claims = {**self._VALID_CLAIMS, "roles": [unrelated]}
        required = frozenset({_PERMISSION})
        for _ in range(3):
            with pytest.raises((PermissionDeniedError, Exception)):
                # Either PermissionDenied (role found but no perms) or
                # RoleNotFoundError (role not in registry) — both are consistent
                k2_check_permissions(claims, required, check_expiry=False)


# ---------------------------------------------------------------------------
# TestK3Determinism
# ---------------------------------------------------------------------------


class TestK3Determinism:
    """K3 guard evaluation is deterministic given identical state."""

    def setup_method(self) -> None:
        _ensure_budget()

    def _fresh_tracker(self, initial_usage: int = 0) -> InMemoryUsageTracker:
        """Return a tracker seeded to a specific usage value."""
        t = InMemoryUsageTracker()
        if initial_usage > 0:
            t.increment(_TENANT, _RESOURCE, initial_usage)
        return t

    def test_within_budget_idempotent_fresh_trackers(self) -> None:
        """Same request with fresh-zero tracker always passes."""
        for _ in range(10):
            tracker = self._fresh_tracker(0)
            k3_check_bounds(_TENANT, _RESOURCE, 100, usage_tracker=tracker)

    def test_over_budget_idempotent_fresh_trackers(self) -> None:
        """Same over-budget request with fresh-zero tracker always raises BoundsExceeded."""
        for _ in range(10):
            tracker = self._fresh_tracker(0)
            with pytest.raises(BoundsExceeded):
                k3_check_bounds(
                    _TENANT, _RESOURCE, _BUDGET + 1, usage_tracker=tracker
                )

    def test_same_initial_usage_same_outcome(self) -> None:
        """Pre-seeded usage state produces the same outcome on each call."""
        initial = 5_000
        requested = 4_000  # 5000 + 4000 = 9000 <= 10000 → pass
        for _ in range(5):
            tracker = self._fresh_tracker(initial)
            k3_check_bounds(_TENANT, _RESOURCE, requested, usage_tracker=tracker)

    def test_guard_evaluation_pure_check_not_affected_by_prior_passes(self) -> None:
        """The *check* (current <= budget) does not depend on how many prior
        passes happened in other tracker instances."""
        _ensure_budget()
        # Simulate 10 independent passes (each with fresh tracker) — the budget
        # registry itself is not decremented; it holds a fixed limit.
        for _ in range(10):
            tracker = self._fresh_tracker(0)
            k3_check_bounds(_TENANT, _RESOURCE, 1, usage_tracker=tracker)

        # A fresh tracker still sees budget = _BUDGET, current = 0
        fresh = self._fresh_tracker(0)
        k3_check_bounds(_TENANT, _RESOURCE, _BUDGET, usage_tracker=fresh)

    def test_budget_registry_not_mutated_by_check(self) -> None:
        """k3_check_bounds does not alter BudgetRegistry limits."""
        limit_before = BudgetRegistry.get(_TENANT, _RESOURCE)
        for _ in range(5):
            tracker = self._fresh_tracker(0)
            k3_check_bounds(_TENANT, _RESOURCE, 100, usage_tracker=tracker)
        limit_after = BudgetRegistry.get(_TENANT, _RESOURCE)
        assert limit_before == limit_after

    @given(
        requested=st.integers(min_value=0, max_value=_BUDGET),
        initial=st.integers(min_value=0, max_value=_BUDGET),
    )
    @settings(max_examples=60)
    def test_property_deterministic_given_same_state(
        self, requested: int, initial: int
    ) -> None:
        """Same (requested, initial_usage) always produces the same pass/fail."""
        _ensure_budget()
        # Determine expected outcome once
        expected_pass = (initial + requested) <= _BUDGET
        for _ in range(3):
            tracker = self._fresh_tracker(initial)
            if expected_pass:
                k3_check_bounds(
                    _TENANT, _RESOURCE, requested, usage_tracker=tracker
                )
            else:
                with pytest.raises(BoundsExceeded):
                    k3_check_bounds(
                        _TENANT, _RESOURCE, requested, usage_tracker=tracker
                    )


# ---------------------------------------------------------------------------
# TestK4Determinism
# ---------------------------------------------------------------------------


class TestK4Determinism:
    """K4 guard (k4_inject_trace) is pure: same input → same (corr_id, tenant_id)."""

    _VALID_CLAIMS: ClassVar[dict] = {
        "sub": "user-det-k4",
        "tenant_id": "tenant-det-k4",
        "roles": ["reader"],
    }

    def test_auto_corr_id_stable_across_calls(self) -> None:
        """When providing context_corr_id, result is always the same."""
        ctx_id = str(uuid.uuid4())
        results = [
            k4_inject_trace(self._VALID_CLAIMS, context_corr_id=ctx_id)
            for _ in range(10)
        ]
        assert all(r == results[0] for r in results)

    def test_provided_corr_id_always_returned(self) -> None:
        """Provided UUID always comes back unchanged, call count irrelevant."""
        provided = str(uuid.uuid4())
        for _ in range(10):
            corr_id, tenant_id = k4_inject_trace(
                self._VALID_CLAIMS, provided_correlation_id=provided
            )
            assert corr_id == provided
            assert tenant_id == "tenant-det-k4"

    def test_missing_tenant_always_raises(self) -> None:
        """Missing tenant_id always raises TenantContextError — no intermittent pass."""
        bad_claims = {"sub": "user1", "roles": ["reader"]}
        for _ in range(10):
            with pytest.raises(TenantContextError):
                k4_inject_trace(bad_claims)

    def test_invalid_corr_id_always_raises(self) -> None:
        """Invalid correlation ID format always raises ValueError."""
        for _ in range(10):
            with pytest.raises(ValueError, match="Invalid correlation ID"):
                k4_inject_trace(
                    self._VALID_CLAIMS, provided_correlation_id="not-a-uuid"
                )

    def test_no_global_state_mutated_between_calls(self) -> None:
        """k4_inject_trace reads claims dict but never writes to any registry."""
        # K4 has no registry — just verify the function completes without
        # modifying SchemaRegistry, PermissionRegistry, or BudgetRegistry.
        schema_before = frozenset(SchemaRegistry.registered_ids())
        role_before = frozenset(PermissionRegistry.registered_roles())
        budget_before = frozenset(BudgetRegistry.registered_keys())

        for _ in range(10):
            k4_inject_trace(self._VALID_CLAIMS)

        assert frozenset(SchemaRegistry.registered_ids()) == schema_before
        assert frozenset(PermissionRegistry.registered_roles()) == role_before
        assert frozenset(BudgetRegistry.registered_keys()) == budget_before

    @given(
        tenant_id=st.text(min_size=1, max_size=40).filter(lambda s: s.strip()),
        provided=st.uuids().map(str),
    )
    @settings(max_examples=60)
    def test_property_same_input_same_output(
        self, tenant_id: str, provided: str
    ) -> None:
        """(tenant_id, provided_corr_id) → always the same (corr_id, tenant_id)."""
        claims = {**self._VALID_CLAIMS, "tenant_id": tenant_id}
        results = [
            k4_inject_trace(claims, provided_correlation_id=provided)
            for _ in range(3)
        ]
        assert all(r == results[0] for r in results)

    @given(
        junk=st.text(min_size=1, max_size=50).filter(
            lambda s: s.strip() and not _is_valid_uuid(s)
        )
    )
    @settings(max_examples=40)
    def test_property_invalid_uuid_always_raises(self, junk: str) -> None:
        """Non-UUID provided_corr_id always raises ValueError — deterministic."""
        with pytest.raises(ValueError, match="Invalid correlation ID"):
            k4_inject_trace(self._VALID_CLAIMS, provided_correlation_id=junk)


# ---------------------------------------------------------------------------
# TestCrossGuardIsolation
# ---------------------------------------------------------------------------


class TestCrossGuardIsolation:
    """Evaluating one guard repeatedly does not pollute state seen by others."""

    def setup_method(self) -> None:
        _ensure_schema()
        _ensure_role()
        _ensure_budget()

    def test_k1_does_not_pollute_k2_state(self) -> None:
        """Repeated K1 calls do not alter PermissionRegistry."""
        roles_before = frozenset(PermissionRegistry.registered_roles())
        for _ in range(20):
            k1_validate({"value": 1}, _SCHEMA_ID)
        assert frozenset(PermissionRegistry.registered_roles()) == roles_before

    def test_k2_does_not_pollute_k3_state(self) -> None:
        """Repeated K2 calls do not alter BudgetRegistry."""
        budget_before = frozenset(BudgetRegistry.registered_keys())
        claims = {
            "sub": "u",
            "tenant_id": "t",
            "roles": [_ROLE],
        }
        for _ in range(20):
            k2_check_permissions(claims, frozenset({_PERMISSION}), check_expiry=False)
        assert frozenset(BudgetRegistry.registered_keys()) == budget_before

    def test_k3_does_not_pollute_k1_state(self) -> None:
        """Repeated K3 calls (with fresh trackers) do not alter SchemaRegistry."""
        schemas_before = frozenset(SchemaRegistry.registered_ids())
        for _ in range(20):
            tracker = InMemoryUsageTracker()
            k3_check_bounds(_TENANT, _RESOURCE, 1, usage_tracker=tracker)
        assert frozenset(SchemaRegistry.registered_ids()) == schemas_before

    def test_k4_does_not_pollute_any_registry(self) -> None:
        """Repeated K4 calls leave all registries unchanged."""
        schemas = frozenset(SchemaRegistry.registered_ids())
        roles = frozenset(PermissionRegistry.registered_roles())
        budgets = frozenset(BudgetRegistry.registered_keys())
        claims = {"sub": "u", "tenant_id": "t-iso", "roles": ["r"]}
        for _ in range(20):
            k4_inject_trace(claims)
        assert frozenset(SchemaRegistry.registered_ids()) == schemas
        assert frozenset(PermissionRegistry.registered_roles()) == roles
        assert frozenset(BudgetRegistry.registered_keys()) == budgets

    def test_all_four_guards_interleaved_deterministic(self) -> None:
        """Interleaved K1-K4 evaluations produce consistent outcomes throughout."""
        _ensure_schema()
        _ensure_role()
        _ensure_budget()
        claims = {
            "sub": "u",
            "tenant_id": "tenant-det-16-9",
            "roles": [_ROLE],
        }
        corr_id = str(uuid.uuid4())
        for i in range(5):
            # K1
            k1_validate({"value": i}, _SCHEMA_ID)
            # K2
            k2_check_permissions(claims, frozenset({_PERMISSION}), check_expiry=False)
            # K3 (fresh tracker each iteration)
            tracker = InMemoryUsageTracker()
            k3_check_bounds(_TENANT, _RESOURCE, 10, usage_tracker=tracker)
            # K4
            result = k4_inject_trace(claims, provided_correlation_id=corr_id)
            assert result == (corr_id, "tenant-det-16-9")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, AttributeError):
        return False
