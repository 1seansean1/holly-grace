"""Tests for holly.kernel.state_machine — KernelContext state-machine validator.

Task 14.5 — Implement formal state-machine validator.

Covers:
    validate_transition   — pure guard; deterministic; no side effects
    apply_event           — pure event dispatcher
    validate_trace        — full-trace validation
    reachable_from        — successor-set query
    KernelStateMachineValidator — stateful wrapper

Test taxonomy
─────────────
Structure       verify VALID_TRANSITIONS mirrors TLA+ spec (8 transitions, 5 states)
Unit-valid      every valid (from, to) pair returns True from validate_transition
Unit-invalid    every invalid pair raises KernelInvariantError
Unit-event      every KernelEvent applied from the correct state produces correct result
Unit-event-err  every KernelEvent applied from the wrong state raises
Unit-trace      happy path, gate-fail, async-cancel, exit-fail traces
Unit-validator  KernelStateMachineValidator lifecycle, error isolation, read-only state
Property        Hypothesis: determinism, no side effects, state-space coverage,
                trace/transition consistency, invariant preservation under random events
Invariants      Behavior Spec §1.1 INV-3 (state set) and INV-4 (determinism/purity)
"""

from __future__ import annotations

import contextlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holly.kernel.exceptions import KernelInvariantError
from holly.kernel.state_machine import (
    _EVENT_TRANSITION,
    VALID_TRANSITIONS,
    KernelEvent,
    KernelState,
    KernelStateMachineValidator,
    apply_event,
    reachable_from,
    validate_trace,
    validate_transition,
)

# ---------------------------------------------------------------------------
# Helpers and strategies
# ---------------------------------------------------------------------------

ALL_STATES = list(KernelState)
ALL_EVENTS = list(KernelEvent)
ALL_PAIRS: list[tuple[KernelState, KernelState]] = [
    (f, t) for f in KernelState for t in KernelState
]
INVALID_TRANSITIONS: list[tuple[KernelState, KernelState]] = [
    p for p in ALL_PAIRS if p not in VALID_TRANSITIONS
]

st_state = st.sampled_from(ALL_STATES)
st_event = st.sampled_from(ALL_EVENTS)
st_state_pair = st.tuples(st_state, st_state)


# ---------------------------------------------------------------------------
# Structure: verify table matches TLA+ spec
# ---------------------------------------------------------------------------


class TestValidTransitionsTable:
    """VALID_TRANSITIONS must exactly mirror KernelInvariants.tla (Task 14.1)."""

    def test_exactly_eight_transitions(self) -> None:
        """TLA+ spec defines exactly 8 actions (8 valid transitions)."""
        assert len(VALID_TRANSITIONS) == 8

    def test_all_five_states_present(self) -> None:
        """Every KernelState appears as source or target in at least one transition."""
        sources = {f for f, _ in VALID_TRANSITIONS}
        targets = {t for _, t in VALID_TRANSITIONS}
        assert sources | targets == set(KernelState)

    def test_idle_successor_is_entering_only(self) -> None:
        assert reachable_from(KernelState.IDLE) == {KernelState.ENTERING}

    def test_entering_successors(self) -> None:
        assert reachable_from(KernelState.ENTERING) == {
            KernelState.ACTIVE,
            KernelState.FAULTED,
        }

    def test_active_successors(self) -> None:
        assert reachable_from(KernelState.ACTIVE) == {
            KernelState.EXITING,
            KernelState.FAULTED,
        }

    def test_exiting_successors(self) -> None:
        assert reachable_from(KernelState.EXITING) == {
            KernelState.IDLE,
            KernelState.FAULTED,
        }

    def test_faulted_successor_is_idle_only(self) -> None:
        assert reachable_from(KernelState.FAULTED) == {KernelState.IDLE}

    def test_no_self_loops(self) -> None:
        """No state may transition to itself (Behavior Spec §1.1)."""
        for state in KernelState:
            assert (state, state) not in VALID_TRANSITIONS

    def test_event_table_covers_all_events(self) -> None:
        """Every KernelEvent has an entry in _EVENT_TRANSITION."""
        assert set(_EVENT_TRANSITION) == set(KernelEvent)

    def test_event_table_transitions_are_valid(self) -> None:
        """Every entry in _EVENT_TRANSITION is also in VALID_TRANSITIONS."""
        for event, (from_s, to_s) in _EVENT_TRANSITION.items():
            assert (from_s, to_s) in VALID_TRANSITIONS, (
                f"{event.value}: ({from_s.value}, {to_s.value}) not in VALID_TRANSITIONS"
            )


