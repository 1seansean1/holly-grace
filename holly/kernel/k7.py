"""K7 — HITL (Human-in-the-Loop) Gate (Task 18.3).

Blocks execution when an operation's confidence score falls below a
configurable per-boundary threshold, and routes it through a human review
channel.  High-confidence operations pass transparently.

Behavior Spec §1.8:

State machine (simplified):
    EVALUATING → CONFIDENT (score ≥ threshold) → PASS
    EVALUATING → UNCERTAIN (score < threshold) → BLOCKED → HUMAN_APPROVED → PASS
                                                           → HUMAN_REJECTED → FAULTED
                                                           → APPROVAL_TIMEOUT → FAULTED

Fail-safe invariants:
    * Confidence evaluator exception  → ConfidenceError     → FAULTED (deny)
    * Approval channel exception      → ApprovalChannelError → FAULTED (deny)
    * No human decision within TTL    → ApprovalTimeout     → FAULTED (deny)
    * Human rejection                 → OperationRejected   → FAULTED (deny)
    * Confidence score outside [0,1]  → ValueError           → FAULTED (deny)

TLA+ reference: Task 14.1 KernelContext state-machine (liveness: all paths
reach IDLE via success or FAULTED→EXC_CONSUMED).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

try:
    from datetime import UTC
except ImportError:  # Python < 3.11 — datetime.UTC added in 3.11
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

from holly.kernel.exceptions import (
    ApprovalChannelError,
    ApprovalTimeout,
    ConfidenceError,
    OperationRejected,
)

if TYPE_CHECKING:
    from holly.kernel.context import KernelContext

Gate = Callable[["KernelContext"], Awaitable[None]]

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_SECONDS: float = 86_400.0  # 24 hours (Behavior Spec §1.8)


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """Immutable record emitted to the approval channel when confidence is low.

    Attributes
    ----------
    request_id : str
        UUID4 string uniquely identifying this approval request.
    operation_type : str
        Logical operation type (e.g. ``"workflow:execute"``).  Used for
        threshold lookup and audit trail.
    confidence_score : float
        Score in [0.0, 1.0] that fell below the threshold.
    threshold : float
        The configured threshold for this operation type.
    payload : Any
        The full operation payload.  Callers are responsible for PII
        scrubbing before emitting to the channel.
    corr_id : str
        KernelContext correlation ID for trace linkage.
    created_at : datetime
        UTC timestamp at request creation time.
    timeout_seconds : float
        Channel wait timeout in seconds (default 86400 = 24 h).
    """

    request_id: str
    operation_type: str
    confidence_score: float
    threshold: float
    payload: Any
    corr_id: str
    created_at: datetime
    timeout_seconds: float = field(default=_DEFAULT_TIMEOUT_SECONDS)


@dataclass(frozen=True, slots=True)
class HumanDecision:
    """Immutable record returned by the approval channel after human review.

    Attributes
    ----------
    request_id : str
        Must match the corresponding ``ApprovalRequest.request_id``.
    action : str
        ``"approve"`` or ``"reject"`` — the reviewer's decision.
    reviewer_id : str
        Identity of the reviewer (user ID, email, etc.).
    reason : str
        Optional free-text reason, mandatory on rejection by convention.
    decided_at : datetime
        UTC timestamp of the human decision.
    """

    request_id: str
    action: str  # "approve" | "reject"
    reviewer_id: str
    reason: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfidenceEvaluator(Protocol):
    """Synchronous confidence evaluator protocol.

    Implementations may use rule-based heuristics, LLM classifiers, or
    ensemble methods.  The function must be *deterministic within a session*
    (Behavior Spec §1.8 Invariant 3).

    Methods
    -------
    evaluate(operation_type, payload)
        Return a score in [0.0, 1.0].  Raise if evaluation fails.
    """

    def evaluate(self, operation_type: str, payload: Any) -> float:
        """Return confidence score in [0.0, 1.0].

        Args:
            operation_type: Logical operation type string.
            payload: The full operation payload.

        Returns:
            Float in [0.0, 1.0].

        Raises:
            Any exception: wrapped by k7 into ``ConfidenceError``.
        """
        ...


@runtime_checkable
class ThresholdConfig(Protocol):
    """Per-operation-type confidence threshold lookup protocol.

    Methods
    -------
    get_threshold(operation_type)
        Return the threshold in [0.0, 1.0] for the given operation type.
    """

    def get_threshold(self, operation_type: str) -> float:
        """Return confidence threshold for *operation_type*.

        Args:
            operation_type: Logical operation type string.

        Returns:
            Float in [0.0, 1.0].

        Raises:
            Any exception: caller may treat missing config as error.
        """
        ...


@runtime_checkable
class ApprovalChannel(Protocol):
    """Async approval channel protocol.

    Implementations must be non-blocking on ``emit`` and blocking on
    ``wait_for_decision`` (up to *timeout*).

    Methods
    -------
    emit(request)
        Dispatch the approval request (non-blocking).
    wait_for_decision(request_id, *, timeout)
        Block until a human decision arrives or timeout elapses.
    """

    def emit(self, request: ApprovalRequest) -> None:
        """Dispatch *request* to the human review channel.

        Args:
            request: The approval request to emit.

        Raises:
            ApprovalChannelError: If the channel is unreachable.
        """
        ...

    def wait_for_decision(
        self,
        request_id: str,
        *,
        timeout: float,
    ) -> HumanDecision:
        """Block until a human decision for *request_id* arrives.

        Args:
            request_id: UUID of the ``ApprovalRequest`` to wait on.
            timeout: Maximum seconds to wait.

        Returns:
            ``HumanDecision`` with ``action in {"approve", "reject"}``.

        Raises:
            ApprovalTimeout: No decision arrived within *timeout* seconds.
            ApprovalChannelError: Channel became unavailable while waiting.
        """
        ...


# ---------------------------------------------------------------------------
# In-process approval channel implementations (testing / single-process)
# ---------------------------------------------------------------------------


class InMemoryApprovalChannel:
    """Synchronous in-memory approval channel for testing.

    Callers inject decisions via :meth:`inject_decision` before the gate
    runs, or call :meth:`inject_timeout` to simulate a timeout.

    Attributes
    ----------
    emitted : list[ApprovalRequest]
        All requests emitted since instantiation (for test assertions).
    _decisions : dict[str, HumanDecision]
        Pre-injected decisions keyed by ``request_id``.
    _fail_emit : bool
        If ``True``, ``emit`` raises ``ApprovalChannelError``.
    _timeout_all : bool
        If ``True``, ``wait_for_decision`` always raises ``ApprovalTimeout``.
    """

    __slots__ = ("_decisions", "_fail_emit", "_timeout_all", "emitted")

    def __init__(self) -> None:
        self.emitted: list[ApprovalRequest] = []
        self._decisions: dict[str, HumanDecision] = {}
        self._fail_emit: bool = False
        self._timeout_all: bool = False

    # -- test helpers --------------------------------------------------------

    def inject_decision(
        self,
        request_id: str,
        *,
        action: str,
        reviewer_id: str,
        reason: str = "",
    ) -> None:
        """Pre-inject a human decision that ``wait_for_decision`` will return."""
        self._decisions[request_id] = HumanDecision(
            request_id=request_id,
            action=action,
            reviewer_id=reviewer_id,
            reason=reason,
        )

    def inject_approve(self, request_id: str, reviewer_id: str = "test-reviewer") -> None:
        """Convenience: inject an approval decision."""
        self.inject_decision(request_id, action="approve", reviewer_id=reviewer_id)

    def inject_reject(
        self,
        request_id: str,
        reviewer_id: str = "test-reviewer",
        reason: str = "rejected in test",
    ) -> None:
        """Convenience: inject a rejection decision."""
        self.inject_decision(
            request_id, action="reject", reviewer_id=reviewer_id, reason=reason
        )

    def set_fail_emit(self, *, fail: bool = True) -> None:
        """Configure ``emit`` to raise ``ApprovalChannelError``."""
        self._fail_emit = fail

    def set_timeout_all(self, *, timeout: bool = True) -> None:
        """Configure ``wait_for_decision`` to always time out."""
        self._timeout_all = timeout

    # -- protocol implementation ---------------------------------------------

    def emit(self, request: ApprovalRequest) -> None:
        """Record the request; raise if in fail mode."""
        if self._fail_emit:
            raise ApprovalChannelError("InMemoryApprovalChannel: emit fail-mode active")
        self.emitted.append(request)

    def wait_for_decision(
        self,
        request_id: str,
        *,
        timeout: float,
    ) -> HumanDecision:
        """Return a pre-injected decision or raise timeout/channel error."""
        if self._timeout_all:
            raise ApprovalTimeout(request_id, timeout_seconds=timeout)
        decision = self._decisions.get(request_id)
        if decision is None:
            # No decision pre-injected → simulate timeout
            raise ApprovalTimeout(request_id, timeout_seconds=timeout)
        return decision


# ---------------------------------------------------------------------------
# In-process confidence evaluator implementations
# ---------------------------------------------------------------------------


class FixedConfidenceEvaluator:
    """Returns a fixed score for all operations. For testing.

    Attributes
    ----------
    score : float
        Fixed confidence score returned for every evaluation call.
    """

    __slots__ = ("score",)

    def __init__(self, score: float) -> None:
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"score must be in [0.0, 1.0], got {score}")
        self.score = score

    def evaluate(self, operation_type: str, payload: Any) -> float:
        """Return the fixed score regardless of inputs."""
        return self.score


class FailConfidenceEvaluator:
    """Always raises RuntimeError to simulate evaluator failure."""

    __slots__ = ("detail",)

    def __init__(self, detail: str = "evaluator failure") -> None:
        self.detail = detail

    def evaluate(self, operation_type: str, payload: Any) -> float:
        """Always raises to simulate evaluator failure."""
        raise RuntimeError(self.detail)


# ---------------------------------------------------------------------------
# In-process threshold config implementations
# ---------------------------------------------------------------------------


class FixedThresholdConfig:
    """Returns the same threshold for every operation type.

    Attributes
    ----------
    threshold : float
        Threshold returned for every ``get_threshold`` call.
    """

    __slots__ = ("threshold",)

    def __init__(self, threshold: float) -> None:
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")
        self.threshold = threshold

    def get_threshold(self, operation_type: str) -> float:
        """Return the fixed threshold regardless of operation type."""
        return self.threshold


class MappedThresholdConfig:
    """Returns per-operation-type thresholds from an explicit mapping.

    Falls back to *default_threshold* for unregistered operation types.

    Attributes
    ----------
    _map : dict[str, float]
        Mapping from operation_type to threshold value.
    _default : float
        Fallback threshold for unknown operation types.
    """

    __slots__ = ("_default", "_map")

    def __init__(
        self,
        thresholds: dict[str, float],
        *,
        default_threshold: float = 0.80,
    ) -> None:
        for k, v in thresholds.items():
            if not (0.0 <= v <= 1.0):
                raise ValueError(
                    f"threshold for {k!r} must be in [0.0, 1.0], got {v}"
                )
        if not (0.0 <= default_threshold <= 1.0):
            raise ValueError(
                f"default_threshold must be in [0.0, 1.0], got {default_threshold}"
            )
        self._map = dict(thresholds)
        self._default = default_threshold

    def get_threshold(self, operation_type: str) -> float:
        """Return threshold for *operation_type*, or *default_threshold*."""
        return self._map.get(operation_type, self._default)


# ---------------------------------------------------------------------------
# k7_check_confidence — pure guard
# ---------------------------------------------------------------------------


def k7_check_confidence(
    score: float,
    *,
    threshold: float,
) -> bool:
    """Return ``True`` if *score* meets *threshold* (confident path).

    This is the deterministic guard for K7 (Behavior Spec §1.8 Invariant 3,
    INV-4: guards are pure with no side effects).

    Args:
        score: Confidence score in [0.0, 1.0].
        threshold: Confidence threshold in [0.0, 1.0].

    Returns:
        ``True`` if ``score >= threshold`` (operation proceeds without HITL).
        ``False`` if ``score < threshold`` (human review required).

    Raises:
        ValueError: *score* or *threshold* is outside [0.0, 1.0].
    """
    if not (0.0 <= score <= 1.0):
        raise ValueError(f"confidence score must be in [0.0, 1.0], got {score}")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"confidence threshold must be in [0.0, 1.0], got {threshold}")
    return score >= threshold


# ---------------------------------------------------------------------------
# k7_gate factory
# ---------------------------------------------------------------------------


def k7_gate(
    *,
    operation_type: str,
    payload: Any,
    evaluator: ConfidenceEvaluator,
    threshold_config: ThresholdConfig,
    approval_channel: ApprovalChannel,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Gate:
    """Return a Gate that enforces K7 HITL confidence checks.

    Execution flow inside ``KernelContext.__aenter__``:

    1. Fetch threshold: ``threshold_config.get_threshold(operation_type)``
    2. Evaluate confidence: ``evaluator.evaluate(operation_type, payload)``
       - Evaluator exception → wrap as ``ConfidenceError`` → FAULTED.
       - Score outside [0,1] → raise ``ValueError`` → FAULTED.
    3. Check: ``k7_check_confidence(score, threshold=threshold)``
       - CONFIDENT (score ≥ threshold) → gate returns (no approval needed).
       - UNCERTAIN (score < threshold) → continue to step 4.
    4. Create ``ApprovalRequest`` with a fresh UUID4.
    5. ``approval_channel.emit(request)``
       - Emit exception → wrap as ``ApprovalChannelError`` → FAULTED.
    6. ``approval_channel.wait_for_decision(request_id, timeout=timeout_seconds)``
       - ``ApprovalTimeout`` raised by channel → re-raise → FAULTED.
       - ``ApprovalChannelError`` raised by channel → re-raise → FAULTED.
       - Other exception → wrap as ``ApprovalChannelError`` → FAULTED.
    7. Inspect ``HumanDecision.action``:
       - ``"approve"`` → gate returns (operation proceeds).
       - ``"reject"`` → raise ``OperationRejected`` → FAULTED.
       - Unknown action → raise ``ValueError`` → FAULTED (fail-safe).

    TLA+ liveness: every branch ends in return (PASS) or exception (FAULTED →
    EXC_CONSUMED → IDLE).

    Args:
        operation_type: Logical operation type for threshold lookup and
                        audit trail (e.g. ``"workflow:execute"``).
        payload: The operation payload; included in ``ApprovalRequest`` for
                 reviewer context.  Callers are responsible for PII scrubbing.
        evaluator: ``ConfidenceEvaluator`` instance.
        threshold_config: ``ThresholdConfig`` instance.
        approval_channel: ``ApprovalChannel`` instance.
        timeout_seconds: Maximum seconds to wait for a human decision.
                         Defaults to 86400 (24 hours, Behavior Spec §1.8).

    Returns:
        An async ``Gate`` callable compatible with ``KernelContext``.

    Raises:
        ConfidenceError: Confidence evaluator raised an exception.
        ApprovalTimeout: No human decision within *timeout_seconds*.
        OperationRejected: Human reviewer rejected the operation.
        ApprovalChannelError: Approval channel is unavailable.
        ValueError: Confidence score or threshold is outside [0.0, 1.0],
                    or ``HumanDecision.action`` is not ``"approve"``/``"reject"``.
    """

    async def _k7_gate(ctx: KernelContext) -> None:
        # 1. Fetch threshold
        threshold = threshold_config.get_threshold(operation_type)

        # 2. Evaluate confidence (fail-safe: evaluator failure → deny)
        try:
            score = evaluator.evaluate(operation_type, payload)
        except Exception as exc:
            raise ConfidenceError(f"evaluator raised {type(exc).__name__}: {exc}") from exc

        # Validate score range (fail-safe: invalid score → deny)
        if not (0.0 <= score <= 1.0):
            raise ValueError(
                f"ConfidenceEvaluator returned score {score!r} outside [0.0, 1.0]"
            )

        # 3. Check confidence
        if k7_check_confidence(score, threshold=threshold):
            # CONFIDENT: proceed without human review
            return

        # 4. UNCERTAIN: build approval request
        request_id = str(uuid.uuid4())
        corr_id = ctx.corr_id or ""
        request = ApprovalRequest(
            request_id=request_id,
            operation_type=operation_type,
            confidence_score=score,
            threshold=threshold,
            payload=payload,
            corr_id=corr_id,
            created_at=datetime.now(UTC),
            timeout_seconds=timeout_seconds,
        )

        # 5. Emit to approval channel (fail-safe: channel error → deny)
        try:
            approval_channel.emit(request)
        except ApprovalChannelError:
            raise
        except Exception as exc:
            raise ApprovalChannelError(
                f"emit raised {type(exc).__name__}: {exc}"
            ) from exc

        # 6. Wait for human decision
        try:
            decision = approval_channel.wait_for_decision(
                request_id,
                timeout=timeout_seconds,
            )
        except (ApprovalTimeout, ApprovalChannelError):
            raise
        except Exception as exc:
            raise ApprovalChannelError(
                f"wait_for_decision raised {type(exc).__name__}: {exc}"
            ) from exc

        # 7. Inspect decision
        if decision.action == "approve":
            return
        elif decision.action == "reject":
            raise OperationRejected(
                request_id,
                reviewer_id=decision.reviewer_id,
                reason=decision.reason,
            )
        else:
            raise ValueError(
                f"HumanDecision.action must be 'approve' or 'reject', "
                f"got {decision.action!r}"
            )

    return _k7_gate
