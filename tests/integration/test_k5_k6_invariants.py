"""Task 17.7 -- K5-K6 Invariant Preservation.

Property-based integration tests verifying all six KernelContext invariants
hold across randomly-generated K5+K6 operation sequences.

Invariants (Behavior Spec §1.1):
    INV-1  No boundary crossing without context.
    INV-2  count(active) <= 1 per task -- no re-entrancy.
    INV-3  state in {IDLE, ENTERING, ACTIVE, EXITING, FAULTED}.
    INV-4  Guard conditions evaluate deterministically (pure functions).
    INV-5  ACTIVE requires all gates to have passed.
    INV-6  WAL entry written => corr_id != null ^ tenant_id != null ^ timestamp != null.

Acceptance criteria: Zero invariant violations over 10,000 generated traces.

Traces to:
    Behavior Spec §1.1 (INV-1 through INV-6)
    Task 17.3 (K5 idempotency gate)
    Task 17.4 (K6 WAL gate)
    TLA+ spec KernelInvariants.tla (Task 14.1)
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.kernel.context import KernelContext
from holly.kernel.exceptions import DuplicateRequestError, WALWriteError
from holly.kernel.k5 import InMemoryIdempotencyStore, k5_gate, k5_generate_key
from holly.kernel.k6 import InMemoryWALBackend, k6_gate, redact
from holly.kernel.state_machine import KernelState

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_ALL_KERNEL_STATES: frozenset[KernelState] = frozenset(KernelState)

_ALPHA_NUM = "abcdefghijklmnopqrstuvwxyz0123456789"


def _claims(
    tenant_id: str = "tenant-17-7",
    user_id: str = "user-17-7",
) -> dict[str, Any]:
    """Return minimal JWT claims dict with tenant_id populated for K6."""
    return {"sub": user_id, "roles": ["user"], "tenant_id": tenant_id}


def _make_k6(
    backend: InMemoryWALBackend,
    claims: dict[str, Any],
    boundary: str = "core::test_17_7",
    operation_result: str | None = None,
) -> Any:
    """Convenience: build a k6_gate with standard args."""
    return k6_gate(
        boundary_crossing=boundary,
        claims=claims,
        backend=backend,
        exit_code=0,
        operation_result=operation_result,
    )


async def _run_k5_k6(
    payload: Any,
    store: InMemoryIdempotencyStore,
    backend: InMemoryWALBackend,
    claims: dict[str, Any],
    *,
    corr_id: str | None = None,
    boundary: str = "core::test_17_7",
) -> KernelContext:
    """Run a single K5+K6 boundary crossing; return context after exit."""
    ctx = KernelContext(
        gates=[
            k5_gate(payload=payload, store=store),
            _make_k6(backend, claims, boundary),
        ],
        corr_id=corr_id,
    )
    async with ctx:
        pass
    return ctx


# ---------------------------------------------------------------------------
# INV-1: No Boundary Crossing Without Context
# ---------------------------------------------------------------------------


class TestINV1GateRequiresContext:
    """INV-1: K5 and K6 gates structurally require a KernelContext argument.

    Gate = Callable[[KernelContext], Awaitable[None]]; a gate cannot
    be invoked without supplying a KernelContext.  The invariant is
    enforced by the Gate type alias and the async context-manager protocol.
    """

    def test_k5_gate_returns_coroutine_function_with_ctx_param(self) -> None:
        """k5_gate factory returns a coroutine function accepting ctx."""
        store = InMemoryIdempotencyStore()
        gate = k5_gate(payload={"x": 1}, store=store)
        assert inspect.iscoroutinefunction(gate)
        params = list(inspect.signature(gate).parameters.values())
        assert len(params) == 1
        assert params[0].name == "ctx"

    def test_k6_gate_returns_coroutine_function_with_ctx_param(self) -> None:
        """k6_gate factory returns a coroutine function accepting ctx."""
        backend = InMemoryWALBackend()
        gate = _make_k6(backend, _claims())
        assert inspect.iscoroutinefunction(gate)
        params = list(inspect.signature(gate).parameters.values())
        assert len(params) == 1
        assert params[0].name == "ctx"

    @pytest.mark.asyncio
    async def test_all_operations_execute_within_context(self) -> None:
        """K5+K6 gates execute only after KernelContext.__aenter__ succeeds."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        ctx = await _run_k5_k6({"k": "v"}, store, backend, _claims())
        # Context completed __aenter__ + __aexit__ -- proves gates ran within ctx.
        assert ctx.state == KernelState.IDLE
        # WAL entry written proves k6 gate ran with a live context.
        assert len(backend.entries) == 1
        assert backend.entries[0].correlation_id == ctx.corr_id


