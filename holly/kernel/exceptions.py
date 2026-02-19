"""Kernel-layer exception hierarchy.

Tasks 3.7 & 3a.10 — ICD contract enforcement + K8 eval gate exceptions.

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
