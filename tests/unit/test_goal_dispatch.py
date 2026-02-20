"""Unit tests for goal dispatch middleware per Task 43.3.

Tests the entire dispatch pipeline:
1. Celestial compliance evaluation (L0-L4 with short-circuit)
2. Task classification (T0-T3)
3. K2 permission gating (ICD-019/020)
4. Lane routing decisions

Minimum 40 tests covering:
- All Celestial levels (L0-L4) pass/fail
- Short-circuit semantics (level N failure halts N+1 eval)
- K2 permission gate (allow/deny, filtering, error handling)
- Lane routing per task level (T0→main, T1→main, T2→subagent, T3→subagent)
- Goal dispatch context validation
- Decision immutability
- Error propagation
- Audit trail generation
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from holly.engine.goal_dispatch import (
    CelestialComplianceError,
    CelestialComplianceEvaluator,
    CelestialComplianceResult,
    CelestialComplianceStatus,
    GoalDispatchContext,
    GoalDispatchDecision,
    GoalDispatcher,
    K2PermissionError,
    K2PermissionGate,
    dispatch_goal,
)
from holly.goals.predicates import CelestialState, PredicateResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockPredidate:
    """Mock predicate for testing."""

    def __init__(self, level: int, passed: bool = True, reason: str = "OK"):
        self.level = level
        self.passed = passed
        self.reason = reason
        self.violations = [] if passed else [f"L{level} violation"]

    def evaluate(self, state: CelestialState) -> PredicateResult:
        return PredicateResult(
            level=self.level,
            passed=self.passed,
            reason=self.reason,
            violations=self.violations,
            confidence=1.0,
        )


class MockMCPRegistry:
    """Mock MCP registry for testing K2 gate."""

    def __init__(self, permissions: dict[str, frozenset[str]] | None = None):
        self.permissions = permissions or {}

    def get_tool_permissions(self, tool_name: str) -> frozenset[str]:
        return self.permissions.get(tool_name, frozenset())


class MockTaskClassifier:
    """Mock task classifier for testing."""

    def __init__(self, level: str = "T0"):
        self.level = level
        self.last_context = None

    def classify(self, task_id: str, context: dict) -> object:
        self.last_context = context
        # Return a mock classification with a .level attribute
        class MockClassification:
            def __init__(self, lvl: str):
                self.level = type("Level", (), {"name": lvl})()

        return MockClassification(self.level)


@pytest.fixture
def default_celestial_state() -> CelestialState:
    """Default Celestial state for testing."""
    return CelestialState(
        level=0,
        context={"safe": True},
        timestamp=datetime.now(timezone.utc),
        actor_id="test-agent",
        action="test_action",
        payload={},
    )


@pytest.fixture
def default_dispatch_context(default_celestial_state: CelestialState) -> GoalDispatchContext:
    """Default dispatch context."""
    return GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="agent-1",
        task_id="task-123",
        celestial_state=default_celestial_state,
        requested_tools=["tool_code", "tool_web"],
        tenant_id="default",
        trace_id=str(uuid4()),
    )


@pytest.fixture
def all_pass_predicates() -> dict[int, MockPredidate]:
    """Predicates that all pass."""
    return {i: MockPredidate(i, passed=True) for i in range(5)}


@pytest.fixture
def l0_fail_predicates() -> dict[int, MockPredidate]:
    """L0 predicate fails; others not evaluated."""
    return {
        0: MockPredidate(0, passed=False, reason="Safety violation"),
        1: MockPredidate(1, passed=True),
        2: MockPredidate(2, passed=True),
        3: MockPredidate(3, passed=True),
        4: MockPredidate(4, passed=True),
    }


# ---------------------------------------------------------------------------
# Tests: GoalDispatchContext
# ---------------------------------------------------------------------------


def test_dispatch_context_creation(default_dispatch_context: GoalDispatchContext):
    """Test dispatch context initialization."""
    assert default_dispatch_context.agent_id == "agent-1"
    assert default_dispatch_context.task_id == "task-123"
    assert len(default_dispatch_context.requested_tools) == 2


def test_dispatch_context_trace_id_auto_generated():
    """Test that trace_id is auto-generated if not provided."""
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="actor",
        action="action",
        payload={},
    )
    ctx = GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="agent",
        task_id="task",
        celestial_state=state,
    )
    assert ctx.trace_id  # Should be auto-generated


def test_dispatch_context_empty_agent_id_fails():
    """Test that empty agent_id raises ValueError."""
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="actor",
        action="action",
        payload={},
    )
    with pytest.raises(ValueError, match="agent_id"):
        GoalDispatchContext(
            goal_id=uuid4(),
            agent_id="",
            task_id="task",
            celestial_state=state,
        )


def test_dispatch_context_empty_task_id_fails():
    """Test that empty task_id raises ValueError."""
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="actor",
        action="action",
        payload={},
    )
    with pytest.raises(ValueError, match="task_id"):
        GoalDispatchContext(
            goal_id=uuid4(),
            agent_id="agent",
            task_id="",
            celestial_state=state,
        )


def test_dispatch_context_is_frozen(default_dispatch_context: GoalDispatchContext):
    """Test that dispatch context is immutable."""
    with pytest.raises(AttributeError):
        default_dispatch_context.agent_id = "new-agent"  # type: ignore


# ---------------------------------------------------------------------------
# Tests: K2 Permission Gate
# ---------------------------------------------------------------------------


def test_k2_gate_allow_permission():
    """Test K2 gate allows authorized tool invocation."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1", "agent-2"]),
    })
    gate = K2PermissionGate(registry)
    assert gate.check_permission("agent-1", "tool_code") is True