# ---------------------------------------------------------------------------
# validate_transition — unit tests
# ---------------------------------------------------------------------------


class TestValidateTransition:
    @pytest.mark.parametrize(
        "from_s,to_s",
        sorted(VALID_TRANSITIONS, key=lambda p: (p[0].value, p[1].value)),
    )
    def test_valid_transition_returns_true(
        self, from_s: KernelState, to_s: KernelState
    ) -> None:
        assert validate_transition(from_s, to_s) is True

    @pytest.mark.parametrize("from_s,to_s", INVALID_TRANSITIONS)
    def test_invalid_transition_raises_kernel_invariant_error(
        self, from_s: KernelState, to_s: KernelState
    ) -> None:
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_transition(from_s, to_s)
        assert exc_info.value.invariant == "state_transition"
        assert from_s.value in str(exc_info.value)
        assert to_s.value in str(exc_info.value)

    # Spot-checks for key failure modes (Behavior Spec §1.1)
    def test_faulted_cannot_go_to_active(self) -> None:
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.FAULTED, KernelState.ACTIVE)

    def test_faulted_cannot_go_to_entering(self) -> None:
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.FAULTED, KernelState.ENTERING)

    def test_faulted_cannot_go_to_exiting(self) -> None:
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.FAULTED, KernelState.EXITING)

    def test_idle_cannot_skip_to_active(self) -> None:
        """INV-5: ACTIVE requires all gates passed; IDLE→ACTIVE would bypass them."""
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.IDLE, KernelState.ACTIVE)

    def test_active_cannot_return_to_idle_directly(self) -> None:
        """ACTIVE must pass through EXITING; no direct ACTIVE→IDLE shortcut."""
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.ACTIVE, KernelState.IDLE)

    def test_error_message_lists_valid_successors(self) -> None:
        """Error from IDLE→ACTIVE must mention ENTERING (the only valid successor)."""
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_transition(KernelState.IDLE, KernelState.ACTIVE)
        assert "ENTERING" in str(exc_info.value)

    def test_error_message_names_both_states(self) -> None:
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_transition(KernelState.ENTERING, KernelState.IDLE)
        assert "ENTERING" in str(exc_info.value)
        assert "IDLE" in str(exc_info.value)


# ---------------------------------------------------------------------------
# apply_event — unit tests
# ---------------------------------------------------------------------------


class TestApplyEvent:
    def test_aenter_from_idle(self) -> None:
        assert apply_event(KernelState.IDLE, KernelEvent.AENTER) == KernelState.ENTERING

    def test_all_gates_pass_from_entering(self) -> None:
        assert (
            apply_event(KernelState.ENTERING, KernelEvent.ALL_GATES_PASS)
            == KernelState.ACTIVE
        )

    def test_gate_fail_from_entering(self) -> None:
        assert (
            apply_event(KernelState.ENTERING, KernelEvent.GATE_FAIL)
            == KernelState.FAULTED
        )

    def test_op_complete_from_active(self) -> None:
        assert (
            apply_event(KernelState.ACTIVE, KernelEvent.OP_COMPLETE)
            == KernelState.EXITING
        )

    def test_async_cancel_from_active(self) -> None:
        assert (
            apply_event(KernelState.ACTIVE, KernelEvent.ASYNC_CANCEL)
            == KernelState.FAULTED
        )

    def test_exit_ok_from_exiting(self) -> None:
        assert (
            apply_event(KernelState.EXITING, KernelEvent.EXIT_OK) == KernelState.IDLE
        )

    def test_exit_fail_from_exiting(self) -> None:
        assert (
            apply_event(KernelState.EXITING, KernelEvent.EXIT_FAIL)
            == KernelState.FAULTED
        )

    def test_exc_consumed_from_faulted(self) -> None:
        assert (
            apply_event(KernelState.FAULTED, KernelEvent.EXC_CONSUMED)
            == KernelState.IDLE
        )

    def test_aenter_from_non_idle_raises(self) -> None:
        wrong_states = [
            KernelState.ENTERING,
            KernelState.ACTIVE,
            KernelState.EXITING,
            KernelState.FAULTED,
        ]
        for state in wrong_states:
            with pytest.raises(KernelInvariantError) as exc_info:
                apply_event(state, KernelEvent.AENTER)
            # Error must mention the required state (IDLE)
            assert "IDLE" in str(exc_info.value)

    def test_all_gates_pass_from_non_entering_raises(self) -> None:
        for state in (
            KernelState.IDLE,
            KernelState.ACTIVE,
            KernelState.EXITING,
            KernelState.FAULTED,
        ):
            with pytest.raises(KernelInvariantError):
                apply_event(state, KernelEvent.ALL_GATES_PASS)

    def test_exc_consumed_from_non_faulted_raises(self) -> None:
        for state in (
            KernelState.IDLE,
            KernelState.ENTERING,
            KernelState.ACTIVE,
            KernelState.EXITING,
        ):
            with pytest.raises(KernelInvariantError):
                apply_event(state, KernelEvent.EXC_CONSUMED)

    def test_error_names_required_and_actual_state(self) -> None:
        with pytest.raises(KernelInvariantError) as exc_info:
            apply_event(KernelState.ACTIVE, KernelEvent.AENTER)
        msg = str(exc_info.value)
        assert "IDLE" in msg  # required state
        assert "ACTIVE" in msg  # actual state


