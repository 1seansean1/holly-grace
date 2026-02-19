"""Task 20.3 — Dissimilar Verification Channel integration tests.

Verifies Behavior Spec §1.1 INV-5 + §1.2-§1.9: the dissimilar verification
channel independently detects kernel invariant violations from WAL audit
evidence produced by real K4+K6 gate executions, without re-executing kernel
gate code.

Acceptance criteria (Task_Manifest.md §20.3):
1. Catches intentionally-injected kernel bug (zero false negatives).
2. Clean gate chain WAL entries pass with no violations.
3. Each of the 8 invariants (K1-K8) independently produces a violation when
   the corresponding WAL field contradicts the exit_code.
4. Cross-entry invariants (tenant isolation, duplicate IDs) are independently
   detected.
5. verify_wal_entries is dissimilar: does not invoke K1-K8 gate functions.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import pytest

from holly.kernel.context import KernelContext
from holly.kernel.dissimilar import VerificationReport, verify_wal_entries
from holly.kernel.exceptions import DissimilarVerificationError
from holly.kernel.k4 import k4_gate
from holly.kernel.k6 import InMemoryWALBackend, WALEntry, k6_gate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLAIMS: dict[str, Any] = {
    "sub": "user-20-3",
    "tenant_id": "tenant-20-3",
    "roles": ["viewer"],
    "exp": 9_999_999_999,
}

_BOUNDARY = "core::test_20_3"


def _make_k4() -> Any:
    """Build a k4_gate with standard test claims."""
    return k4_gate(claims=_CLAIMS)


def _make_k6(
    backend: InMemoryWALBackend,
    *,
    k1_valid: bool = True,
    k2_authorized: bool = True,
    k3_within_budget: bool = True,
    k7_confidence_score: float | None = None,
    k7_human_approved: bool | None = None,
    k8_eval_passed: bool | None = None,
    exit_code: int = 0,
    boundary: str = _BOUNDARY,
) -> Any:
    """Build a k6_gate capturing specified gate decision outcomes."""
    return k6_gate(
        boundary_crossing=boundary,
        claims=_CLAIMS,
        backend=backend,
        exit_code=exit_code,
        k1_valid=k1_valid,
        k2_authorized=k2_authorized,
        k3_within_budget=k3_within_budget,
        k7_confidence_score=k7_confidence_score,
        k7_human_approved=k7_human_approved,
        k8_eval_passed=k8_eval_passed,
    )


async def _run(
    *gates: Any,
    should_fail: bool = False,
) -> None:
    """Execute a KernelContext with the given gate chain."""
    ctx = KernelContext(gates=list(gates))
    try:
        async with ctx:
            pass
    except Exception:
        if not should_fail:
            raise


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_backend() -> InMemoryWALBackend:
    """Each test gets a clean InMemoryWALBackend (returned for convenience)."""
    return InMemoryWALBackend()


# ---------------------------------------------------------------------------
# TestCleanGateChainPasses
# ---------------------------------------------------------------------------


class TestCleanGateChainPasses:
    """WAL entries from clean K4+K6 gate chains pass the dissimilar verifier."""

    async def test_single_successful_crossing(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """One successful K4+K6 crossing → one WALEntry → no violations."""
        backend = _fresh_backend
        await _run(_make_k4(), _make_k6(backend))
        entries = backend.entries
        assert len(entries) == 1
        report = verify_wal_entries(entries, strict=False)
        assert report.passed is True
        assert report.entries_checked == 1

    async def test_multiple_successful_crossings(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Three sequential crossings → three WALEntries → all clean."""
        backend = _fresh_backend
        for _ in range(3):
            await _run(_make_k4(), _make_k6(backend))
        assert len(backend.entries) == 3
        report = verify_wal_entries(backend.entries, strict=False)
        assert report.passed is True

    async def test_k7_fields_populated_pass(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """K7 fields present and valid (confidence=0.92, approved=True) → no violation."""
        backend = _fresh_backend
        await _run(
            _make_k4(),
            _make_k6(backend, k7_confidence_score=0.92, k7_human_approved=True),
        )
        report = verify_wal_entries(backend.entries, strict=False)
        assert report.passed is True

    async def test_k8_field_populated_pass(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """K8 field present and True → no violation."""
        backend = _fresh_backend
        await _run(_make_k4(), _make_k6(backend, k8_eval_passed=True))
        report = verify_wal_entries(backend.entries, strict=False)
        assert report.passed is True


# ---------------------------------------------------------------------------
# TestInjectedBugsCaught — AC: catches intentionally-injected kernel bug
# ---------------------------------------------------------------------------


class TestInjectedBugsCaught:
    """Mutate WALEntry fields to simulate kernel bugs; verify all caught."""

    async def _get_entry(
        self, backend: InMemoryWALBackend, **k6_kwargs: Any
    ) -> WALEntry:
        """Run a crossing and return the single WALEntry."""
        await _run(_make_k4(), _make_k6(backend, **k6_kwargs))
        return backend.entries[0]

    async def test_k1_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: k1_valid=False, exit_code=0 → DissimilarVerificationError K1."""
        entry = await self._get_entry(_fresh_backend, k1_valid=True)
        buggy = replace(entry, k1_valid=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K1_schema_validation"

    async def test_k2_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: k2_authorized=False, exit_code=0 → DissimilarVerificationError K2."""
        entry = await self._get_entry(_fresh_backend, k2_authorized=True)
        buggy = replace(entry, k2_authorized=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K2_permission"

    async def test_k3_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: k3_within_budget=False, exit_code=0 → K3_bounds."""
        entry = await self._get_entry(_fresh_backend, k3_within_budget=True)
        buggy = replace(entry, k3_within_budget=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K3_bounds"

    async def test_k4_tenant_id_erasure_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: tenant_id erased after K4 ran → K4_trace_tenant_id."""
        entry = await self._get_entry(_fresh_backend)
        assert entry.tenant_id  # K4 should have populated it
        buggy = replace(entry, tenant_id="")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K4_trace_tenant_id"

    async def test_k4_correlation_id_erasure_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: correlation_id erased → K4_trace_correlation_id."""
        entry = await self._get_entry(_fresh_backend)
        buggy = replace(entry, correlation_id="")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K4_trace_correlation_id"

    async def test_k6_required_field_erasure_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: boundary_crossing erased → K6_wal_required_field."""
        entry = await self._get_entry(_fresh_backend)
        buggy = replace(entry, boundary_crossing="")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K6_wal_required_field"

    async def test_k7_approval_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: k7_human_approved=False, exit_code=0 → K7_hitl_approval."""
        entry = await self._get_entry(
            _fresh_backend, k7_human_approved=True, k7_confidence_score=0.9
        )
        buggy = replace(entry, k7_human_approved=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K7_hitl_approval"

    async def test_k8_eval_bug_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Inject bug: k8_eval_passed=False, exit_code=0 → K8_eval."""
        entry = await self._get_entry(_fresh_backend, k8_eval_passed=True)
        buggy = replace(entry, k8_eval_passed=False, exit_code=0)
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([buggy])
        assert exc_info.value.invariant == "K8_eval"


# ---------------------------------------------------------------------------
# TestCrossEntryInvariants
# ---------------------------------------------------------------------------


class TestCrossEntryInvariants:
    """Cross-entry dissimilar checks (tenant isolation, duplicate IDs)."""

    async def test_tenant_isolation_violation_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Two entries share a correlation_id but different tenant_ids → K4_tenant_isolation."""
        backend = _fresh_backend
        await _run(_make_k4(), _make_k6(backend, boundary="a::x"))
        entries = backend.entries.copy()
        entry0 = entries[0]
        # Manufacture a second entry with same corr_id but different tenant
        injected = replace(
            entry0,
            id=str(uuid.uuid4()),
            tenant_id="attacker-tenant",
            boundary_crossing="b::y",
        )
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([entry0, injected])
        assert exc_info.value.invariant == "K4_tenant_isolation"

    async def test_duplicate_entry_ids_caught(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """Replay attack: same WALEntry.id in two entries → K6_wal_duplicate_id."""
        backend = _fresh_backend
        await _run(_make_k4(), _make_k6(backend, boundary="core::alpha"))
        entry = backend.entries[0]
        duplicate = replace(entry, boundary_crossing="core::beta")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_wal_entries([entry, duplicate])
        assert exc_info.value.invariant == "K6_wal_duplicate_id"


# ---------------------------------------------------------------------------
# TestLegitimateFailurePasses
# ---------------------------------------------------------------------------


class TestLegitimateFailurePasses:
    """Entries with exit_code > 0 and gate results False should NOT be flagged
    (these represent legitimate gate-blocked crossings, not kernel bugs).
    """

    async def test_legitimate_k2_denial_not_flagged(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """exit_code=1, k2_authorized=False → legitimate failure, no violation."""
        backend = _fresh_backend
        # k6_gate does not itself fail; it records the gate outcome.
        await _run(
            _make_k4(),
            _make_k6(backend, k2_authorized=False, exit_code=1),
        )
        report = verify_wal_entries(backend.entries, strict=False)
        assert report.passed is True

    async def test_non_strict_reports_not_raises(
        self, _fresh_backend: InMemoryWALBackend
    ) -> None:
        """strict=False on injected-bug batch returns report, does not raise."""
        backend = _fresh_backend
        await _run(_make_k4(), _make_k6(backend))
        entry = backend.entries[0]
        buggy = replace(entry, k1_valid=False, exit_code=0)
        report = verify_wal_entries([buggy], strict=False)
        assert isinstance(report, VerificationReport)
        assert report.passed is False
        assert any(v.invariant == "K1_schema_validation" for v in report.violations)
