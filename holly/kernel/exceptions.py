"""Kernel-layer exception hierarchy.

Tasks 3.7, 3a.10, 16.4, 16.5, 16.6, 17.3, 17.4, 18.3 — ICD contract
enforcement, K8 eval gate, K2 permission gate, K3 bounds checking, K4 trace
injection, K5 idempotency, K6 WAL, K7 HITL gate exceptions.

All kernel exceptions inherit from ``KernelError`` to enable
blanket ``except KernelError`` handling at boundary gateways.
"""

from __future__ import annotations

from typing import Any


class KernelError(Exception):
    """Base exception for all kernel-layer failures."""

    __slots__ = ()


class SchemaNotFoundError(KernelError):
    """Raised when a schema_id cannot be resolved from the registry."""

    __slots__ = ("schema_id",)

    def __init__(self, schema_id: str) -> None:
        super().__init__(f"Schema {schema_id!r} not found in registry")
        self.schema_id = schema_id


class SchemaParseError(KernelError):
    """Raised when a schema is syntactically or semantically invalid."""

    __slots__ = ("detail", "schema_id")

    def __init__(self, schema_id: str, detail: str) -> None:
        super().__init__(f"Schema {schema_id!r} parse error: {detail}")
        self.schema_id = schema_id
        self.detail = detail


class ValidationError(KernelError):
    """Raised when a payload violates an ICD schema.

    Attributes
    ----------
    schema_id : str
        The ICD identifier for the schema that was violated.
    errors : list[dict[str, Any]]
        Field-level validation errors.  Each entry contains at minimum
        ``path`` (JSON Pointer to the violating field) and ``message``.
    payload_hash : str
        SHA-256 of the serialised payload (for audit correlation;
        original payload is *not* stored to avoid PII leakage).
    """

    __slots__ = ("errors", "payload_hash", "schema_id")

    def __init__(
        self,
        schema_id: str,
        errors: list[dict[str, Any]],
        *,
        payload_hash: str = "",
    ) -> None:
        n = len(errors)
        summary = f"{n} violation{'s' if n != 1 else ''}"
        super().__init__(
            f"ICD schema {schema_id!r} validation failed: {summary}"
        )
        self.schema_id = schema_id
        self.errors = errors
        self.payload_hash = payload_hash


class SchemaAlreadyRegisteredError(KernelError):
    """Raised when attempting to re-register an existing schema_id."""

    __slots__ = ("schema_id",)

    def __init__(self, schema_id: str) -> None:
        super().__init__(
            f"Schema {schema_id!r} is already registered and cannot be overwritten"
        )
        self.schema_id = schema_id


class PayloadTooLargeError(KernelError):
    """Raised when payload exceeds the size or nesting depth limit."""

    __slots__ = ("limit", "schema_id", "size")

    def __init__(
        self,
        schema_id: str,
        *,
        size: int,
        limit: int,
    ) -> None:
        super().__init__(
            f"Payload for schema {schema_id!r} exceeds limit: "
            f"{size:,} bytes > {limit:,} bytes"
        )
        self.schema_id = schema_id
        self.size = size
        self.limit = limit


# ── K8 Eval Gate exceptions (Task 3a.10) ─────────────────────────


class KernelInvariantError(KernelError):
    """Raised when a runtime kernel invariant is violated.

    Unlike assertions (which can be stripped with ``python -O``), this
    exception always fires and is always catchable as a ``KernelError``.

    Attributes
    ----------
    invariant : str
        Short identifier for the invariant that was violated
        (e.g. ``"payload_immutability"``).
    """

    __slots__ = ("invariant",)

    def __init__(self, invariant: str, detail: str = "") -> None:
        msg = f"Kernel invariant {invariant!r} violated"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
        self.invariant = invariant


class PredicateNotFoundError(KernelError):
    """Raised when a predicate_id cannot be resolved from the registry."""

    __slots__ = ("predicate_id",)

    def __init__(self, predicate_id: str) -> None:
        super().__init__(f"Predicate {predicate_id!r} not found in registry")
        self.predicate_id = predicate_id


