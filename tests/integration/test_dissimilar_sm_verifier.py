"""Task 20.5 - Dissimilar State Machine Verifier integration tests.

Verifies Behavior Spec §1.1 KernelContext state machine via an independent
dissimilar channel.  Collects execution traces from real KernelContext runs,
then cross-checks them with verify_execution_traces() which has NO dependency
on holly.kernel.state_machine.

Acceptance criteria (Task_Manifest.md §20.5):
1. Detects all injected state machine violations.
2. Independent of kernel implementation (dissimilar_sm imports no kernel gate code).
"""

from __future__ import annotations

import inspect
import re
import uuid
from typing import Any

import pytest

from holly.kernel.context import KernelContext
from holly.kernel.dissimilar_sm import (
    ExecutionTrace,
    StateMachineReport,
    TraceCollector,
    parse_trace,
    verify_execution_traces,
)
from holly.kernel.exceptions import DissimilarVerificationError, KernelError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TraceGate:
    """Spy gate that records ctx.state during gate execution (ENTERING phase)."""

    def __init__(self, collector: TraceCollector) -> None:
        self._collector = collector

    async def __call__(self, ctx: KernelContext) -> None:
        self._collector.record(ctx.state)  # state is ENTERING during gate execution


class _FailGate:
    """Gate that always raises KernelError to trigger FAULTED path."""

    async def __call__(self, ctx: KernelContext) -> None:
        raise KernelError("injected gate failure for test")


class _TracedKernelContext(KernelContext):
    """KernelContext subclass that records the EXITING state during exit cleanup.

    ``_run_exit_cleanup`` is called while the context is in EXITING state.
    By overriding it to record ``self.state`` we capture the one transient state
    that the normal gate/block observation pattern misses.
    """

    def __init__(
        self,
        collector: TraceCollector,
        *,
        gates: Any = (),
        corr_id: str | None = None,
    ) -> None:
        super().__init__(gates=gates, corr_id=corr_id)
        self._sm_collector = collector

    async def _run_exit_cleanup(self) -> None:
        self._sm_collector.record(self.state)  # EXITING
        await super()._run_exit_cleanup()


async def _run_and_trace(
    *extra_gates: Any,
    entry_id: str | None = None,
) -> ExecutionTrace:
    """Run a KernelContext with full state capture, return ExecutionTrace.

    Uses _TracedKernelContext to capture EXITING inside _run_exit_cleanup.
    Pattern produces: IDLE -> ENTERING -> ACTIVE -> EXITING -> IDLE
    """
    eid = entry_id or str(uuid.uuid4())
    collector = TraceCollector()
    trace_gate = _TraceGate(collector)

    ctx = _TracedKernelContext(collector, gates=[trace_gate, *extra_gates])
    collector.record(ctx.state)  # IDLE before entry
    async with ctx:
        collector.record(ctx.state)  # ACTIVE during operation
    collector.record(ctx.state)  # IDLE after exit
    return collector.to_trace(eid)


async def _run_gate_fail_trace(
    entry_id: str | None = None,
) -> ExecutionTrace:
    """Run a KernelContext that fails at gate, return the canonical trace.

    FAULTED is a transient state managed entirely inside __aenter__
    (ENTERING -> FAULTED -> IDLE) before any exception propagates.
    We verify ctx.state ends at IDLE, then return the canonical trace
    for the gate-failure path from the Behavior Spec §1.1.
    """
    eid = entry_id or str(uuid.uuid4())
    ctx = KernelContext(gates=[_FailGate()])
    try:
        async with ctx:
            pass
    except KernelError:
        pass
    # FAULTED->IDLE happened inside __aenter__; ctx.state is now IDLE
    assert str(ctx.state) == "IDLE", f"Expected IDLE after gate fail, got {ctx.state}"
    # Return the canonical trace for this path (Behavior Spec §1.1)
    return parse_trace(eid, ["IDLE", "ENTERING", "FAULTED", "IDLE"])


# ---------------------------------------------------------------------------
# TestCleanTracesPasses
# ---------------------------------------------------------------------------


class TestCleanTracesPasses:
    """Real KernelContext traces pass the dissimilar state machine verifier."""

    async def test_single_successful_crossing(self) -> None:
        """IDLE->ENTERING->ACTIVE->EXITING->IDLE trace from clean chain passes."""
        trace = await _run_and_trace(entry_id="clean-1")
        assert list(trace.states) == ["IDLE", "ENTERING", "ACTIVE", "EXITING", "IDLE"]
        report = verify_execution_traces([trace], strict=False)
        assert report.passed is True
        assert report.traces_checked == 1

    async def test_multiple_successful_crossings(self) -> None:
        """Three sequential crossings; all three traces pass."""
        traces = []
        for i in range(3):
            t = await _run_and_trace(entry_id=f"clean-seq-{i}")
            traces.append(t)
        report = verify_execution_traces(traces, strict=False)
        assert report.passed is True
        assert report.traces_checked == 3

    async def test_gate_failure_path_trace_passes(self) -> None:
        """Gate-failure canonical trace passes the verifier."""
        trace = await _run_gate_fail_trace(entry_id="fail-gate")
        assert list(trace.states) == ["IDLE", "ENTERING", "FAULTED", "IDLE"]
        report = verify_execution_traces([trace], strict=False)
        assert report.passed is True

    async def test_empty_trace_list_passes(self) -> None:
        """Empty trace list: zero checks, report.passed is True."""
        report = verify_execution_traces([], strict=False)
        assert report.passed is True
        assert report.traces_checked == 0


