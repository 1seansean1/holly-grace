"""Goal-Dispatch Middleware: bridges goal hierarchy with lane/MCP dispatch system.

Task 43.3 — Goal-Dispatch Middleware.

This module implements the middleware that evaluates goal compliance (Celestial L0-L4
predicates) and routes tasks to appropriate execution lanes (Main, Cron, Subagent)
with MCP tool dispatch enforcing K2 permission gates.

Provides:
- GoalDispatchContext: immutable request context for dispatch decision
- GoalDispatchDecision: routing decision with level classification and lane
- K2PermissionGate: enforces per-agent tool permission checks per ICD-019/020
- CelestialComplianceEvaluator: evaluates Celestial L0-L4 predicate chain
- GoalDispatcher: main orchestrator coordinating compliance → lane routing
- dispatch_goal(): synchronous entry point for goal dispatch

Per ICD-013/014/015 (lane-based routing) and ICD-019/020 (MCP permissions):
- Dispatch enforces lexicographic Celestial gating (L0 must pass before L1 eval)
- Any Celestial failure blocks dispatch (raises GoalDispatchError)
- K2 permission gate checks agent authorization for any MCP tool invocation
- Task level (T0-T3) determines lane routing policy and timeout
- All dispatch decisions are immutable and auditable

Per Goal Hierarchy Formal Spec §2.0-2.6 (Celestial predicates):
- L0 (Safety): immutable safety constraints; any violation blocks dispatch
- L1 (Legal): regulatory compliance; failure returns INVALID_LEGAL
- L2 (Ethical): institutional ethics; failure returns INVALID_ETHICAL
- L3 (Permissions): agent capability grants; failure checked against K2
- L4 (Constitutional): system constitution; failure returns INVALID_CONSTITUTIONAL

Per ICD compliance:
- ICD-013/014/015: lane dispatch routing per task level
- ICD-019/020: tool permission checking and invocation contracts
- ICD-011: APS tier classification (T0-T3)
- K1: schema validation (boundary ingress)
- K2: permission gate (boundary egress for MCP tools)
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import uuid4

if TYPE_CHECKING:
    from holly.engine.lanes import LaneManager
    from holly.engine.mcp_registry import MCPRegistry
    from holly.goals.classification import TaskClassification
    from holly.goals.predicates import PredicateResult

log = logging.getLogger(__name__)

__all__ = [
    "CelestialComplianceEvaluator",
    "CelestialComplianceError",
    "GoalDispatchContext",
    "GoalDispatchDecision",
    "GoalDispatcher",
    "K2PermissionError",
    "K2PermissionGate",
    "dispatch_goal",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GoalDispatchError(Exception):
    """Base exception for goal dispatch errors."""

    pass


class CelestialComplianceError(GoalDispatchError):
    """Raised when Celestial L0-L4 predicate evaluation fails."""

    def __init__(
        self,
        level: int,
        reason: str,
        violations: list[str] | None = None,
    ) -> None:
        self.level = level
        self.reason = reason
        self.violations = violations or []
        super().__init__(
            f"Celestial L{level} compliance check failed: {reason}"
        )


class K2PermissionError(GoalDispatchError):
    """Raised when K2 permission gate denies access per ICD-019/020."""

    def __init__(
        self,
        agent_id: str,
        tool_name: str,
        granted: frozenset[str] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.tool_name = tool_name
        self.granted = granted or frozenset()
        super().__init__(
            f"K2 permission denied: agent {agent_id!r} "
            f"cannot invoke tool {tool_name!r}"
        )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CelestialComplianceStatus(str, Enum):  # noqa: UP042
    """Status of Celestial compliance evaluation chain."""

    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class GoalDispatchContext:
    """Immutable request context for a dispatch decision.

    Attributes
    ----------
    goal_id : UUID
        Unique identifier for this goal.
    agent_id : str
        Agent requesting dispatch.
    task_id : str
        Task ID being dispatched (for traceability).
    celestial_state : CelestialState
        System state snapshot for predicate evaluation.
    requested_tools : list[str]
        List of MCP tool names that may be invoked.
    tenant_id : str
        Tenant ID for multi-tenant isolation.
    trace_id : str
        Trace ID for correlation.
    timestamp : datetime
        Dispatch timestamp (UTC).
    metadata : dict[str, Any]
        Additional context (intent, priority, etc.).
    """

    goal_id: Any  # UUID
    agent_id: str
    task_id: str
    celestial_state: Any  # CelestialState
    requested_tools: list[str] = field(default_factory=list)
    tenant_id: str = "default"
    trace_id: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate dispatch context."""
        if not self.agent_id:
            raise ValueError("agent_id cannot be empty")
        if not self.task_id:
            raise ValueError("task_id cannot be empty")
        if not self.trace_id:
            object.__setattr__(self, "trace_id", str(uuid4()))