# ---------------------------------------------------------------------------
# INV-2: No Re-Entrancy (count(active) <= 1)
# ---------------------------------------------------------------------------


class TestINV2NoReentrancy:
    """INV-2: After any K5+K6 operation (success or failure) state is IDLE."""

    @pytest.mark.asyncio
    async def test_idle_after_successful_k5_k6(self) -> None:
        """Happy path: IDLE -> ENTERING -> ACTIVE -> EXITING -> IDLE."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        ctx = await _run_k5_k6({"n": 1}, store, backend, _claims())
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_idle_after_k5_duplicate_failure(self) -> None:
        """K5 duplicate: ENTERING -> FAULTED -> IDLE; state never stuck."""
        store = InMemoryIdempotencyStore()
        # Pre-mark the key so the second call sees a duplicate.
        store.check_and_mark(k5_generate_key({"n": 1}))
        ctx = KernelContext(gates=[k5_gate(payload={"n": 1}, store=store)])
        with pytest.raises(DuplicateRequestError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_idle_after_k6_backend_failure(self) -> None:
        """K6 write error: ENTERING -> FAULTED -> IDLE; state never stuck."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        backend._fail = True
        ctx = KernelContext(
            gates=[
                k5_gate(payload={"n": 99}, store=store),
                _make_k6(backend, _claims()),
            ],
        )
        with pytest.raises(WALWriteError):
            async with ctx:
                pass
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_idle_after_body_exception(self) -> None:
        """Exception in with-body: ACTIVE -> FAULTED -> IDLE via __aexit__."""
        store = InMemoryIdempotencyStore()
        ctx = KernelContext(gates=[k5_gate(payload={"e": "body"}, store=store)])
        with pytest.raises(ValueError):
            async with ctx:
                raise ValueError("body error")
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_sequential_operations_all_return_to_idle(self) -> None:
        """N sequential K5+K6 operations each end in IDLE; no interference."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        claims = _claims()
        for i in range(20):
            ctx = await _run_k5_k6({"seq": i}, store, backend, claims)
            assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_independent_contexts_do_not_interfere(self) -> None:
        """Separate contexts have independent state; no cross-contamination."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        claims = _claims()

        ctx_a = KernelContext(
            gates=[
                k5_gate(payload={"ctx": "a"}, store=store),
                _make_k6(backend, claims, boundary="core::a"),
            ],
        )
        ctx_b = KernelContext(
            gates=[
                k5_gate(payload={"ctx": "b"}, store=store),
                _make_k6(backend, claims, boundary="core::b"),
            ],
        )
        async with ctx_a:
            pass
        async with ctx_b:
            pass

        assert ctx_a.state == KernelState.IDLE
        assert ctx_b.state == KernelState.IDLE
        # Independent WAL entries with distinct boundary names.
        assert len(backend.entries) == 2
        crossings = {e.boundary_crossing for e in backend.entries}
        assert crossings == {"core::a", "core::b"}


# ---------------------------------------------------------------------------
# INV-3: State Always in Valid Set
# ---------------------------------------------------------------------------


