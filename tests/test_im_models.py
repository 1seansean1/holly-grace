"""Tests for IM data models (src/im/models.py)."""

import pytest
from src.im.models import (
    IMWorkspace,
    WorkspaceStage,
    Regime,
    Severity,
    TopologyPattern,
    Verdict,
    G1Tuple,
    GoalTuple,
    IMPredicate,
    IMBlock,
    CrossBlockCoupling,
    CouplingMatrix,
    MatrixOverride,
    IMEigenvalue,
    Codimension,
    IMAgentSpec,
    IMOrchestratorSpec,
    RankBudget,
    MemoryTier,
    KEntry,
    CrystallisationPolicy,
    MemoryArchitecture,
    Assignment,
    TopologyNode,
    TopologyEdge,
    WorkflowSpec,
    Feasibility,
)


class TestEnums:
    def test_workspace_stages_are_strings(self):
        assert WorkspaceStage.CREATED.value == "created"
        assert WorkspaceStage.FEASIBILITY_VALIDATED.value == "feasibility_validated"

    def test_all_stages_exist(self):
        stages = [s.value for s in WorkspaceStage]
        assert len(stages) == 10

    def test_severity_levels(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.LOW.value == "low"

    def test_regime_types(self):
        assert Regime.SIMPLE.value == "simple"
        assert Regime.COMPLEX.value == "complex"

    def test_topology_patterns(self):
        patterns = [p.value for p in TopologyPattern]
        assert "flat" in patterns
        assert "mesh" in patterns
        assert "hybrid" in patterns

    def test_verdict(self):
        assert Verdict.FEASIBLE.value == "feasible"
        assert Verdict.INFEASIBLE.value == "infeasible"


class TestIMWorkspace:
    def test_defaults(self):
        ws = IMWorkspace(workspace_id="test_001")
        assert ws.workspace_id == "test_001"
        assert ws.stage == "created"
        assert ws.version == 1
        assert ws.predicates == []
        assert ws.predicate_blocks == []
        assert ws.coupling_matrix == {}
        assert ws.feasibility == {}

    def test_mutable_defaults_isolated(self):
        ws1 = IMWorkspace(workspace_id="a")
        ws2 = IMWorkspace(workspace_id="b")
        ws1.predicates.append({"id": "f_001"})
        assert ws2.predicates == [], "Mutable defaults should be isolated"

    def test_all_stages_reachable(self):
        ws = IMWorkspace(workspace_id="test")
        for stage in WorkspaceStage:
            ws.stage = stage.value
        assert ws.stage == "feasibility_validated"


class TestGoalModels:
    def test_g1_tuple_defaults(self):
        g = G1Tuple()
        assert g.epsilon_g == 0.05
        assert g.horizon_t == 3600
        assert g.failure_predicates == []

    def test_goal_tuple(self):
        gt = GoalTuple(g0_preference="Build a chatbot")
        assert gt.g0_preference == "Build a chatbot"
        assert gt.g1_candidates == []
        assert gt.ambiguities == []


class TestPredicateModels:
    def test_im_predicate(self):
        p = IMPredicate(id="f_001", name="auth_failure")
        assert p.id == "f_001"
        assert p.block_id == ""
        assert p.severity == "medium"
        assert p.dim_star is None

    def test_im_block(self):
        b = IMBlock(id="BLK_A", name="Security", predicate_ids=["f_001", "f_002"])
        assert len(b.predicate_ids) == 2
        assert b.intra_rank is None

    def test_cross_block_coupling(self):
        cc = CrossBlockCoupling(from_block="A", to_block="B", rho=0.5)
        assert cc.rho == 0.5


class TestCouplingModels:
    def test_coupling_matrix_defaults(self):
        cm = CouplingMatrix()
        assert cm.m == []
        assert cm.locked is False

    def test_matrix_override(self):
        mo = MatrixOverride(row=0, col=1, value=0.8)
        assert mo.value == 0.8


class TestCodimensionModels:
    def test_eigenvalue(self):
        ev = IMEigenvalue(index=1, value=2.5, block_attribution="BLK_A")
        assert ev.value == 2.5

    def test_codimension(self):
        cd = Codimension(cod_pi_g=5, tau=0.05)
        assert cd.cod_pi_g == 5


class TestRankBudgetModels:
    def test_agent_spec(self):
        agent = IMAgentSpec(agent_id="a1", name="TestBot", jacobian_rank=3)
        assert agent.context_window == 200000
        assert agent.blanket_level == 0

    def test_orchestrator_spec(self):
        orch = IMOrchestratorSpec(model_family="claude-opus-4-6", jacobian_rank=5)
        assert orch.jacobian_rank == 5

    def test_rank_budget(self):
        rb = RankBudget(regime="medium", total_rank=10, cod_pi_g=5)
        assert rb.rank_surplus_or_deficit == 0  # default


class TestMemoryModels:
    def test_memory_tier(self):
        mt = MemoryTier(tier="M0", scope="Agent-private")
        assert mt.persistence == ""

    def test_k_entry(self):
        k = KEntry(name="domain_rules", cod_reduction=2.0, tier="M1")
        assert k.cod_reduction == 2.0

    def test_crystallisation_policy(self):
        cp = CrystallisationPolicy(primary_criterion="K-extending")
        assert cp.reject_criterion == ""

    def test_memory_architecture(self):
        ma = MemoryArchitecture()
        assert ma.tiers == []
        assert ma.k_preloaded == []


class TestAssignmentModels:
    def test_assignment(self):
        a = Assignment(delta_norm=0.01, delta_rank=1)
        assert a.governance_margin == 0.0

    def test_topology_node(self):
        n = TopologyNode(node_id="orch", agent_id="orchestrator", role="orchestrator")
        assert n.role == "orchestrator"

    def test_topology_edge(self):
        e = TopologyEdge(source="orch", target="a1", protocol="async")
        assert e.capacity == 0


class TestWorkflowModels:
    def test_workflow_spec(self):
        ws = WorkflowSpec(compiled=True)
        assert ws.validation_errors == []

    def test_feasibility(self):
        f = Feasibility(
            rank_coverage=True,
            coupling_coverage=True,
            power_coverage=True,
            verdict="feasible",
        )
        assert f.verdict == "feasible"
        assert f.remediation is None