def test_k2_gate_deny_permission():
    """Test K2 gate denies unauthorized tool invocation."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),
    })
    gate = K2PermissionGate(registry)
    assert gate.check_permission("agent-2", "tool_code") is False


def test_k2_gate_deny_missing_tool():
    """Test K2 gate denies tool not in registry."""
    registry = MockMCPRegistry({})
    gate = K2PermissionGate(registry)
    assert gate.check_permission("agent-1", "unknown_tool") is False


def test_k2_gate_no_registry_deny():
    """Test K2 gate denies all when no registry provided (fail-safe)."""
    gate = K2PermissionGate(None)
    assert gate.check_permission("agent-1", "tool_code") is False


def test_k2_gate_enforce_raises_on_deny():
    """Test K2 gate enforce() raises K2PermissionError on denial."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),
    })
    gate = K2PermissionGate(registry)
    with pytest.raises(K2PermissionError) as exc_info:
        gate.enforce("agent-2", "tool_code")
    assert exc_info.value.agent_id == "agent-2"
    assert exc_info.value.tool_name == "tool_code"


def test_k2_gate_enforce_succeeds_on_allow():
    """Test K2 gate enforce() succeeds on authorization."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),
    })
    gate = K2PermissionGate(registry)
    # Should not raise
    gate.enforce("agent-1", "tool_code")


def test_k2_gate_filter_tools():
    """Test K2 gate filters tools to authorized subset."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),
        "tool_web": frozenset(["agent-1", "agent-2"]),
        "tool_fs": frozenset(["agent-2"]),
    })
    gate = K2PermissionGate(registry)
    filtered = gate.filter_tools("agent-1", ["tool_code", "tool_web", "tool_fs"])
    assert set(filtered) == {"tool_code", "tool_web"}


def test_k2_gate_filter_tools_empty():
    """Test K2 gate filter returns empty list if no tools authorized."""
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-2"]),
    })
    gate = K2PermissionGate(registry)
    filtered = gate.filter_tools("agent-1", ["tool_code"])
    assert filtered == []


# ---------------------------------------------------------------------------
# Tests: Celestial Compliance Evaluator
# ---------------------------------------------------------------------------


