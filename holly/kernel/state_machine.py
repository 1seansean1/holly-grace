"""Formal state-machine validator for the KernelContext lifecycle.

Task 14.5 — Implement formal state-machine validator.

Traces to:
    TLA+ spec  docs/tla/KernelInvariants.tla  (Task 14.1)
    Behavior Spec §1.1  KernelContext state machine (states and transitions)
    FMEA-K001  docs/FMEA_Kernel_Invariants.md

SIL: 3  (docs/SIL_Classification_Matrix.md)

This module exposes:

- ``KernelState``   — enum of the five legal KernelContext states.
- ``KernelEvent``   — enum of events that drive state transitions.
- ``VALID_TRANSITIONS`` — frozenset of (from, to) pairs; mirrors TLA+ spec.
- ``validate_transition`` — pure, side-effect-free guard evaluator.
- ``apply_event``   — pure function: state x event → next state.
- ``validate_trace`` — verifies a sequence of KernelState values.
- ``reachable_from`` — returns the set of immediate successors of a state.
- ``KernelStateMachineValidator`` — stateful wrapper for runtime use.

Design constraints (Behavior Spec §1.1 INV-4):
    All transition guards are *pure functions* — deterministic, no side
    effects on evaluation.  Same inputs always produce the same output.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from holly.kernel.exceptions import KernelInvariantError

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# State and event enumerations
# ---------------------------------------------------------------------------


class KernelState(StrEnum):
    """The five legal states of a KernelContext (Behavior Spec §1.1 Table 1).

    Corresponds to the ``KernelStates`` set in KernelInvariants.tla.
    """

    IDLE = "IDLE"
    ENTERING = "ENTERING"
    ACTIVE = "ACTIVE"
    EXITING = "EXITING"
    FAULTED = "FAULTED"


class KernelEvent(StrEnum):
    """Events that drive KernelContext state transitions (Behavior Spec §1.1).

    Each value corresponds to one named action in KernelInvariants.tla.
    """

    AENTER = "AENTER"
    """``__aenter__()`` called by the context-manager protocol.
    Maps to TLA+ action ``Aenter``.
    Applicable from: IDLE.  Result: ENTERING.
    """

    ALL_GATES_PASS = "ALL_GATES_PASS"
    """All K1-K8 gates evaluated and passed.
    Maps to TLA+ action ``AllGatesPass``.
    Applicable from: ENTERING.  Result: ACTIVE.
    """

    GATE_FAIL = "GATE_FAIL"
    """Any K1-K8 gate raised an exception.
    Maps to TLA+ action ``GateFails``.
    Applicable from: ENTERING.  Result: FAULTED.
    """

    OP_COMPLETE = "OP_COMPLETE"
    """Boundary operation completed normally.
    Maps to TLA+ action ``OperationComplete``.
    Applicable from: ACTIVE.  Result: EXITING.
    """

    ASYNC_CANCEL = "ASYNC_CANCEL"
    """asyncio.CancelledError raised while ACTIVE, or K8 eval gate failure.
    Maps to TLA+ action ``AsyncCancelOrK8Fail``.
    Applicable from: ACTIVE.  Result: FAULTED.
    """

    EXIT_OK = "EXIT_OK"
    """``__aexit__()`` completed and WAL entry written successfully.
    Maps to TLA+ action ``ExitSuccess``.
    Applicable from: EXITING.  Result: IDLE.
    """

    EXIT_FAIL = "EXIT_FAIL"
    """Exit gate failure (WAL write error or trace injection failure).
    Maps to TLA+ action ``ExitFails``.
    Applicable from: EXITING.  Result: FAULTED.
    """

    EXC_CONSUMED = "EXC_CONSUMED"
    """Exception consumed by the caller's exception handler.
    Maps to TLA+ action ``ExceptionConsumed``.
    Applicable from: FAULTED.  Result: IDLE.
    """


# ---------------------------------------------------------------------------
# Transition tables (derived from KernelInvariants.tla, Task 14.1)
# ---------------------------------------------------------------------------

#: All valid (from_state, to_state) pairs.
#: Immutable frozenset; matches the eight actions in KernelInvariants.tla.
#: This is the single source of truth; every other table is derived from it.
VALID_TRANSITIONS: frozenset[tuple[KernelState, KernelState]] = frozenset(
    {
        (KernelState.IDLE, KernelState.ENTERING),  # Aenter
        (KernelState.ENTERING, KernelState.ACTIVE),  # AllGatesPass
        (KernelState.ENTERING, KernelState.FAULTED),  # GateFails
        (KernelState.ACTIVE, KernelState.EXITING),  # OperationComplete
        (KernelState.ACTIVE, KernelState.FAULTED),  # AsyncCancelOrK8Fail
        (KernelState.EXITING, KernelState.IDLE),  # ExitSuccess
        (KernelState.EXITING, KernelState.FAULTED),  # ExitFails
        (KernelState.FAULTED, KernelState.IDLE),  # ExceptionConsumed
    }
)

#: Each event maps to exactly one (required_from, next_state) pair.
#: Applying an event from any other state is invalid.
_EVENT_TRANSITION: dict[KernelEvent, tuple[KernelState, KernelState]] = {
    KernelEvent.AENTER: (KernelState.IDLE, KernelState.ENTERING),
    KernelEvent.ALL_GATES_PASS: (KernelState.ENTERING, KernelState.ACTIVE),
    KernelEvent.GATE_FAIL: (KernelState.ENTERING, KernelState.FAULTED),
    KernelEvent.OP_COMPLETE: (KernelState.ACTIVE, KernelState.EXITING),
    KernelEvent.ASYNC_CANCEL: (KernelState.ACTIVE, KernelState.FAULTED),
    KernelEvent.EXIT_OK: (KernelState.EXITING, KernelState.IDLE),
    KernelEvent.EXIT_FAIL: (KernelState.EXITING, KernelState.FAULTED),
    KernelEvent.EXC_CONSUMED: (KernelState.FAULTED, KernelState.IDLE),
}


# ---------------------------------------------------------------------------
# Pure guard functions (Behavior Spec §1.1 INV-4)
# ---------------------------------------------------------------------------


def validate_transition(
    from_state: KernelState,
    to_state: KernelState,
) -> bool:
    """Return ``True`` iff ``from_state → to_state`` is a valid transition.

    This is a *pure guard*: it is deterministic and has no side effects
    (Behavior Spec §1.1 INV-4).  The same inputs always produce the same
    output.  Callers may safely call it multiple times without concern for
    ordering or sequencing.

    Parameters
    ----------
    from_state:
        The current KernelContext state.
    to_state:
        The proposed next state.

    Returns
    -------
    bool
        ``True`` if the transition is in ``VALID_TRANSITIONS``.

    Raises
    ------
    KernelInvariantError
        If the transition is not in ``VALID_TRANSITIONS``.  The error
        message names the invalid pair and lists the valid successors
        (Behavior Spec §1.1 "State Violation" failure predicate).
    """
    if (from_state, to_state) in VALID_TRANSITIONS:
        return True
    valid_successors = sorted(
        t.value for f, t in VALID_TRANSITIONS if f == from_state
    )
    raise KernelInvariantError(
        invariant="state_transition",
        detail=(
            f"Invalid KernelContext transition "
            f"{from_state.value!r} \u2192 {to_state.value!r}.  "
            f"Valid successors of {from_state.value!r}: {valid_successors}"
        ),
    )


def apply_event(state: KernelState, event: KernelEvent) -> KernelState:
    """Apply *event* to *state* and return the resulting next state.

    Pure function — deterministic, no side effects.  Raises
    ``KernelInvariantError`` if *event* is not applicable from *state*.

    Parameters
    ----------
    state:
        The current KernelContext state.
    event:
        The event to apply.

    Returns
    -------
    KernelState
        The next state.

    Raises
    ------
    KernelInvariantError
        If *event* is not applicable from *state*.
    """
    required_from, next_state = _EVENT_TRANSITION[event]
    if state != required_from:
        raise KernelInvariantError(
            invariant="state_transition",
            detail=(
                f"Event {event.value!r} requires state "
                f"{required_from.value!r}, but current state is "
                f"{state.value!r}"
            ),
        )
    return next_state


def validate_trace(trace: Sequence[KernelState]) -> None:
    """Validate a complete execution trace against the KernelContext state machine.

    Iterates over consecutive (state[i], state[i+1]) pairs and calls
    ``validate_transition`` on each.  Raises on the first invalid pair.

    A trace of length 0 or 1 is trivially valid.

    Parameters
    ----------
    trace:
        A sequence of KernelState values representing an execution path.

    Raises
    ------
    KernelInvariantError
        If any consecutive pair is an invalid transition.
    """
    for i in range(len(trace) - 1):
        validate_transition(trace[i], trace[i + 1])


def reachable_from(state: KernelState) -> frozenset[KernelState]:
    """Return the set of states directly reachable from *state* in one step.

    Pure function — reads only ``VALID_TRANSITIONS`` (no side effects).

    Parameters
    ----------
    state:
        Source state.

    Returns
    -------
    frozenset[KernelState]
        Immediately reachable successor states.
    """
    return frozenset(t for f, t in VALID_TRANSITIONS if f == state)


# ---------------------------------------------------------------------------
# Stateful wrapper for runtime use
# ---------------------------------------------------------------------------


class KernelStateMachineValidator:
    """Stateful wrapper that tracks KernelContext state and validates transitions.

    Intended for runtime use (e.g. inside ``KernelContext.__aenter__`` /
    ``__aexit__``).  The underlying guard functions are pure; this class
    only adds state storage.

    Invariants
    ----------
    * ``self.state`` is always a member of ``KernelState``.
    * ``self.state`` evolves only via ``advance()``.  The ``state``
      property has no setter; direct assignment raises ``AttributeError``.

    Usage::

        validator = KernelStateMachineValidator()
        validator.advance(KernelEvent.AENTER)          # IDLE → ENTERING
        validator.advance(KernelEvent.ALL_GATES_PASS)  # ENTERING → ACTIVE
        validator.advance(KernelEvent.OP_COMPLETE)     # ACTIVE → EXITING
        validator.advance(KernelEvent.EXIT_OK)         # EXITING → IDLE
        assert validator.state == KernelState.IDLE
    """

    __slots__ = ("_state",)

    def __init__(self) -> None:
        self._state: KernelState = KernelState.IDLE

    @property
    def state(self) -> KernelState:
        """Current KernelContext state (read-only)."""
        return self._state

    def advance(self, event: KernelEvent) -> KernelState:
        """Apply *event* to the current state and advance.

        If the event is not applicable from the current state,
        ``KernelInvariantError`` is raised and the state is **not** changed.

        Parameters
        ----------
        event:
            The event to apply.

        Returns
        -------
        KernelState
            The new state after the transition.

        Raises
        ------
        KernelInvariantError
            If *event* is not applicable from the current state.
        """
        # Compute next state first (may raise); only assign on success
        # so that an invalid event leaves self._state unchanged.
        next_state = apply_event(self._state, event)
        self._state = next_state
        return self._state

    def check_transition(self, to_state: KernelState) -> bool:
        """Validate a prospective transition from the current state to *to_state*.

        Delegates to ``validate_transition`` (pure guard — no side effects
        on the validator's own state, and no state advancement).

        Parameters
        ----------
        to_state:
            The proposed next state.

        Returns
        -------
        bool
            ``True`` if the transition is valid.

        Raises
        ------
        KernelInvariantError
            If the transition is invalid.
        """
        return validate_transition(self._state, to_state)

    def reset(self) -> None:
        """Reset state to IDLE.

        Provided for test harnesses.  Production code should create a new
        ``KernelStateMachineValidator`` instance per boundary crossing.
        """
        self._state = KernelState.IDLE

    def __repr__(self) -> str:
        return f"KernelStateMachineValidator(state={self._state.value!r})"