class EvalGateFailure(KernelError):
    """Raised when an output violates a K8 eval gate predicate.

    Attributes
    ----------
    predicate_id : str
        The predicate that was violated.
    output_hash : str
        SHA-256 of the serialised output (for audit; original output
        is *not* stored to avoid PII leakage).
    reason : str
        Human-readable explanation of the violation.
    """

    __slots__ = ("output_hash", "predicate_id", "reason")

    def __init__(
        self,
        predicate_id: str,
        *,
        output_hash: str = "",
        reason: str = "Output violated eval gate",
    ) -> None:
        super().__init__(
            f"K8 eval gate {predicate_id!r} failed: {reason}"
        )
        self.predicate_id = predicate_id
        self.output_hash = output_hash
        self.reason = reason


class EvalError(KernelError):
    """Raised when a predicate evaluation raises an unhandled exception."""

    __slots__ = ("detail", "predicate_id")

    def __init__(self, predicate_id: str, detail: str) -> None:
        super().__init__(
            f"Predicate {predicate_id!r} evaluation error: {detail}"
        )
        self.predicate_id = predicate_id
        self.detail = detail


class PredicateAlreadyRegisteredError(KernelError):
    """Raised when attempting to re-register an existing predicate_id."""

    __slots__ = ("predicate_id",)

    def __init__(self, predicate_id: str) -> None:
        super().__init__(
            f"Predicate {predicate_id!r} is already registered"
        )
        self.predicate_id = predicate_id


# ── K2 Permission Gate exceptions (Task 16.4) ────────────────────────────


class JWTError(KernelError):
    """Raised when JWT claims are missing, malformed, or fail required-field checks.

    Attributes
    ----------
    detail : str
        Human-readable description of the malformed-claims condition.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"JWT claims error: {detail}")
        self.detail = detail


class ExpiredTokenError(JWTError):
    """Raised when the JWT ``exp`` claim is in the past.

    Attributes
    ----------
    exp : int
        The ``exp`` value (Unix timestamp) from the claims dict.
    """

    __slots__ = ("exp",)

    def __init__(self, exp: int) -> None:
        super().__init__(f"token expired at {exp}")
        self.exp = exp


class RevokedTokenError(JWTError):
    """Raised when the JWT ``jti`` is found in the revocation cache.

    Attributes
    ----------
    jti : str
        The ``jti`` (JWT ID) that was revoked.
    """

    __slots__ = ("jti",)

    def __init__(self, jti: str) -> None:
        super().__init__(f"token {jti!r} has been revoked")
        self.jti = jti


class PermissionDeniedError(KernelError):
    """Raised when required permissions are not a subset of granted permissions.

    Attributes
    ----------
    granted : frozenset[str]
        The full set of permissions the caller holds.
    missing : frozenset[str]
        Permissions that were required but not granted (``required - granted``).
    required : frozenset[str]
        The full set of permissions the gate required.
    user_id : str
        Subject identifier from the JWT claims (``sub`` field).
    """

    __slots__ = ("granted", "missing", "required", "user_id")

    def __init__(
        self,
        *,
        user_id: str,
        required: frozenset[str],
        granted: frozenset[str],
        missing: frozenset[str],
    ) -> None:
        super().__init__(
            f"user {user_id!r} missing permissions: {sorted(missing)}"
        )
        self.user_id = user_id
        self.required = required
        self.granted = granted
        self.missing = missing


class RoleNotFoundError(KernelError):
    """Raised when a role has no entry in the PermissionRegistry.

    Attributes
    ----------
    role : str
        The role name that could not be resolved.
    """

    __slots__ = ("role",)

    def __init__(self, role: str) -> None:
        super().__init__(f"Role {role!r} not found in PermissionRegistry")
        self.role = role


class RevocationCacheError(KernelError):
    """Raised when the revocation cache is unavailable.

    The K2 gate applies fail-safe semantics: if revocation status cannot be
    determined, access is denied.

    Attributes
    ----------
    detail : str
        Description of the cache failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Revocation cache unavailable: {detail}")
        self.detail = detail


# ── K3 Bounds Checking exceptions (Task 16.5) ────────────────────────────


