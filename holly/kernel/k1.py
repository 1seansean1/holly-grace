"""K1 — Schema Validation gate.

Task 3.7 — ICD contract enforcement.

Validates an incoming payload against an ICD JSON Schema.  This is the
runtime enforcement counterpart to the metadata-only ``@kernel_boundary``
decorator from Task 3.6.

The gate implements the K1 state machine from Behavior Spec §1.2:

    WAITING → RESOLVING → RESOLVED → VALIDATING → VALID (pass)
                                                 → INVALID → FAULTED (raise)
              → NOT_FOUND → FAULTED (raise)

Usage (standalone)::

    from holly.kernel.k1 import k1_validate
    validated = k1_validate(payload, "ICD-006")

Usage (via decorator)::

    @kernel_boundary(gate_id="K1", invariant="schema_validation",
                     icd_schema="ICD-006")
    def my_boundary_func(payload: dict) -> ...:
        ...  # payload is validated before this runs

Design constraints
------------------
- Payload is **never** mutated — deep-copy check is the caller's
  responsibility (invariant 4 from Behavior Spec).
- Schema is resolved **once** per call via SchemaRegistry (cached
  singleton; invariant 2).
- Payload size checked **before** JSON Schema validation to avoid
  expensive traversal on oversized inputs.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

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