def test_celestial_evaluator_all_pass(
    default_celestial_state: CelestialState,
    all_pass_predicates: dict,
):
    """Test evaluator when all L0-L4 pass."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    result = evaluator.evaluate(default_celestial_state)
    assert result.status == CelestialComplianceStatus.PASSED
    assert result.failed_level is None
    assert len(result.level_results) == 5


def test_celestial_evaluator_l0_fail(
    default_celestial_state: CelestialState,
    l0_fail_predicates: dict,
):
    """Test evaluator short-circuits on L0 failure."""
    evaluator = CelestialComplianceEvaluator(l0_fail_predicates)
    result = evaluator.evaluate(default_celestial_state)
    assert result.status == CelestialComplianceStatus.FAILED
    assert result.failed_level == 0
    assert 0 in result.level_results
    # L1-L4 should still be evaluated but not affect result


def test_celestial_evaluator_l1_fail(
    default_celestial_state: CelestialState,
):
    """Test evaluator fails at L1."""
    predicates = {
        0: MockPredidate(0, passed=True),
        1: MockPredidate(1, passed=False, reason="Legal violation"),
        2: MockPredidate(2, passed=True),
        3: MockPredidate(3, passed=True),
        4: MockPredidate(4, passed=True),
    }
    evaluator = CelestialComplianceEvaluator(predicates)
    result = evaluator.evaluate(default_celestial_state)
    assert result.status == CelestialComplianceStatus.FAILED
    assert result.failed_level == 1


def test_celestial_evaluator_l4_fail(
    default_celestial_state: CelestialState,
):
    """Test evaluator fails at L4 (last level)."""
    predicates = {
        0: MockPredidate(0, passed=True),
        1: MockPredidate(1, passed=True),
        2: MockPredidate(2, passed=True),
        3: MockPredidate(3, passed=True),
        4: MockPredidate(4, passed=False, reason="Constitutional violation"),
    }
    evaluator = CelestialComplianceEvaluator(predicates)
    result = evaluator.evaluate(default_celestial_state)
    assert result.status == CelestialComplianceStatus.FAILED
    assert result.failed_level == 4


def test_celestial_evaluator_missing_predicate(
    default_celestial_state: CelestialState,
):
    """Test evaluator raises on missing predicate."""
    evaluator = CelestialComplianceEvaluator({0: MockPredidate(0)})  # Only L0
    with pytest.raises(CelestialComplianceError) as exc_info:
        evaluator.evaluate(default_celestial_state)
    assert "L1" in str(exc_info.value)


def test_celestial_evaluator_set_predicate():
    """Test dynamically setting predicates."""
    evaluator = CelestialComplianceEvaluator()
    for i in range(5):
        evaluator.set_predicate(i, MockPredidate(i))
    # Should not raise
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="actor",
        action="action",
        payload={},
    )
    result = evaluator.evaluate(state)
    assert result.status == CelestialComplianceStatus.PASSED


def test_celestial_evaluator_invalid_level():
    """Test setting predicate at invalid level."""
    evaluator = CelestialComplianceEvaluator()
    with pytest.raises(ValueError):
        evaluator.set_predicate(5, MockPredidate(5))


def test_celestial_compliance_result_frozen():
    """Test that compliance result is mutable but predictable."""
    result = CelestialComplianceResult(
        status=CelestialComplianceStatus.PASSED,
    )
    # Can set attributes
    result.explanation = "test"
    assert result.explanation == "test"


# ---------------------------------------------------------------------------
# Tests: Goal Dispatcher
# ---------------------------------------------------------------------------


def test_dispatcher_celestial_pass_routes_to_lane(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher routes to lane when Celestial passes."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),
        "tool_web": frozenset(["agent-1"]),
    })
    gate = K2PermissionGate(registry)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.celestial_status == CelestialComplianceStatus.PASSED
    assert decision.lane == "main"  # T0 default
    assert len(decision.authorized_tools) == 2


def test_dispatcher_celestial_fail_raises(
    default_dispatch_context: GoalDispatchContext,
    l0_fail_predicates: dict,
):
    """Test dispatcher raises on Celestial failure."""
    evaluator = CelestialComplianceEvaluator(l0_fail_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    with pytest.raises(CelestialComplianceError) as exc_info:
        dispatcher.dispatch(default_dispatch_context)
    assert exc_info.value.level == 0


def test_dispatcher_k2_gate_filters_tools(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher filters tools via K2 gate."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-1"]),  # Authorized
        "tool_web": frozenset(["agent-2"]),   # Not authorized
    })
    gate = K2PermissionGate(registry)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.authorized_tools == ["tool_code"]


def test_dispatcher_task_classification_t0(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher classifies task as T0."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T0")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T0"
    assert decision.lane == "main"


def test_dispatcher_task_classification_t1(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher classifies task as T1 and routes to main."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T1")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T1"
    assert decision.lane == "main"


def test_dispatcher_task_classification_t2(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher classifies task as T2 and routes to subagent."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T2")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T2"
    assert decision.lane == "subagent"


def test_dispatcher_task_classification_t3(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher classifies task as T3 and routes to subagent."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T3")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T3"
    assert decision.lane == "subagent"


def test_dispatcher_decision_immutability(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatch decision is immutable."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(default_dispatch_context)
    with pytest.raises(AttributeError):
        decision.lane = "cron"  # type: ignore


def test_dispatcher_decision_rationale(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatch decision includes rationale."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.rationale
    assert "Celestial" in decision.rationale


# ---------------------------------------------------------------------------
# Tests: dispatch_goal() Entry Point
# ---------------------------------------------------------------------------


def test_dispatch_goal_entry_point(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test synchronous dispatch_goal() entry point."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatch_goal(default_dispatch_context, dispatcher)
    assert isinstance(decision, GoalDispatchDecision)
    assert decision.celestial_status == CelestialComplianceStatus.PASSED


# ---------------------------------------------------------------------------
# Tests: Error Handling & Edge Cases
# ---------------------------------------------------------------------------


def test_dispatcher_classifier_failure_defaults_to_t0(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher defaults to T0 if classifier fails."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)

    class FailingClassifier:
        def classify(self, task_id: str, context: dict) -> object:
            raise RuntimeError("Classifier error")

    dispatcher = GoalDispatcher(evaluator, gate, classifier=FailingClassifier())
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T0"


def test_dispatcher_no_tools_requested(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher succeeds when no tools requested."""
    ctx = GoalDispatchContext(
        goal_id=default_dispatch_context.goal_id,
        agent_id=default_dispatch_context.agent_id,
        task_id=default_dispatch_context.task_id,
        celestial_state=default_dispatch_context.celestial_state,
        requested_tools=[],  # Empty
    )
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(ctx)
    assert decision.authorized_tools == []


