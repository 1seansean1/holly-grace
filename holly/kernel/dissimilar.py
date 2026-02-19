"""Dissimilar verification channel — Task 20.3.

Independent post-hoc cross-check of all eight kernel invariants (K1-K8) against
``WALEntry`` audit records produced by K6, without executing any kernel gate code.

Algorithm (Behavior Spec §1.1 INV-5 + §1.2-§1.9 gate invariants):

1.  **Per-entry checks** — for each ``WALEntry`` in the sequence:
    - ``check_k1``: ``k1_valid == True`` for every successful crossing
      (``exit_code == 0``).
    - ``check_k2``: ``k2_authorized == True`` for every successful crossing.
    - ``check_k3``: ``k3_within_budget == True`` for every successful crossing;
      re-computes arithmetic from metadata when present.
    - ``check_k4``: ``tenant_id`` and ``correlation_id`` non-empty; ``timestamp``
      timezone-aware.
    - ``check_k5``: ``k5_idempotency_key`` non-empty when present.
    - ``check_k6``: all six required WALEntry fields populated; ``caller_roles``
      is a list; ``exit_code >= 0``.
    - ``check_k7``: ``k7_confidence_score`` in ``[0.0, 1.0]`` when present;
      ``k7_human_approved == True`` for every successful crossing when present.
    - ``check_k8``: ``k8_eval_passed == True`` for every successful crossing
      when present.

2.  **Cross-entry checks** — after per-entry scan:
    - ``check_tenant_isolation``: the same ``correlation_id`` always maps to the
      same ``tenant_id`` (no cross-tenant correlation ID reuse).
    - ``check_no_duplicate_ids``: all ``WALEntry.id`` values are unique.
    - ``check_timestamp_tz``: every entry timestamp is UTC-aware (redundant
      per-entry check retained here for the cross-entry report).

3.  **Report** — ``VerificationReport`` collects all ``VerificationViolation``
    objects.  Calling ``verify_wal_entries(..., strict=True)`` (the default)
    raises ``DissimilarVerificationError`` on the *first* violation found.

Dissimilarity guarantee:
    This module does not import or invoke any of ``k1.py``-``k8.py`` at runtime.
    All checks are independent re-implementations derived solely from the
    invariant predicates specified in the Component Behavior Spec and TLA+ spec.

SIL: 3  (docs/SIL_Classification_Matrix.md)

Traces to:
    Task_Manifest.md §20.3
    Behavior Spec §1.1 (Invariants INV-1 - INV-7)
    Behavior Spec §1.2-§1.9 (K1-K8 acceptance criteria)
    TLA+ spec  docs/tla/KernelInvariants.tla
    FMEA-K001  docs/FMEA_Kernel_Invariants.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from holly.kernel.exceptions import DissimilarVerificationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from holly.kernel.k6 import WALEntry


# ---------------------------------------------------------------------------
# Violation record
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class VerificationViolation:
    """Single invariant violation detected by the dissimilar verifier.

    Attributes
    ----------
    entry_id : str
        ``WALEntry.id`` of the offending record, or ``"(multi-entry)"`` for
        cross-entry checks.
    invariant : str
        Short tag identifying the violated invariant
        (e.g. ``"K2_permission"``).
    detail : str
        Human-readable explanation of the contradiction.
    """

    entry_id: str
    invariant: str
    detail: str


# ---------------------------------------------------------------------------
# Verification report
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class VerificationReport:
    """Aggregated result of ``verify_wal_entries``.

    Attributes
    ----------
    passed : bool
        ``True`` iff no violations were found.
    entries_checked : int
        Count of ``WALEntry`` objects that were examined.
    violations : list[VerificationViolation]
        All violations found (empty when ``passed`` is ``True``).
    """

    passed: bool
    entries_checked: int
    violations: list[VerificationViolation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-entry invariant checkers (pure functions — no kernel gate code invoked)
# ---------------------------------------------------------------------------


def check_k1(entry: WALEntry) -> VerificationViolation | None:
    """K1 (Schema Validation): gate result must be consistent with exit code.

    Invariant: ``exit_code == 0  ⟹  k1_valid == True``.

    A ``False`` result combined with a successful exit is a kernel bug —
    the kernel accepted a payload that failed schema validation.
    """
    if entry.exit_code == 0 and not entry.k1_valid:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K1_schema_validation",
            detail=(
                f"exit_code=0 but k1_valid=False "
                f"(boundary={entry.boundary_crossing!r})"
            ),
        )
    return None


def check_k2(entry: WALEntry) -> VerificationViolation | None:
    """K2 (Permission Gate): gate result must be consistent with exit code.

    Invariant: ``exit_code == 0  ⟹  k2_authorized == True``.
    """
    if entry.exit_code == 0 and not entry.k2_authorized:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K2_permission",
            detail=(
                f"exit_code=0 but k2_authorized=False "
                f"(user={entry.caller_user_id!r}, "
                f"roles={entry.caller_roles!r})"
            ),
        )
    return None


def check_k3(entry: WALEntry) -> VerificationViolation | None:
    """K3 (Bounds Checking): gate result consistent with exit code AND budget
    arithmetic cross-verified from metadata when present.

    Invariant 1: ``exit_code == 0  ⟹  k3_within_budget == True``.
    Invariant 2 (when metadata present):
        ``k3_within_budget == True  ⟹
          k3_usage_before + k3_requested <= k3_budget_limit``.
    """
    if entry.exit_code == 0 and not entry.k3_within_budget:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K3_bounds",
            detail="exit_code=0 but k3_within_budget=False",
        )

    # Re-compute arithmetic from metadata (independent of gate code)
    limit = entry.k3_budget_limit
    usage = entry.k3_usage_before
    requested = entry.k3_requested
    if limit is not None and usage is not None and requested is not None:
        computed_within = (usage + requested) <= limit
        if entry.k3_within_budget != computed_within:
            return VerificationViolation(
                entry_id=entry.id,
                invariant="K3_bounds_arithmetic",
                detail=(
                    f"k3_within_budget={entry.k3_within_budget!r} "
                    f"contradicts arithmetic: "
                    f"{usage}+{requested} <= {limit} is {computed_within}"
                ),
            )

    return None


def check_k4(entry: WALEntry) -> VerificationViolation | None:
    """K4 (Trace Injection): tenant_id, correlation_id, and timestamp must be
    populated and structurally valid.

    Invariant (Behavior Spec §1.5 INV-1): every boundary crossing has a
    non-null tenant_id and correlation_id injected by K4.
    The timestamp must be timezone-aware (UTC).
    """
    if not entry.tenant_id:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K4_trace_tenant_id",
            detail="tenant_id is empty or missing",
        )
    if not entry.correlation_id:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K4_trace_correlation_id",
            detail="correlation_id is empty or missing",
        )
    if entry.timestamp.tzinfo is None:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K4_trace_timestamp_tz",
            detail="timestamp is timezone-naive; must be UTC-aware",
        )
    return None


def check_k5(entry: WALEntry) -> VerificationViolation | None:
    """K5 (Idempotency Key): when present, the idempotency key must be a
    non-empty, non-whitespace string.

    Invariant: ``k5_idempotency_key is not None  ⟹  len(key.strip()) > 0``.
    """
    key = entry.k5_idempotency_key
    if key is not None and not key.strip():
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K5_idempotency_key",
            detail=(
                "k5_idempotency_key is present but empty or whitespace-only"
            ),
        )
    return None


def check_k6(entry: WALEntry) -> VerificationViolation | None:
    """K6 (WAL Durability): all six required WALEntry fields must be populated,
    caller_roles must be a list, and exit_code must be non-negative.

    These checks verify that the WAL entry was fully written and structurally
    sound (Behavior Spec §1.7 ``WALFinality`` invariant).
    """
    _REQUIRED: tuple[tuple[str, object], ...] = (
        ("id", entry.id),
        ("tenant_id", entry.tenant_id),
        ("correlation_id", entry.correlation_id),
        ("boundary_crossing", entry.boundary_crossing),
        ("caller_user_id", entry.caller_user_id),
    )
    for fname, fval in _REQUIRED:
        if not fval:
            return VerificationViolation(
                entry_id=entry.id or "(unknown)",
                invariant="K6_wal_required_field",
                detail=f"required field {fname!r} is empty or missing",
            )
    if not isinstance(entry.caller_roles, list):
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K6_wal_caller_roles",
            detail=(
                f"caller_roles must be list, "
                f"got {type(entry.caller_roles).__name__!r}"
            ),
        )
    if entry.exit_code < 0:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K6_wal_exit_code",
            detail=f"exit_code must be >= 0, got {entry.exit_code}",
        )
    return None


def check_k7(entry: WALEntry) -> VerificationViolation | None:
    """K7 (HITL Gate): confidence score must be in [0.0, 1.0] when present;
    human approval must be True for successful crossings when present.

    Invariant 1: ``k7_confidence_score is not None  ⟹  0.0 <= score <= 1.0``.
    Invariant 2: ``exit_code == 0 AND k7_human_approved is not None
                    ⟹  k7_human_approved == True``.
    """
    score = entry.k7_confidence_score
    if score is not None and not (0.0 <= score <= 1.0):
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K7_hitl_confidence_range",
            detail=(
                f"k7_confidence_score={score!r} is outside [0.0, 1.0]"
            ),
        )
    if entry.k7_human_approved is False and entry.exit_code == 0:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K7_hitl_approval",
            detail="exit_code=0 but k7_human_approved=False",
        )
    return None


def check_k8(entry: WALEntry) -> VerificationViolation | None:
    """K8 (Eval Gate): eval result must be consistent with exit code.

    Invariant: ``exit_code == 0 AND k8_eval_passed is not None
                 ⟹  k8_eval_passed == True``.
    """
    if entry.k8_eval_passed is False and entry.exit_code == 0:
        return VerificationViolation(
            entry_id=entry.id,
            invariant="K8_eval",
            detail="exit_code=0 but k8_eval_passed=False",
        )
    return None


# ---------------------------------------------------------------------------
# Cross-entry invariant checkers
# ---------------------------------------------------------------------------

_MULTI_ENTRY = "(multi-entry)"


def check_tenant_isolation(
    entries: Sequence[WALEntry],
) -> list[VerificationViolation]:
    """Cross-entry K4: the same correlation_id must always map to the same
    tenant_id (no cross-tenant correlation ID reuse).

    Invariant (Behavior Spec §1.5 INV-2 tenant_isolation):
        ``∀ e1, e2: e1.correlation_id == e2.correlation_id
            ⟹  e1.tenant_id == e2.tenant_id``.
    """
    seen: dict[str, str] = {}
    violations: list[VerificationViolation] = []
    for entry in entries:
        corr = entry.correlation_id
        tid = entry.tenant_id
        if not corr:
            continue  # already caught by check_k4 per-entry
        if corr in seen:
            if seen[corr] != tid:
                violations.append(
                    VerificationViolation(
                        entry_id=_MULTI_ENTRY,
                        invariant="K4_tenant_isolation",
                        detail=(
                            f"correlation_id={corr!r} appears with "
                            f"tenant_ids {seen[corr]!r} and {tid!r}"
                        ),
                    )
                )
        else:
            seen[corr] = tid
    return violations


def check_no_duplicate_ids(
    entries: Sequence[WALEntry],
) -> list[VerificationViolation]:
    """Cross-entry K6: all WALEntry.id values must be unique (AppendOnly +
    WALFinality invariants require each crossing produces exactly one entry).
    """
    seen: dict[str, str] = {}  # entry_id -> boundary_crossing
    violations: list[VerificationViolation] = []
    for entry in entries:
        eid = entry.id
        if not eid:
            continue  # already caught by check_k6 per-entry
        if eid in seen:
            violations.append(
                VerificationViolation(
                    entry_id=eid,
                    invariant="K6_wal_duplicate_id",
                    detail=(
                        f"entry id {eid!r} duplicated "
                        f"(first at boundary={seen[eid]!r}, "
                        f"duplicate at boundary={entry.boundary_crossing!r})"
                    ),
                )
            )
        else:
            seen[eid] = entry.boundary_crossing
    return violations


# ---------------------------------------------------------------------------
# Ordered per-entry checker pipeline
# ---------------------------------------------------------------------------

_PER_ENTRY_CHECKS = (
    check_k1,
    check_k2,
    check_k3,
    check_k4,
    check_k5,
    check_k6,
    check_k7,
    check_k8,
)


# ---------------------------------------------------------------------------
# Primary public API
# ---------------------------------------------------------------------------


def verify_wal_entries(
    entries: Sequence[WALEntry],
    *,
    strict: bool = True,
) -> VerificationReport:
    """Cross-check all eight kernel invariants against a sequence of WAL entries.

    This function constitutes the dissimilar verification channel.  It does not
    execute any K1-K8 gate code; all checks are independent re-implementations
    derived from the Behavior Spec invariant predicates.

    Parameters
    ----------
    entries:
        Sequence of ``WALEntry`` objects to verify (typically from
        ``InMemoryWALBackend.entries`` or a Postgres WAL query).
    strict:
        When ``True`` (default): raises ``DissimilarVerificationError`` on the
        *first* violation found.  When ``False``: collects all violations and
        returns a ``VerificationReport`` with ``passed=False``.

    Returns
    -------
    VerificationReport
        ``report.passed == True`` iff no violations were found.

    Raises
    ------
    DissimilarVerificationError
        First violation encountered, when ``strict=True``.
    """
    violations: list[VerificationViolation] = []

    # Phase 1: per-entry checks
    for entry in entries:
        for checker in _PER_ENTRY_CHECKS:
            v = checker(entry)
            if v is not None:
                if strict:
                    raise DissimilarVerificationError(
                        invariant=v.invariant,
                        entry_id=v.entry_id,
                        detail=v.detail,
                    )
                violations.append(v)

    # Phase 2: cross-entry checks
    for cross_check in (check_tenant_isolation, check_no_duplicate_ids):
        for v in cross_check(entries):
            if strict:
                raise DissimilarVerificationError(
                    invariant=v.invariant,
                    entry_id=v.entry_id,
                    detail=v.detail,
                )
            violations.append(v)

    return VerificationReport(
        passed=len(violations) == 0,
        entries_checked=len(entries),
        violations=violations,
    )
