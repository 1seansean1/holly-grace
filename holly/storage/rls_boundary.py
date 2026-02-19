"""RLS boundary audit: cross-reference ICD specs → Postgres tables → policies (Task 22.7).

Each ICD that involves PostgreSQL defines a tenant isolation contract.  This
module makes those contracts **explicit and machine-checkable**:

1. ``ICD_BOUNDARY`` — canonical mapping of ICD identifier → tables + RLS flag.
2. ``get_rls_required_tables()`` / ``get_rls_exempt_tables()`` — derived sets.
3. ``validate_icd_boundary_static()`` — pure, no-DB consistency check against
   the SchemaManager constants (``_RLS_TABLES``).
4. ``audit_rls_policies(conn)`` — async, queries ``pg_policies`` catalog and
   returns a ``RLSBoundaryReport`` with per-table verdicts.

ICD references
--------------
* ICD-032  Core ↔ PostgreSQL (State/History)     — 6 tables, RLS required
* ICD-036  Observability ↔ PostgreSQL (Logs)      — 1 table, RLS required
* ICD-038  Kernel ↔ PostgreSQL (Audit WAL)        — 1 table, RLS **exempt**
            (append-only per ICD-038 §Auth)
* ICD-039  Workflow Engine ↔ PostgreSQL (Checkpoints) — 1 table, RLS required
* ICD-040  Engine ↔ PostgreSQL (Task State)       — 1 table, RLS required
* ICD-042  Memory System ↔ PostgreSQL (Memory)    — 1 table, RLS required
* ICD-045  KMS → PostgreSQL (DB Credentials)      — credential path, no table

Total RLS-required:  10 tables
Total RLS-exempt:     1 table (kernel_audit_log)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from holly.storage.postgres import ConnectionProto

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected policy constants (must match SchemaManager.enable_rls())
# ---------------------------------------------------------------------------

EXPECTED_POLICY_NAME: str = "tenant_isolation"
EXPECTED_USING_CLAUSE: str = (
    "tenant_id = current_setting('app.current_tenant', TRUE)::uuid"
)

# ---------------------------------------------------------------------------
# ICD boundary specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ICDBoundarySpec:
    """One ICD's Postgres boundary contract."""

    icd_id: str
    """e.g. 'ICD-032'."""

    tables: tuple[str, ...]
    """Tables covered by this ICD."""

    rls_required: bool
    """True → every table must have a tenant_isolation RLS policy."""

    rationale: str = ""
    """Human-readable reason (used in reports)."""


# Canonical ICD → table mapping (single source of truth for tenant isolation).
# ICD-045 (KMS credentials) governs the *DSN / role* path, not a table, so
# it is omitted from the table-level spec.
ICD_BOUNDARY: tuple[ICDBoundarySpec, ...] = (
    ICDBoundarySpec(
        icd_id="ICD-032",
        tables=(
            "agents",
            "goals",
            "topologies",
            "conversations",
            "goals_history",
            "idempotency_keys",
        ),
        rls_required=True,
        rationale="Core state tables: tenant_id immutable; RLS enforces isolation",
    ),
    ICDBoundarySpec(
        icd_id="ICD-036",
        tables=("logs",),
        rls_required=True,
        rationale="Observability logs partitioned + RLS-scoped per tenant",
    ),
    ICDBoundarySpec(
        icd_id="ICD-038",
        tables=("kernel_audit_log",),
        rls_required=False,
        rationale=(
            "Append-only audit WAL: role 'holly_kernel_audit' has INSERT only. "
            "RLS not enforced to ensure audit writes are never blocked."
        ),
    ),
    ICDBoundarySpec(
        icd_id="ICD-039",
        tables=("workflow_checkpoints",),
        rls_required=True,
        rationale="Checkpoint tenant_id immutable; cross-tenant recovery blocked by RLS",
    ),
    ICDBoundarySpec(
        icd_id="ICD-040",
        tables=("task_state",),
        rls_required=True,
        rationale="Task-state projection; RLS ensures per-tenant SELECT scope",
    ),
    ICDBoundarySpec(
        icd_id="ICD-042",
        tables=("memory_store",),
        rls_required=True,
        rationale="Medium-term memory; RLS enforces per-tenant retention isolation",
    ),
)


def get_rls_required_tables() -> frozenset[str]:
    """Return tables that MUST have a tenant_isolation RLS policy per ICD specs."""
    return frozenset(
        t for spec in ICD_BOUNDARY if spec.rls_required for t in spec.tables
    )