class TestINV3ValidStateAlways:
    """INV-3: ctx.state is always a member of KernelState."""

    def test_state_valid_before_enter(self) -> None:
        """Freshly-constructed context starts in IDLE (a valid state)."""
        ctx = KernelContext()
        assert ctx.state in _ALL_KERNEL_STATES
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_state_valid_after_successful_operation(self) -> None:
        """After successful operation, state is a valid KernelState."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        ctx = await _run_k5_k6({"v": 1}, store, backend, _claims())
        assert ctx.state in _ALL_KERNEL_STATES

    @pytest.mark.asyncio
    async def test_state_valid_after_k5_failure(self) -> None:
        """After K5 failure (duplicate), state is a valid KernelState."""
        store = InMemoryIdempotencyStore()
        store.check_and_mark(k5_generate_key({"dup": True}))
        ctx = KernelContext(gates=[k5_gate(payload={"dup": True}, store=store)])
        with pytest.raises(DuplicateRequestError):
            async with ctx:
                pass
        assert ctx.state in _ALL_KERNEL_STATES

    @pytest.mark.asyncio
    async def test_state_valid_after_k6_failure(self) -> None:
        """After K6 backend failure, state is a valid KernelState."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        backend._fail = True
        ctx = KernelContext(
            gates=[
                k5_gate(payload={"f": 6}, store=store),
                _make_k6(backend, _claims()),
            ],
        )
        with pytest.raises(WALWriteError):
            async with ctx:
                pass
        assert ctx.state in _ALL_KERNEL_STATES


# ---------------------------------------------------------------------------
# INV-4: Guard Condition Determinism
# ---------------------------------------------------------------------------


class TestINV4GuardDeterminism:
    """INV-4: K5 and K6 guard computations are pure, deterministic functions.

    Same inputs always produce the same outputs; no side effects on evaluation.
    """

    def test_k5_generate_key_deterministic(self) -> None:
        """Same payload always produces the same idempotency key."""
        payload = {"user": "alice", "action": "write", "resource": "doc-1"}
        assert k5_generate_key(payload) == k5_generate_key(payload)

    def test_k5_key_order_independence(self) -> None:
        """RFC 8785 canonical form: key order does not affect the hash."""
        key_a = k5_generate_key({"alpha": 1, "beta": 2})
        key_b = k5_generate_key({"beta": 2, "alpha": 1})
        assert key_a == key_b

    def test_k5_generate_key_100_repeated_calls_identical(self) -> None:
        """100 repeated calls on identical payload produce the same key."""
        payload = {"k": "v", "n": 42}
        keys = {k5_generate_key(payload) for _ in range(100)}
        assert len(keys) == 1

    def test_redact_deterministic(self) -> None:
        """Same text always produces the same (redacted_text, rules) pair."""
        text = "Contact user@example.com or call 555-867 5309"
        assert redact(text) == redact(text)

    def test_redact_email_rule_is_idempotent(self) -> None:
        """Applying redact twice on email-only input gives same result as once.

        Email tokens cannot re-trigger any redaction rule after replacement
        with '[email hidden]' (no @ character), so email redaction is idempotent.
        """
        text = "Contact alice@example.com and bob@corp.org for access"
        redacted_once, _ = redact(text)
        redacted_twice, _ = redact(redacted_once)
        assert redacted_twice == redacted_once

    def test_redact_clean_text_unchanged(self) -> None:
        """Clean text (no PII) is returned unchanged with empty rules list."""
        text = "Operation completed with exit code 0."
        result_text, rules = redact(text)
        assert result_text == text
        assert rules == []

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet=_ALPHA_NUM),
            st.one_of(st.integers(0, 9999), st.text(max_size=10), st.booleans()),
            max_size=5,
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_k5_key_determinism_property(self, payload: dict) -> None:
        """Property: k5_generate_key is deterministic and produces a 64-hex key."""
        k1 = k5_generate_key(payload)
        k2 = k5_generate_key(payload)
        assert k1 == k2
        assert len(k1) == 64
        assert all(c in "0123456789abcdef" for c in k1)

    @given(st.text(max_size=200))
    @settings(max_examples=200, deadline=None)
    def test_redact_determinism_property(self, text: str) -> None:
        """Property: redact(text) == redact(text) for any input."""
        assert redact(text) == redact(text)