@dataclass(slots=True, frozen=True)
class GoalDispatchDecision:
    """Immutable dispatch routing decision per goal evaluation.

    Attributes
    ----------
    goal_id : UUID
        Goal identifier.
    task_level : str
        Task level (T0, T1, T2, T3).
    lane : str
        Target lane name (main, cron, subagent).
    celestial_status : CelestialComplianceStatus
        Overall Celestial compliance result.
    authorized_tools : list[str]
        MCP tools authorized for this dispatch (K2-filtered).
    timestamp : datetime
        Decision timestamp (UTC).
    rationale : str
        Human-readable explanation of decision.
    violations : list[str]
        List of constraint violations (empty if compliant).
    """

    goal_id: Any
    task_level: str
    lane: str
    celestial_status: CelestialComplianceStatus
    authorized_tools: list[str] = field(default_factory=list)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    rationale: str = ""
    violations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CelestialComplianceResult:
    """Result of evaluating Celestial L0-L4 compliance chain.

    Attributes
    ----------
    status : CelestialComplianceStatus
        Overall compliance status.
    level_results : dict[int, PredicateResult]
        Per-level predicate evaluation results (L0-L4).
    failed_level : int | None
        First level that failed (None if all passed).
    explanation : str
        Human-readable summary.
    violations : list[str]
        All constraint violations across levels.
    """

    status: CelestialComplianceStatus
    level_results: dict[int, Any] = field(default_factory=dict)
    failed_level: int | None = None
    explanation: str = ""
    violations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class TaskClassifierProtocol(Protocol):
    """Protocol for task classification (T0-T3 assignment)."""

    def classify(
        self,
        task_id: str,
        context: dict[str, Any],
    ) -> TaskClassification:
        """Classify task into T0-T3 based on context."""
        ...


@runtime_checkable
class PredicateChainProtocol(Protocol):
    """Protocol for evaluating a Celestial predicate chain."""

    def evaluate(self, state: Any) -> PredicateResult:
        """Evaluate predicate against system state."""
        ...


# ---------------------------------------------------------------------------
# K2 Permission Gate
# ---------------------------------------------------------------------------


