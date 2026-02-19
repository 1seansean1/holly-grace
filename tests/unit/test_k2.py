"""Tests for k2 — K2 RBAC permission gate.

Task 16.4 — K2 permission gating per TLA+.

Traces to: Behavior Spec §1.3 K2, TLA+ spec (14.1), KernelContext (15.4).
SIL: 3

Acceptance criteria verified (per Task_Manifest.md §16.4):
  AC1  Authorized caller passes (required ⊆ granted)
  AC2  Unauthorized caller raises PermissionDeniedError; state -> IDLE
  AC3  Missing JWT (None claims) raises JWTError; state -> IDLE
  AC4  Expired JWT raises ExpiredTokenError; state -> IDLE
  AC5  Revoked JWT raises RevokedTokenError; state -> IDLE
  AC6  Revocation cache failure raises RevocationCacheError (fail-safe deny)
  AC7  Unknown role raises RoleNotFoundError
  AC8  k2_gate integrates with KernelContext; Gate protocol satisfied

Test taxonomy
-------------
Structure         k2 importable; gate factory returns coroutine; RevocationCache protocol
HappyPath         authorized claims pass; multiple roles union; empty required; IDLE after
PermissionDenied  missing permission -> PermissionDeniedError + IDLE; partial miss
MissingJWT        None claims -> JWTError + IDLE
MalformedClaims   missing sub/roles; roles not a list; exp non-numeric
Expiry            exp in past -> ExpiredTokenError + IDLE; future exp ok; check_expiry=False skips
Revocation        jti revoked -> RevokedTokenError + IDLE; cache fail -> RevocationCacheError
RoleNotFound      unknown role -> RoleNotFoundError
Ordering          k2_gate composes with k1_gate; fail stops subsequent gates
Property          Hypothesis: authorized always IDLE; unauthorized always IDLE
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.kernel.context import KernelContext
from holly.kernel.exceptions import (
    ExpiredTokenError,
    JWTError,
    PermissionDeniedError,
    RevocationCacheError,
    RevokedTokenError,
    RoleNotFoundError,
)
from holly.kernel.k2 import (
    FailRevocationCache,
    NullRevocationCache,
    RevocationCache,
    k2_check_permissions,
    k2_gate,
)
from holly.kernel.permission_registry import PermissionRegistry
from holly.kernel.state_machine import KernelState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROLE_READER = "reader"
ROLE_WRITER = "writer"
ROLE_ADMIN = "admin"

PERM_READ = "read:orders"
PERM_WRITE = "write:orders"
PERM_DELETE = "delete:orders"


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    PermissionRegistry.clear()
    yield
    PermissionRegistry.clear()


@pytest.fixture()
def populated_registry() -> None:
    PermissionRegistry.register_role(ROLE_READER, {PERM_READ})
    PermissionRegistry.register_role(ROLE_WRITER, {PERM_READ, PERM_WRITE})
    PermissionRegistry.register_role(ROLE_ADMIN, {PERM_READ, PERM_WRITE, PERM_DELETE})


def _claims(
    roles: list[str] | None = None,
    sub: str = "user-123",
    exp: int | None = None,
    jti: str | None = None,
) -> dict[str, Any]:
    c: dict[str, Any] = {"sub": sub, "roles": roles if roles is not None else [ROLE_READER]}
    if exp is not None:
        c["exp"] = exp
    if jti is not None:
        c["jti"] = jti
    return c


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestStructure:
    def test_k2_gate_importable(self) -> None:
        from holly.kernel.k2 import k2_gate as _g

        assert _g is not None

    def test_k2_gate_importable_from_kernel_init(self) -> None:
        from holly.kernel import k2_gate as _g

        assert _g is not None

    def test_k2_check_permissions_importable(self) -> None:
        from holly.kernel.k2 import k2_check_permissions as _f

        assert _f is not None

    def test_null_revocation_cache_is_revocation_cache(self) -> None:
        assert isinstance(NullRevocationCache(), RevocationCache)

    def test_fail_revocation_cache_is_revocation_cache(self) -> None:
        assert isinstance(FailRevocationCache(), RevocationCache)

    def test_k2_gate_returns_callable(self, populated_registry: None) -> None:
        gate = k2_gate(_claims(), required={PERM_READ})
        assert callable(gate)

    def test_returned_gate_is_coroutine_function(self, populated_registry: None) -> None:
        import inspect

        gate = k2_gate(_claims(), required={PERM_READ})
        assert inspect.iscoroutinefunction(gate)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_authorized_single_role_passes(self, populated_registry: None) -> None:
        """AC1: caller with required permission passes gate."""
        ctx = KernelContext(gates=[k2_gate(_claims([ROLE_READER]), required={PERM_READ})])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_authorized_multi_role_union(self, populated_registry: None) -> None:
        """Roles union: reader+writer grants read+write."""
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_READER, ROLE_WRITER]), required={PERM_READ, PERM_WRITE})]
        )
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_empty_required_always_passes(self, populated_registry: None) -> None:
        """Empty required set: gate is a no-op permission check."""
        ctx = KernelContext(gates=[k2_gate(_claims([ROLE_READER]), required=set())])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_admin_role_satisfies_all_permissions(self, populated_registry: None) -> None:
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_ADMIN]), required={PERM_READ, PERM_WRITE, PERM_DELETE})]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_future_exp_does_not_raise(self, populated_registry: None) -> None:
        """Valid future expiry: gate passes."""
        future_exp = int(time.time()) + 3600
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_READER], exp=future_exp), required={PERM_READ})]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_non_revoked_jti_passes(self, populated_registry: None) -> None:
        """jti not in null cache: gate passes."""
        ctx = KernelContext(
            gates=[
                k2_gate(
                    _claims([ROLE_READER], jti="tok-abc"),
                    required={PERM_READ},
                    revocation_cache=NullRevocationCache(),
                )
            ]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_multiple_valid_crossings_end_idle(self, populated_registry: None) -> None:
        ctx = KernelContext(gates=[k2_gate(_claims([ROLE_READER]), required={PERM_READ})])
        for _ in range(3):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Permission denied
# ---------------------------------------------------------------------------


class TestPermissionDenied:
    @pytest.mark.asyncio
    async def test_missing_permission_raises(self, populated_registry: None) -> None:
        """AC2: reader lacks write:orders -> PermissionDeniedError."""
        ctx = KernelContext(gates=[k2_gate(_claims([ROLE_READER]), required={PERM_WRITE})])
        with pytest.raises(PermissionDeniedError) as exc_info:
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE
        exc = exc_info.value
        assert PERM_WRITE in exc.missing
        assert exc.user_id == "user-123"

    @pytest.mark.asyncio
    async def test_permission_denied_required_and_granted_populated(
        self, populated_registry: None
    ) -> None:
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_READER]), required={PERM_READ, PERM_DELETE})]
        )
        with pytest.raises(PermissionDeniedError) as exc_info:
            async with ctx:
                pass
        exc = exc_info.value
        assert exc.required == frozenset({PERM_READ, PERM_DELETE})
        assert exc.granted == frozenset({PERM_READ})
        assert exc.missing == frozenset({PERM_DELETE})

    @pytest.mark.asyncio
    async def test_no_roles_raises_permission_denied(self, populated_registry: None) -> None:
        """Empty roles list -> granted is empty -> any required perm denied."""
        ctx = KernelContext(gates=[k2_gate(_claims([]), required={PERM_READ})])
        with pytest.raises(PermissionDeniedError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    def test_check_permissions_direct_raises(self, populated_registry: None) -> None:
        """k2_check_permissions raises directly (non-gate path)."""
        with pytest.raises(PermissionDeniedError):
            k2_check_permissions(
                _claims([ROLE_READER]),
                frozenset({PERM_WRITE}),
            )


# ---------------------------------------------------------------------------
# Missing JWT
# ---------------------------------------------------------------------------


class TestMissingJWT:
    @pytest.mark.asyncio
    async def test_none_claims_raises_jwt_error(self, populated_registry: None) -> None:
        """AC3: None claims -> JWTError + IDLE."""
        ctx = KernelContext(gates=[k2_gate(None, required={PERM_READ})])
        with pytest.raises(JWTError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_missing_sub_raises_jwt_error(self, populated_registry: None) -> None:
        bad_claims: dict[str, Any] = {"roles": [ROLE_READER]}
        ctx = KernelContext(gates=[k2_gate(bad_claims, required={PERM_READ})])
        with pytest.raises(JWTError) as exc_info:
            async with ctx:
                pass
        assert "sub" in str(exc_info.value)
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_missing_roles_raises_jwt_error(self, populated_registry: None) -> None:
        bad_claims: dict[str, Any] = {"sub": "u1"}
        ctx = KernelContext(gates=[k2_gate(bad_claims, required={PERM_READ})])
        with pytest.raises(JWTError) as exc_info:
            async with ctx:
                pass
        assert "roles" in str(exc_info.value)
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_roles_not_list_raises_jwt_error(self, populated_registry: None) -> None:
        bad_claims: dict[str, Any] = {"sub": "u1", "roles": "admin"}
        ctx = KernelContext(gates=[k2_gate(bad_claims, required={PERM_READ})])
        with pytest.raises(JWTError) as exc_info:
            async with ctx:
                pass
        assert "list" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exp_non_numeric_raises_jwt_error(self, populated_registry: None) -> None:
        bad_claims: dict[str, Any] = {"sub": "u1", "roles": [ROLE_READER], "exp": "tomorrow"}
        ctx = KernelContext(gates=[k2_gate(bad_claims, required={PERM_READ})])
        with pytest.raises(JWTError):
            async with ctx:
                pass


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------


class TestExpiry:
    @pytest.mark.asyncio
    async def test_expired_token_raises(self, populated_registry: None) -> None:
        """AC4: exp in past -> ExpiredTokenError + IDLE."""
        past_exp = int(time.time()) - 1
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_READER], exp=past_exp), required={PERM_READ})]
        )
        with pytest.raises(ExpiredTokenError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.exp == past_exp
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_check_expiry_false_skips_expiry(self, populated_registry: None) -> None:
        """check_expiry=False: expired token still passes the expiry check."""
        past_exp = int(time.time()) - 3600
        ctx = KernelContext(
            gates=[
                k2_gate(
                    _claims([ROLE_READER], exp=past_exp),
                    required={PERM_READ},
                    check_expiry=False,
                )
            ]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_no_exp_claim_skips_expiry_check(self, populated_registry: None) -> None:
        """Claims without exp: no ExpiredTokenError even with check_expiry=True."""
        ctx = KernelContext(
            gates=[k2_gate(_claims([ROLE_READER]), required={PERM_READ}, check_expiry=True)]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------


class TestRevocation:
    @pytest.mark.asyncio
    async def test_revoked_jti_raises(self, populated_registry: None) -> None:
        """AC5: jti in revocation cache -> RevokedTokenError + IDLE."""

        class _Cache:
            def is_revoked(self, jti: str) -> bool:
                return jti == "bad-token"

        ctx = KernelContext(
            gates=[
                k2_gate(
                    _claims([ROLE_READER], jti="bad-token"),
                    required={PERM_READ},
                    revocation_cache=_Cache(),
                )
            ]
        )
        with pytest.raises(RevokedTokenError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.jti == "bad-token"
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_cache_failure_raises_revocation_cache_error(
        self, populated_registry: None
    ) -> None:
        """AC6: cache unavailable -> RevocationCacheError (fail-safe deny) + IDLE."""
        ctx = KernelContext(
            gates=[
                k2_gate(
                    _claims([ROLE_READER], jti="tok-xyz"),
                    required={PERM_READ},
                    revocation_cache=FailRevocationCache(),
                )
            ]
        )
        with pytest.raises(RevocationCacheError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_no_jti_skips_revocation_check(self, populated_registry: None) -> None:
        """No jti in claims: revocation cache not consulted."""
        ctx = KernelContext(
            gates=[
                k2_gate(
                    _claims([ROLE_READER]),  # no jti
                    required={PERM_READ},
                    revocation_cache=FailRevocationCache(),  # would raise if called
                )
            ]
        )
        async with ctx:
            pass
        assert ctx.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Role not found
# ---------------------------------------------------------------------------


class TestRoleNotFound:
    @pytest.mark.asyncio
    async def test_unknown_role_raises(self) -> None:
        """AC7: role not in PermissionRegistry -> RoleNotFoundError + IDLE."""
        # registry is empty (autouse fixture cleared it)
        ctx = KernelContext(
            gates=[k2_gate(_claims(["nonexistent-role"]), required={PERM_READ})]
        )
        with pytest.raises(RoleNotFoundError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.role == "nonexistent-role"
        assert ctx.state == KernelState.IDLE

    def test_role_not_found_direct(self) -> None:
        with pytest.raises(RoleNotFoundError):
            PermissionRegistry.get_permissions("ghost-role")


# ---------------------------------------------------------------------------
# Ordering / composition
# ---------------------------------------------------------------------------


class TestOrdering:
    @pytest.mark.asyncio
    async def test_k2_gate_composes_with_k1_gate(self, populated_registry: None) -> None:
        """AC8: k2_gate + k1_gate both in KernelContext.gates list."""
        from holly.kernel.k1 import k1_gate
        from holly.kernel.schema_registry import SchemaRegistry

        SchemaRegistry.clear()
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
        SchemaRegistry.register("ICD-K2-COMPOSE", schema)

        ctx = KernelContext(
            gates=[
                k1_gate({"name": "Alice"}, "ICD-K2-COMPOSE"),
                k2_gate(_claims([ROLE_READER]), required={PERM_READ}),
            ]
        )
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE

        SchemaRegistry.clear()

    @pytest.mark.asyncio
    async def test_k2_fail_stops_subsequent_gates(self, populated_registry: None) -> None:
        """First-fail-abort: k2 failure prevents subsequent gate execution."""
        ran: list[bool] = []

        async def _should_not_run(ctx: KernelContext) -> None:
            ran.append(True)

        ctx = KernelContext(
            gates=[
                k2_gate(_claims([ROLE_READER]), required={PERM_DELETE}),
                _should_not_run,
            ]
        )
        with pytest.raises(PermissionDeniedError):
            async with ctx:
                pass
        assert not ran


# ---------------------------------------------------------------------------
# Permission registry unit tests
# ---------------------------------------------------------------------------


class TestPermissionRegistry:
    def test_register_and_get(self) -> None:
        PermissionRegistry.register_role("r1", {"perm:a", "perm:b"})
        assert PermissionRegistry.get_permissions("r1") == frozenset({"perm:a", "perm:b"})

    def test_has_role(self) -> None:
        PermissionRegistry.register_role("r2", {"perm:c"})
        assert PermissionRegistry.has_role("r2")
        assert not PermissionRegistry.has_role("r99")

    def test_registered_roles_snapshot(self) -> None:
        PermissionRegistry.register_role("r3", {"perm:d"})
        PermissionRegistry.register_role("r4", {"perm:e"})
        assert {"r3", "r4"} <= PermissionRegistry.registered_roles()

    def test_duplicate_register_raises(self) -> None:
        PermissionRegistry.register_role("dup", {"perm:f"})
        with pytest.raises(ValueError, match="already registered"):
            PermissionRegistry.register_role("dup", {"perm:g"})

    def test_get_unknown_role_raises(self) -> None:
        with pytest.raises(RoleNotFoundError):
            PermissionRegistry.get_permissions("unknown")

    def test_clear_removes_all(self) -> None:
        PermissionRegistry.register_role("tmp", {"perm:h"})
        PermissionRegistry.clear()
        assert not PermissionRegistry.has_role("tmp")


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis)
# ---------------------------------------------------------------------------


class TestPropertyBased:
    @given(
        name=st.text(min_size=1, max_size=64),
        sub=st.text(min_size=1, max_size=32),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_authorized_caller_always_idles(self, name: str, sub: str) -> None:
        """Property: any caller with the required role → IDLE after gate."""
        PermissionRegistry.clear()
        PermissionRegistry.register_role("prop-role", {PERM_READ})
        c = {"sub": sub, "roles": ["prop-role"]}
        ctx = KernelContext(gates=[k2_gate(c, required={PERM_READ})])
        async with ctx:
            assert ctx.state == KernelState.ACTIVE
        assert ctx.state == KernelState.IDLE
        PermissionRegistry.clear()

    @given(sub=st.text(min_size=1, max_size=32))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_unauthorized_caller_always_raises_and_idles(self, sub: str) -> None:
        """Property: caller without required permission → PermissionDeniedError + IDLE."""
        PermissionRegistry.clear()
        PermissionRegistry.register_role("ro-role", {PERM_READ})
        c = {"sub": sub, "roles": ["ro-role"]}
        ctx = KernelContext(gates=[k2_gate(c, required={PERM_DELETE})])
        with pytest.raises(PermissionDeniedError) as exc_info:
            async with ctx:
                pass
        assert exc_info.value.user_id == sub
        assert ctx.state == KernelState.IDLE
        PermissionRegistry.clear()

    @given(exp_offset=st.integers(min_value=1, max_value=86400))
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_expired_token_always_raises_and_idles(self, exp_offset: int) -> None:
        """Property: exp in past by any amount → ExpiredTokenError + IDLE."""
        PermissionRegistry.clear()
        PermissionRegistry.register_role("exp-role", {PERM_READ})
        past_exp = int(time.time()) - exp_offset
        c = _claims(["exp-role"], exp=past_exp)
        ctx = KernelContext(gates=[k2_gate(c, required={PERM_READ})])
        with pytest.raises(ExpiredTokenError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE
        PermissionRegistry.clear()
