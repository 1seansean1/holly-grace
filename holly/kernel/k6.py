"""K6 - Durability / WAL (Write-Ahead Log) gate (Task 17.4).

Append-only audit log recording every boundary crossing with full context
(payload, claims, gate decision outcomes), enabling compliance auditing,
incident reconstruction, and redaction of sensitive data before persistence.

Algorithm (Behavior Spec §1.7):

1. **ACCUMULATING** — collect trace data from the boundary crossing.
2. **PREPARING** — populate ``WALEntry`` with all K1-K8 gate results.
3. **REDACTING** — apply regex-based redaction rules to ``operation_result``.
4. **WRITING** — call ``WALBackend.append(entry)`` (Postgres in production,
   ``InMemoryWALBackend`` for tests/single-process).
5. **WRITTEN / WRITE_FAILED** — return or raise ``WALWriteError``.

Redaction rules (ICD v0.1 §redaction policy):

- **Email addresses:** ``[email hidden]``
- **API keys / tokens:** ``[secret redacted]``
- **Credit card numbers:** ``****-****-****-<last4>``
- **SSN:** ``[pii redacted]``
- **Phone numbers:** ``[pii redacted]``

TLA+ invariants (Task 14.1):

- ``WALFinality``:  every completed crossing produces exactly one entry.
- ``AppendOnly``:   no entry is deleted or mutated after ``append()``.
- ``RedactionComplete``: ``¬contains_pii(entry.operation_result)`` after write.
- ``TimestampOrdering``: entries ordered by ``timestamp`` in insertion order.

SIL: 3  (docs/SIL_Classification_Matrix.md)
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

try:
    from datetime import UTC
except ImportError:  # Python < 3.11 — datetime.UTC added in 3.11
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

from holly.kernel.exceptions import RedactionError, WALFormatError, WALWriteError

if TYPE_CHECKING:
    from holly.kernel.context import KernelContext

# ---------------------------------------------------------------------------
# Gate type alias (mirrors context.Gate — repeated to avoid circular import)
# ---------------------------------------------------------------------------

Gate = Callable[["KernelContext"], Awaitable[None]]


# ---------------------------------------------------------------------------
# WALEntry dataclass
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WALEntry:
    """Immutable-by-convention audit record for a single boundary crossing.

    Required fields must be supplied at construction time.  Optional K-gate
    fields default to ``None`` and are populated by the caller when the
    corresponding gate ran.  ``redaction_rules_applied`` and
    ``contains_pii_before_redaction`` are populated by ``k6_write_entry``
    during the REDACTING phase.

    Attributes
    ----------
    id : str
        UUID4 string — unique per entry.
    tenant_id : str
        Tenant that owns this boundary crossing.
    correlation_id : str
        Distributed trace correlation ID (set by K4).
    timestamp : datetime
        UTC datetime at entry creation (nanosecond precision where supported).
    boundary_crossing : str
        Symbolic name of the boundary, e.g. ``"core::intent_classifier"``.
    caller_user_id : str
        ``sub`` field from the JWT claims.
    caller_roles : list[str]
        ``roles`` field from the JWT claims.
    exit_code : int
        0 = success, >0 = error code.
    k1_valid : bool
        Result of the K1 schema validation gate.
    k2_authorized : bool
        Result of the K2 permission gate.
    k3_within_budget : bool
        Result of the K3 bounds gate.
    """

    # ── Required ──────────────────────────────────────────────────────────────
    id: str
    tenant_id: str
    correlation_id: str
    timestamp: datetime
    boundary_crossing: str
    caller_user_id: str
    caller_roles: list[str]
    exit_code: int
    k1_valid: bool
    k2_authorized: bool
    k3_within_budget: bool

    # ── Optional K-gate fields ────────────────────────────────────────────────
    k1_schema_id: str | None = None
    k2_required_permissions: list[str] | None = None
    k2_granted_permissions: list[str] | None = None
    k3_resource_type: str | None = None
    k3_budget_limit: int | None = None
    k3_usage_before: int | None = None
    k3_requested: int | None = None
    k5_idempotency_key: str | None = None
    k7_confidence_score: float | None = None
    k7_human_approved: bool | None = None
    k8_eval_passed: bool | None = None
    operation_result: str | None = None

    # ── Populated by k6_write_entry (redaction phase) ────────────────────────
    redaction_rules_applied: list[str] = field(default_factory=list)
    contains_pii_before_redaction: bool = False


# ---------------------------------------------------------------------------
# WALBackend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WALBackend(Protocol):
    """Protocol for append-only WAL storage backends.

    Production implementation uses a PostgreSQL ``audit_wal`` table.
    ``InMemoryWALBackend`` provides an in-process implementation for tests
    and single-process deployments.

    Implementations must guarantee:

    - **Atomicity:** ``append`` either succeeds fully or raises and leaves no
      partial record.
    - **Ordering:** entries are returned in insertion order.
    - **No mutation / deletion** of persisted entries.
    """

    def append(self, entry: WALEntry) -> None:
        """Persist *entry* to the WAL.

        Parameters
        ----------
        entry:
            Fully populated, already-redacted ``WALEntry``.

        Raises
        ------
        WALWriteError
            Backend could not persist the entry.
        """
        ...


class InMemoryWALBackend:
    """In-memory ``WALBackend`` for tests and single-process deployments.

    Thread safety: NOT thread-safe; suitable for sequential tests only.

    Attributes
    ----------
    _entries : list[WALEntry]
        Ordered log of all appended entries.
    _fail : bool
        When ``True``, ``append`` raises ``WALWriteError`` to simulate
        backend failures.
    """

    __slots__ = ("_entries", "_fail")

    def __init__(self) -> None:
        self._entries: list[WALEntry] = []
        self._fail: bool = False

    def append(self, entry: WALEntry) -> None:
        """Append *entry*; raises ``WALWriteError`` when ``_fail`` is set."""
        if self._fail:
            raise WALWriteError("InMemoryWALBackend: simulated write failure")
        self._entries.append(entry)

    @property
    def entries(self) -> list[WALEntry]:
        """Return a snapshot of all appended entries in insertion order."""
        return list(self._entries)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Email: RFC 5322-simplified local-part + @ + domain + TLD
_EMAIL_PAT: re.Pattern[str] = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# API keys / tokens: OpenAI sk- keys, Bearer tokens, generic key=value
_API_KEY_OPENAI_PAT: re.Pattern[str] = re.compile(
    r"\bsk-[A-Za-z0-9_\-]{20,}"
)
_API_KEY_BEARER_PAT: re.Pattern[str] = re.compile(
    r"\bbearer\s+[A-Za-z0-9._\-=+/]{20,}",
    re.IGNORECASE,
)
_API_KEY_GENERIC_PAT: re.Pattern[str] = re.compile(
    r"(?:api[_\-]?key|api[_\-]?token|access[_\-]?token|auth[_\-]?token|secret)"
    r"[=:\s\"']+[A-Za-z0-9._\-=+/]{8,}",
    re.IGNORECASE,
)
_API_KEY_PATS: tuple[re.Pattern[str], ...] = (
    _API_KEY_OPENAI_PAT,
    _API_KEY_BEARER_PAT,
    _API_KEY_GENERIC_PAT,
)

# Credit card: 16 digits in 4 groups (hyphen or space separators optional)
# Capture group 4 = last 4 digits; replacement keeps last 4.
_CREDIT_CARD_PAT: re.Pattern[str] = re.compile(
    r"\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b"
)

# SSN: NNN-NN-NNNN
_SSN_PAT: re.Pattern[str] = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Phone: optional country code, optional parentheses, various separators
_PHONE_PAT: re.Pattern[str] = re.compile(
    r"\b\+?1?[\s\-]?\(?(\d{3})\)?[\s\-]?\d{3}[\s\-]\d{4}\b"
)

_RULE_EMAIL = "email"
_RULE_API_KEY = "api_key"
_RULE_CREDIT_CARD = "credit_card"
_RULE_SSN = "ssn"
_RULE_PHONE = "phone"


def redact(text: str) -> tuple[str, list[str]]:
    """Apply all ICD v0.1 redaction rules to *text*.

    Rules applied in order:

    1. Email addresses → ``[email hidden]``
    2. API keys / tokens → ``[secret redacted]``
    3. Credit card numbers → ``****-****-****-<last4>``
    4. SSN → ``[pii redacted]``
    5. Phone numbers → ``[pii redacted]``

    Parameters
    ----------
    text:
        Raw input string (typically ``WALEntry.operation_result``).

    Returns
    -------
    tuple[str, list[str]]
        ``(redacted_text, rules_applied)`` where ``rules_applied`` is the
        sorted list of rule names that fired (e.g. ``["email", "ssn"]``).
    """
    rules_applied: list[str] = []

    # 1. Email
    redacted_text, n = _EMAIL_PAT.subn("[email hidden]", text)
    if n:
        text = redacted_text
        rules_applied.append(_RULE_EMAIL)

    # 2. API keys / tokens (three patterns, one rule label)
    api_matched = False
    for pat in _API_KEY_PATS:
        redacted_text, n = pat.subn("[secret redacted]", text)
        if n:
            text = redacted_text
            api_matched = True
    if api_matched:
        rules_applied.append(_RULE_API_KEY)

    # 3. Credit card — keep last 4 digits
    def _cc_replace(m: re.Match[str]) -> str:
        return f"****-****-****-{m.group(4)}"

    redacted_text, n = _CREDIT_CARD_PAT.subn(_cc_replace, text)
    if n:
        text = redacted_text
        rules_applied.append(_RULE_CREDIT_CARD)

    # 4. SSN
    redacted_text, n = _SSN_PAT.subn("[pii redacted]", text)
    if n:
        text = redacted_text
        rules_applied.append(_RULE_SSN)

    # 5. Phone
    redacted_text, n = _PHONE_PAT.subn("[pii redacted]", text)
    if n:
        text = redacted_text
        rules_applied.append(_RULE_PHONE)

    return text, rules_applied


def _detect_pii(text: str) -> bool:
    """Return ``True`` if *text* contains any pattern matched by redaction rules.

    Called BEFORE redaction to populate
    ``WALEntry.contains_pii_before_redaction``.
    """
    if _EMAIL_PAT.search(text):
        return True
    for pat in _API_KEY_PATS:
        if pat.search(text):
            return True
    return bool(
        _CREDIT_CARD_PAT.search(text)
        or _SSN_PAT.search(text)
        or _PHONE_PAT.search(text)
    )


# ---------------------------------------------------------------------------
# k6_write_entry
# ---------------------------------------------------------------------------


def k6_write_entry(entry: WALEntry, backend: WALBackend) -> None:
    """Validate, redact, and append *entry* to *backend*.

    Execution phases:
    ``PREPARING`` → ``REDACTING`` → ``REDACTED`` → ``WRITING`` →
    ``WRITTEN`` / ``WRITE_FAILED``.

    Parameters
    ----------
    entry:
        ``WALEntry`` populated by the caller.  ``redaction_rules_applied``
        and ``contains_pii_before_redaction`` are populated here.
    backend:
        ``WALBackend`` implementation.

    Raises
    ------
    WALFormatError
        A required field is empty or invalid.
    RedactionError
        Redaction engine raised an unexpected exception.
    WALWriteError
        Backend ``append`` failed.
    """
    # PREPARING — validate required fields
    if not entry.tenant_id:
        raise WALFormatError("WALEntry.tenant_id must be non-empty")
    if not entry.correlation_id:
        raise WALFormatError("WALEntry.correlation_id must be non-empty")
    if not entry.boundary_crossing:
        raise WALFormatError("WALEntry.boundary_crossing must be non-empty")
    if not entry.caller_user_id:
        raise WALFormatError("WALEntry.caller_user_id must be non-empty")

    # REDACTING — detect PII before redaction, then apply rules
    if entry.operation_result is not None:
        try:
            entry.contains_pii_before_redaction = _detect_pii(
                entry.operation_result
            )
        except Exception as exc:  # pragma: no cover
            raise RedactionError(f"PII detection failed: {exc}") from exc

        try:
            redacted_text, rules = redact(entry.operation_result)
        except Exception as exc:  # pragma: no cover
            raise RedactionError(f"Redaction failed: {exc}") from exc

        entry.operation_result = redacted_text
        entry.redaction_rules_applied = rules

    # WRITING — delegate to backend
    try:
        backend.append(entry)
    except WALWriteError:
        raise
    except Exception as exc:
        raise WALWriteError(f"Backend append failed: {exc}") from exc


# ---------------------------------------------------------------------------
# k6_gate factory
# ---------------------------------------------------------------------------


def k6_gate(
    *,
    boundary_crossing: str,
    claims: dict[str, Any],
    backend: WALBackend,
    exit_code: int = 0,
    operation_result: str | None = None,
    k1_valid: bool = True,
    k1_schema_id: str | None = None,
    k2_authorized: bool = True,
    k2_required_permissions: list[str] | None = None,
    k2_granted_permissions: list[str] | None = None,
    k3_within_budget: bool = True,
    k3_resource_type: str | None = None,
    k3_budget_limit: int | None = None,
    k3_usage_before: int | None = None,
    k3_requested: int | None = None,
    k5_idempotency_key: str | None = None,
    k7_confidence_score: float | None = None,
    k7_human_approved: bool | None = None,
    k8_eval_passed: bool | None = None,
) -> Gate:
    """Return a Gate that writes a WAL entry stamped with context trace IDs.

    The returned gate reads ``ctx.corr_id`` and ``ctx.tenant_id`` at
    execution time (after K4 has injected them) to stamp the entry.  All
    other fields are captured from the closure.

    Parameters
    ----------
    boundary_crossing:
        Symbolic name of the boundary, e.g. ``"core::intent_classifier"``.
    claims:
        Pre-decoded JWT claims dict.  ``sub`` and ``roles`` are extracted.
    backend:
        ``WALBackend`` to write to.
    exit_code:
        0 = success, >0 = error code.  Default 0.
    operation_result:
        Redacted payload or error string.  ``None`` for no result field.
    k1_valid … k8_eval_passed:
        Gate decision outcomes to record.

    Returns
    -------
    Gate
        Async callable ``gate(ctx: KernelContext) -> None``.

    Raises
    ------
    WALFormatError
        Entry validation failed.
    RedactionError
        Redaction engine raised unexpectedly.
    WALWriteError
        Backend write failed; context → FAULTED.
    """

    async def _k6_gate(ctx: KernelContext) -> None:
        entry = WALEntry(
            id=str(uuid.uuid4()),
            tenant_id=ctx.tenant_id or claims.get("tenant_id", ""),
            correlation_id=ctx.corr_id,
            timestamp=datetime.now(UTC),
            boundary_crossing=boundary_crossing,
            caller_user_id=claims.get("sub", ""),
            caller_roles=list(claims.get("roles", [])),
            exit_code=exit_code,
            k1_valid=k1_valid,
            k1_schema_id=k1_schema_id,
            k2_authorized=k2_authorized,
            k2_required_permissions=k2_required_permissions,
            k2_granted_permissions=k2_granted_permissions,
            k3_within_budget=k3_within_budget,
            k3_resource_type=k3_resource_type,
            k3_budget_limit=k3_budget_limit,
            k3_usage_before=k3_usage_before,
            k3_requested=k3_requested,
            k5_idempotency_key=k5_idempotency_key,
            k7_confidence_score=k7_confidence_score,
            k7_human_approved=k7_human_approved,
            k8_eval_passed=k8_eval_passed,
            operation_result=operation_result,
        )
        k6_write_entry(entry, backend)

    return _k6_gate
