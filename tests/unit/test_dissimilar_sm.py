"""Unit tests for holly.kernel.dissimilar_sm — Task 20.5.

Verifies all per-trace invariant checkers and the verify_execution_traces
API in isolation, using manually constructed ExecutionTrace objects.

No KernelContext or state_machine imports — pure unit tests.
"""

from __future__ import annotations

import uuid

import pytest

from holly.kernel.dissimilar_sm import (
    ExecutionTrace,
    StateMachineReport,
    TraceCollector,
    check_each_transition,
    check_initial_state,
    check_terminal_state,
    check_valid_state_names,
    parse_trace,
    verify_execution_traces,
)
from holly.kernel.exceptions import DissimilarVerificationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CLEAN_SUCCESS = ("IDLE", "ENTERING", "ACTIVE", "EXITING", "IDLE")
_CLEAN_GATE_FAIL = ("IDLE", "ENTERING", "FAULTED", "IDLE")
_CLEAN_OP_FAIL = ("IDLE", "ENTERING", "ACTIVE", "FAULTED", "IDLE")


def _trace(
    *states: str,
    entry_id: str | None = None,
) -> ExecutionTrace:
    eid = entry_id or str(uuid.uuid4())
    return ExecutionTrace(entry_id=eid, states=tuple(states))


# ---------------------------------------------------------------------------
# TestCheckValidStateNames
# ---------------------------------------------------------------------------


class TestCheckValidStateNames:
    def test_known_states_pass(self) -> None:
        t = _trace(*_CLEAN_SUCCESS)
        assert check_valid_state_names(t) == []

    def test_unknown_state_flagged(self) -> None:
        t = _trace("IDLE", "PROCESSING", "IDLE")
        violations = check_valid_state_names(t)
        assert len(violations) == 1
        assert violations[0].invariant == "SM_unknown_state"
        assert violations[0].step == 1
        assert "PROCESSING" in violations[0].detail

    def test_multiple_unknown_states_all_flagged(self) -> None:
        t = _trace("IDLE", "BOOTING", "RUNNING", "IDLE")
        violations = check_valid_state_names(t)
        assert len(violations) == 2
        invariants = {v.invariant for v in violations}
        assert invariants == {"SM_unknown_state"}

    def test_empty_trace_passes(self) -> None:
        t = _trace()
        assert check_valid_state_names(t) == []


# ---------------------------------------------------------------------------
# TestCheckInitialState
# ---------------------------------------------------------------------------


class TestCheckInitialState:
    def test_starts_idle_passes(self) -> None:
        t = _trace("IDLE", "ENTERING", "ACTIVE", "EXITING", "IDLE")
        assert check_initial_state(t) is None

    def test_starts_non_idle_violation(self) -> None:
        t = _trace("ENTERING", "ACTIVE", "EXITING", "IDLE")
        v = check_initial_state(t)
        assert v is not None
        assert v.invariant == "SM_initial_state"
        assert v.step == 0
        assert "ENTERING" in v.detail

    def test_empty_trace_passes(self) -> None:
        assert check_initial_state(_trace()) is None

    def test_faulted_start_violation(self) -> None:
        t = _trace("FAULTED", "IDLE")
        v = check_initial_state(t)
        assert v is not None
        assert v.invariant == "SM_initial_state"


# ---------------------------------------------------------------------------
# TestCheckTerminalState
# ---------------------------------------------------------------------------


class TestCheckTerminalState:
    def test_ends_idle_passes(self) -> None:
        t = _trace(*_CLEAN_SUCCESS)
        assert check_terminal_state(t) is None

    def test_ends_non_idle_violation(self) -> None:
        # Simulate a trace that got stuck in ACTIVE
        t = _trace("IDLE", "ENTERING", "ACTIVE")
        v = check_terminal_state(t)
        assert v is not None
        assert v.invariant == "SM_terminal_state"
        assert v.step == 2
        assert "ACTIVE" in v.detail

    def test_empty_trace_passes(self) -> None:
        assert check_terminal_state(_trace()) is None

    def test_gate_fail_path_ends_idle(self) -> None:
        t = _trace(*_CLEAN_GATE_FAIL)
        assert check_terminal_state(t) is None


# ---------------------------------------------------------------------------
# TestCheckEachTransition
# ---------------------------------------------------------------------------


