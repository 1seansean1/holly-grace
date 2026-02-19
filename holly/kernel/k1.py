"""K1 — Schema Validation gate.

Tasks 3.7 & 16.3 — ICD contract enforcement + KernelContext integration.

Validates an incoming payload against an ICD JSON Schema.  This is the
runtime enforcement counterpart to the metadata-only ``@kernel_boundary``
decorator from Task 3.6.

The gate implements the K1 state machine from Behavior Spec §1.2:

    WAITING -> RESOLVING -> RESOLVED -> VALIDATING -> VALID (pass)
                                                   -> INVALID -> FAULTED (raise)
               -> NOT_FOUND -> FAULTED (raise)

Task 16.3 adds ``k1_gate``, a factory that returns a ``Gate``-compatible
async callable for use within ``KernelContext``:

    async with KernelContext(gates=[k1_gate(payload, "ICD-006")]) as ctx:
        ...  # payload guaranteed schema-valid here

When the gate fails, ``KernelContext.__aenter__`` catches the exception,
advances ENTERING->FAULTED->IDLE (TLA+ liveness: EventuallyIdle), and
re-raises — so the caller always sees the original ``KernelError``.

Usage (standalone)::

    from holly.kernel.k1 import k1_validate
    validated = k1_validate(payload, "ICD-006")

Usage (via KernelContext gate, Task 16.3)::

    from holly.kernel.k1 import k1_gate
    async with KernelContext(gates=[k1_gate(payload, "ICD-006")]) as ctx:
        ...  # payload is guaranteed valid here

Usage (via decorator)::

    @kernel_boundary(gate_id="K1", invariant="schema_validation",
                     icd_schema="ICD-006")
    def my_boundary_func(payload: dict) -> ...:
        ...  # payload is validated before this runs

Design constraints
------------------
- Payload is **never** mutated - deep-copy check is the caller's
  responsibility (invariant 4 from Behavior Spec).
- Schema is resolved **once** per call via SchemaRegistry (cached
  singleton; invariant 2).
- Payload size checked **before** JSON Schema validation to avoid
  expensive traversal on oversized inputs.

Traces to: Behavior Spec §1.2, TLA+ spec (14.1), KernelContext (15.4).
SIL: 3
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from holly.kernel.context import KernelContext

from holly.kernel.exceptions import (
    KernelInvariantError,
    PayloadTooLargeError,
    ValidationError,
)
from holly.kernel.schema_registry import SchemaRegistry

# ── Constants ────────────────────────────────────────────

MAX_PAYLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_NESTING_DEPTH: int = 20


# ── Helpers ──────────────────────────────────────────────


def _payload_hash(payload: Any) -> str:
    """SHA-256 of the JSON-serialised payload (for audit, not PII)."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _measure_depth(obj: Any, _current: int = 0, _ceiling: int = 0) -> int:
    """Return the nesting depth of a JSON-like object.

    When *_ceiling* > 0, traversal short-circuits as soon as depth
    reaches the ceiling — prevents O(N^D) cost on adversarial payloads.
    """
    if _ceiling > 0 and _current >= _ceiling:
        return _current
    if isinstance(obj, dict):
        if not obj:
            return _current + 1
        return max(
            _measure_depth(v, _current + 1, _ceiling) for v in obj.values()
        )
    if isinstance(obj, list):
        if not obj:
            return _current + 1
        return max(
            _measure_depth(v, _current + 1, _ceiling) for v in obj
        )
    return _current


# ── K1 Gate ──────────────────────────────────────────────


