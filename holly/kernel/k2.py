"""K2 Permission Gate — RBAC enforcement for KernelContext.

Task 16.4 — K2 permission gating per TLA+.

K2 operates on pre-decoded JWT claims (``dict[str, Any]``) rather than
raw JWT strings.  JWT decode/signature verification is middleware's
responsibility; the kernel gate enforces RBAC logic from extracted claims.

Claims dict contract
--------------------
``sub``   (str, required)   Subject identifier (user/service ID).
``roles`` (list[str], required)  Roles assigned to the subject.
``exp``   (int, optional)   Expiry Unix timestamp.  Checked against
                            ``time.time()`` when ``check_expiry=True`` (default).
``jti``   (str, optional)   JWT ID.  Checked against *revocation_cache*
                            when provided.

Usage
-----
>>> gate = k2_gate(claims, required={"read:orders"})
>>> ctx = KernelContext(gates=[k2_gate(claims, required={"read:orders"})])
>>> async with ctx:
...     pass  # only reaches here if claims satisfy required permissions

Traces to: Behavior Spec §1.3 K2, TLA+ spec §14.1, KernelContext §15.4.
SIL: 3
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from holly.kernel.exceptions import (
    ExpiredTokenError,
    JWTError,
    PermissionDeniedError,
    RevocationCacheError,
    RevokedTokenError,
)
from holly.kernel.permission_registry import PermissionRegistry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from holly.kernel.context import KernelContext


# ---------------------------------------------------------------------------
# RevocationCache protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RevocationCache(Protocol):
    """Protocol for token revocation stores.

    Implementors check whether a JWT ID (``jti``) has been revoked.
    The method MUST NOT swallow errors silently — if the cache is
    unavailable, raise ``RevocationCacheError`` so K2 can apply
    fail-safe deny semantics.
    """

    def is_revoked(self, jti: str) -> bool:
        """Return ``True`` if *jti* has been revoked.

        Raises
        ------
        holly.kernel.exceptions.RevocationCacheError
            If the cache is unavailable and revocation status cannot be
            determined.
        """
        ...


class NullRevocationCache:
    """Revocation cache that never revokes any token.

    Suitable for development/test environments where revocation is not
    required.  In production, replace with a Redis- or DB-backed
    implementation.
    """

    def is_revoked(self, jti: str) -> bool:
        return False


class FailRevocationCache:
    """Revocation cache that always raises ``RevocationCacheError``.

    Used in tests to verify K2 fail-safe deny semantics when the cache
    is unavailable.
    """

    def is_revoked(self, jti: str) -> bool:
        raise RevocationCacheError("cache unavailable (FailRevocationCache)")


# Default singleton — override per-deployment
_DEFAULT_REVOCATION_CACHE: RevocationCache = NullRevocationCache()


# ---------------------------------------------------------------------------
# Core validation function
# ---------------------------------------------------------------------------


def k2_check_permissions(
    claims: dict[str, Any] | None,
    required: frozenset[str],
    *,
    revocation_cache: RevocationCache | None = None,
    check_expiry: bool = True,
) -> None:
    """Validate *claims* against *required* permissions.

    Steps (in order):
    1. Reject ``None`` claims (missing/malformed JWT).
    2. Validate required fields (``sub``, ``roles``).
    3. Check ``exp`` if present and ``check_expiry`` is ``True``.
    4. Check revocation via *revocation_cache* if ``jti`` is in claims.
    5. Resolve roles → permission union via ``PermissionRegistry``.
    6. Assert ``required ⊆ granted``; raise ``PermissionDeniedError`` if not.

    Parameters
    ----------
    claims:
        Pre-decoded JWT claims dict.  ``None`` is treated as missing JWT.
    required:
        Frozenset of permission strings that must be satisfied.
    revocation_cache:
        Optional revocation store.  Defaults to ``NullRevocationCache``.
    check_expiry:
        When ``True`` (default), enforce ``exp`` claim if present.

    Raises
    ------
    JWTError
        Claims dict is ``None``, missing ``sub``, or ``roles`` is not a list.
    ExpiredTokenError
        ``exp`` claim is in the past.
    RevokedTokenError
        ``jti`` is found in the revocation cache.
    RevocationCacheError
        Revocation cache unavailable (fail-safe deny).
    PermissionDeniedError
        Granted permissions do not satisfy required set.
    holly.kernel.exceptions.RoleNotFoundError
        A role in ``claims["roles"]`` is not in ``PermissionRegistry``.
    """
    cache = revocation_cache if revocation_cache is not None else _DEFAULT_REVOCATION_CACHE

    # 1. Reject None
    if claims is None:
        raise JWTError("claims dict is None (missing JWT)")

    # 2. Required fields
    if "sub" not in claims:
        raise JWTError("claims missing required field 'sub'")
    sub: str = str(claims["sub"])

    if "roles" not in claims:
        raise JWTError("claims missing required field 'roles'")
    roles = claims["roles"]
    if not isinstance(roles, list):
        raise JWTError(f"'roles' must be a list, got {type(roles).__name__!r}")

    # 3. Expiry
    if check_expiry and "exp" in claims:
        exp = claims["exp"]
        if not isinstance(exp, (int, float)):
            raise JWTError(f"'exp' must be numeric, got {type(exp).__name__!r}")
        if time.time() > exp:
            raise ExpiredTokenError(int(exp))

    # 4. Revocation
    if "jti" in claims:
        jti = str(claims["jti"])
        if cache.is_revoked(jti):
            raise RevokedTokenError(jti)

    # 5. Resolve permissions
    granted: frozenset[str] = frozenset()
    for role in roles:
        granted = granted | PermissionRegistry.get_permissions(str(role))

    # 6. Permission check
    missing = required - granted
    if missing:
        raise PermissionDeniedError(
            user_id=sub,
            required=required,
            granted=granted,
            missing=missing,
        )


# ---------------------------------------------------------------------------
# Gate factory
# ---------------------------------------------------------------------------


def k2_gate(
    claims: dict[str, Any] | None,
    *,
    required: set[str] | frozenset[str],
    revocation_cache: RevocationCache | None = None,
    check_expiry: bool = True,
) -> Callable[[KernelContext], Awaitable[None]]:
    """Return a Gate that enforces RBAC on *claims*.

    The returned gate is an async callable conforming to the
    ``Gate = Callable[[KernelContext], Awaitable[None]]`` protocol.

    Parameters
    ----------
    claims:
        Pre-decoded JWT claims dict (or ``None`` for missing JWT).
    required:
        Permission strings that the caller must hold.
    revocation_cache:
        Optional revocation store.  Defaults to ``NullRevocationCache``.
    check_expiry:
        Enforce ``exp`` claim when ``True`` (default).

    Returns
    -------
    Gate
        Async callable ``async def gate(ctx: KernelContext) -> None``.

    Examples
    --------
    >>> gate = k2_gate(claims, required={"read:orders"})
    >>> ctx = KernelContext(gates=[gate])
    >>> async with ctx:
    ...     pass
    """
    _required: frozenset[str] = frozenset(required)

    async def _k2_gate(ctx: KernelContext) -> None:
        k2_check_permissions(
            claims,
            _required,
            revocation_cache=revocation_cache,
            check_expiry=check_expiry,
        )

    return _k2_gate