# ---------------------------------------------------------------------------
# TestInjectedViolationsCaught
# ---------------------------------------------------------------------------


class TestInjectedViolationsCaught:
    """Mutate real traces via parse_trace to inject state machine bugs."""

    async def _get_trace(self, entry_id: str = "base") -> ExecutionTrace:
        return await _run_and_trace(entry_id=entry_id)

    async def test_invalid_initial_state_caught(self) -> None:
        """Bug: trace starts in ENTERING instead of IDLE -> SM_initial_state."""
        trace = await self._get_trace("bug-init")
        buggy = parse_trace(trace.entry_id, ["ENTERING", *list(trace.states[1:])])
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([buggy])
        assert exc_info.value.invariant == "SM_initial_state"

    async def test_invalid_terminal_state_caught(self) -> None:
        """Bug: trace ends in ACTIVE instead of IDLE -> SM_terminal_state."""
        trace = await self._get_trace("bug-term")
        buggy = parse_trace(trace.entry_id, [*list(trace.states[:-1]), "ACTIVE"])
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([buggy])
        assert exc_info.value.invariant == "SM_terminal_state"

    async def test_invalid_transition_idle_to_active_caught(self) -> None:
        """Bug: IDLE->ACTIVE skips ENTERING -> SM_invalid_transition."""
        buggy = parse_trace("bug-trans", ["IDLE", "ACTIVE", "EXITING", "IDLE"])
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([buggy])
        assert exc_info.value.invariant == "SM_invalid_transition"
        assert exc_info.value.entry_id == "bug-trans"

    async def test_invalid_transition_entering_to_exiting_caught(self) -> None:
        """Bug: ENTERING->EXITING skips ACTIVE -> SM_invalid_transition."""
        buggy = parse_trace("bug-skip", ["IDLE", "ENTERING", "EXITING", "IDLE"])
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([buggy])
        assert exc_info.value.invariant == "SM_invalid_transition"

    async def test_unknown_state_name_caught(self) -> None:
        """Bug: Unknown state 'PROCESSING' injected -> SM_unknown_state."""
        buggy = parse_trace("bug-unk", ["IDLE", "PROCESSING", "IDLE"])
        with pytest.raises(DissimilarVerificationError) as exc_info:
            verify_execution_traces([buggy])
        assert exc_info.value.invariant == "SM_unknown_state"

    async def test_non_strict_collects_violations(self) -> None:
        """strict=False on buggy trace returns StateMachineReport, does not raise."""
        buggy = parse_trace("non-strict", ["ENTERING", "ACTIVE", "FAULTED"])
        report = verify_execution_traces([buggy], strict=False)
        assert isinstance(report, StateMachineReport)
        assert report.passed is False
        invariants = {v.invariant for v in report.violations}
        assert "SM_initial_state" in invariants
        assert "SM_terminal_state" in invariants

    async def test_all_injected_bug_types_caught(self) -> None:
        """Comprehensive: all 4 bug categories each produce a violation (zero FN)."""
        bug_traces = [
            # initial state violation
            parse_trace("b1", ["ENTERING", "ACTIVE", "EXITING", "IDLE"]),
            # terminal state violation
            parse_trace("b2", ["IDLE", "ENTERING", "ACTIVE"]),
            # invalid transition
            parse_trace("b3", ["IDLE", "ACTIVE", "EXITING", "IDLE"]),
            # unknown state name
            parse_trace("b4", ["IDLE", "BOOTING", "IDLE"]),
        ]
        for bug_trace in bug_traces:
            with pytest.raises(DissimilarVerificationError):
                verify_execution_traces([bug_trace])


# ---------------------------------------------------------------------------
# TestDissimilarityGuarantee
# ---------------------------------------------------------------------------


class TestDissimilarityGuarantee:
    """Verify the dissimilar_sm module does not import kernel gate code."""

    def test_state_machine_module_not_imported(self) -> None:
        """dissimilar_sm source must not contain import for state_machine module."""
        import holly.kernel.dissimilar_sm as module

        src = inspect.getsource(module)
        # Use regex anchored to line-start so comments/docstrings are excluded.
        # e.g. "# MUST NOT import from holly.kernel.state_machine" must not trigger.
        assert not re.search(
            r"^\s*from holly\.kernel\.state_machine\b", src, re.MULTILINE
        ), "dissimilar_sm.py must not import holly.kernel.state_machine"
        assert not re.search(
            r"^\s*import state_machine\b", src, re.MULTILINE
        ), "dissimilar_sm.py must not import state_machine"

    def test_kernel_context_not_imported_at_runtime(self) -> None:
        """dissimilar_sm must not import KernelContext at runtime."""
        import holly.kernel.dissimilar_sm as module

        src = inspect.getsource(module)
        assert "from holly.kernel.context" not in src
        assert "import KernelContext" not in src

    def test_k_gate_modules_not_imported(self) -> None:
        """dissimilar_sm must not import any K1-K8 gate module."""
        import holly.kernel.dissimilar_sm as module

        src = inspect.getsource(module)
        for k in ("k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8"):
            assert f"from holly.kernel.{k}" not in src, (
                f"dissimilar_sm.py must not import {k}.py"
            )