# ---------------------------------------------------------------------------
# validate_trace — unit tests
# ---------------------------------------------------------------------------


class TestValidateTrace:
    def test_empty_trace_is_valid(self) -> None:
        validate_trace([])  # no exception

    def test_single_state_trace_is_valid(self) -> None:
        for state in KernelState:
            validate_trace([state])

    def test_happy_path_full_trace(self) -> None:
        """IDLE → ENTERING → ACTIVE → EXITING → IDLE"""
        validate_trace(
            [
                KernelState.IDLE,
                KernelState.ENTERING,
                KernelState.ACTIVE,
                KernelState.EXITING,
                KernelState.IDLE,
            ]
        )

    def test_gate_failure_trace(self) -> None:
        """IDLE → ENTERING → FAULTED → IDLE"""
        validate_trace(
            [
                KernelState.IDLE,
                KernelState.ENTERING,
                KernelState.FAULTED,
                KernelState.IDLE,
            ]
        )

    def test_async_cancel_trace(self) -> None:
        """IDLE → ENTERING → ACTIVE → FAULTED → IDLE"""
        validate_trace(
            [
                KernelState.IDLE,
                KernelState.ENTERING,
                KernelState.ACTIVE,
                KernelState.FAULTED,
                KernelState.IDLE,
            ]
        )

    def test_exit_failure_trace(self) -> None:
        """IDLE → ENTERING → ACTIVE → EXITING → FAULTED → IDLE"""
        validate_trace(
            [
                KernelState.IDLE,
                KernelState.ENTERING,
                KernelState.ACTIVE,
                KernelState.EXITING,
                KernelState.FAULTED,
                KernelState.IDLE,
            ]
        )

    def test_repeated_crossing_trace(self) -> None:
        """Two consecutive happy-path crossings in one trace."""
        crossing = [
            KernelState.IDLE,
            KernelState.ENTERING,
            KernelState.ACTIVE,
            KernelState.EXITING,
            KernelState.IDLE,
        ]
        # Second crossing starts from IDLE (the last element of the first)
        trace = crossing + crossing[1:]
        validate_trace(trace)

    def test_idle_to_active_skip_raises(self) -> None:
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_trace([KernelState.IDLE, KernelState.ACTIVE])
        assert "IDLE" in str(exc_info.value)
        assert "ACTIVE" in str(exc_info.value)

    def test_entering_to_idle_invalid(self) -> None:
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_trace(
                [KernelState.IDLE, KernelState.ENTERING, KernelState.IDLE]
            )
        assert "ENTERING" in str(exc_info.value)
        assert "IDLE" in str(exc_info.value)

    def test_first_invalid_pair_is_reported(self) -> None:
        """validate_trace raises on the first bad pair, not a later one."""
        # Valid: IDLE→ENTERING. Invalid: ENTERING→IDLE.  Never reaches IDLE→ENTERING again.
        with pytest.raises(KernelInvariantError) as exc_info:
            validate_trace(
                [
                    KernelState.IDLE,
                    KernelState.ENTERING,
                    KernelState.IDLE,  # ← first invalid pair
                    KernelState.ACTIVE,  # ← also invalid, but not reached
                ]
            )
        msg = str(exc_info.value)
        assert "ENTERING" in msg
        assert "IDLE" in msg


