"""Unit tests for holly/kernel/dissimilar.py — Task 20.3.

Verifies that the dissimilar verification channel independently detects every
category of kernel invariant violation from WAL audit evidence, without
executing any K1-K8 gate code.

Acceptance criteria (Task_Manifest.md §20.3):
1. Catches intentionally-injected kernel bug (gate result False + exit_code 0).
2. Zero false negatives: every injected bug triggers a violation.
3. Clean entries pass without violations.
4. verify_wal_entries strict=True raises DissimilarVerificationError.
5. verify_wal_entries strict=False collects all violations.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from holly.kernel.dissimilar import (
    VerificationReport,
    VerificationViolation,
    check_k1,
    check_k2,
    check_k3,
    check_k4,
    check_k5,
    check_k6,
    check_k7,
    check_k8,
    check_no_duplicate_ids,
    check_tenant_isolation,
    verify_wal_entries,
)
from holly.kernel.exceptions import DissimilarVerificationError
from holly.kernel.k6 import WALEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW_UTC = datetime.now(UTC)


def _make_entry(
    *,
    entry_id: str | None = None,
    tenant_id: str = "t-001",
    correlation_id: str = "c-001",
    boundary: str = "core::test_boundary",
    caller_user_id: str = "u-001",
    exit_code: int = 0,
    k1_valid: bool = True,
    k2_authorized: bool = True,
    k3_within_budget: bool = True,
    timestamp: datetime = _NOW_UTC,
) -> WALEntry:
    """Construct a minimal valid WALEntry (all gates passed, successful exit)."""
    return WALEntry(
        id=entry_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        timestamp=timestamp,
        boundary_crossing=boundary,
        caller_user_id=caller_user_id,
        caller_roles=["viewer"],
        exit_code=exit_code,
        k1_valid=k1_valid,
        k2_authorized=k2_authorized,
        k3_within_budget=k3_within_budget,
    )


# ---------------------------------------------------------------------------
# TestCheckK1
# ---------------------------------------------------------------------------


class TestCheckK1:
    """check_k1: schema validation gate result vs exit code."""

    def test_clean_entry_passes(self) -> None:
        """k1_valid=True, exit_code=0 → no violation."""
        assert check_k1(_make_entry(k1_valid=True, exit_code=0)) is None

    def test_failed_gate_with_failed_crossing_passes(self) -> None:
        """k1_valid=False, exit_code=1 → legitimate failure, no violation."""
        assert check_k1(_make_entry(k1_valid=False, exit_code=1)) is None

    def test_injected_k1_bug_caught(self) -> None:
        """Kernel bug: k1_valid=False but exit_code=0 → violation K1_schema_validation."""
        v = check_k1(_make_entry(k1_valid=False, exit_code=0))
        assert v is not None
        assert v.invariant == "K1_schema_validation"
        assert "k1_valid=False" in v.detail


# ---------------------------------------------------------------------------
# TestCheckK2
# ---------------------------------------------------------------------------


class TestCheckK2:
    """check_k2: permission gate result vs exit code."""

    def test_clean_entry_passes(self) -> None:
        """k2_authorized=True, exit_code=0 → no violation."""
        assert check_k2(_make_entry(k2_authorized=True, exit_code=0)) is None

    def test_failed_gate_with_failed_crossing_passes(self) -> None:
        """k2_authorized=False, exit_code=1 → legitimate failure, no violation."""
        assert check_k2(_make_entry(k2_authorized=False, exit_code=1)) is None

    def test_injected_k2_bug_caught(self) -> None:
        """Kernel bug: k2_authorized=False but exit_code=0 → violation K2_permission."""
        v = check_k2(_make_entry(k2_authorized=False, exit_code=0))
        assert v is not None
        assert v.invariant == "K2_permission"
        assert "k2_authorized=False" in v.detail


# ---------------------------------------------------------------------------
# TestCheckK3
# ---------------------------------------------------------------------------


class TestCheckK3:
    """check_k3: bounds gate result and budget arithmetic cross-check."""

    def test_clean_entry_passes(self) -> None:
        """k3_within_budget=True, exit_code=0, no metadata → no violation."""
        assert check_k3(_make_entry(k3_within_budget=True, exit_code=0)) is None

    def test_failed_gate_with_failed_crossing_passes(self) -> None:
        """k3_within_budget=False, exit_code=1 → legitimate failure."""
        assert check_k3(_make_entry(k3_within_budget=False, exit_code=1)) is None

    def test_injected_k3_bug_caught(self) -> None:
        """Kernel bug: k3_within_budget=False but exit_code=0 → K3_bounds."""
        v = check_k3(_make_entry(k3_within_budget=False, exit_code=0))
        assert v is not None
        assert v.invariant == "K3_bounds"

    def test_budget_arithmetic_contradiction_caught(self) -> None:
        """k3_within_budget=True but arithmetic says False → K3_bounds_arithmetic."""
        entry = _make_entry(k3_within_budget=True, exit_code=0)
        entry = replace(
            entry,
            k3_budget_limit=100,
            k3_usage_before=90,
            k3_requested=20,  # 90+20=110 > 100, but k3_within_budget=True
        )
        v = check_k3(entry)
        assert v is not None
        assert v.invariant == "K3_bounds_arithmetic"
        assert "110" in v.detail or "contradicts" in v.detail

    def test_budget_arithmetic_consistent_passes(self) -> None:
        """k3_within_budget=True and arithmetic also says True → no violation."""
        entry = _make_entry(k3_within_budget=True, exit_code=0)
        entry = replace(
            entry,
            k3_budget_limit=100,
            k3_usage_before=50,
            k3_requested=30,  # 50+30=80 <= 100
        )
        assert check_k3(entry) is None


# ---------------------------------------------------------------------------
# TestCheckK4
# ---------------------------------------------------------------------------


class TestCheckK4:
    """check_k4: trace injection — tenant_id, correlation_id, timestamp."""

    def test_clean_entry_passes(self) -> None:
        """All K4 fields populated and UTC-aware → no violation."""
        assert check_k4(_make_entry()) is None

    def test_empty_tenant_id_caught(self) -> None:
        """tenant_id='' → K4_trace_tenant_id violation."""
        v = check_k4(_make_entry(tenant_id=""))
        assert v is not None
        assert v.invariant == "K4_trace_tenant_id"

    def test_empty_correlation_id_caught(self) -> None:
        """correlation_id='' → K4_trace_correlation_id violation."""
        v = check_k4(_make_entry(correlation_id=""))
        assert v is not None
        assert v.invariant == "K4_trace_correlation_id"

    def test_naive_timestamp_caught(self) -> None:
        """Timezone-naive datetime → K4_trace_timestamp_tz violation."""
        naive_ts = datetime(2026, 2, 19, 9, 0, 0)  # no tzinfo
        v = check_k4(_make_entry(timestamp=naive_ts))
        assert v is not None
        assert v.invariant == "K4_trace_timestamp_tz"


# ---------------------------------------------------------------------------
# TestCheckK5
# ---------------------------------------------------------------------------


class TestCheckK5:
    """check_k5: idempotency key structural validity."""

    def test_no_key_passes(self) -> None:
        """k5_idempotency_key=None → no violation (K5 optional)."""
        entry = _make_entry()
        # default is None
        assert check_k5(entry) is None

    def test_valid_key_passes(self) -> None:
        """Non-empty k5_idempotency_key → no violation."""
        entry = replace(_make_entry(), k5_idempotency_key="idm-abc-123")
        assert check_k5(entry) is None

    def test_empty_key_caught(self) -> None:
        """k5_idempotency_key='' or whitespace → K5_idempotency_key violation."""
        entry = replace(_make_entry(), k5_idempotency_key="   ")
        v = check_k5(entry)
        assert v is not None
        assert v.invariant == "K5_idempotency_key"


# ---------------------------------------------------------------------------
# TestCheckK6
# ---------------------------------------------------------------------------


class TestCheckK6:
    """check_k6: WAL structural integrity checks."""

    def test_valid_entry_passes(self) -> None:
        """Fully populated valid entry → no violation."""
        assert check_k6(_make_entry()) is None

    def test_empty_boundary_crossing_caught(self) -> None:
        """boundary_crossing='' → K6_wal_required_field violation."""
        v = check_k6(_make_entry(boundary=""))
        assert v is not None
        assert v.invariant == "K6_wal_required_field"
        assert "boundary_crossing" in v.detail

    def test_negative_exit_code_caught(self) -> None:
        """exit_code=-1 → K6_wal_exit_code violation."""
        entry = replace(_make_entry(), exit_code=-1)
        v = check_k6(entry)
        assert v is not None
        assert v.invariant == "K6_wal_exit_code"

    def test_non_list_caller_roles_caught(self) -> None:
        """caller_roles='admin' (string) → K6_wal_caller_roles violation."""
        entry = replace(_make_entry(), caller_roles="admin")  # type: ignore[arg-type]
        v = check_k6(entry)
        assert v is not None
        assert v.invariant == "K6_wal_caller_roles"


# ---------------------------------------------------------------------------
# TestCheckK7
# ---------------------------------------------------------------------------


class TestCheckK7:
    """check_k7: HITL confidence score range and human approval consistency."""

    def test_clean_entry_no_k7_fields_passes(self) -> None:
        """k7_confidence_score=None, k7_human_approved=None → no violation."""
        assert check_k7(_make_entry()) is None

    def test_confidence_above_1_caught(self) -> None:
        """k7_confidence_score=1.5 → K7_hitl_confidence_range violation."""
        entry = replace(_make_entry(), k7_confidence_score=1.5)
        v = check_k7(entry)
        assert v is not None
        assert v.invariant == "K7_hitl_confidence_range"

    def test_confidence_below_0_caught(self) -> None:
        """k7_confidence_score=-0.1 → K7_hitl_confidence_range violation."""
        entry = replace(_make_entry(), k7_confidence_score=-0.1)
        v = check_k7(entry)
        assert v is not None
        assert v.invariant == "K7_hitl_confidence_range"

    def test_injected_k7_approval_bug_caught(self) -> None:
        """Kernel bug: k7_human_approved=False + exit_code=0 → K7_hitl_approval."""
        entry = replace(_make_entry(exit_code=0), k7_human_approved=False)
        v = check_k7(entry)
        assert v is not None
        assert v.invariant == "K7_hitl_approval"

    def test_human_approved_true_passes(self) -> None:
        """k7_human_approved=True + exit_code=0 → no violation."""
        entry = replace(
            _make_entry(exit_code=0),
            k7_confidence_score=0.95,
            k7_human_approved=True,
        )
        assert check_k7(entry) is None


# ---------------------------------------------------------------------------
# TestCheckK8
# ---------------------------------------------------------------------------


class TestCheckK8:
    """check_k8: eval gate result consistency with exit code."""

    def test_clean_entry_no_k8_field_passes(self) -> None:
        """k8_eval_passed=None → no violation (K8 optional)."""
        assert check_k8(_make_entry()) is None

    def test_eval_passed_true_passes(self) -> None:
        """k8_eval_passed=True + exit_code=0 → no violation."""
        entry = replace(_make_entry(exit_code=0), k8_eval_passed=True)
        assert check_k8(entry) is None

    def test_injected_k8_bug_caught(self) -> None:
        """Kernel bug: k8_eval_passed=False + exit_code=0 → K8_eval violation."""
        entry = replace(_make_entry(exit_code=0), k8_eval_passed=False)
        v = check_k8(entry)
        assert v is not None
        assert v.invariant == "K8_eval"
        assert "k8_eval_passed=False" in v.detail


# ---------------------------------------------------------------------------
# TestCrossEntryChecks
# ---------------------------------------------------------------------------


class TestCrossEntryChecks:
    """Cross-entry K4 and K6 invariant checks."""

    def test_tenant_isolation_violation_caught(self) -> None:
        """Same correlation_id with different tenant_ids → K4_tenant_isolation."""
        e1 = _make_entry(correlation_id="corr-x", tenant_id="tenant-A")
        e2 = _make_entry(correlation_id="corr-x", tenant_id="tenant-B")
        violations = check_tenant_isolation([e1, e2])
        assert len(violations) == 1
        assert violations[0].invariant == "K4_tenant_isolation"
        assert "tenant-A" in violations[0].detail or "tenant-B" in violations[0].detail

    def test_tenant_isolation_clean_batch_passes(self) -> None:
        """Same correlation_id with same tenant_id → no violation."""
        e1 = _make_entry(correlation_id="corr-x", tenant_id="tenant-A")
        e2 = _make_entry(correlation_id="corr-x", tenant_id="tenant-A")
        assert check_tenant_isolation([e1, e2]) == []

    def test_duplicate_entry_id_caught(self) -> None:
        """Two WALEntries with same id → K6_wal_duplicate_id violation."""
        eid = str(uuid.uuid4())
        e1 = _make_entry(entry_id=eid, boundary="a::b")
        e2 = _make_entry(entry_id=eid, boundary="c::d")
        violations = check_no_duplicate_ids([e1, e2])
        assert len(violations) == 1
        assert violations[0].invariant == "K6_wal_duplicate_id"

    def test_unique_entry_ids_pass(self) -> None:
        """Entries with distinct ids → no duplicate violation."""
        entries = [_make_entry() for _ in range(5)]
        assert check_no_duplicate_ids(entries) == []


# ---------------------------------------------------------------------------
# TestVerifyWalEntries
# ---------------------------------------------------------------------------


class TestVerifyWalEntries:
    """Main public API: verify_wal_entries — strict and non-strict modes."""

    def test_clean_batch_passes(self) -> None:
        """All-valid entries → VerificationReport(passed=True, violations=[])."""
        entries = [_make_entry() for _ in range(4)]
        report = verify_wal_entries(entries, strict=False)
        assert report.passed is True
        assert report.violations == []
        assert report.entries_checked == 4

    def test_empty_batch_passes(self) -> None:
        """Zero entries → VerificationReport(passed=True)."""
        report = verify_wal_entries([], strict=False)
        assert report.passed is True
        assert report.entries_checked == 0

    def test_strict_mode_raises_on_first_violation(self) -> None:
        """strict=True (default): first violation raises DissimilarVerificationError."""
        bad = _make_entry(k2_authorized=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([bad])
        exc = exc_info.value
        assert exc.invariant == "K2_permission"
        assert isinstance(exc, DissimilarVerificationError)

    def test_non_strict_collects_all_violations(self) -> None:
        """strict=False: all violations collected, report.passed=False."""
        entries = [
            _make_entry(k1_valid=False, exit_code=0),  # K1 bug
            _make_entry(k2_authorized=False, exit_code=0),  # K2 bug
            _make_entry(k3_within_budget=False, exit_code=0),  # K3 bug
        ]
        report = verify_wal_entries(entries, strict=False)
        assert report.passed is False
        invariants = {v.invariant for v in report.violations}
        assert "K1_schema_validation" in invariants
        assert "K2_permission" in invariants
        assert "K3_bounds" in invariants

    def test_injected_kernel_bug_k2_caught_zero_false_negatives(self) -> None:
        """AC: catches intentionally-injected kernel bug; zero false negatives.

        Injects all 5 detectable 'gate passed but exit succeeded' bugs:
        K1, K2, K3, K7, K8. Verifies each produces exactly one violation.
        """
        bugs = [
            ("K1_schema_validation", _make_entry(k1_valid=False, exit_code=0)),
            ("K2_permission", _make_entry(k2_authorized=False, exit_code=0)),
            ("K3_bounds", _make_entry(k3_within_budget=False, exit_code=0)),
            ("K7_hitl_approval", replace(_make_entry(exit_code=0), k7_human_approved=False)),
            ("K8_eval", replace(_make_entry(exit_code=0), k8_eval_passed=False)),
        ]
        for expected_invariant, bad_entry in bugs:
            with pytest.raises(DissimilarVerificationError) as exc_info:
                verify_wal_entries([bad_entry], strict=True)
            assert exc_info.value.invariant == expected_invariant, (
                f"Expected {expected_invariant!r}, "
                f"got {exc_info.value.invariant!r}"
            )

    def test_report_is_verification_report_instance(self) -> None:
        """verify_wal_entries returns VerificationReport dataclass."""
        report = verify_wal_entries([], strict=False)
        assert isinstance(report, VerificationReport)

    def test_violation_is_verification_violation_instance(self) -> None:
        """Violations in report are VerificationViolation instances."""
        bad = _make_entry(k1_valid=False, exit_code=0)
        report = verify_wal_entries([bad], strict=False)
        assert len(report.violations) == 1
        assert isinstance(report.violations[0], VerificationViolation)