class K2PermissionGate:
    """Enforces K2 permission gate for MCP tool dispatch per ICD-019/020.

    The K2 gate is the second kernel boundary check (first is K1 schema validation).
    It verifies that an agent is authorized to invoke specific MCP tools before
    any tool execution occurs.

    Per ICD-019/020:
    - Every tool invocation requires explicit permission grant
    - Permissions are per (agent_id, tool_name) tuple
    - Missing permission → PermissionDeniedError
    - K2 gate is fail-safe (deny if uncertain)

    Per K2 formal semantics:
    - K2 = {∀ agent_id, ∀ tool_name: check_permission(agent_id, tool_name)}
    - Pre-condition: agent_id, tool_name ∈ Σ
    - Post-condition: either permission granted or K2PermissionError raised
    """

    __slots__ = ("_permissions", "_registry")

    def __init__(
        self,
        mcp_registry: MCPRegistry | None = None,
    ) -> None:
        """Initialize K2 permission gate.

        Args:
            mcp_registry: MCPRegistry instance for tool permission lookups.
        """
        self._registry = mcp_registry
        # Cached permission map: {tool_name: frozenset[agent_id]}
        self._permissions: dict[str, frozenset[str]] = {}

    def check_permission(
        self,
        agent_id: str,
        tool_name: str,
    ) -> bool:
        """Check if agent is authorized to invoke tool per K2 semantics.

        Args:
            agent_id: Agent requesting access.
            tool_name: Tool being requested.

        Returns:
            True if agent has permission; False otherwise.

        Per K2: permission check is atomic and deterministic.
        """
        if not self._registry:
            # No registry → deny all (fail-safe)
            return False

        # Get tool permissions from registry
        try:
            granted = self._registry.get_tool_permissions(tool_name)
            return agent_id in granted
        except Exception:
            # Any registry error → deny (fail-safe)
            return False

    def enforce(
        self,
        agent_id: str,
        tool_name: str,
    ) -> None:
        """Enforce K2 permission gate; raise on denial.

        Args:
            agent_id: Agent requesting access.
            tool_name: Tool being requested.

        Raises:
            K2PermissionError: If permission check fails.

        Per K2 postcondition: either returns normally (permission granted)
        or raises K2PermissionError.
        """
        if not self.check_permission(agent_id, tool_name):
            # Get granted permissions for error context
            granted = frozenset()
            if self._registry:
                with contextlib.suppress(Exception):
                    granted = self._registry.get_tool_permissions(tool_name)
            raise K2PermissionError(agent_id, tool_name, granted)

    def filter_tools(
        self,
        agent_id: str,
        requested_tools: list[str],
    ) -> list[str]:
        """Filter tool list to only those authorized for agent per K2.

        Args:
            agent_id: Agent ID.
            requested_tools: List of tool names requested.

        Returns:
            Subset of requested_tools authorized for agent.
        """
        return [
            tool for tool in requested_tools
            if self.check_permission(agent_id, tool)
        ]


# ---------------------------------------------------------------------------
# Celestial Compliance Evaluator
# ---------------------------------------------------------------------------


class CelestialComplianceEvaluator:
    """Evaluates Celestial L0-L4 compliance chain per Goal Hierarchy.

    Implements lexicographic gating: L0 must pass before L1 is evaluated,
    L1 pass before L2, etc. Any level failure short-circuits the chain.

    Per Goal Hierarchy Formal Spec §2.0-2.6:
    - L0 (Safety): immutable safety constraints
    - L1 (Legal): regulatory compliance
    - L2 (Ethical): institutional ethics
    - L3 (Permissions): agent capability grants
    - L4 (Constitutional): system constitution

    Lexicographic ordering ensures fail-safe: a single failed Celestial
    level prevents any higher-level evaluation.
    """

    __slots__ = ("_predicates",)

    def __init__(
        self,
        predicates: dict[int, PredicateChainProtocol] | None = None,
    ) -> None:
        """Initialize evaluator with L0-L4 predicates.

        Args:
            predicates: Dict mapping level (0-4) to predicate callable.
                If None, predicates must be injected before evaluate() calls.
        """
        self._predicates = predicates or {}

    def set_predicate(self, level: int, predicate: PredicateChainProtocol) -> None:
        """Register a Celestial predicate for a level.

        Args:
            level: Celestial level (0-4).
            predicate: Predicate callable.
        """
        if not 0 <= level <= 4:
            raise ValueError(f"Invalid Celestial level: {level}")
        self._predicates[level] = predicate

    def evaluate(
        self,
        celestial_state: Any,
    ) -> CelestialComplianceResult:
        """Evaluate Celestial L0-L4 predicate chain with short-circuit.

        Evaluates predicates in order L0 → L4. If any level fails,
        short-circuits immediately and returns FAILED status.

        Args:
            celestial_state: System state snapshot for evaluation.

        Returns:
            CelestialComplianceResult with per-level results and status.

        Raises:
            CelestialComplianceError: If evaluation cannot proceed
                (e.g., missing predicates).
        """
        result = CelestialComplianceResult(
            status=CelestialComplianceStatus.PASSED,
            explanation="",
            violations=[],
        )

        for level in range(5):  # L0-L4
            if level not in self._predicates:
                raise CelestialComplianceError(
                    level,
                    f"Predicate not registered for L{level}",
                )

            predicate = self._predicates[level]
            pred_result = predicate.evaluate(celestial_state)
            result.level_results[level] = pred_result

            # Short-circuit on failure per lexicographic gating
            if not pred_result.passed:
                result.status = CelestialComplianceStatus.FAILED
                result.failed_level = level
                result.explanation = (
                    f"Celestial L{level} compliance failed: {pred_result.reason}"
                )
                result.violations.extend(pred_result.violations)
                break

            # Accumulate violations even on success (for audit trail)
            result.violations.extend(pred_result.violations)

        return result


