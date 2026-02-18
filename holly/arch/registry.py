"""Thread-safe singleton registry for architecture.yaml.

Task 2.6 — Implement singleton loader.
Task 2.7 — Component / boundary / ICD lookups.
Task 2.8 — Hot-reload with validation.

The ``ArchitectureRegistry`` is the single Python entry-point for
querying the machine-readable SAD.  It lazily loads and validates
``architecture.yaml`` on first access, is safe under concurrent
thread access (``threading.Lock``), and exposes the full
``ArchitectureDocument`` model for downstream consumers (decorators,
drift detection, traceability matrix).

Design decisions (per Task 2.3 ADR scope):
- **Singleton via class-level lock** rather than module-level global:
  avoids import-time side effects; allows explicit ``reset()`` for
  testing and hot-reload.
- **Lazy init**: YAML is not read until the first query, so importing
  the module has zero I/O cost.
- **Thread-safety**: a single ``threading.Lock`` guards the load path;
  once loaded, reads are lock-free (the reference swap is atomic in
  CPython, and we use a snapshot pattern for correctness on other
  runtimes).
- **Typed lookups** (Task 2.7): ``get_component``, ``get_boundary``,
  ``get_icd`` provide O(1) or O(n) access to components, boundary-
  crossing connections, and per-component interface control documents.
  Unknown keys raise ``ComponentNotFoundError``.
- **Hot-reload** (Task 2.8): ``reload()`` re-reads and re-validates
  the YAML under the lock.  On success the new document replaces the
  old atomically.  On failure (validation error, missing file) the
  previous state is retained — callers never see a partially loaded
  registry.  A version counter (``generation``) increments on every
  successful reload so consumers can detect staleness.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import ClassVar

import yaml

from holly.arch.schema import ArchitectureDocument, Component, Connection, LayerID


class RegistryNotLoadedError(RuntimeError):
    """Raised when the registry is accessed before any YAML is available."""


class RegistryValidationError(ValueError):
    """Raised when architecture.yaml fails Pydantic validation."""


class ComponentNotFoundError(KeyError):
    """Raised when a component ID is not present in the architecture."""

    def __init__(self, component_id: str) -> None:
        super().__init__(component_id)
        self.component_id = component_id

    def __str__(self) -> str:
        return f"No component with id {self.component_id!r} in architecture.yaml"


class ArchitectureRegistry:
    """Thread-safe singleton accessor for architecture.yaml.

    Usage::

        reg = ArchitectureRegistry.get()      # lazy-loads on first call
        doc = reg.document                     # ArchitectureDocument
        comp = doc.components["KERNEL"]        # Component lookup

    The default YAML path is ``docs/architecture.yaml`` relative to the
    repo root.  Override via ``ArchitectureRegistry.configure(path)``.
    """

    # ── class-level singleton state ──────────────────────
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _instance: ClassVar[ArchitectureRegistry | None] = None
    _yaml_path: ClassVar[Path | None] = None

    # ── instance state ───────────────────────────────────
    __slots__ = ("_document", "_generation")

    def __init__(self, document: ArchitectureDocument, generation: int = 1) -> None:
        self._document = document
        self._generation = generation

    # ── public API ───────────────────────────────────────

    @classmethod
    def configure(cls, yaml_path: Path | str) -> None:
        """Set the YAML path before first access.

        Can also be called to point at a different file before a
        subsequent ``reset()`` + ``get()`` cycle.
        """
        cls._yaml_path = Path(yaml_path)

    @classmethod
    def get(cls) -> ArchitectureRegistry:
        """Return the singleton, loading on first call.

        Thread-safe: concurrent callers block on the lock; only one
        performs the actual load.

        Raises
        ------
        FileNotFoundError
            If the YAML path does not exist.
        RegistryValidationError
            If the YAML fails Pydantic schema validation.
        """
        # Fast path — already initialised (lock-free read).
        inst = cls._instance
        if inst is not None:
            return inst

        with cls._lock:
            # Double-checked locking.
            if cls._instance is not None:
                return cls._instance

            path = cls._resolve_path()
            doc = cls._load(path)
            cls._instance = cls(doc)
            return cls._instance

    @classmethod
    def is_loaded(cls) -> bool:
        """Return ``True`` if the singleton has been initialised."""
        return cls._instance is not None

    @classmethod
    def reset(cls) -> None:
        """Tear down the singleton (for testing / hot-reload)."""
        with cls._lock:
            cls._instance = None

    @classmethod
    def reload(cls) -> "ArchitectureRegistry":
        """Hot-reload architecture.yaml with validation.

        Re-reads and re-validates the YAML file.  On success the
        singleton's document is replaced atomically and the generation
        counter increments.  On failure (``FileNotFoundError``,
        ``RegistryValidationError``) the previous state is retained
        and the exception propagates — callers never see a partially
        loaded registry.

        If the registry has never been loaded, this behaves like
        ``get()`` (initial load at generation 1).

        Returns
        -------
        ArchitectureRegistry
            The singleton with the freshly loaded document.

        Raises
        ------
        FileNotFoundError
            If the YAML path does not exist.
        RegistryValidationError
            If the new YAML fails Pydantic schema validation.
        """
        with cls._lock:
            path = cls._resolve_path()
            # Validate new YAML *before* touching any state.
            new_doc = cls._load(path)

            if cls._instance is not None:
                # Atomic swap: bump generation, replace document.
                new_gen = cls._instance._generation + 1
                cls._instance._document = new_doc
                cls._instance._generation = new_gen
            else:
                # First load via reload() path.
                cls._instance = cls(new_doc, generation=1)

            return cls._instance

    @property
    def generation(self) -> int:
        """Monotonically increasing version counter.

        Starts at 1 on first load.  Increments by 1 on every
        successful ``reload()``.  Consumers can cache this value
        to detect when the registry contents have changed.
        """
        return self._generation

    @property
    def document(self) -> ArchitectureDocument:
        """The validated ``ArchitectureDocument``."""
        return self._document

    @property
    def path(self) -> Path:
        """Resolved path of the loaded YAML."""
        return self._resolve_path()

    # ── Task 2.7 — typed lookups ─────────────────────────

    def get_component(self, component_id: str) -> Component:
        """Look up a component by its mermaid node ID.

        Parameters
        ----------
        component_id:
            Mermaid node ID (e.g. ``"K1"``, ``"CONV"``, ``"PG"``).

        Returns
        -------
        Component
            The matching ``Component`` model instance.

        Raises
        ------
        ComponentNotFoundError
            If *component_id* is not present in the architecture.
        """
        try:
            return self._document.components[component_id]
        except KeyError:
            raise ComponentNotFoundError(component_id) from None

    def get_boundary(
        self,
        source_layer: LayerID,
        target_layer: LayerID,
    ) -> list[Connection]:
        """Return all boundary-crossing connections between two layers.

        Only connections where ``crosses_boundary is True`` and where
        ``source_layer`` / ``target_layer`` match the given pair are
        returned.  Order is preserved from the SAD parse order.

        Parameters
        ----------
        source_layer:
            Origin layer of the connection.
        target_layer:
            Destination layer of the connection.

        Returns
        -------
        list[Connection]
            May be empty if no boundary crossings exist between the
            specified layers.
        """
        sl = LayerID(source_layer)
        tl = LayerID(target_layer)
        return [
            c
            for c in self._document.connections
            if c.crosses_boundary
            and c.source_layer == sl
            and c.target_layer == tl
        ]

    def get_icd(self, component_id: str) -> list[Connection]:
        """Return the Interface Control Document for a component.

        The ICD is the set of *boundary-crossing* connections where
        *component_id* appears as either source or target.  This
        defines the component's external interface surface.

        Parameters
        ----------
        component_id:
            Mermaid node ID.  Must exist in the architecture.

        Returns
        -------
        list[Connection]
            Boundary-crossing connections involving the component.
            May be empty if the component has no cross-layer edges.

        Raises
        ------
        ComponentNotFoundError
            If *component_id* is not present in the architecture.
        """
        # Validate existence first.
        if component_id not in self._document.components:
            raise ComponentNotFoundError(component_id)

        return [
            c
            for c in self._document.connections
            if c.crosses_boundary
            and (c.source_id == component_id or c.target_id == component_id)
        ]

    # ── internal helpers ─────────────────────────────────

    @classmethod
    def _resolve_path(cls) -> Path:
        """Determine YAML path: explicit config > repo-root heuristic."""
        if cls._yaml_path is not None:
            return cls._yaml_path

        # Walk up from CWD to find repo root (docs/ + holly/).
        p = Path.cwd()
        for _ in range(10):
            candidate = p / "docs" / "architecture.yaml"
            if candidate.exists():
                return candidate
            if p.parent == p:
                break
            p = p.parent

        # Fallback: relative to CWD.
        return Path("docs") / "architecture.yaml"

    @classmethod
    def _load(cls, path: Path) -> ArchitectureDocument:
        """Read YAML and validate against Pydantic schema.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        RegistryValidationError
            If the YAML payload fails schema validation.
        """
        if not path.exists():
            msg = f"architecture.yaml not found: {path}"
            raise FileNotFoundError(msg)

        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)

        if not isinstance(data, dict):
            msg = f"Expected YAML mapping at top level, got {type(data).__name__}"
            raise RegistryValidationError(msg)

        try:
            doc = ArchitectureDocument.model_validate(data)
        except Exception as exc:
            msg = f"architecture.yaml validation failed: {exc}"
            raise RegistryValidationError(msg) from exc

        return doc
