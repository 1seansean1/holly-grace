"""ICD Schema Registry — resolves and caches ICD schemas.

Task 3.7 — ICD contract enforcement.

The registry is a process-global, thread-safe store of JSON-Schema
objects keyed by ICD identifier (e.g. ``"ICD-006"``).  Schemas are
registered programmatically during application bootstrap and are
immutable once registered (no hot-swap to avoid mid-request
schema changes).

Design rationale
----------------
- In Phase A Spiral (Slice 1) schemas are registered in-process via
  ``register()``.  Later slices may add file-based or remote resolution.
- Deterministic: ``get()`` always returns the same dict for a given ID.
- Thread-safe: uses a lock around the mutable ``_schemas`` dict.
"""

from __future__ import annotations

import threading
from typing import Any, ClassVar

from holly.kernel.exceptions import (
    SchemaAlreadyRegisteredError,
    SchemaNotFoundError,
    SchemaParseError,
)


class SchemaRegistry:
    """Process-global ICD schema registry.

    Class-level singleton — all access goes through class methods.
    """

    _lock: threading.Lock = threading.Lock()
    _schemas: ClassVar[dict[str, dict[str, Any]]] = {}

    # -- mutators (bootstrap only) -----------------------------------------

    @classmethod
    def register(cls, schema_id: str, schema: dict[str, Any]) -> None:
        """Register a JSON Schema for *schema_id*.

        Parameters
        ----------
        schema_id:
            ICD identifier (e.g. ``"ICD-006"``).
        schema:
            A valid JSON Schema dict.

        Raises
        ------
        SchemaParseError
            If *schema* is not a dict or lacks a ``"type"`` key.
        """
        if not isinstance(schema, dict):
            raise SchemaParseError(
                schema_id, f"Expected dict, got {type(schema).__name__}"
            )
        if "type" not in schema:
            raise SchemaParseError(
                schema_id, "Schema dict must contain a 'type' key"
            )
        with cls._lock:
            if schema_id in cls._schemas:
                raise SchemaAlreadyRegisteredError(schema_id)
            cls._schemas[schema_id] = schema

    @classmethod
    def clear(cls) -> None:
        """Remove all registered schemas.  Intended for testing only."""
        with cls._lock:
            cls._schemas.clear()

    # -- queries -----------------------------------------------------------

    @classmethod
    def get(cls, schema_id: str) -> dict[str, Any]:
        """Resolve *schema_id* to its JSON Schema dict.

        Returns the exact same dict object on every call (idempotent).

        Raises
        ------
        SchemaNotFoundError
            If *schema_id* has not been registered.
        """
        with cls._lock:
            try:
                return cls._schemas[schema_id]
            except KeyError:
                raise SchemaNotFoundError(schema_id) from None

    @classmethod
    def has(cls, schema_id: str) -> bool:
        """Return True if *schema_id* is registered."""
        with cls._lock:
            return schema_id in cls._schemas

    @classmethod
    def registered_ids(cls) -> frozenset[str]:
        """Return all registered schema IDs."""
        with cls._lock:
            return frozenset(cls._schemas)