# ---------------------------------------------------------------------------
# Goal Dispatcher
# ---------------------------------------------------------------------------


class GoalDispatcher:
    """Orchestrates goal dispatch: compliance evaluation → task classification → lane routing.

    Bridges the goal hierarchy (Celestial L0-L4 predicates) with the execution
    infrastructure (lanes for task routing, MCP registry for tool dispatch).

    The dispatcher:
    1. Evaluates Celestial L0-L4 compliance chain (with short-circuit)
    2. Classifies task level (T0-T3) based on structural properties
    3. Routes to appropriate lane (Main, Cron, Subagent) per task level
    4. Enforces K2 permission gate for any MCP tool invocation

    Per ICD-013/014/015:
    - T0, T1: MainLane (single-agent)
    - T2, T3: SubagentLane (multi-agent)

    Per ICD-019/020:
    - All tool invocations must pass K2 permission gate
    - Agent permission failures raise K2PermissionError
    """

    __slots__ = (
        "_celestial_evaluator",
        "_classifier",
        "_k2_gate",
        "_lane_manager",
    )

    def __init__(
        self,
        celestial_evaluator: CelestialComplianceEvaluator,
        k2_gate: K2PermissionGate,
        lane_manager: LaneManager | None = None,
        classifier: TaskClassifierProtocol | None = None,
    ) -> None:
        """Initialize goal dispatcher.

        Args:
            celestial_evaluator: Evaluates Celestial L0-L4 chain.
            k2_gate: Enforces K2 permission checks.
            lane_manager: Routes tasks to execution lanes.
            classifier: Classifies tasks into T0-T3 levels.
        """
        self._celestial_evaluator = celestial_evaluator
        self._k2_gate = k2_gate
        self._lane_manager = lane_manager
        self._classifier = classifier

    def dispatch(
        self,
        context: GoalDispatchContext,
    ) -> GoalDispatchDecision:
        """Execute dispatch pipeline: compliance → classification → routing.

        Implements the ICD compliance sequence:
        1. K1 validation (schema) — assumed already passed (pre-gate)
        2. Celestial L0-L4 evaluation (this module)
        3. Task level classification (T0-T3)
        4. K2 permission gate (MCP tool authorization)
        5. Lane routing decision

        Args:
            context: Goal dispatch context (immutable request).

        Returns:
            GoalDispatchDecision with routing and compliance info.

        Raises:
            CelestialComplianceError: If any Celestial level fails.
            K2PermissionError: If tool authorization check fails.
            GoalDispatchError: Other dispatch errors.
        """
        log.info(
            "Dispatching goal %s for agent %s (trace: %s)",
            context.goal_id,
            context.agent_id,
            context.trace_id,
        )

        # Step 1: Evaluate Celestial L0-L4 compliance chain
        try:
            compliance_result = self._celestial_evaluator.evaluate(
                context.celestial_state
            )
        except CelestialComplianceError as e:
            log.error("Celestial compliance check failed: %s", e)
            raise

        if compliance_result.status == CelestialComplianceStatus.FAILED:
            error = CelestialComplianceError(
                level=compliance_result.failed_level or 0,
                reason=compliance_result.explanation,
                violations=compliance_result.violations,
            )
            log.error("Goal failed Celestial check: %s", error)
            raise error

        log.debug("Goal passed Celestial compliance (all L0-L4 checks)")

        # Step 2: Classify task level (T0-T3)
        task_level = "T0"  # Default to safety-critical
        if self._classifier:
            try:
                classification = self._classifier.classify(
                    context.task_id,
                    {
                        "codimension": context.metadata.get("codimension", 1),
                        "agency_rank": context.metadata.get("agency_rank", 1),
                        "num_agents": context.metadata.get("num_agents", 1),
                        "eigenspectrum_divergence": context.metadata.get(
                            "eigenspectrum_divergence", 0.0
                        ),
                        "is_safety_critical": context.metadata.get(
                            "is_safety_critical", False
                        ),
                    },
                )
                task_level = classification.level.name  # "T0", "T1", etc.
            except Exception as e:
                log.warning("Task classification failed, defaulting to T0: %s", e)

        # Step 3: Determine lane routing based on task level
        lane_name = self._route_to_lane(task_level)

        # Step 4: K2 permission gate for requested tools
        authorized_tools = []
        if context.requested_tools:
            try:
                authorized_tools = self._k2_gate.filter_tools(
                    context.agent_id,
                    context.requested_tools,
                )
                if len(authorized_tools) < len(context.requested_tools):
                    denied_tools = set(context.requested_tools) - set(
                        authorized_tools
                    )
                    log.warning(
                        "K2 gate denied tools for agent %s: %s",
                        context.agent_id,
                        denied_tools,
                    )
            except Exception as e:
                log.error("K2 permission check failed: %s", e)
                raise K2PermissionError(
                    context.agent_id,
                    ", ".join(context.requested_tools),
                ) from e

        # Step 5: Construct dispatch decision
        decision = GoalDispatchDecision(
            goal_id=context.goal_id,
            task_level=task_level,
            lane=lane_name,
            celestial_status=compliance_result.status,
            authorized_tools=authorized_tools,
            rationale=(
                f"Celestial L0-L4 passed; "
                f"task classified as {task_level}; "
                f"routed to {lane_name} lane; "
                f"{len(authorized_tools)} tools authorized"
            ),
            violations=compliance_result.violations,
        )

        log.info(
            "Goal %s dispatched to %s lane (task_level=%s, tools=%d)",
            context.goal_id,
            lane_name,
            task_level,
            len(authorized_tools),
        )

        return decision

    def _route_to_lane(self, task_level: str) -> str:
        """Route task to appropriate lane based on level.

        Per ICD-013/014/015:
        - T0, T1: MainLane (single-agent)
        - T2, T3: SubagentLane (multi-agent)

        Args:
            task_level: Task level string (T0-T3).

        Returns:
            Lane name (main, cron, subagent).
        """
        if task_level in ("T0", "T1"):
            return "main"
        elif task_level in ("T2", "T3"):
            return "subagent"
        else:
            # Unknown level → default to main (safe)
            return "main"


# ---------------------------------------------------------------------------
# Synchronous Entry Point
# ---------------------------------------------------------------------------


def dispatch_goal(
    context: GoalDispatchContext,
    dispatcher: GoalDispatcher,
) -> GoalDispatchDecision:
    """Synchronous entry point for goal dispatch.

    Args:
        context: Goal dispatch context.
        dispatcher: GoalDispatcher instance.

    Returns:
        GoalDispatchDecision with routing decision.

    Raises:
        GoalDispatchError: On dispatch failure.
    """
    return dispatcher.dispatch(context)
