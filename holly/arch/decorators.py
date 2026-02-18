# ruff: noqa: UP047
"""Core architectural decorators for Holly boundary enforcement.

Task 3.6 - Implement core decorators.

Five decorators stamp architectural metadata onto functions and classes
that participate in boundary crossings.  Each decorator:

1. Attaches a ``_holly_meta`` dict to the decorated callable with
   structured metadata (decorator kind, component ID, layer, options).
2. Preserves the original callable's signature and behaviour — decorators
   are *metadata-only* at this stage.  Runtime enforcement (K1 schema
   validation, permission gating, etc.) is added by Task 3.7 and later.
3. Integrates with the ``ArchitectureRegistry``: if a ``component_id``
   is supplied, it is validated against the registry at decoration time
   (when ``validate=True``, the default).  Stale or unknown IDs raise
   ``DecoratorRegistryError`` immediately rather than failing at runtime.

Design per ADR in Dev_Environment_Spec §Option B: custom decorator
registry with full control and architecture.yaml integration.

Decorators
----------
- ``@kernel_boundary`` -- marks a function/class as a kernel invariant
  gate (K1-K8).  Metadata includes gate ID and invariant name.
- ``@tenant_scoped`` -- marks a function/class as requiring tenant
  isolation.  Metadata includes isolation strategy.
- ``@lane_dispatch`` -- marks a function/class as a workflow lane
  dispatcher.  Metadata includes lane semantics.
- ``@mcp_tool`` -- marks a function as an MCP tool endpoint.  Metadata
  includes tool name and permission mask.
- ``@eval_gated`` -- marks a function as guarded by a K8 eval gate.
  Metadata includes eval predicate reference.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, Literal, TypeVar, overload

from holly.arch.registry import ArchitectureRegistry, ComponentNotFoundError

# ── Types ─────────────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Any])

DecoratorKind = Literal[
    "kernel_boundary",
    "tenant_scoped",
    "lane_dispatch",
    "mcp_tool",
    "eval_gated",
]

# ── Exceptions ────────────────────────────────────────


class DecoratorRegistryError(RuntimeError):
    """Raised when a decorator references an unknown architecture component."""

    def __init__(self, component_id: str, decorator_kind: DecoratorKind) -> None:
        super().__init__(
            f"@{decorator_kind}: component_id {component_id!r} "
            f"not found in architecture.yaml"
        )
        self.component_id = component_id
        self.decorator_kind = decorator_kind


# ── Metadata helpers ──────────────────────────────────


def get_holly_meta(obj: Any) -> dict[str, Any] | None:
    """Return the ``_holly_meta`` dict attached by a Holly decorator, or None."""
    return getattr(obj, "_holly_meta", None)


def has_holly_decorator(obj: Any, kind: DecoratorKind | None = None) -> bool:
    """Check whether *obj* has been decorated with a Holly decorator.

    If *kind* is given, also checks the specific decorator kind.
    """
    meta = get_holly_meta(obj)
    if meta is None:
        return False
    if kind is not None:
        return meta.get("kind") == kind
    return True


def _attach_meta(func: F, meta: dict[str, Any]) -> F:
    """Attach ``_holly_meta`` to *func* and return it.

    Works on both functions and classes.  For classes, metadata is
    attached directly without wrapping (preserving ``isinstance``,
    ``issubclass``, and class attribute access).
    """
    func._holly_meta = meta  # type: ignore[attr-defined]
    return func


def _decorate(fn: F, meta: dict[str, Any]) -> F:
    """Apply metadata to *fn*, wrapping only if it is a function (not a class).

    Classes receive metadata directly — no wrapper — to preserve
    ``isinstance``, ``issubclass``, and class attribute access.
    Functions get a thin ``functools.wraps`` wrapper for future
    runtime enforcement hooks (Task 3.7+).
    """
    if isinstance(fn, type):
        # Class: attach metadata directly, return unchanged class.
        return _attach_meta(fn, meta)  # type: ignore[return-value]
    # Function: wrap to enable future runtime enforcement.
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    return _attach_meta(wrapper, meta)  # type: ignore[return-value]


def _validate_component(
    component_id: str | None,
    decorator_kind: DecoratorKind,
    validate: bool,
) -> None:
    """Validate *component_id* against the registry if requested."""
    if component_id is None or not validate:
        return
    if not ArchitectureRegistry.is_loaded():
        # Registry not loaded yet — skip validation.
        # This allows decorators to be applied at import time before
        # the registry is initialized.  Validation will happen at
        # startup when the registry loads and the AST scanner runs.
        return
    try:
        ArchitectureRegistry.get().get_component(component_id)
    except ComponentNotFoundError:
        raise DecoratorRegistryError(component_id, decorator_kind) from None


# ── @kernel_boundary ──────────────────────────────────


@overload
def kernel_boundary(func: F) -> F: ...


@overload
def kernel_boundary(
    *,
    gate_id: str = "",
    invariant: str = "",
    component_id: str | None = None,
    validate: bool = True,
) -> Callable[[F], F]: ...


def kernel_boundary(
    func: F | None = None,
    *,
    gate_id: str = "",
    invariant: str = "",
    component_id: str | None = None,
    validate: bool = True,
) -> F | Callable[[F], F]:
    """Mark a function or class as a kernel boundary gate.

    Can be used bare (``@kernel_boundary``) or with arguments
    (``@kernel_boundary(gate_id="K1", invariant="schema_validation")``).

    Parameters
    ----------
    gate_id:
        Kernel gate identifier (e.g. ``"K1"`` through ``"K8"``).
    invariant:
        Human-readable invariant name (e.g. ``"schema_validation"``).
    component_id:
        Optional SAD component ID for registry validation.
    validate:
        If True and the registry is loaded, validate *component_id*.
    """

    def decorator(fn: F) -> F:
        _validate_component(component_id, "kernel_boundary", validate)
        return _decorate(fn, {
            "kind": "kernel_boundary",
            "gate_id": gate_id,
            "invariant": invariant,
            "component_id": component_id,
            "layer": "L1",
        })

    if func is not None:
        # Bare @kernel_boundary usage.
        return decorator(func)
    return decorator


# ── @tenant_scoped ────────────────────────────────────


@overload
def tenant_scoped(func: F) -> F: ...


@overload
def tenant_scoped(
    *,
    isolation: str = "row_level_security",
    component_id: str | None = None,
    validate: bool = True,
) -> Callable[[F], F]: ...


def tenant_scoped(
    func: F | None = None,
    *,
    isolation: str = "row_level_security",
    component_id: str | None = None,
    validate: bool = True,
) -> F | Callable[[F], F]:
    """Mark a function or class as requiring tenant isolation.

    Parameters
    ----------
    isolation:
        Isolation strategy: ``"row_level_security"``,
        ``"schema_per_tenant"``, ``"database_per_tenant"``.
    component_id:
        Optional SAD component ID for registry validation.
    validate:
        If True and the registry is loaded, validate *component_id*.
    """

    def decorator(fn: F) -> F:
        _validate_component(component_id, "tenant_scoped", validate)
        return _decorate(fn, {
            "kind": "tenant_scoped",
            "isolation": isolation,
            "component_id": component_id,
        })

    if func is not None:
        return decorator(func)
    return decorator


# ── @lane_dispatch ────────────────────────────────────


@overload
def lane_dispatch(func: F) -> F: ...


@overload
def lane_dispatch(
    *,
    semantics: str = "concurrent",
    component_id: str | None = None,
    validate: bool = True,
) -> Callable[[F], F]: ...


def lane_dispatch(
    func: F | None = None,
    *,
    semantics: str = "concurrent",
    component_id: str | None = None,
    validate: bool = True,
) -> F | Callable[[F], F]:
    """Mark a function or class as a workflow lane dispatcher.

    Parameters
    ----------
    semantics:
        Lane semantics: ``"concurrent"``, ``"sequential"``,
        ``"fan_out_fan_in"``.
    component_id:
        Optional SAD component ID for registry validation.
    validate:
        If True and the registry is loaded, validate *component_id*.
    """

    def decorator(fn: F) -> F:
        _validate_component(component_id, "lane_dispatch", validate)
        return _decorate(fn, {
            "kind": "lane_dispatch",
            "semantics": semantics,
            "component_id": component_id,
        })

    if func is not None:
        return decorator(func)
    return decorator


# ── @mcp_tool ─────────────────────────────────────────


@overload
def mcp_tool(func: F) -> F: ...


@overload
def mcp_tool(
    *,
    tool_name: str = "",
    permission_mask: str = "*",
    component_id: str | None = None,
    validate: bool = True,
) -> Callable[[F], F]: ...


def mcp_tool(
    func: F | None = None,
    *,
    tool_name: str = "",
    permission_mask: str = "*",
    component_id: str | None = None,
    validate: bool = True,
) -> F | Callable[[F], F]:
    """Mark a function as an MCP tool endpoint.

    Parameters
    ----------
    tool_name:
        MCP tool name.  If empty, derived from the function name.
    permission_mask:
        Per-agent permission mask (e.g. ``"read"``, ``"write"``,
        ``"*"``).
    component_id:
        Optional SAD component ID for registry validation.
    validate:
        If True and the registry is loaded, validate *component_id*.
    """

    def decorator(fn: F) -> F:
        _validate_component(component_id, "mcp_tool", validate)
        resolved_name = tool_name or fn.__name__
        return _decorate(fn, {
            "kind": "mcp_tool",
            "tool_name": resolved_name,
            "permission_mask": permission_mask,
            "component_id": component_id,
        })

    if func is not None:
        return decorator(func)
    return decorator


# ── @eval_gated ───────────────────────────────────────


@overload
def eval_gated(func: F) -> F: ...


@overload
def eval_gated(
    *,
    predicate: str = "",
    gate_id: str = "K8",
    component_id: str | None = None,
    validate: bool = True,
) -> Callable[[F], F]: ...


def eval_gated(
    func: F | None = None,
    *,
    predicate: str = "",
    gate_id: str = "K8",
    component_id: str | None = None,
    validate: bool = True,
) -> F | Callable[[F], F]:
    """Mark a function as guarded by a K8 eval gate.

    Parameters
    ----------
    predicate:
        Reference to the eval predicate (e.g. a goal hierarchy level
        or eval suite name).
    gate_id:
        Kernel gate that performs the eval check.  Default ``"K8"``.
    component_id:
        Optional SAD component ID for registry validation.
    validate:
        If True and the registry is loaded, validate *component_id*.
    """

    def decorator(fn: F) -> F:
        _validate_component(component_id, "eval_gated", validate)
        return _decorate(fn, {
            "kind": "eval_gated",
            "predicate": predicate,
            "gate_id": gate_id,
            "component_id": component_id,
        })

    if func is not None:
        return decorator(func)
    return decorator