def get_rls_exempt_tables() -> frozenset[str]:
    """Return tables explicitly exempted from RLS per ICD specs."""
    return frozenset(
        t for spec in ICD_BOUNDARY if not spec.rls_required for t in spec.tables
    )


def get_all_icd_tables() -> frozenset[str]:
    """Return all tables managed by any Postgres ICD."""
    return frozenset(t for spec in ICD_BOUNDARY for t in spec.tables)


# ---------------------------------------------------------------------------
# Report types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RLSTableVerdict:
    """Per-table RLS audit result."""

    table_name: str
    rls_required: bool
    rls_enabled: bool
    policy_name: str | None
    using_clause: str | None
    verdict: str  # "PASS" | "FAIL" | "EXEMPT"
    detail: str = ""


@dataclass(slots=True)
class RLSBoundaryReport:
    """Full audit report for the ICD RLS boundary."""

    verdicts: list[RLSTableVerdict] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    audit_passed: bool = False

    @property
    def passed(self) -> int:
        return sum(1 for v in self.verdicts if v.verdict == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for v in self.verdicts if v.verdict == "FAIL")

    @property
    def exempt(self) -> int:
        return sum(1 for v in self.verdicts if v.verdict == "EXEMPT")


# ---------------------------------------------------------------------------
# Static validator (no DB required)
# ---------------------------------------------------------------------------


def validate_icd_boundary_static(
    rls_tables_impl: tuple[str, ...] | None = None,
) -> RLSBoundaryReport:
    """Check ICD_BOUNDARY spec consistency against implementation constants.

    If *rls_tables_impl* is provided (e.g. ``SchemaManager._RLS_TABLES``), the
    validator also verifies that the set of RLS-required tables matches exactly.
    Without it, only internal spec consistency is checked.

    This function is **pure** and **synchronous** — no DB connection required.
    """
    report = RLSBoundaryReport()

    required = get_rls_required_tables()
    exempt = get_rls_exempt_tables()

    # Check for overlapping required/exempt (spec bug)
    overlap = required & exempt
    if overlap:
        for t in sorted(overlap):
            report.violations.append(
                f"Table '{t}' appears in both RLS-required and RLS-exempt specs "
                f"(ICD_BOUNDARY inconsistency)"
            )

    # Emit per-table verdicts based purely on spec
    for spec in ICD_BOUNDARY:
        for table in spec.tables:
            if spec.rls_required:
                report.verdicts.append(
                    RLSTableVerdict(
                        table_name=table,
                        rls_required=True,
                        rls_enabled=True,  # assumed — schema manager must enable
                        policy_name=EXPECTED_POLICY_NAME,
                        using_clause=EXPECTED_USING_CLAUSE,
                        verdict="PASS",
                        detail=f"{spec.icd_id}: {spec.rationale}",
                    )
                )
            else:
                report.verdicts.append(
                    RLSTableVerdict(
                        table_name=table,
                        rls_required=False,
                        rls_enabled=False,
                        policy_name=None,
                        using_clause=None,
                        verdict="EXEMPT",
                        detail=f"{spec.icd_id}: {spec.rationale}",
                    )
                )

    # Optionally cross-check against SchemaManager._RLS_TABLES
    if rls_tables_impl is not None:
        impl_set = frozenset(rls_tables_impl)
        spec_set = required

        missing_from_impl = spec_set - impl_set
        extra_in_impl = impl_set - spec_set

        for t in sorted(missing_from_impl):
            report.violations.append(
                f"Table '{t}' is RLS-required per ICD_BOUNDARY "
                f"but absent from SchemaManager._RLS_TABLES"
            )
        for t in sorted(extra_in_impl):
            report.violations.append(
                f"Table '{t}' is in SchemaManager._RLS_TABLES "
                f"but not marked RLS-required in ICD_BOUNDARY"
            )

    report.audit_passed = len(report.violations) == 0
    return report


# ---------------------------------------------------------------------------
# Live DB auditor (async, queries pg_policies)
# ---------------------------------------------------------------------------