class BoundsExceeded(KernelError):
    """Raised when a resource request would exceed the allocated budget.

    Attributes
    ----------
    budget : int
        The configured budget limit for (tenant, resource_type).
    current : int
        The current cumulative usage before this request.
    remaining : int
        Budget remaining before this request (``budget - current``).
    requested : int
        The amount requested in this crossing.
    resource_type : str
        The resource type being checked (e.g. ``"tokens"``, ``"cpu_ms"``).
    tenant_id : str
        The tenant for which the budget was evaluated.
    """

    __slots__ = ("budget", "current", "remaining", "requested", "resource_type", "tenant_id")

    def __init__(
        self,
        *,
        tenant_id: str,
        resource_type: str,
        budget: int,
        current: int,
        requested: int,
        remaining: int,
    ) -> None:
        super().__init__(
            f"K3 bounds exceeded for tenant={tenant_id!r} resource={resource_type!r}: "
            f"current={current} + requested={requested} > budget={budget}"
        )
        self.tenant_id = tenant_id
        self.resource_type = resource_type
        self.budget = budget
        self.current = current
        self.requested = requested
        self.remaining = remaining


class BudgetNotFoundError(KernelError):
    """Raised when no budget is configured for a (tenant, resource_type) pair.

    Attributes
    ----------
    resource_type : str
        The resource type that had no budget entry.
    tenant_id : str
        The tenant for which the budget was sought.
    """

    __slots__ = ("resource_type", "tenant_id")

    def __init__(self, tenant_id: str, resource_type: str) -> None:
        super().__init__(
            f"No budget configured for tenant={tenant_id!r} resource={resource_type!r}"
        )
        self.tenant_id = tenant_id
        self.resource_type = resource_type


class InvalidBudgetError(KernelError):
    """Raised when a configured budget limit is invalid (e.g. negative).

    Attributes
    ----------
    limit : int
        The invalid limit value.
    resource_type : str
        The resource type with the invalid budget.
    tenant_id : str
        The tenant with the invalid budget.
    """

    __slots__ = ("limit", "resource_type", "tenant_id")

    def __init__(self, tenant_id: str, resource_type: str, *, limit: int) -> None:
        super().__init__(
            f"Invalid budget limit {limit} for tenant={tenant_id!r} "
            f"resource={resource_type!r}: must be >= 0"
        )
        self.tenant_id = tenant_id
        self.resource_type = resource_type
        self.limit = limit


class UsageTrackingError(KernelError):
    """Raised when the usage tracking store is unavailable.

    K3 applies fail-safe semantics: if current usage cannot be determined,
    access is denied.

    Attributes
    ----------
    detail : str
        Description of the tracking failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Usage tracker unavailable: {detail}")
        self.detail = detail


# ── K4 Trace Injection exceptions (Task 16.6) ────────────────────────────────


class TenantContextError(KernelError):
    """Raised when JWT claims lack the required ``tenant_id`` field.

    K4 applies fail-safe semantics: every boundary crossing must carry
    tenant context; access is denied if it cannot be established.

    Attributes
    ----------
    detail : str
        Description of the missing context.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Tenant context missing: {detail}")
        self.detail = detail


# ── K5 Idempotency exceptions (Task 17.3) ────────────────────────────────────


class CanonicalizeError(KernelError):
    """Raised when RFC 8785 canonicalization of a payload fails.

    Triggered by non-JSON-serializable types (e.g., ``datetime``, custom
    objects) or unexpected jcs library errors.

    Attributes
    ----------
    detail : str
        Human-readable description of the canonicalization failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Canonicalization failed: {detail}")
        self.detail = detail


class DuplicateRequestError(KernelError):
    """Raised when a request with an already-seen idempotency key is detected.

    K5 applies exactly-once semantics: if a key derived from the payload has
    already been recorded in the idempotency store, the request is a duplicate
    and must be rejected.

    Attributes
    ----------
    key : str
        The 64-char SHA-256 hex idempotency key that collided.
    """

    __slots__ = ("key",)

    def __init__(self, key: str) -> None:
        super().__init__(f"Duplicate request: idempotency key {key!r} already seen")
        self.key = key


# ── K6 WAL exceptions (Task 17.4) ────────────────────────────────────────────


class WALWriteError(KernelError):
    """Raised when the WAL backend fails to persist an entry.

    Typically wraps a database or I/O error.  K6 applies fail-safe
    semantics: a write failure blocks the boundary crossing (EXITING →
    FAULTED).

    Attributes
    ----------
    detail : str
        Human-readable description of the write failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"WAL write error: {detail}")
        self.detail = detail


