"""Kernel-layer exception hierarchy.

Tasks 3.7, 3a.10 & 16.4 — ICD contract enforcement, K8 eval gate, K2 permission
gate exceptions.

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
