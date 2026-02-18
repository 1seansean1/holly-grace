"""ICD Schema Registry — resolves schema_id to Pydantic model with TTL cache.

Task 5.8 — Build ICD Schema Registry.

Extends the JSON-Schema-based ``SchemaRegistry`` (Task 3.7) with Pydantic
model resolution and time-based cache eviction.  This is the Slice 2
evolution: schemas are now typed Pydantic ``BaseModel`` subclasses that
the K1 gate can use for both structural validation and type coercion.

Design rationale
----------------
- Process-global, thread-safe class-level singleton (mirrors SchemaRegistry
  and PredicateRegistry patterns from Slice 1).
- Each cache entry has an ``expires_at`` timestamp.  Entries older than
  ``ttl_seconds`` are evicted on next access (lazy eviction) or via
  explicit ``evict_stale()``.
- Models are registered programmatically during bootstrap.  In later
  slices, a loader may populate from ICD v0.1 spec files.
- ``resolve()`` always returns the same model *class* for a given ID
  within the TTL window (deterministic).
- ``validate()`` instantiates the model with the payload, leveraging
  Pydantic v2 validation.  Returns a model instance on success, raises
  ``ICDValidationError`` on failure.

Performance target
------------------
Per ICD resolution time < 1 ms (p99).  The in-memory dict lookup with
a single float comparison achieves sub-microsecond resolution.
"""

from __future__ import annotations

import threading
import time
from typing import Any, ClassVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from holly.kernel.exceptions import (
    SchemaNotFoundError,
)

# ── Constants ────────────────────────────────────────────

DEFAULT_TTL_SECONDS: float = 3600.0  # 1 hour


# ── Cache entry ──────────────────────────────────────────


class _CacheEntry:
    """Internal cache entry with expiration timestamp."""

    __slots__ = ("expires_at", "model")

    def __init__(self, model: type[BaseModel], expires_at: float) -> None:
        self.model = model
        self.expires_at = expires_at


# ── Exceptions ───────────────────────────────────────────


class ICDValidationError(Exception):
    """Raised when a payload fails Pydantic validation against an ICD model.

    Attributes
    ----------
    schema_id : str
        The ICD identifier for the model that was violated.
    errors : list[dict[str, Any]]
        Pydantic validation errors.
    """

    __slots__ = ("errors", "schema_id")

    def __init__(self, schema_id: str, errors: list[dict[str, Any]]) -> None:
        n = len(errors)
        summary = f"{n} error{'s' if n != 1 else ''}"
        super().__init__(
            f"ICD model {schema_id!r} validation failed: {summary}"
        )
        self.schema_id = schema_id
        self.errors = errors


class ICDModelAlreadyRegisteredError(Exception):
    """Raised when attempting to re-register an existing schema_id."""

    __slots__ = ("schema_id",)

    def __init__(self, schema_id: str) -> None:
        super().__init__(
            f"ICD model {schema_id!r} is already registered and cannot be overwritten"
        )
        self.schema_id = schema_id


# ── Registry ─────────────────────────────────────────────