class WALFormatError(KernelError):
    """Raised when a WALEntry is malformed or missing required fields.

    Examples: empty ``tenant_id``, missing ``correlation_id``, entry that
    cannot be serialised for the backend.

    Attributes
    ----------
    detail : str
        Human-readable description of the format violation.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"WAL format error: {detail}")
        self.detail = detail


class RedactionError(KernelError):
    """Raised when the redaction engine fails unexpectedly.

    Triggered when regex application raises an exception or when PII
    detection throws.  Context → FAULTED on ``RedactionError``.

    Attributes
    ----------
    detail : str
        Human-readable description of the redaction failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Redaction error: {detail}")
        self.detail = detail


# ── K7 HITL Gate exceptions (Task 18.3) ──────────────────────────────────────


class ConfidenceError(KernelError):
    """Raised when the confidence evaluator fails unexpectedly.

    K7 applies fail-safe semantics: if confidence cannot be computed,
    access is denied (operation blocked).

    Attributes
    ----------
    detail : str
        Human-readable description of the evaluator failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Confidence evaluator error: {detail}")
        self.detail = detail


class ApprovalTimeout(KernelError):
    """Raised when no human decision arrives within the configured TTL.

    K7 fail-safe: timeout → deny.

    Attributes
    ----------
    request_id : str
        UUID of the approval request that timed out.
    timeout_seconds : float
        The timeout value (seconds) that elapsed with no decision.
    """

    __slots__ = ("request_id", "timeout_seconds")

    def __init__(self, request_id: str, *, timeout_seconds: float) -> None:
        super().__init__(
            f"Approval request {request_id!r} timed out after {timeout_seconds}s"
        )
        self.request_id = request_id
        self.timeout_seconds = timeout_seconds


class OperationRejected(KernelError):
    """Raised when a human reviewer explicitly rejects an operation.

    Attributes
    ----------
    reason : str
        Human-supplied rejection reason (may be empty string).
    request_id : str
        UUID of the approval request that was rejected.
    reviewer_id : str
        Identity of the reviewer who rejected the operation.
    """

    __slots__ = ("reason", "request_id", "reviewer_id")

    def __init__(
        self,
        request_id: str,
        *,
        reviewer_id: str,
        reason: str = "",
    ) -> None:
        msg = f"Operation {request_id!r} rejected by reviewer {reviewer_id!r}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)
        self.request_id = request_id
        self.reviewer_id = reviewer_id
        self.reason = reason


class ApprovalChannelError(KernelError):
    """Raised when the approval channel (WebSocket/email/dashboard) is unreachable.

    K7 applies fail-safe semantics: channel unavailable → deny.

    Attributes
    ----------
    detail : str
        Human-readable description of the channel failure.
    """

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(f"Approval channel unavailable: {detail}")
        self.detail = detail


# ── Dissimilar verification exceptions (Task 20.3) ────────────────────────


class DissimilarVerificationError(KernelError):
    """Raised when the dissimilar verification channel detects an invariant
    violation in a WAL audit record.

    This exception signals that a kernel invariant was satisfied by the kernel
    itself (execution succeeded and a WALEntry was produced) yet the independent
    dissimilar verifier — which re-checks invariants *without* executing kernel
    gate code — found a contradiction in the audit evidence.

    Attributes
    ----------
    invariant : str
        Short identifier for the violated invariant (e.g. ``"K2_permission"``).
    entry_id : str
        ``WALEntry.id`` of the offending record, or ``"(multi-entry)"`` for
        cross-entry checks.
    detail : str
        Human-readable description of the contradiction detected.
    """

    __slots__ = ("entry_id", "invariant")

    def __init__(self, invariant: str, entry_id: str, detail: str = "") -> None:
        msg = f"Dissimilar verification failed [{invariant}] entry={entry_id!r}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
        self.invariant = invariant
        self.entry_id = entry_id