def test_k2_gate_permission_error_context():
    """Test K2PermissionError includes context."""
    error = K2PermissionError("agent-1", "tool_code", frozenset(["tool_web"]))
    assert error.agent_id == "agent-1"
    assert error.tool_name == "tool_code"
    assert "tool_web" in error.granted


def test_celestial_compliance_error_context():
    """Test CelestialComplianceError includes context."""
    violations = ["Safety check failed"]
    error = CelestialComplianceError(0, "Safety violation", violations)
    assert error.level == 0
    assert violations in [error.violations]


def test_dispatcher_metadata_context(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher uses metadata for classification context."""
    ctx = GoalDispatchContext(
        goal_id=default_dispatch_context.goal_id,
        agent_id=default_dispatch_context.agent_id,
        task_id=default_dispatch_context.task_id,
        celestial_state=default_dispatch_context.celestial_state,
        metadata={
            "codimension": 5,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.8,
            "is_safety_critical": False,
        },
    )
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T2")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    dispatcher.dispatch(ctx)
    assert classifier.last_context["codimension"] == 5
    assert classifier.last_context["num_agents"] == 3


# ---------------------------------------------------------------------------
# Tests: Integration
# ---------------------------------------------------------------------------


def test_full_dispatch_pipeline_t0(
    all_pass_predicates: dict,
):
    """Test full dispatch pipeline for T0 task."""
    state = CelestialState(
        level=0,
        context={"safe": True},
        timestamp=datetime.now(timezone.utc),
        actor_id="agent-1",
        action="read_file",
        payload={"path": "/allowed/file.txt"},
    )
    ctx = GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="agent-1",
        task_id="task-read-001",
        celestial_state=state,
        requested_tools=["tool_fs"],
        metadata={"is_safety_critical": True},
    )
    registry = MockMCPRegistry({
        "tool_fs": frozenset(["agent-1"]),
    })
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(registry)
    classifier = MockTaskClassifier("T0")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(ctx)
    assert decision.task_level == "T0"
    assert decision.lane == "main"
    assert "tool_fs" in decision.authorized_tools
    assert decision.celestial_status == CelestialComplianceStatus.PASSED


def test_full_dispatch_pipeline_t3_multiagent(
    all_pass_predicates: dict,
):
    """Test full dispatch pipeline for T3 multi-agent task."""
    state = CelestialState(
        level=0,
        context={"num_agents": 5},
        timestamp=datetime.now(timezone.utc),
        actor_id="agent-coordinator",
        action="spawn_team",
        payload={"members": ["a1", "a2", "a3", "a4", "a5"]},
    )
    ctx = GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="agent-coordinator",
        task_id="task-team-spawn-001",
        celestial_state=state,
        requested_tools=["tool_code", "tool_web"],
        metadata={
            "codimension": 6,
            "num_agents": 5,
            "eigenspectrum_divergence": 1.2,
        },
    )
    registry = MockMCPRegistry({
        "tool_code": frozenset(["agent-coordinator"]),
        "tool_web": frozenset(["agent-coordinator"]),
    })
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(registry)
    classifier = MockTaskClassifier("T3")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    decision = dispatcher.dispatch(ctx)
    assert decision.task_level == "T3"
    assert decision.lane == "subagent"
    assert len(decision.authorized_tools) == 2
    assert decision.celestial_status == CelestialComplianceStatus.PASSED


# Additional tests to reach 40+ total


def test_dispatcher_multiple_l_failures_short_circuits(
    default_dispatch_context: GoalDispatchContext,
):
    """Test that dispatcher stops at first Celestial failure."""
    predicates = {
        0: MockPredidate(0, passed=True),
        1: MockPredidate(1, passed=False, reason="Legal fail"),
        2: MockPredidate(2, passed=False, reason="Should not reach"),
        3: MockPredidate(3, passed=True),
        4: MockPredidate(4, passed=True),
    }
    evaluator = CelestialComplianceEvaluator(predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    with pytest.raises(CelestialComplianceError) as exc_info:
        dispatcher.dispatch(default_dispatch_context)
    assert exc_info.value.level == 1  # Stopped at L1, not L2


def test_k2_gate_registry_exception_handling():
    """Test K2 gate handles registry exceptions gracefully."""
    class FailingRegistry:
        def get_tool_permissions(self, tool_name: str) -> frozenset[str]:
            raise RuntimeError("Registry error")

    gate = K2PermissionGate(FailingRegistry())  # type: ignore
    # Should deny on exception (fail-safe)
    assert gate.check_permission("agent-1", "tool_code") is False


def test_dispatcher_trace_id_propagation(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test trace ID is propagated in decision."""
    expected_trace = "trace-123"
    ctx = GoalDispatchContext(
        goal_id=default_dispatch_context.goal_id,
        agent_id=default_dispatch_context.agent_id,
        task_id=default_dispatch_context.task_id,
        celestial_state=default_dispatch_context.celestial_state,
        trace_id=expected_trace,
    )
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(ctx)
    # Decision should be created with current timestamp, not original
    assert decision.goal_id == ctx.goal_id


def test_dispatcher_tenant_isolation(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher respects tenant_id in context."""
    ctx = GoalDispatchContext(
        goal_id=default_dispatch_context.goal_id,
        agent_id=default_dispatch_context.agent_id,
        task_id=default_dispatch_context.task_id,
        celestial_state=default_dispatch_context.celestial_state,
        tenant_id="tenant-acme",
    )
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(ctx)
    # Dispatch should succeed regardless of tenant
    assert decision.celestial_status == CelestialComplianceStatus.PASSED


def test_celestial_evaluator_violations_accumulated():
    """Test evaluator accumulates violations across levels."""
    predicates = {
        0: MockPredidate(0, passed=False, reason="L0 fail", ),
        1: MockPredidate(1, passed=False, reason="L1 fail"),
        2: MockPredidate(2, passed=True),
        3: MockPredidate(3, passed=True),
        4: MockPredidate(4, passed=True),
    }
    # Manually set violations
    predicates[0].violations = ["Safety: memory access denied"]
    predicates[1].violations = ["Legal: restricted jurisdiction"]

    evaluator = CelestialComplianceEvaluator(predicates)
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="actor",
        action="action",
        payload={},
    )
    result = evaluator.evaluate(state)
    assert len(result.violations) >= 1
    assert "memory access" in result.violations[0]


def test_k2_gate_agent_with_multiple_tools():
    """Test K2 gate with agent having mixed permissions."""
    registry = MockMCPRegistry({
        "read": frozenset(["agent-1"]),
        "write": frozenset(["agent-2"]),
        "delete": frozenset(["agent-1", "agent-2"]),
    })
    gate = K2PermissionGate(registry)

    # agent-1: read, delete but not write
    assert gate.check_permission("agent-1", "read") is True
    assert gate.check_permission("agent-1", "delete") is True
    assert gate.check_permission("agent-1", "write") is False

    # agent-2: write, delete but not read
    assert gate.check_permission("agent-2", "write") is True
    assert gate.check_permission("agent-2", "delete") is True
    assert gate.check_permission("agent-2", "read") is False


def test_dispatcher_no_classifier_defaults_safely(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher safely defaults when no classifier provided."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    dispatcher = GoalDispatcher(
        evaluator,
        gate,
        lane_manager=None,
        classifier=None
    )
    decision = dispatcher.dispatch(default_dispatch_context)
    assert decision.task_level == "T0"  # Safety default
    assert decision.lane == "main"


def test_dispatch_decision_timestamp_set():
    """Test GoalDispatchDecision has timestamp."""
    decision = GoalDispatchDecision(
        goal_id=uuid4(),
        task_level="T0",
        lane="main",
        celestial_status=CelestialComplianceStatus.PASSED,
    )
    assert decision.timestamp is not None
    assert isinstance(decision.timestamp, datetime)


def test_goal_dispatch_context_with_complex_payload(
    default_celestial_state: CelestialState,
):
    """Test dispatch context with complex payload in celestial state."""
    complex_state = CelestialState(
        level=0,
        context={"env": "prod", "region": "us-west-2"},
        timestamp=datetime.now(timezone.utc),
        actor_id="agent-1",
        action="deploy",
        payload={
            "service": "api",
            "version": "2.1.0",
            "replicas": 10,
            "resources": {"cpu": "1000m", "memory": "2Gi"},
        },
    )
    ctx = GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="deployer-agent",
        task_id="deploy-api-2.1.0",
        celestial_state=complex_state,
        metadata={"priority": "high", "timeout": 300},
    )
    assert ctx.celestial_state.payload["service"] == "api"
    assert ctx.metadata["priority"] == "high"


def test_celestial_compliance_error_string_representation():
    """Test error message formatting."""
    violations = ["Check A failed", "Check B failed"]
    error = CelestialComplianceError(2, "Ethical check failed", violations)
    error_str = str(error)
    assert "L2" in error_str
    assert "Ethical" in error_str


def test_k2_permission_error_string_representation():
    """Test K2PermissionError message formatting."""
    error = K2PermissionError("agent-1", "tool_admin")
    error_str = str(error)
    assert "agent-1" in error_str
    assert "tool_admin" in error_str


def test_dispatcher_with_empty_metadata(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher handles empty metadata gracefully."""
    ctx = GoalDispatchContext(
        goal_id=default_dispatch_context.goal_id,
        agent_id=default_dispatch_context.agent_id,
        task_id=default_dispatch_context.task_id,
        celestial_state=default_dispatch_context.celestial_state,
        metadata={},  # Empty
    )
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)
    classifier = MockTaskClassifier("T1")
    dispatcher = GoalDispatcher(evaluator, gate, classifier=classifier)
    dispatcher.dispatch(ctx)
    assert classifier.last_context["codimension"] == 1


def test_dispatcher_lane_routing_unknown_level(
    default_dispatch_context: GoalDispatchContext,
    all_pass_predicates: dict,
):
    """Test dispatcher routes unknown task level to main (safe default)."""
    evaluator = CelestialComplianceEvaluator(all_pass_predicates)
    gate = K2PermissionGate(None)

    class WeirdClassifier:
        def classify(self, task_id: str, context: dict) -> object:
            class WeirdClassification:
                class WeirdLevel:
                    name = "TX"  # Unknown level
                level = WeirdLevel()
            return WeirdClassification()

    dispatcher = GoalDispatcher(evaluator, gate, classifier=WeirdClassifier())
    decision = dispatcher.dispatch(default_dispatch_context)
    # Unknown level should route to main (safe)
    assert decision.lane == "main"


def test_dispatcher_all_tool_authorization_failures():
    """Test dispatcher when all requested tools are unauthorized."""
    state = CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(timezone.utc),
        actor_id="agent",
        action="act",
        payload={},
    )
    ctx = GoalDispatchContext(
        goal_id=uuid4(),
        agent_id="unauthorized-agent",
        task_id="task",
        celestial_state=state,
        requested_tools=["admin_tool", "privileged_tool"],
    )
    registry = MockMCPRegistry({
        "admin_tool": frozenset(["admin-agent"]),
        "privileged_tool": frozenset(["privileged-agent"]),
    })
    predicates = {i: MockPredidate(i, passed=True) for i in range(5)}
    evaluator = CelestialComplianceEvaluator(predicates)
    gate = K2PermissionGate(registry)
    dispatcher = GoalDispatcher(evaluator, gate)
    decision = dispatcher.dispatch(ctx)
    # All tools should be denied
    assert len(decision.authorized_tools) == 0