class ICDSchemaRegistry:
    """Process-global ICD schema registry with Pydantic model support and TTL cache.

    Class-level singleton - all access goes through class methods.

    Each registered model is cached with an expiration timestamp.  Stale
    entries are lazily evicted on ``resolve()`` and can be bulk-evicted
    via ``evict_stale()``.
    """

    _lock: threading.Lock = threading.Lock()
    _entries: ClassVar[dict[str, _CacheEntry]] = {}
    _ttl: ClassVar[float] = DEFAULT_TTL_SECONDS

    # -- configuration -----------------------------------------------------

    @classmethod
    def set_ttl(cls, seconds: float) -> None:
        """Set the TTL for all future registrations.

        Parameters
        ----------
        seconds:
            TTL in seconds.  Must be positive.
        """
        if seconds <= 0:
            msg = f"TTL must be positive, got {seconds}"
            raise ValueError(msg)
        with cls._lock:
            cls._ttl = seconds

    @classmethod
    def get_ttl(cls) -> float:
        """Return the current TTL in seconds."""
        with cls._lock:
            return cls._ttl

    # -- mutators (bootstrap only) -----------------------------------------

    @classmethod
    def register(
        cls,
        schema_id: str,
        model: type[BaseModel],
        *,
        ttl: float | None = None,
    ) -> None:
        """Register a Pydantic model for *schema_id*.

        Parameters
        ----------
        schema_id:
            ICD identifier (e.g. ``"ICD-006"``).
        model:
            A Pydantic ``BaseModel`` subclass.
        ttl:
            Per-entry TTL override.  If None, uses the registry-level TTL.

        Raises
        ------
        TypeError
            If *model* is not a BaseModel subclass.
        ICDModelAlreadyRegisteredError
            If *schema_id* is already registered (and not expired).
        """
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            msg = f"Expected BaseModel subclass, got {type(model).__name__}"
            raise TypeError(msg)

        now = time.monotonic()
        with cls._lock:
            existing = cls._entries.get(schema_id)
            if existing is not None and existing.expires_at > now:
                raise ICDModelAlreadyRegisteredError(schema_id)
            entry_ttl = ttl if ttl is not None else cls._ttl
            cls._entries[schema_id] = _CacheEntry(
                model=model,
                expires_at=now + entry_ttl,
            )

    @classmethod
    def clear(cls) -> None:
        """Remove all registered models.  Intended for testing only."""
        with cls._lock:
            cls._entries.clear()
            cls._ttl = DEFAULT_TTL_SECONDS

    @classmethod
    def evict_stale(cls) -> int:
        """Remove all expired entries.  Returns the number evicted."""
        now = time.monotonic()
        with cls._lock:
            stale = [
                sid for sid, entry in cls._entries.items()
                if entry.expires_at <= now
            ]
            for sid in stale:
                del cls._entries[sid]
            return len(stale)

    # -- queries -----------------------------------------------------------

    @classmethod
    def resolve(cls, schema_id: str) -> type[BaseModel]:
        """Resolve *schema_id* to its Pydantic model class.

        Lazily evicts the entry if its TTL has expired and raises
        ``SchemaNotFoundError``.

        Parameters
        ----------
        schema_id:
            ICD identifier (e.g. ``"ICD-006"``).

        Returns
        -------
        type[BaseModel]
            The registered Pydantic model class.

        Raises
        ------
        SchemaNotFoundError
            If *schema_id* has not been registered or has expired.
        """
        now = time.monotonic()
        with cls._lock:
            entry = cls._entries.get(schema_id)
            if entry is None:
                raise SchemaNotFoundError(schema_id)
            if entry.expires_at <= now:
                del cls._entries[schema_id]
                raise SchemaNotFoundError(schema_id)
            return entry.model

    @classmethod
    def has(cls, schema_id: str) -> bool:
        """Return True if *schema_id* is registered and not expired."""
        now = time.monotonic()
        with cls._lock:
            entry = cls._entries.get(schema_id)
            if entry is None:
                return False
            if entry.expires_at <= now:
                del cls._entries[schema_id]
                return False
            return True

    @classmethod
    def registered_ids(cls) -> frozenset[str]:
        """Return all registered (non-expired) schema IDs."""
        now = time.monotonic()
        with cls._lock:
            return frozenset(
                sid for sid, entry in cls._entries.items()
                if entry.expires_at > now
            )

    @classmethod
    def validate(cls, schema_id: str, payload: dict[str, Any]) -> BaseModel:
        """Resolve *schema_id* and validate *payload* against the model.

        Parameters
        ----------
        schema_id:
            ICD identifier.
        payload:
            Dict to validate.

        Returns
        -------
        BaseModel
            A validated Pydantic model instance.

        Raises
        ------
        SchemaNotFoundError
            If schema_id is not registered or expired.
        ICDValidationError
            If the payload fails Pydantic validation.
        """
        model_cls = cls.resolve(schema_id)
        try:
            return model_cls.model_validate(payload)
        except PydanticValidationError as exc:
            errors = [
                {
                    "loc": list(e["loc"]),
                    "msg": e["msg"],
                    "type": e["type"],
                }
                for e in exc.errors()
            ]
            raise ICDValidationError(schema_id, errors) from exc