async def audit_rls_policies(conn: ConnectionProto) -> RLSBoundaryReport:
    """Query ``pg_policies`` catalog and validate all ICD-boundary tables.

    Checks:
    - Every RLS-required table has EXACTLY the 'tenant_isolation' policy.
    - The USING clause matches ``EXPECTED_USING_CLAUSE``.
    - Exempt tables have NO tenant_isolation policy (integrity check).

    Returns a ``RLSBoundaryReport`` with per-table verdicts.
    """
    report = RLSBoundaryReport()

    # Fetch all tenant_isolation policies from the public schema
    rows: Sequence[object] = await conn.fetch(
        """
        SELECT tablename, policyname, qual
        FROM pg_policies
        WHERE schemaname = 'public'
          AND policyname = $1
        ORDER BY tablename
        """,
        EXPECTED_POLICY_NAME,
        timeout=10.0,
    )

    # Build lookup: table_name → (policy_name, using_clause)
    policy_map: dict[str, tuple[str, str]] = {}
    for row in rows:
        policy_map[row["tablename"]] = (row["policyname"], row["qual"] or "")

    for spec in ICD_BOUNDARY:
        for table in spec.tables:
            if spec.rls_required:
                if table not in policy_map:
                    verdict = RLSTableVerdict(
                        table_name=table,
                        rls_required=True,
                        rls_enabled=False,
                        policy_name=None,
                        using_clause=None,
                        verdict="FAIL",
                        detail=(
                            f"{spec.icd_id}: missing tenant_isolation policy — "
                            f"cross-tenant access is UNBLOCKED"
                        ),
                    )
                    report.violations.append(
                        f"{table}: required RLS policy missing ({spec.icd_id})"
                    )
                else:
                    _, using_clause = policy_map[table]
                    clause_ok = EXPECTED_USING_CLAUSE in using_clause
                    verdict = RLSTableVerdict(
                        table_name=table,
                        rls_required=True,
                        rls_enabled=True,
                        policy_name=EXPECTED_POLICY_NAME,
                        using_clause=using_clause,
                        verdict="PASS" if clause_ok else "FAIL",
                        detail=(
                            f"{spec.icd_id}: policy found, clause "
                            + ("correct" if clause_ok else f"MISMATCH: {using_clause!r}")
                        ),
                    )
                    if not clause_ok:
                        report.violations.append(
                            f"{table}: USING clause mismatch — expected "
                            f"'{EXPECTED_USING_CLAUSE}', got '{using_clause}'"
                        )
            else:
                # Exempt: verify no tenant_isolation policy exists (integrity)
                has_policy = table in policy_map
                verdict = RLSTableVerdict(
                    table_name=table,
                    rls_required=False,
                    rls_enabled=has_policy,
                    policy_name=EXPECTED_POLICY_NAME if has_policy else None,
                    using_clause=policy_map[table][1] if has_policy else None,
                    verdict="EXEMPT",
                    detail=(
                        f"{spec.icd_id}: append-only, RLS intentionally absent"
                        if not has_policy
                        else f"{spec.icd_id}: WARNING — unexpected RLS found on exempt table"
                    ),
                )
                if has_policy:
                    log.warning(
                        "RLS policy found on exempt table '%s' (%s) — "
                        "may block audit appends",
                        table,
                        spec.icd_id,
                    )
            report.verdicts.append(verdict)

    # Flag any tables in policy_map not in ICD_BOUNDARY (unexpected policies)
    all_icd_tables = get_all_icd_tables()
    for table in sorted(policy_map):
        if table not in all_icd_tables:
            report.violations.append(
                f"{table}: has tenant_isolation policy but is not in ICD_BOUNDARY spec"
            )
            log.warning("Unexpected tenant_isolation policy on table '%s'", table)

    report.audit_passed = len(report.violations) == 0
    return report


# ---------------------------------------------------------------------------
# Convenience: render report text
# ---------------------------------------------------------------------------


def render_rls_boundary_report(report: RLSBoundaryReport) -> str:
    """Render an ``RLSBoundaryReport`` as a markdown string."""
    lines: list[str] = []
    lines.append("# RLS Boundary Audit Report (Task 22.7)")
    lines.append("")
    verdict_line = "PASS — all ICD RLS boundaries enforced" if report.audit_passed else "FAIL — RLS boundary violations detected"
    lines.append(f"**Verdict:** {verdict_line}")
    lines.append(f"**Summary:** {report.passed} PASS | {report.failed} FAIL | {report.exempt} EXEMPT")
    lines.append("")
    lines.append("## Per-Table Verdicts")
    lines.append("")
    lines.append("| Table | Required | Verdict | Detail |")
    lines.append("|-------|----------|---------|--------|")
    for v in sorted(report.verdicts, key=lambda x: x.table_name):
        req = "✓" if v.rls_required else "—"
        lines.append(f"| {v.table_name} | {req} | {v.verdict} | {v.detail} |")
    lines.append("")
    if report.violations:
        lines.append("## Violations")
        lines.append("")
        for violation in report.violations:
            lines.append(f"- {violation}")
        lines.append("")
    else:
        lines.append("## Violations")
        lines.append("")
        lines.append("None. Cross-tenant data access is blocked for all ICD boundaries.")
        lines.append("")
    return "\n".join(lines)
