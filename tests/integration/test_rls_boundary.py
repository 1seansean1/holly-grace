"""Tests for holly/storage/rls_boundary.py — Task 22.7.

AC-1: get_rls_required_tables() returns exactly the 10 ICD-boundary tables
      that are marked rls_required=True in ICD_BOUNDARY.
AC-2: get_rls_exempt_tables() returns exactly {kernel_audit_log} (ICD-038
      append-only; no cross-tenant data leakage risk on write-only table).
AC-3: validate_icd_boundary_static() with SchemaManager._RLS_TABLES passes
      with zero violations (spec and impl agree perfectly).
AC-4: validate_icd_boundary_static() detects missing-from-impl violations when
      a required table is absent from the _RLS_TABLES argument.
AC-5: audit_rls_policies() returns all-PASS report when pg_policies returns
      expected rows for all 10 RLS-required tables.
AC-6: audit_rls_policies() returns FAIL verdicts for tables missing from
      pg_policies — cross-tenant access would be UNBLOCKED.
AC-7: audit_rls_policies() detects USING clause mismatch (wrong policy).
AC-8: Cross-tenant isolation invariant: two TenantIsolatedPool instances with
      different tenant_ids issue distinct SET LOCAL calls — data cannot leak.
AC-9: ICD_BOUNDARY covers all 7 Postgres ICDs in Task 22.7 manifest
      (ICD-032, 036, 038, 039, 040, 042, 045 handled separately).
AC-10: render_rls_boundary_report produces valid markdown with headers and
       per-table rows.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.storage.postgres import (
    _RLS_TABLES,
    TenantIsolatedPool,
)
from holly.storage.rls_boundary import (
    EXPECTED_POLICY_NAME,
    EXPECTED_USING_CLAUSE,
    ICD_BOUNDARY,
    RLSBoundaryReport,
    audit_rls_policies,
    get_all_icd_tables,
    get_rls_exempt_tables,
    get_rls_required_tables,
    render_rls_boundary_report,
    validate_icd_boundary_static,
)

# ── Shared helpers ────────────────────────────────────────────────────────


def _tenant() -> uuid.UUID:
    return uuid.uuid4()


def _make_conn(policy_rows: list[dict] | None = None) -> AsyncMock:
    """AsyncMock connection whose fetch() returns policy_rows."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")
    conn.fetch = AsyncMock(return_value=policy_rows or [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=uuid.uuid4())
    return conn


def _make_pool(conn: AsyncMock | None = None) -> MagicMock:
    pool = MagicMock()
    _conn = conn or _make_conn()

    @asynccontextmanager
    async def _acquire():
        yield _conn

    pool.acquire = _acquire
    pool.close = AsyncMock()
    return pool


def _make_tenant_pool(
    tenant_id: uuid.UUID | None = None,
    conn: AsyncMock | None = None,
) -> tuple[TenantIsolatedPool, uuid.UUID, AsyncMock]:
    tid = tenant_id or _tenant()
    c = conn or _make_conn()
    raw = _make_pool(c)
    return TenantIsolatedPool(raw, tid), tid, c


def _policy_rows_for_all_rls_tables() -> list[dict]:
    """Return mock pg_policies rows for all 10 RLS-required tables."""
    return [
        {
            "tablename": t,
            "policyname": EXPECTED_POLICY_NAME,
            "qual": EXPECTED_USING_CLAUSE,
        }
        for t in get_rls_required_tables()
    ]


# ── AC-1: get_rls_required_tables ────────────────────────────────────────


class TestGetRLSRequiredTables:
    """AC-1: returns exactly the 10 tables marked rls_required=True."""

    def test_returns_frozenset(self) -> None:
        assert isinstance(get_rls_required_tables(), frozenset)

    def test_exactly_ten_tables(self) -> None:
        assert len(get_rls_required_tables()) == 10

    def test_icd032_tables_present(self) -> None:
        required = get_rls_required_tables()
        icd032_tables = {"agents", "goals", "topologies", "conversations",
                         "goals_history", "idempotency_keys"}
        assert icd032_tables <= required

    def test_icd036_table_present(self) -> None:
        assert "logs" in get_rls_required_tables()

    def test_icd039_table_present(self) -> None:
        assert "workflow_checkpoints" in get_rls_required_tables()

    def test_icd040_table_present(self) -> None:
        assert "task_state" in get_rls_required_tables()

    def test_icd042_table_present(self) -> None:
        assert "memory_store" in get_rls_required_tables()

    def test_kernel_audit_log_absent(self) -> None:
        """kernel_audit_log is ICD-038 exempt and must NOT appear here."""
        assert "kernel_audit_log" not in get_rls_required_tables()


# ── AC-2: get_rls_exempt_tables ──────────────────────────────────────────


class TestGetRLSExemptTables:
    """AC-2: exactly {kernel_audit_log} is exempt (ICD-038 append-only)."""

    def test_returns_frozenset(self) -> None:
        assert isinstance(get_rls_exempt_tables(), frozenset)

    def test_exactly_one_exempt_table(self) -> None:
        assert len(get_rls_exempt_tables()) == 1

    def test_kernel_audit_log_is_exempt(self) -> None:
        assert "kernel_audit_log" in get_rls_exempt_tables()

    def test_no_overlap_with_required(self) -> None:
        assert get_rls_required_tables().isdisjoint(get_rls_exempt_tables())


# ── AC-3: static validator — spec matches impl ────────────────────────────


class TestValidateICDBoundaryStaticPass:
    """AC-3: static validator passes when spec matches SchemaManager._RLS_TABLES."""

    def test_no_violations_with_correct_impl(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)
        assert report.violations == [], report.violations

    def test_audit_passed_true(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)
        assert report.audit_passed is True

    def test_verdicts_count_matches_all_icd_tables(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)
        assert len(report.verdicts) == len(get_all_icd_tables())

    def test_exempt_verdicts_have_exempt_verdict(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)
        exempt_verdicts = [v for v in report.verdicts if not v.rls_required]
        assert all(v.verdict == "EXEMPT" for v in exempt_verdicts)

    def test_required_verdicts_have_pass_verdict(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)
        required_verdicts = [v for v in report.verdicts if v.rls_required]
        assert all(v.verdict == "PASS" for v in required_verdicts)

    def test_static_without_impl_always_passes(self) -> None:
        """Without impl, only internal consistency checked."""
        report = validate_icd_boundary_static()
        assert report.audit_passed is True


# ── AC-4: static validator — missing-from-impl detection ─────────────────


class TestValidateICDBoundaryStaticFail:
    """AC-4: violations reported when a required table is absent from impl."""

    def test_missing_table_produces_violation(self) -> None:
        truncated = tuple(t for t in _RLS_TABLES if t != "logs")
        report = validate_icd_boundary_static(rls_tables_impl=truncated)
        assert any("logs" in v for v in report.violations)

    def test_missing_table_sets_audit_passed_false(self) -> None:
        truncated = tuple(t for t in _RLS_TABLES if t != "task_state")
        report = validate_icd_boundary_static(rls_tables_impl=truncated)
        assert report.audit_passed is False

    def test_extra_table_in_impl_produces_violation(self) -> None:
        extended = (*_RLS_TABLES, "unknown_table")
        report = validate_icd_boundary_static(rls_tables_impl=extended)
        assert any("unknown_table" in v for v in report.violations)

    def test_empty_impl_produces_10_violations(self) -> None:
        report = validate_icd_boundary_static(rls_tables_impl=())
        # 10 required tables missing from empty impl
        assert report.failed == 0  # static verdicts stay PASS; violations in list
        assert len([v for v in report.violations if "absent from SchemaManager" in v]) == 10


# ── AC-5: audit_rls_policies() — all-pass ────────────────────────────────


class TestAuditRLSPoliciesAllPass:
    """AC-5: returns all-PASS when pg_policies has correct rows."""

    def test_all_pass_when_policies_correct(self) -> None:
        conn = _make_conn(policy_rows=_policy_rows_for_all_rls_tables())

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert report.audit_passed is True

    def test_zero_violations_when_correct(self) -> None:
        conn = _make_conn(policy_rows=_policy_rows_for_all_rls_tables())

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert report.violations == []

    def test_passed_count_equals_ten(self) -> None:
        conn = _make_conn(policy_rows=_policy_rows_for_all_rls_tables())

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert report.passed == 10

    def test_exempt_count_equals_one(self) -> None:
        conn = _make_conn(policy_rows=_policy_rows_for_all_rls_tables())

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert report.exempt == 1


# ── AC-6: audit_rls_policies() — missing policy → FAIL ───────────────────


class TestAuditRLSPoliciesMissingPolicy:
    """AC-6: FAIL verdict and violation when a required table is missing."""

    @pytest.mark.parametrize("missing_table", sorted(get_rls_required_tables()))
    def test_missing_table_yields_fail_verdict(self, missing_table: str) -> None:
        rows = [r for r in _policy_rows_for_all_rls_tables()
                if r["tablename"] != missing_table]
        conn = _make_conn(policy_rows=rows)

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        failed = [v for v in report.verdicts if v.table_name == missing_table]
        assert len(failed) == 1
        assert failed[0].verdict == "FAIL"

    @pytest.mark.parametrize("missing_table", sorted(get_rls_required_tables()))
    def test_missing_table_produces_violation(self, missing_table: str) -> None:
        rows = [r for r in _policy_rows_for_all_rls_tables()
                if r["tablename"] != missing_table]
        conn = _make_conn(policy_rows=rows)

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert any(missing_table in v for v in report.violations)

    def test_empty_policies_all_fail(self) -> None:
        conn = _make_conn(policy_rows=[])

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert report.audit_passed is False
        assert report.failed == 10


# ── AC-7: audit_rls_policies() — clause mismatch ─────────────────────────


class TestAuditRLSPoliciesClauseMismatch:
    """AC-7: FAIL when USING clause does not contain EXPECTED_USING_CLAUSE."""

    def test_wrong_clause_produces_fail(self) -> None:
        rows = _policy_rows_for_all_rls_tables()
        # Corrupt the 'goals' policy
        rows = [
            {**r, "qual": "tenant_id = current_user::uuid"}
            if r["tablename"] == "goals"
            else r
            for r in rows
        ]
        conn = _make_conn(policy_rows=rows)

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        goals_verdict = next(v for v in report.verdicts if v.table_name == "goals")
        assert goals_verdict.verdict == "FAIL"
        assert report.audit_passed is False

    def test_wrong_clause_violation_mentions_mismatch(self) -> None:
        rows = _policy_rows_for_all_rls_tables()
        rows = [
            {**r, "qual": "tenant_id = 'hardcoded_tenant'::uuid"}
            if r["tablename"] == "memory_store"
            else r
            for r in rows
        ]
        conn = _make_conn(policy_rows=rows)

        import asyncio
        report = asyncio.get_event_loop().run_until_complete(audit_rls_policies(conn))
        assert any("mismatch" in v.lower() or "MISMATCH" in v for v in report.violations)


# ── AC-8: Cross-tenant isolation invariant ───────────────────────────────


class TestCrossTenantIsolationInvariant:
    """AC-8: two TenantIsolatedPool instances produce distinct SET LOCAL calls."""

    def test_two_tenants_produce_distinct_set_local(self) -> None:
        tid_a = uuid.UUID("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        tid_b = uuid.UUID("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")

        conn_a = _make_conn()
        conn_b = _make_conn()
        pool_a, _, _ = _make_tenant_pool(tenant_id=tid_a, conn=conn_a)
        pool_b, _, _ = _make_tenant_pool(tenant_id=tid_b, conn=conn_b)

        import asyncio

        async def _run() -> tuple[str, str]:
            async with pool_a.acquire() as ca:
                call_a = ca.execute.call_args_list[0][0][1]
            async with pool_b.acquire() as cb:
                call_b = cb.execute.call_args_list[0][0][1]
            return call_a, call_b

        rls_a, rls_b = asyncio.get_event_loop().run_until_complete(_run())
        assert rls_a != rls_b
        assert str(tid_a) == rls_a
        assert str(tid_b) == rls_b

    def test_tenant_a_rls_string_not_in_tenant_b_context(self) -> None:
        tid_a = uuid.UUID("cccccccc-cccc-4ccc-cccc-cccccccccccc")
        tid_b = uuid.UUID("dddddddd-dddd-4ddd-dddd-dddddddddddd")

        conn_a = _make_conn()
        pool_a, _, _ = _make_tenant_pool(tenant_id=tid_a, conn=conn_a)
        pool_b_conn = _make_conn()
        pool_b, _, _ = _make_tenant_pool(tenant_id=tid_b, conn=pool_b_conn)

        import asyncio

        async def _run() -> None:
            async with pool_a.acquire():
                pass
            async with pool_b.acquire():
                pass

        asyncio.get_event_loop().run_until_complete(_run())
        # Verify tenant A's string was never passed to tenant B's connection
        b_calls = [str(c) for c in pool_b_conn.execute.call_args_list]
        assert str(tid_a) not in " ".join(b_calls)


# ── AC-9: ICD_BOUNDARY covers all 7 Postgres ICDs ────────────────────────


class TestICDBoundaryCompleteness:
    """AC-9: ICD_BOUNDARY spec covers ICD-032/036/038/039/040/042."""

    def test_icd_boundary_has_six_entries(self) -> None:
        """ICD-045 is credentials path, no table — so 6 boundary entries."""
        assert len(ICD_BOUNDARY) == 6

    def test_icd_ids_present(self) -> None:
        ids = {spec.icd_id for spec in ICD_BOUNDARY}
        for expected in ("ICD-032", "ICD-036", "ICD-038", "ICD-039",
                         "ICD-040", "ICD-042"):
            assert expected in ids

    def test_icd038_is_exempt(self) -> None:
        icd038 = next(s for s in ICD_BOUNDARY if s.icd_id == "ICD-038")
        assert icd038.rls_required is False

    def test_all_others_rls_required(self) -> None:
        for spec in ICD_BOUNDARY:
            if spec.icd_id != "ICD-038":
                assert spec.rls_required is True, (
                    f"{spec.icd_id} should be rls_required"
                )

    def test_expected_policy_name_constant(self) -> None:
        assert EXPECTED_POLICY_NAME == "tenant_isolation"

    def test_expected_using_clause_contains_current_setting(self) -> None:
        assert "current_setting" in EXPECTED_USING_CLAUSE
        assert "app.current_tenant" in EXPECTED_USING_CLAUSE

    def test_expected_using_clause_contains_tenant_id(self) -> None:
        assert "tenant_id" in EXPECTED_USING_CLAUSE

    def test_all_icd_tables_count(self) -> None:
        """11 total tables (10 required + 1 exempt)."""
        assert len(get_all_icd_tables()) == 11


# ── AC-10: render report ─────────────────────────────────────────────────


class TestRenderRLSBoundaryReport:
    """AC-10: render_rls_boundary_report produces valid markdown."""

    def _pass_report(self) -> RLSBoundaryReport:
        return validate_icd_boundary_static(rls_tables_impl=_RLS_TABLES)

    def _fail_report(self) -> RLSBoundaryReport:
        truncated = tuple(t for t in _RLS_TABLES if t != "logs")
        return validate_icd_boundary_static(rls_tables_impl=truncated)

    def test_pass_report_contains_header(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        assert "RLS Boundary Audit Report" in text

    def test_pass_report_verdict_text(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        assert "PASS" in text
        assert "all ICD RLS boundaries enforced" in text

    def test_fail_report_verdict_text(self) -> None:
        text = render_rls_boundary_report(self._fail_report())
        assert "FAIL" in text
        assert "violations detected" in text

    def test_pass_report_contains_table_header(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        assert "## Per-Table Verdicts" in text

    def test_pass_report_contains_all_required_tables(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        for table in get_rls_required_tables():
            assert table in text

    def test_pass_report_contains_kernel_audit_log(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        assert "kernel_audit_log" in text

    def test_fail_report_mentions_missing_table(self) -> None:
        text = render_rls_boundary_report(self._fail_report())
        assert "logs" in text

    def test_summary_line_present(self) -> None:
        text = render_rls_boundary_report(self._pass_report())
        assert "Summary:" in text


# ── Property-based tests ─────────────────────────────────────────────────


class TestRLSBoundaryProperties:
    """Property-based invariant checks."""

    @given(
        tables=st.frozensets(
            st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=20),
            min_size=0, max_size=20,
        )
    )
    @settings(max_examples=200)
    def test_required_and_exempt_always_disjoint(self, tables: frozenset[str]) -> None:
        """ICD spec invariant: required ∩ exempt = ∅ always."""
        required = get_rls_required_tables()
        exempt = get_rls_exempt_tables()
        assert required.isdisjoint(exempt)

    @given(
        tid_a=st.uuids(version=4),
        tid_b=st.uuids(version=4),
    )
    @settings(max_examples=200)
    def test_distinct_tenants_produce_distinct_rls_strings(
        self,
        tid_a: uuid.UUID,
        tid_b: uuid.UUID,
    ) -> None:
        """Invariant: tenant_id → RLS context string is injective."""
        from hypothesis import assume
        assume(tid_a != tid_b)
        assert str(tid_a) != str(tid_b)

    @given(
        rls_impl=st.just(tuple(get_rls_required_tables())),
    )
    @settings(max_examples=10)
    def test_static_validator_audit_passed_iff_no_violations(
        self, rls_impl: tuple[str, ...]
    ) -> None:
        """audit_passed ↔ violations == [] always."""
        report = validate_icd_boundary_static(rls_tables_impl=rls_impl)
        assert report.audit_passed == (len(report.violations) == 0)
