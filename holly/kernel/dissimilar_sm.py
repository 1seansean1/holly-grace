"""Dissimilar State Machine Verifier - Task 20.5.

Independent post-hoc cross-check of the KernelContext lifecycle state machine
from execution trace records, without importing or executing any kernel gate
code or referencing ``state_machine.py``.

Architecture
------------
Three layers, mirroring the dissimilar invariant channel (Task 20.3):

1.  **Trace collection** - ``TraceCollector`` accumulates ``str(ctx.state)``
    values at observable checkpoints during an integration-test execution.
    Produces ``ExecutionTrace`` objects.

2.  **Per-trace checkers** - pure functions that detect specific invariant
    violations within one trace:

    * ``check_valid_state_names``  - no unknown state names.
    * ``check_initial_state``      - trace must start in IDLE.
    * ``check_terminal_state``     - trace must end in IDLE (TLA+ liveness).
    * ``check_each_transition``    - every consecutive pair is a valid edge.

3.  **Report** - ``StateMachineReport`` collects ``StateViolation`` objects.
    ``verify_execution_traces(..., strict=True)`` (default) raises
    ``DissimilarVerificationError`` on the first violation found.

Dissimilarity guarantee
-----------------------
This module does NOT import or invoke ``holly.kernel.state_machine``,
``holly.kernel.context``, or any K1-K8 gate module at runtime.
The valid-transition table ``_VALID_TRANSITIONS`` is an independent
re-derivation from Behavior Spec §1.1 Table 1 and TLA+ spec
``docs/tla/KernelInvariants.tla`` (Task 14.1).

SIL: 3  (docs/SIL_Classification_Matrix.md)

Traces to:
    Task_Manifest.md §20.5
    Behavior Spec §1.1 (KernelContext state machine: states and transitions)
    TLA+ spec  docs/tla/KernelInvariants.tla  (Task 14.1)
    FMEA-K001  docs/FMEA_Kernel_Invariants.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from holly.kernel.exceptions import DissimilarVerificationError

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Independent transition table
# ---------------------------------------------------------------------------
# Re-derived from Behavior Spec §1.1 Table 1 and KernelInvariants.tla.
# MUST NOT import from holly.kernel.state_machine.
# Each pair (from_state, to_state) corresponds to one named TLA+ action.

_VALID_STATES: frozenset[str] = frozenset(
    {"IDLE", "ENTERING", "ACTIVE", "EXITING", "FAULTED"}
)

_VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("IDLE", "ENTERING"),    # Aenter
        ("ENTERING", "ACTIVE"),  # AllGatesPass
        ("ENTERING", "FAULTED"), # GateFails
        ("ACTIVE", "EXITING"),   # OperationComplete
        ("ACTIVE", "FAULTED"),   # AsyncCancelOrK8Fail
        ("EXITING", "IDLE"),     # ExitSuccess
        ("EXITING", "FAULTED"),  # ExitFails
        ("FAULTED", "IDLE"),     # ExceptionConsumed
    }
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ExecutionTrace:
    """A recorded sequence of KernelContext state names from one boundary crossing.

    Produced by ``TraceCollector`` during integration test executions.
    Can also be constructed directly from serialised/logged trace data via
    ``parse_trace()``.

    Attributes
    ----------
    entry_id : str
        Unique identifier for this trace record (e.g. correlation ID).
    states : tuple[str, ...]
        Ordered sequence of state-name strings observed during the crossing.
    """

    entry_id: str
    states: tuple[str, ...]


@dataclass(slots=True)
class StateViolation:
    """A single state-machine invariant violation found in an ExecutionTrace.

    Attributes
    ----------
    detail : str
        Human-readable description of the violation.
    entry_id : str
        ``ExecutionTrace.entry_id`` of the offending record.
    invariant : str
        Short identifier for the violated invariant (e.g. ``"SM_invalid_transition"``).
    step : int
        Zero-based index in ``ExecutionTrace.states`` where the violation was detected.
    """

    detail: str
    entry_id: str
    invariant: str
    step: int


@dataclass(slots=True)
class StateMachineReport:
    """Report produced by ``verify_execution_traces``.

    Attributes
    ----------
    passed : bool
        ``True`` iff no violations were found.
    traces_checked : int
        Number of ``ExecutionTrace`` objects examined.
    violations : list[StateViolation]
        All violations found (non-empty only when ``strict=False``).
    """

    passed: bool
    traces_checked: int
    violations: list[StateViolation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TraceCollector
# ---------------------------------------------------------------------------


class TraceCollector:
    """Lightweight accumulator for state names during a KernelContext execution.

    Integration-test helper.  Records ``str(ctx.state)`` values at observable
    checkpoints and produces an ``ExecutionTrace`` for the dissimilar verifier.

    Usage::

        collector = TraceCollector()
        ctx = KernelContext(gates=[_TraceGate(collector)])
        collector.record(ctx.state)           # IDLE before entry
        try:
            async with ctx:
                collector.record(ctx.state)   # ACTIVE after gates
        except Exception:
            pass
        collector.record(ctx.state)           # IDLE after exit
        trace = collector.to_trace("crossing-001")
        report = verify_execution_traces([trace])

    This is NOT kernel code — ``TraceCollector`` merely calls ``str()`` on
    the states it receives and has no dependency on ``KernelState``.
    """

    __slots__ = ("_states",)

    def __init__(self) -> None:
        self._states: list[str] = []

    def record(self, state: Any) -> None:
        """Record a state value by calling ``str()`` on it.

        Accepts both plain strings and ``StrEnum`` members.
        """
        self._states.append(str(state))

    def to_trace(self, entry_id: str) -> ExecutionTrace:
        """Return an ``ExecutionTrace`` from the accumulated state records."""
        return ExecutionTrace(entry_id=entry_id, states=tuple(self._states))

    def reset(self) -> None:
        """Clear accumulated states for reuse."""
        self._states.clear()


# ---------------------------------------------------------------------------
# parse_trace helper
# ---------------------------------------------------------------------------


def parse_trace(entry_id: str, states: list[str]) -> ExecutionTrace:
    """Parse a list of state-name strings into an ``ExecutionTrace``.

    Allows construction from serialised/logged trace data without a live
    ``TraceCollector``.

    Parameters
    ----------
    entry_id:
        Unique identifier for the trace record.
    states:
        Ordered list of state-name strings.

    Returns
    -------
    ExecutionTrace
    """
    return ExecutionTrace(entry_id=entry_id, states=tuple(states))


# ---------------------------------------------------------------------------
# Per-trace invariant checkers (pure functions)
# ---------------------------------------------------------------------------


def check_valid_state_names(trace: ExecutionTrace) -> list[StateViolation]:
    """Return violations for any state name not in the five legal states."""
    violations: list[StateViolation] = []
    for i, s in enumerate(trace.states):
        if s not in _VALID_STATES:
            violations.append(
                StateViolation(
                    entry_id=trace.entry_id,
                    invariant="SM_unknown_state",
                    step=i,
                    detail=(
                        f"Unknown state {s!r} at step {i}; "
                        f"legal states: {sorted(_VALID_STATES)}"
                    ),
                )
            )
    return violations


def check_initial_state(trace: ExecutionTrace) -> StateViolation | None:
    """Return a violation if the first state in a non-empty trace is not IDLE.

    All KernelContext executions begin in IDLE (Behavior Spec §1.1 INV-6;
    TLA+ ``Init: kstate = IDLE``).
    """
    if trace.states and trace.states[0] != "IDLE":
        return StateViolation(
            entry_id=trace.entry_id,
            invariant="SM_initial_state",
            step=0,
            detail=(
                f"Trace must begin in IDLE; got {trace.states[0]!r}"
            ),
        )
    return None


def check_terminal_state(trace: ExecutionTrace) -> StateViolation | None:
    """Return a violation if the last state in a non-empty trace is not IDLE.

    All KernelContext executions end in IDLE (TLA+ ``EventuallyIdle:
    []<>(kstate = IDLE)``).
    """
    if trace.states and trace.states[-1] != "IDLE":
        return StateViolation(
            entry_id=trace.entry_id,
            invariant="SM_terminal_state",
            step=len(trace.states) - 1,
            detail=(
                f"Trace must end in IDLE; got {trace.states[-1]!r}"
            ),
        )
    return None


def check_each_transition(trace: ExecutionTrace) -> list[StateViolation]:
    """Return violations for every consecutive pair not in ``_VALID_TRANSITIONS``."""
    violations: list[StateViolation] = []
    for i in range(len(trace.states) - 1):
        from_s = trace.states[i]
        to_s = trace.states[i + 1]
        if (from_s, to_s) not in _VALID_TRANSITIONS:
            valid_successors = sorted(t for f, t in _VALID_TRANSITIONS if f == from_s)
            violations.append(
                StateViolation(
                    entry_id=trace.entry_id,
                    invariant="SM_invalid_transition",
                    step=i,
                    detail=(
                        f"Invalid transition {from_s!r} -> {to_s!r} at step {i}; "
                        f"valid successors of {from_s!r}: {valid_successors}"
                    ),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# Ordered check sequences
# ---------------------------------------------------------------------------

# Checkers that return a single Optional[StateViolation]:
_SINGLE_CHECKS = (check_initial_state, check_terminal_state)

# Checkers that return a list[StateViolation]:
_MULTI_CHECKS = (check_valid_state_names, check_each_transition)


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------


def verify_execution_traces(
    traces: Sequence[ExecutionTrace],
    *,
    strict: bool = True,
) -> StateMachineReport:
    """Verify a sequence of ``ExecutionTrace`` records against the state machine.

    Parameters
    ----------
    traces:
        Sequence of ``ExecutionTrace`` objects (one per KernelContext execution).
    strict:
        If ``True`` (default), raise ``DissimilarVerificationError`` on the
        first violation.  If ``False``, collect all violations and return
        them in the ``StateMachineReport``.

    Returns
    -------
    StateMachineReport
        ``passed=True`` iff no violations were found.

    Raises
    ------
    DissimilarVerificationError
        If ``strict=True`` and any violation is detected.
    """
    all_violations: list[StateViolation] = []

    for trace in traces:
        # Single-return checkers
        for checker in _SINGLE_CHECKS:
            v = checker(trace)
            if v is not None:
                if strict:
                    raise DissimilarVerificationError(
                        invariant=v.invariant,
                        entry_id=v.entry_id,
                        detail=v.detail,
                    )
                all_violations.append(v)

        # Multi-return checkers
        for checker in _MULTI_CHECKS:
            for v in checker(trace):
                if strict:
                    raise DissimilarVerificationError(
                        invariant=v.invariant,
                        entry_id=v.entry_id,
                        detail=v.detail,
                    )
                all_violations.append(v)

    return StateMachineReport(
        passed=len(all_violations) == 0,
        traces_checked=len(traces),
        violations=all_violations,
    )
