"""Kernel-layer exception hierarchy.

Task 3.7 — ICD contract enforcement exceptions.

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
