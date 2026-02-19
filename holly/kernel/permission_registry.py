"""K2 Permission Registry — role-to-permission mapping store.

Task 16.4 — K2 permission gating per TLA+.

Thread-safe class-level singleton following the same pattern as
``SchemaRegistry``.  Roles map to frozen sets of permission strings.

Traces to: Behavior Spec §1.3 K2, TLA+ spec §14.1.
"""

from __future__ import annotations

import threading
from typing import ClassVar


class PermissionRegistry:
    """Class-level registry mapping role names to permission sets.

    All methods are class methods; no instantiation is required.  A
    ``threading.Lock`` guards all mutation operations.

    Examples
    --------
    >>> PermissionRegistry.register_role("admin", {"read", "write", "delete"})
    >>> PermissionRegistry.get_permissions("admin")
    frozenset({'delete', 'read', 'write'})
    """

    _registry: ClassVar[dict[str, frozenset[str]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    @classmethod
    def register_role(cls, role: str, permissions: set[str] | frozenset[str]) -> None:
        """Register *role* with *permissions*.

        Parameters
        ----------
        role:
            Role identifier string (e.g. ``"admin"``).
        permissions:
            Set of permission strings granted to this role.

        Raises
        ------
        ValueError
            If *role* is already registered (idempotent registration is not
            permitted — use ``clear()`` and re-register if you need to update).
        """
        from holly.kernel.exceptions import RoleNotFoundError as _  # noqa: F401

        with cls._lock:
            if role in cls._registry:
                raise ValueError(
                    f"Role {role!r} is already registered in PermissionRegistry"
                )
            cls._registry[role] = frozenset(permissions)

    @classmethod
    def clear(cls) -> None:
        """Remove all registered roles (primarily for test isolation)."""
        with cls._lock:
            cls._registry.clear()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @classmethod
    def get_permissions(cls, role: str) -> frozenset[str]:
        """Return the permission set for *role*.

        Parameters
        ----------
        role:
            Role identifier to look up.

        Returns
        -------
        frozenset[str]
            Immutable set of permission strings.

        Raises
        ------
        holly.kernel.exceptions.RoleNotFoundError
            If *role* is not registered.
        """
        from holly.kernel.exceptions import RoleNotFoundError

        with cls._lock:
            try:
                return cls._registry[role]
            except KeyError:
                raise RoleNotFoundError(role) from None

    @classmethod
    def has_role(cls, role: str) -> bool:
        """Return ``True`` if *role* is registered."""
        with cls._lock:
            return role in cls._registry

    @classmethod
    def registered_roles(cls) -> frozenset[str]:
        """Return a snapshot of all currently registered role names."""
        with cls._lock:
            return frozenset(cls._registry)