def k1_validate(
    payload: Any,
    schema_id: str,
    *,
    max_bytes: int = MAX_PAYLOAD_BYTES,
    max_depth: int = MAX_NESTING_DEPTH,
) -> Any:
    """Validate *payload* against the ICD schema identified by *schema_id*.

    Returns the original *payload* unchanged on success.

    Raises
    ------
    SchemaNotFoundError
        If *schema_id* is not in the SchemaRegistry.
    PayloadTooLargeError
        If the serialised payload exceeds *max_bytes* or nesting exceeds
        *max_depth*.
    ValidationError
        If the payload does not conform to the schema.
    """
    # ── Size guard (before expensive work) ────────────────
    raw = json.dumps(payload, sort_keys=True, default=str)
    size = len(raw.encode("utf-8"))
    if size > max_bytes:
        raise PayloadTooLargeError(schema_id, size=size, limit=max_bytes)

    # ── Depth guard ───────────────────────────────────────
    depth = _measure_depth(payload, _ceiling=max_depth + 1)
    if depth > max_depth:
        raise PayloadTooLargeError(
            schema_id,
            size=depth,
            limit=max_depth,
        )

    # ── Schema resolution (RESOLVING → RESOLVED | NOT_FOUND) ─
    schema = SchemaRegistry.get(schema_id)  # raises SchemaNotFoundError

    # ── Payload immutability snapshot ─────────────────────
    payload_before = copy.deepcopy(payload)

    # ── Validation (VALIDATING → VALID | INVALID) ─────────
    validator = Draft202012Validator(schema)
    errors_raw = list(validator.iter_errors(payload))

    if errors_raw:
        field_errors = [
            {
                "path": "/".join(str(p) for p in e.absolute_path) or "/",
                "message": e.message,
                "validator": e.validator,
            }
            for e in errors_raw
        ]
        raise ValidationError(
            schema_id,
            field_errors,
            payload_hash=_payload_hash(payload),
        )

    # ── Post-validation immutability check ────────────────
    # Explicit exception rather than `assert` so the guard cannot be
    # stripped by Python's -O / -OO optimise flags.
    if payload != payload_before:
        raise KernelInvariantError(
            "payload_immutability",
            "payload was mutated during JSON Schema validation",
        )

    return payload


# ── K1 Gate adapter (KernelContext integration — Task 16.3) ──────────────


def k1_gate(
    payload: Any,
    schema_id: str,
    *,
    max_bytes: int = MAX_PAYLOAD_BYTES,
    max_depth: int = MAX_NESTING_DEPTH,
) -> Callable[[KernelContext], Awaitable[None]]:
    """Return a Gate that validates *payload* against schema *schema_id*.

    The returned coroutine is compatible with the ``Gate`` protocol from
    ``holly.kernel.context`` and participates in the KernelContext
    IDLE->ENTERING->ACTIVE lifecycle::

        async with KernelContext(gates=[k1_gate(payload, "ICD-006")]) as ctx:
            ...  # payload is guaranteed schema-valid here

    On failure the gate raises a subclass of ``KernelError``.  The
    ``KernelContext.__aenter__`` catches it, advances the kernel state
    ENTERING->FAULTED->IDLE, and re-raises — satisfying the TLA+ liveness
    property ``EventuallyIdle: []<>(kstate = IDLE)``.

    Parameters
    ----------
    payload:
        The JSON-like object to validate.
    schema_id:
        ICD identifier registered in ``SchemaRegistry``
        (e.g. ``"ICD-006"``).
    max_bytes:
        Serialised payload size ceiling in bytes (default 10 MB).
    max_depth:
        Maximum nesting depth (default 20 levels).

    Returns
    -------
    Callable[[KernelContext], Awaitable[None]]
        An async gate coroutine; pass it in ``KernelContext(gates=[...])``.

    Raises (propagated through KernelContext)
    -----------------------------------------
    SchemaNotFoundError
        If *schema_id* is not registered.
    PayloadTooLargeError
        If the payload exceeds *max_bytes* or *max_depth*.
    ValidationError
        If the payload violates the schema.

    Traces to: Behavior Spec §1.2 K1, TLA+ spec §14.1, KernelContext §15.4.
    """

    async def _k1_gate(ctx: KernelContext) -> None:
        k1_validate(payload, schema_id, max_bytes=max_bytes, max_depth=max_depth)

    return _k1_gate