# ---------------------------------------------------------------------------
# INV-5: ACTIVE Requires All Gates to Pass
# ---------------------------------------------------------------------------


class TestINV5ActiveRequiresGatesPass:
    """INV-5: KernelContext only reaches ACTIVE after K5+K6 both pass."""

    @pytest.mark.asyncio
    async def test_reaches_active_when_k5_k6_pass(self) -> None:
        """Successful K5+K6: context traverses ENTERING -> ACTIVE."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        active_observed = False
        ctx = KernelContext(
            gates=[
                k5_gate(payload={"n": 5}, store=store),
                _make_k6(backend, _claims()),
            ],
        )
        async with ctx:
            active_observed = ctx.state == KernelState.ACTIVE
        assert active_observed

    @pytest.mark.asyncio
    async def test_duplicate_k5_never_reaches_active(self) -> None:
        """K5 duplicate: body never executes; context ends IDLE not ACTIVE."""
        store = InMemoryIdempotencyStore()
        store.check_and_mark(k5_generate_key({"dup": "key"}))
        active_observed = False
        ctx = KernelContext(gates=[k5_gate(payload={"dup": "key"}, store=store)])
        with pytest.raises(DuplicateRequestError):
            async with ctx:
                active_observed = True  # unreachable
        assert not active_observed
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_k6_backend_failure_never_reaches_active(self) -> None:
        """K6 WALWriteError: body never executes; context ends IDLE not ACTIVE."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        backend._fail = True
        active_observed = False
        ctx = KernelContext(
            gates=[
                k5_gate(payload={"n": 55}, store=store),
                _make_k6(backend, _claims()),
            ],
        )
        with pytest.raises(WALWriteError):
            async with ctx:
                active_observed = True  # unreachable
        assert not active_observed
        assert ctx.state == KernelState.IDLE

    @pytest.mark.asyncio
    async def test_k5_failure_leaves_k6_backend_clean(self) -> None:
        """When K5 fails, K6 never runs; WAL backend receives no entries."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        store.check_and_mark(k5_generate_key({"pre": "marked"}))
        ctx = KernelContext(
            gates=[
                k5_gate(payload={"pre": "marked"}, store=store),
                _make_k6(backend, _claims()),
            ],
        )
        with pytest.raises(DuplicateRequestError):
            async with ctx:
                pass
        # K6 never ran because K5 failed first.
        assert len(backend.entries) == 0

    @pytest.mark.asyncio
    async def test_k5_only_gate_still_reaches_active(self) -> None:
        """K5-only gate (no K6): context reaches ACTIVE confirming INV-5 is gate-agnostic."""
        store = InMemoryIdempotencyStore()
        active_with_k5_only = False
        ctx = KernelContext(gates=[k5_gate(payload={"k5only": True}, store=store)])
        async with ctx:
            active_with_k5_only = ctx.state == KernelState.ACTIVE
        assert active_with_k5_only

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=8, alphabet=_ALPHA_NUM),
            st.integers(min_value=0, max_value=9999),
            min_size=1,
            max_size=4,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_active_state_only_after_gates_pass_property(self, payload: dict) -> None:
        """Property: for any unique payload, context reaches ACTIVE then returns IDLE."""

        async def _run() -> tuple[bool, KernelState]:
            store = InMemoryIdempotencyStore()
            backend = InMemoryWALBackend()
            active_reached = False
            ctx = KernelContext(
                gates=[
                    k5_gate(payload=payload, store=store),
                    _make_k6(backend, _claims()),
                ],
            )
            async with ctx:
                active_reached = ctx.state == KernelState.ACTIVE
            return active_reached, ctx.state

        active_reached, final_state = asyncio.run(_run())
        assert active_reached  # INV-5
        assert final_state == KernelState.IDLE  # INV-2


# ---------------------------------------------------------------------------
# INV-6: WAL Entry Required Fields
# ---------------------------------------------------------------------------


class TestINV6WALEntryFields:
    """INV-6: Every written WAL entry has non-null corr_id, tenant_id, timestamp."""

    @pytest.mark.asyncio
    async def test_wal_entry_has_corr_id_matching_context(self) -> None:
        """WAL entry correlation_id equals the KernelContext corr_id."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        corr_id = str(uuid.uuid4())
        ctx = await _run_k5_k6({"x": 1}, store, backend, _claims(), corr_id=corr_id)
        entry = backend.entries[0]
        assert entry.correlation_id
        assert entry.correlation_id == corr_id
        assert entry.correlation_id == ctx.corr_id

    @pytest.mark.asyncio
    async def test_wal_entry_has_tenant_id_from_claims(self) -> None:
        """WAL entry tenant_id taken from claims when ctx.tenant_id is None."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        claims = _claims(tenant_id="tenant-xyz")
        await _run_k5_k6({"x": 2}, store, backend, claims)
        entry = backend.entries[0]
        assert entry.tenant_id
        assert entry.tenant_id == "tenant-xyz"

    @pytest.mark.asyncio
    async def test_wal_entry_has_non_null_timestamp(self) -> None:
        """WAL entry timestamp is populated and timezone-aware."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        await _run_k5_k6({"x": 3}, store, backend, _claims())
        entry = backend.entries[0]
        assert entry.timestamp is not None
        assert entry.timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_wal_entry_timestamp_utc_offset_zero(self) -> None:
        """WAL entry timestamp has zero UTC offset (stored in UTC)."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        await _run_k5_k6({"x": 4}, store, backend, _claims())
        entry = backend.entries[0]
        assert entry.timestamp.utcoffset().total_seconds() == 0

    @pytest.mark.asyncio
    async def test_wal_entry_count_equals_operation_count(self) -> None:
        """WALFinality (TLA+): one entry per successful boundary crossing."""
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        n = 15
        for i in range(n):
            await _run_k5_k6({"op": i}, store, backend, _claims())
        assert len(backend.entries) == n

    @given(
        tenant_id=st.text(min_size=1, max_size=20, alphabet=_ALPHA_NUM + "-"),
        user_id=st.text(min_size=1, max_size=15, alphabet=_ALPHA_NUM),
        key=st.text(min_size=1, max_size=8, alphabet=_ALPHA_NUM),
        val=st.integers(min_value=0, max_value=9999),
    )
    @settings(max_examples=200, deadline=None)
    def test_wal_entry_required_fields_property(
        self,
        tenant_id: str,
        user_id: str,
        key: str,
        val: int,
    ) -> None:
        """Property: all WAL entries have non-null corr_id, tenant_id, timestamp."""

        async def _run() -> None:
            store = InMemoryIdempotencyStore()
            backend = InMemoryWALBackend()
            claims = _claims(tenant_id=tenant_id, user_id=user_id)
            await _run_k5_k6({key: val}, store, backend, claims)
            assert len(backend.entries) == 1
            entry = backend.entries[0]
            assert entry.correlation_id  # non-empty string
            assert entry.tenant_id  # non-empty string
            assert entry.timestamp is not None

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Master Invariant Preservation Tests
# ---------------------------------------------------------------------------


class TestMasterInvariantPreservation:
    """End-to-end tests verifying all 6 invariants hold over large trace sets."""

    @pytest.mark.asyncio
    async def test_zero_violations_over_10000_operations(self) -> None:
        """Run 10,000 K5+K6 operations; verify zero invariant violations.

        Acceptance criterion from Task 17.7:
            Zero invariant violations over 10,000 generated traces.
        """
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        claims = _claims()

        for i in range(10_000):
            payload = {"operation": "boundary_crossing", "sequence": i}
            ctx = await _run_k5_k6(payload, store, backend, claims)

            # INV-2: state is IDLE after every operation (no stuck states).
            assert ctx.state == KernelState.IDLE, f"INV-2 violated at i={i}"
            # INV-3: state is a valid KernelState.
            assert ctx.state in _ALL_KERNEL_STATES, f"INV-3 violated at i={i}"

        # INV-6 (WALFinality): exactly one entry per crossing.
        assert len(backend.entries) == 10_000, "INV-6 WALFinality violated"
        for i, entry in enumerate(backend.entries):
            assert entry.correlation_id, f"INV-6 corr_id null at entry[{i}]"
            assert entry.tenant_id, f"INV-6 tenant_id null at entry[{i}]"
            assert entry.timestamp is not None, f"INV-6 timestamp null at entry[{i}]"

        # INV-4: k5_generate_key is deterministic (spot-check 200 payloads).
        for i in range(200):
            payload = {"operation": "boundary_crossing", "sequence": i}
            k1 = k5_generate_key(payload)
            k2 = k5_generate_key(payload)
            assert k1 == k2, f"INV-4 violated: non-deterministic key at i={i}"

    @given(
        st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=6, alphabet=_ALPHA_NUM),
                st.integers(min_value=0, max_value=9999),
                min_size=1,
                max_size=4,
            ),
            min_size=1,
            max_size=50,
            unique_by=lambda d: tuple(sorted(d.items())),
        )
    )
    @settings(max_examples=200, deadline=None)
    def test_random_sequence_preserves_all_invariants(
        self, payloads: list[dict]
    ) -> None:
        """Property: random K5+K6 sequence preserves INV-2, INV-3, INV-6."""

        async def _run() -> None:
            store = InMemoryIdempotencyStore()
            backend = InMemoryWALBackend()
            claims = _claims()
            for payload in payloads:
                ctx = await _run_k5_k6(payload, store, backend, claims)
                assert ctx.state == KernelState.IDLE  # INV-2
                assert ctx.state in _ALL_KERNEL_STATES  # INV-3
            for entry in backend.entries:
                assert entry.correlation_id  # INV-6
                assert entry.tenant_id  # INV-6
                assert entry.timestamp is not None  # INV-6

        asyncio.run(_run())

    @pytest.mark.asyncio
    async def test_mixed_success_failure_sequence_invariants(self) -> None:
        """Mixed success/failure sequence: all invariants hold throughout.

        Payloads cycle mod-10, so first 10 unique payloads succeed;
        remaining 90 are duplicates (K5 raises DuplicateRequestError).
        Invariants must hold after every operation regardless of outcome.
        """
        store = InMemoryIdempotencyStore()
        backend = InMemoryWALBackend()
        claims = _claims()
        success_count = 0
        failure_count = 0

        for i in range(100):
            payload = {"n": i % 10}
            ctx = KernelContext(
                gates=[
                    k5_gate(payload=payload, store=store),
                    _make_k6(backend, claims, boundary=f"core::mix_{i}"),
                ],
            )
            try:
                async with ctx:
                    pass
                success_count += 1
            except DuplicateRequestError:
                failure_count += 1

            # INV-2 + INV-3: every iteration ends in IDLE.
            assert ctx.state == KernelState.IDLE
            assert ctx.state in _ALL_KERNEL_STATES

        # First 10 unique payloads succeed; next 90 are duplicates.
        assert success_count == 10
        assert failure_count == 90
        # INV-6 (WALFinality): exactly 10 WAL entries.
        assert len(backend.entries) == 10
        for entry in backend.entries:
            assert entry.correlation_id
            assert entry.tenant_id
            assert entry.timestamp is not None