# ---------------------------------------------------------------------------
# KernelStateMachineValidator — unit tests
# ---------------------------------------------------------------------------


class TestKernelStateMachineValidator:
    def test_initial_state_is_idle(self) -> None:
        v = KernelStateMachineValidator()
        assert v.state == KernelState.IDLE

    def test_advance_returns_new_state(self) -> None:
        v = KernelStateMachineValidator()
        result = v.advance(KernelEvent.AENTER)
        assert result == KernelState.ENTERING
        assert v.state == KernelState.ENTERING

    def test_full_happy_path(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        v.advance(KernelEvent.ALL_GATES_PASS)
        v.advance(KernelEvent.OP_COMPLETE)
        v.advance(KernelEvent.EXIT_OK)
        assert v.state == KernelState.IDLE

    def test_gate_failure_and_recovery(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        v.advance(KernelEvent.GATE_FAIL)
        assert v.state == KernelState.FAULTED
        v.advance(KernelEvent.EXC_CONSUMED)
        assert v.state == KernelState.IDLE

    def test_async_cancel_and_recovery(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        v.advance(KernelEvent.ALL_GATES_PASS)
        v.advance(KernelEvent.ASYNC_CANCEL)
        assert v.state == KernelState.FAULTED
        v.advance(KernelEvent.EXC_CONSUMED)
        assert v.state == KernelState.IDLE

    def test_exit_failure_and_recovery(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        v.advance(KernelEvent.ALL_GATES_PASS)
        v.advance(KernelEvent.OP_COMPLETE)
        v.advance(KernelEvent.EXIT_FAIL)
        assert v.state == KernelState.FAULTED
        v.advance(KernelEvent.EXC_CONSUMED)
        assert v.state == KernelState.IDLE

    def test_invalid_event_raises_and_does_not_change_state(self) -> None:
        """State must be unchanged after a failed advance (atomicity)."""
        v = KernelStateMachineValidator()
        assert v.state == KernelState.IDLE
        with pytest.raises(KernelInvariantError):
            v.advance(KernelEvent.ALL_GATES_PASS)  # not applicable from IDLE
        assert v.state == KernelState.IDLE  # unchanged

    def test_invalid_event_in_entering_does_not_corrupt_state(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        with pytest.raises(KernelInvariantError):
            v.advance(KernelEvent.EXIT_OK)  # not applicable from ENTERING
        assert v.state == KernelState.ENTERING

    def test_check_transition_is_pure_does_not_advance(self) -> None:
        """check_transition must not advance the validator's state."""
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        result = v.check_transition(KernelState.ACTIVE)  # prospective
        assert result is True
        assert v.state == KernelState.ENTERING  # NOT advanced

    def test_check_transition_invalid_raises_does_not_change_state(self) -> None:
        v = KernelStateMachineValidator()
        with pytest.raises(KernelInvariantError):
            v.check_transition(KernelState.ACTIVE)  # IDLE→ACTIVE is invalid
        assert v.state == KernelState.IDLE

    def test_reset_returns_to_idle(self) -> None:
        v = KernelStateMachineValidator()
        v.advance(KernelEvent.AENTER)
        v.advance(KernelEvent.ALL_GATES_PASS)
        assert v.state == KernelState.ACTIVE
        v.reset()
        assert v.state == KernelState.IDLE

    def test_state_property_has_no_setter(self) -> None:
        """Assigning to state must raise AttributeError (read-only property)."""
        v = KernelStateMachineValidator()
        with pytest.raises(AttributeError):
            v.state = KernelState.ACTIVE  # type: ignore[misc]

    def test_repr_contains_state_name(self) -> None:
        v = KernelStateMachineValidator()
        assert "IDLE" in repr(v)
        v.advance(KernelEvent.AENTER)
        assert "ENTERING" in repr(v)

    def test_multiple_crossings_after_reset(self) -> None:
        """Validator can be reused for multiple crossings after reset()."""
        v = KernelStateMachineValidator()
        for _ in range(3):
            v.advance(KernelEvent.AENTER)
            v.advance(KernelEvent.ALL_GATES_PASS)
            v.advance(KernelEvent.OP_COMPLETE)
            v.advance(KernelEvent.EXIT_OK)
            assert v.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Property-based tests (Hypothesis) — Behavior Spec §1.1 INV-4
# ---------------------------------------------------------------------------


class TestDeterminismAndPurity:
    """Guards must be deterministic and have no side effects (INV-4)."""

    @given(st_state_pair)
    def test_validate_transition_is_deterministic(
        self, pair: tuple[KernelState, KernelState]
    ) -> None:
        """validate_transition(s, t) twice always returns same result."""
        from_s, to_s = pair
        r1 = r2 = None
        e1 = e2 = None
        try:
            r1 = validate_transition(from_s, to_s)
        except KernelInvariantError as e:
            e1 = type(e)
        try:
            r2 = validate_transition(from_s, to_s)
        except KernelInvariantError as e:
            e2 = type(e)
        assert r1 == r2
        assert e1 == e2

    @given(st.tuples(st_state, st_event))
    def test_apply_event_is_deterministic(
        self, pair: tuple[KernelState, KernelEvent]
    ) -> None:
        """apply_event(s, e) twice always returns same result."""
        state, event = pair
        r1 = r2 = None
        e1 = e2 = None
        try:
            r1 = apply_event(state, event)
        except KernelInvariantError as e:
            e1 = type(e)
        try:
            r2 = apply_event(state, event)
        except KernelInvariantError as e:
            e2 = type(e)
        assert r1 == r2
        assert e1 == e2

    @given(st_state_pair)
    def test_validate_transition_does_not_mutate_valid_transitions(
        self, pair: tuple[KernelState, KernelState]
    ) -> None:
        """Calling the guard must not modify VALID_TRANSITIONS."""
        snapshot = frozenset(VALID_TRANSITIONS)
        with contextlib.suppress(KernelInvariantError):
            validate_transition(*pair)
        assert snapshot == VALID_TRANSITIONS

    @given(st.tuples(st_state, st_event))
    def test_apply_event_does_not_mutate_event_table(
        self, pair: tuple[KernelState, KernelEvent]
    ) -> None:
        """apply_event must not modify _EVENT_TRANSITION."""
        snapshot = dict(_EVENT_TRANSITION)
        with contextlib.suppress(KernelInvariantError):
            apply_event(*pair)
        assert snapshot == _EVENT_TRANSITION

    @given(st_state_pair)
    def test_validate_transition_binary_coverage(
        self, pair: tuple[KernelState, KernelState]
    ) -> None:
        """Every (from, to) pair either returns True or raises; no undefined behaviour."""
        from_s, to_s = pair
        if (from_s, to_s) in VALID_TRANSITIONS:
            assert validate_transition(from_s, to_s) is True
        else:
            with pytest.raises(KernelInvariantError):
                validate_transition(from_s, to_s)


# ---------------------------------------------------------------------------
# State-space coverage (Hypothesis)
# ---------------------------------------------------------------------------


class TestStateSpaceCoverage:
    @given(st_state)
    def test_reachable_from_returns_frozenset(self, state: KernelState) -> None:
        result = reachable_from(state)
        assert isinstance(result, frozenset)
        assert all(s in KernelState for s in result)

    @given(st_state)
    def test_every_state_has_at_least_one_successor(self, state: KernelState) -> None:
        """No dead-end states (every state can transition somewhere)."""
        assert len(reachable_from(state)) >= 1

    @given(st.lists(st_event, min_size=0, max_size=25))
    @settings(max_examples=500)
    def test_event_sequence_state_always_valid(
        self, events: list[KernelEvent]
    ) -> None:
        """Any sequence of events keeps the validator's state in KernelState."""
        v = KernelStateMachineValidator()
        for event in events:
            with contextlib.suppress(KernelInvariantError):
                v.advance(event)  # invalid event for current state: state unchanged
            assert v.state in KernelState

    @given(st.lists(st_event, min_size=0, max_size=25))
    @settings(max_examples=500)
    def test_invalid_event_never_corrupts_state(
        self, events: list[KernelEvent]
    ) -> None:
        """After any mix of valid/invalid events, state is always a valid KernelState
        and an invalid event never changes the state."""
        v = KernelStateMachineValidator()
        for event in events:
            before = v.state
            try:
                v.advance(event)
            except KernelInvariantError:
                assert v.state == before  # unchanged on error
            assert v.state in KernelState

    @given(st.lists(st_state, min_size=2, max_size=15))
    @settings(max_examples=500)
    def test_validate_trace_consistent_with_valid_transitions(
        self, trace: list[KernelState]
    ) -> None:
        """validate_trace(t) raises iff any consecutive pair is not in VALID_TRANSITIONS."""
        expected_valid = all(
            (trace[i], trace[i + 1]) in VALID_TRANSITIONS
            for i in range(len(trace) - 1)
        )
        if expected_valid:
            validate_trace(trace)  # must not raise
        else:
            with pytest.raises(KernelInvariantError):
                validate_trace(trace)

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=200)
    def test_repeated_happy_path_cycles_end_in_idle(
        self, n_cycles: int
    ) -> None:
        """N repetitions of the canonical happy-path cycle always end in IDLE.

        Happy-path cycle: AENTER → ALL_GATES_PASS → OP_COMPLETE → EXIT_OK.
        Each cycle begins and ends in IDLE; after N cycles the state is IDLE.
        """
        happy_path = [
            KernelEvent.AENTER,
            KernelEvent.ALL_GATES_PASS,
            KernelEvent.OP_COMPLETE,
            KernelEvent.EXIT_OK,
        ]
        v = KernelStateMachineValidator()
        for _ in range(n_cycles):
            for evt in happy_path:
                v.advance(evt)
        assert v.state == KernelState.IDLE


# ---------------------------------------------------------------------------
# Behavior Spec §1.1 invariants
# ---------------------------------------------------------------------------


class TestBehaviorSpecInvariants:
    """INV-3: state ∈ {IDLE,ENTERING,ACTIVE,EXITING,FAULTED}.
    INV-4: guards are deterministic and have no side effects.
    INV-5: ACTIVE requires all K1-K8 gates passed (no shortcut)."""

    def test_inv3_exactly_five_states(self) -> None:
        """§1.1 INV-3: exactly five legal states."""
        assert set(KernelState) == {
            KernelState.IDLE,
            KernelState.ENTERING,
            KernelState.ACTIVE,
            KernelState.EXITING,
            KernelState.FAULTED,
        }

    def test_inv5_no_idle_to_active_bypass(self) -> None:
        """§1.1 INV-5: no context can be ACTIVE without passing all gates.
        Therefore IDLE→ACTIVE must be rejected."""
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.IDLE, KernelState.ACTIVE)

    def test_inv5_no_faulted_to_active(self) -> None:
        """§1.1: FAULTED→ACTIVE is an invalid transition (spec §1.1 State Violation)."""
        with pytest.raises(KernelInvariantError):
            validate_transition(KernelState.FAULTED, KernelState.ACTIVE)

    @given(st_state_pair)
    def test_inv4_guard_is_deterministic(
        self, pair: tuple[KernelState, KernelState]
    ) -> None:
        """§1.1 INV-4: same (from, to) always produces same guard result."""
        in_set_1 = pair in VALID_TRANSITIONS
        in_set_2 = pair in VALID_TRANSITIONS
        assert in_set_1 == in_set_2

    @given(st_state_pair)
    def test_inv4_guard_has_no_side_effects(
        self, pair: tuple[KernelState, KernelState]
    ) -> None:
        """§1.1 INV-4: evaluating a guard must not change VALID_TRANSITIONS."""
        n_before = len(VALID_TRANSITIONS)
        _ = pair in VALID_TRANSITIONS
        assert len(VALID_TRANSITIONS) == n_before

    def test_fm_001_2_faulted_cannot_silently_become_idle(self) -> None:
        """FM-001-2 mitigation: FAULTED→IDLE is only valid via EXC_CONSUMED.
        Direct transition bypasses exception propagation — must be disallowed
        without an EXC_CONSUMED event."""
        # The only valid event from FAULTED is EXC_CONSUMED.
        for event in KernelEvent:
            if event != KernelEvent.EXC_CONSUMED:
                with pytest.raises(KernelInvariantError):
                    apply_event(KernelState.FAULTED, event)

    def test_fm_001_2_exc_consumed_is_the_only_faulted_exit(self) -> None:
        """Only EXC_CONSUMED can drive FAULTED→IDLE."""
        assert apply_event(KernelState.FAULTED, KernelEvent.EXC_CONSUMED) == KernelState.IDLE