class TestCheckEachTransition:
    def test_clean_success_path_passes(self) -> None:
        t = _trace(*_CLEAN_SUCCESS)
        assert check_each_transition(t) == []

    def test_clean_gate_fail_path_passes(self) -> None:
        t = _trace(*_CLEAN_GATE_FAIL)
        assert check_each_transition(t) == []

    def test_clean_op_fail_path_passes(self) -> None:
        t = _trace(*_CLEAN_OP_FAIL)
        assert check_each_transition(t) == []

    def test_invalid_transition_idle_to_active(self) -> None:
        """IDLE -> ACTIVE directly skips ENTERING — invalid."""
        t = _trace("IDLE", "ACTIVE", "EXITING", "IDLE")
        violations = check_each_transition(t)
        assert len(violations) >= 1
        v = violations[0]
        assert v.invariant == "SM_invalid_transition"
        assert v.step == 0
        assert "IDLE" in v.detail
        assert "ACTIVE" in v.detail

    def test_invalid_transition_active_to_idle_directly(self) -> None:
        """ACTIVE -> IDLE directly skips EXITING — invalid."""
        t = _trace("IDLE", "ENTERING", "ACTIVE", "IDLE")
        violations = check_each_transition(t)
        assert len(violations) >= 1
        assert violations[0].invariant == "SM_invalid_transition"

    def test_multiple_violations_in_one_trace(self) -> None:
        """Two consecutive invalid pairs both reported."""
        t = _trace("IDLE", "ACTIVE", "IDLE", "ENTERING")  # two bad jumps
        violations = check_each_transition(t)
        assert len(violations) >= 2

    def test_empty_trace_passes(self) -> None:
        assert check_each_transition(_trace()) == []

    def test_single_state_trace_passes(self) -> None:
        assert check_each_transition(_trace("IDLE")) == []


# ---------------------------------------------------------------------------
# TestParseTrace
# ---------------------------------------------------------------------------


class TestParseTrace:
    def test_roundtrip(self) -> None:
        states = ["IDLE", "ENTERING", "ACTIVE", "EXITING", "IDLE"]
        t = parse_trace("x", states)
        assert t.entry_id == "x"
        assert list(t.states) == states

    def test_empty_list(self) -> None:
        t = parse_trace("e", [])
        assert t.states == ()


# ---------------------------------------------------------------------------
# TestTraceCollector
# ---------------------------------------------------------------------------


class TestTraceCollector:
    def test_record_str_values(self) -> None:
        c = TraceCollector()
        c.record("IDLE")
        c.record("ENTERING")
        t = c.to_trace("tc-1")
        assert t.states == ("IDLE", "ENTERING")
        assert t.entry_id == "tc-1"

    def test_record_accepts_enum_like(self) -> None:
        """str() is called on each value; StrEnum members stringify correctly."""

        class FakeEnum:
            def __str__(self) -> str:
                return "IDLE"

        c = TraceCollector()
        c.record(FakeEnum())
        t = c.to_trace("tc-2")
        assert t.states == ("IDLE",)

    def test_reset_clears_states(self) -> None:
        c = TraceCollector()
        c.record("IDLE")
        c.reset()
        t = c.to_trace("tc-3")
        assert t.states == ()


# ---------------------------------------------------------------------------
# TestVerifyExecutionTraces
# ---------------------------------------------------------------------------


class TestVerifyExecutionTraces:
    def test_clean_success_trace_passes(self) -> None:
        t = _trace(*_CLEAN_SUCCESS, entry_id="clean-1")
        report = verify_execution_traces([t], strict=False)
        assert report.passed is True
        assert report.traces_checked == 1
        assert report.violations == []

    def test_clean_gate_fail_trace_passes(self) -> None:
        t = _trace(*_CLEAN_GATE_FAIL, entry_id="clean-2")
        report = verify_execution_traces([t], strict=False)
        assert report.passed is True

    def test_empty_list_passes(self) -> None:
        report = verify_execution_traces([], strict=False)
        assert report.passed is True
        assert report.traces_checked == 0

    def test_invalid_transition_strict_raises(self) -> None:
        t = _trace("IDLE", "ACTIVE", "EXITING", "IDLE", entry_id="bug-1")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([t])
        assert exc_info.value.invariant == "SM_invalid_transition"
        assert exc_info.value.entry_id == "bug-1"

    def test_invalid_initial_state_strict_raises(self) -> None:
        t = _trace("ENTERING", "ACTIVE", "EXITING", "IDLE", entry_id="bug-2")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([t])
        assert exc_info.value.invariant == "SM_initial_state"

    def test_non_strict_collects_all_violations(self) -> None:
        # Bad initial + bad transition + bad terminal
        t = _trace("ENTERING", "ACTIVE", "IDLE", "FAULTED", entry_id="multi-bug")
        report = verify_execution_traces([t], strict=False)
        assert isinstance(report, StateMachineReport)
        assert report.passed is False
        invariants = {v.invariant for v in report.violations}
        assert "SM_initial_state" in invariants

    def test_multiple_traces_all_clean_passes(self) -> None:
        traces = [
            _trace(*_CLEAN_SUCCESS, entry_id=f"ok-{i}") for i in range(5)
        ]
        report = verify_execution_traces(traces, strict=False)
        assert report.passed is True
        assert report.traces_checked == 5

    def test_injected_unknown_state_strict_raises(self) -> None:
        t = _trace("IDLE", "UNKNOWN_STATE", "IDLE", entry_id="bug-3")
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([t])
        assert exc_info.value.invariant == "SM_unknown_state"
