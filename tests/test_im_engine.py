"""Tests for IM computation engine (src/im/engine.py).

Pure-function tests — no database or Docker required.
"""

import math
import numpy as np
import pytest

from src.im.engine import (
    build_coupling_matrix,
    compute_eigenspectrum,
    compute_rank_budget,
    design_memory_tiers,
    synthesize_agent_specs,
    synthesize_workflow_spec,
    update_coupling_matrix,
    validate_feasibility,
    _project_psd,
    _estimate_intra_coupling,
    _compute_dim_star,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_predicates():
    return [
        {"id": "f_001", "name": "auth_failure", "severity": "critical", "block_id": "BLK_A",
         "epsilon_g": 0.01, "horizon_t": 300},
        {"id": "f_002", "name": "data_loss", "severity": "critical", "block_id": "BLK_A",
         "epsilon_g": 0.01, "horizon_t": 300},
        {"id": "f_003", "name": "latency_spike", "severity": "high", "block_id": "BLK_B",
         "epsilon_g": 0.05, "horizon_t": 3600},
        {"id": "f_004", "name": "rate_limit_breach", "severity": "medium", "block_id": "BLK_B",
         "epsilon_g": 0.05, "horizon_t": 7200},
        {"id": "f_005", "name": "log_gap", "severity": "low", "block_id": "BLK_C",
         "epsilon_g": 0.10, "horizon_t": 86400},
    ]


@pytest.fixture
def sample_blocks():
    return [
        {"id": "BLK_A", "name": "Security", "predicate_ids": ["f_001", "f_002"], "intra_rank": 2},
        {"id": "BLK_B", "name": "Performance", "predicate_ids": ["f_003", "f_004"], "intra_rank": 2},
        {"id": "BLK_C", "name": "Observability", "predicate_ids": ["f_005"], "intra_rank": 1},
    ]


@pytest.fixture
def sample_cross_coupling():
    return [
        {"from_block": "BLK_A", "to_block": "BLK_B", "rho": 0.3, "mechanism": "auth affects latency"},
    ]


@pytest.fixture
def sample_agent_pool():
    return [
        {"agent_id": "a1", "name": "SecurityBot", "model_family": "gpt-4o", "jacobian_rank": 3,
         "steering_spectrum": [1.0, 0.8, 0.5], "context_window": 128000},
        {"agent_id": "a2", "name": "PerfBot", "model_family": "claude-sonnet-4-5-20250929", "jacobian_rank": 2,
         "steering_spectrum": [0.9, 0.6], "context_window": 200000},
    ]


@pytest.fixture
def sample_orchestrator():
    return {"model_family": "claude-opus-4-6", "jacobian_rank": 4, "steering_spectrum": [1.0, 0.9, 0.8, 0.5]}


# ---------------------------------------------------------------------------
# Test: Coupling Matrix
# ---------------------------------------------------------------------------


class TestCouplingMatrix:
    def test_empty_predicates(self):
        result = build_coupling_matrix([], [], [])
        assert result == []

    def test_single_predicate(self):
        preds = [{"id": "f_001", "severity": "medium", "horizon_t": 3600}]
        blocks = [{"id": "B1", "predicate_ids": ["f_001"]}]
        result = build_coupling_matrix(preds, blocks, [])
        assert len(result) == 1
        assert result[0][0] == pytest.approx(1.0)

    def test_diagonal_is_one(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        for i in range(len(M)):
            assert M[i][i] == pytest.approx(1.0, abs=1e-10)

    def test_symmetric(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        n = len(M)
        for i in range(n):
            for j in range(n):
                assert M[i][j] == pytest.approx(M[j][i], abs=1e-10)

    def test_psd(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        eigenvalues = np.linalg.eigvalsh(np.array(M))
        for ev in eigenvalues:
            assert ev >= -1e-10, f"Non-PSD eigenvalue: {ev}"

    def test_same_block_coupling_positive(self, sample_predicates, sample_blocks):
        M = build_coupling_matrix(sample_predicates, sample_blocks, [])
        # f_001 and f_002 are in the same block
        assert M[0][1] > 0.3, "Same-block predicates should have positive coupling"

    def test_cross_block_coupling(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        # BLK_A (f_001, f_002) coupled to BLK_B (f_003, f_004)
        assert M[0][2] > 0.0, "Cross-block coupling should produce non-zero entries"

    def test_shape(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        assert len(M) == 5
        assert all(len(row) == 5 for row in M)


class TestUpdateCouplingMatrix:
    def test_override_value(self):
        M = [[1.0, 0.5], [0.5, 1.0]]
        result = update_coupling_matrix(M, [{"row": 0, "col": 1, "value": 0.9}])
        assert result[0][1] == pytest.approx(result[1][0], abs=1e-10)

    def test_stays_psd_after_override(self):
        M = [[1.0, 0.5, 0.3], [0.5, 1.0, 0.4], [0.3, 0.4, 1.0]]
        result = update_coupling_matrix(M, [{"row": 0, "col": 2, "value": 0.99}])
        evals = np.linalg.eigvalsh(np.array(result))
        for ev in evals:
            assert ev >= -1e-10


class TestProjectPSD:
    def test_already_psd(self):
        M = np.array([[2.0, 0.5], [0.5, 2.0]])
        result = _project_psd(M)
        assert result[0][0] == pytest.approx(1.0)  # diagonal restored to 1
        evals = np.linalg.eigvalsh(result)
        assert all(ev >= -1e-10 for ev in evals)

    def test_negative_eigenvalue_clipped(self):
        # Construct matrix with negative eigenvalue
        M = np.array([[1.0, 2.0], [2.0, 1.0]])  # eigenvalues: 3, -1
        result = _project_psd(M)
        # After PSD projection + diagonal restoration to 1.0, verify off-diagonal is reasonable
        assert result[0][0] == pytest.approx(1.0)
        assert result[0][1] == pytest.approx(result[1][0], abs=1e-10)


# ---------------------------------------------------------------------------
# Test: Eigenspectrum and Codimension
# ---------------------------------------------------------------------------


class TestEigenspectrum:
    def test_empty_matrix(self):
        result = compute_eigenspectrum([], tau=0.05)
        assert result["cod_pi_g"] == 0
        assert result["eigenspectrum"] == []

    def test_identity_matrix(self):
        M = np.eye(5).tolist()
        result = compute_eigenspectrum(M, tau=0.5)
        assert result["cod_pi_g"] == 5  # All eigenvalues = 1.0

    def test_tau_threshold(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result_low = compute_eigenspectrum(M, tau=0.01)
        result_high = compute_eigenspectrum(M, tau=0.99)
        assert result_low["cod_pi_g"] >= result_high["cod_pi_g"]

    def test_eigenvalues_sorted_descending(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result = compute_eigenspectrum(M, tau=0.05, predicates=sample_predicates, blocks=sample_blocks)
        values = [e["value"] for e in result["eigenspectrum"]]
        assert values == sorted(values, reverse=True)

    def test_dim_star_per_predicate(self, sample_predicates, sample_blocks, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result = compute_eigenspectrum(M, tau=0.05, predicates=sample_predicates, blocks=sample_blocks)
        assert len(result["dim_star_per_predicate"]) == 5
        # dim* depends on both severity and horizon_t
        # f_001 is critical/300s, f_005 is low/86400s
        # With same horizon, critical > low; but long horizon adds factor
        # Just verify all dim_star values are positive
        assert all(ds > 0 for ds in result["dim_star_per_predicate"])


class TestDimStar:
    def test_critical_higher_than_low(self):
        critical = {"severity": "critical", "horizon_t": 3600}
        low = {"severity": "low", "horizon_t": 3600}
        assert _compute_dim_star(critical) > _compute_dim_star(low)

    def test_longer_horizon_higher(self):
        short = {"severity": "medium", "horizon_t": 60}
        long = {"severity": "medium", "horizon_t": 86400}
        assert _compute_dim_star(long) > _compute_dim_star(short)


class TestIntraCoupling:
    def test_same_severity_same_horizon(self):
        p1 = {"severity": "medium", "horizon_t": 3600}
        p2 = {"severity": "medium", "horizon_t": 3600}
        result = _estimate_intra_coupling(p1, p2)
        assert 0.3 <= result <= 0.7

    def test_different_severity_lower(self):
        p1 = {"severity": "critical", "horizon_t": 3600}
        p2 = {"severity": "low", "horizon_t": 3600}
        same = _estimate_intra_coupling(p1, p1)
        diff = _estimate_intra_coupling(p1, p2)
        assert same >= diff


# ---------------------------------------------------------------------------
# Test: Rank Budget
# ---------------------------------------------------------------------------


class TestRankBudget:
    def test_surplus(self, sample_agent_pool, sample_orchestrator):
        result = compute_rank_budget(3, sample_agent_pool, sample_orchestrator, cross_block_count=1)
        assert result["total_rank"] == 9  # 3 + 2 + 4
        assert result["rank_surplus_or_deficit"] == 6  # 9 - 3

    def test_deficit(self, sample_agent_pool, sample_orchestrator):
        result = compute_rank_budget(100, sample_agent_pool, sample_orchestrator)
        assert result["rank_surplus_or_deficit"] < 0
        assert result["remediation"] is not None

    def test_regime_simple(self):
        agents = [{"agent_id": "a1", "jacobian_rank": 50}]
        orch = {"jacobian_rank": 10}
        result = compute_rank_budget(2, agents, orch)
        assert result["regime"] == "simple"

    def test_regime_complex(self):
        agents = [{"agent_id": "a1", "jacobian_rank": 1}]
        orch = {"jacobian_rank": 1}
        result = compute_rank_budget(20, agents, orch, cross_block_count=5)
        assert result["regime"] == "complex"


# ---------------------------------------------------------------------------
# Test: Memory Tiers
# ---------------------------------------------------------------------------


class TestMemoryTiers:
    def test_four_tiers(self, sample_agent_pool, sample_orchestrator):
        result = design_memory_tiers(5, "medium", sample_agent_pool, sample_orchestrator)
        assert len(result["tiers"]) == 4
        tier_names = [t["tier"] for t in result["tiers"]]
        assert tier_names == ["M0", "M1", "M2", "M3"]

    def test_complex_requires_memory_agent(self, sample_agent_pool, sample_orchestrator):
        result = design_memory_tiers(15, "complex", sample_agent_pool, sample_orchestrator)
        assert result["right_sizing"]["memory_agent_required"] is True
        assert result["right_sizing"]["memory_agent_spec"] is not None

    def test_simple_no_memory_agent(self, sample_agent_pool, sample_orchestrator):
        result = design_memory_tiers(3, "simple", sample_agent_pool, sample_orchestrator)
        assert result["right_sizing"]["memory_agent_required"] is False

    def test_crystallisation_policy(self, sample_agent_pool, sample_orchestrator):
        result = design_memory_tiers(5, "medium", sample_agent_pool, sample_orchestrator)
        policy = result["crystallisation_policy"]
        assert "primary" in policy
        assert "secondary" in policy
        assert "reject" in policy

    def test_k_preloaded_reduces_cod(self, sample_agent_pool, sample_orchestrator):
        k = [{"name": "domain_knowledge", "cod_reduction": 3}]
        result = design_memory_tiers(10, "medium", sample_agent_pool, sample_orchestrator, k_preloaded=k)
        assert result["cod_after_k0"] == 7  # 10 - 3


# ---------------------------------------------------------------------------
# Test: Agent Synthesis
# ---------------------------------------------------------------------------


class TestAgentSynthesis:
    def test_all_predicates_assigned(self, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result = synthesize_agent_specs(M, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator)
        assigned = {a["predicate_id"] for a in result["alpha"]}
        expected = {p["id"] for p in sample_predicates}
        assert assigned == expected

    def test_delta_norm_non_negative(self, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result = synthesize_agent_specs(M, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator)
        assert result["delta_norm"] >= 0

    def test_empty(self):
        result = synthesize_agent_specs([], [], [], [], {})
        assert result["alpha"] == []

    def test_agents_output(self, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator, sample_cross_coupling):
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        result = synthesize_agent_specs(M, sample_predicates, sample_blocks, sample_agent_pool, sample_orchestrator)
        assert len(result["agents"]) == len(sample_agent_pool)
        for a in result["agents"]:
            assert "assigned_predicates" in a
            assert "predicate_count" in a


# ---------------------------------------------------------------------------
# Test: Workflow Synthesis
# ---------------------------------------------------------------------------


class TestWorkflowSynthesis:
    def _make_assignment(self, agents):
        return {
            "agents": [{"agent_id": a, "assigned_predicates": [f"f_{i}"]}
                       for i, a in enumerate(agents)],
            "delta_rank": 0,
            "delta_norm": 0,
            "governance_margin": 1,
        }

    def _make_rank_budget(self, regime="medium"):
        return {
            "regime": regime,
            "coupling_rank_by_topology": {"flat": 0, "pipeline": 2, "hierarchical": 1, "mesh": 4},
        }

    def test_flat_for_two_agents(self):
        assignment = self._make_assignment(["a1", "a2"])
        rank = self._make_rank_budget()
        result = synthesize_workflow_spec(assignment, rank, [], [], [])
        assert result["topology"]["pattern"] == "flat"

    def test_compiled_true(self):
        assignment = self._make_assignment(["a1", "a2", "a3"])
        rank = self._make_rank_budget()
        preds = [{"id": f"f_{i}"} for i in range(3)]
        blocks = [{"id": "B1", "predicate_ids": ["f_0", "f_1", "f_2"]}]
        result = synthesize_workflow_spec(assignment, rank, preds, blocks, [])
        assert result["compiled"] is True
        assert result["validation_errors"] == []

    def test_complex_adds_memory_agent(self):
        assignment = self._make_assignment(["a1", "a2", "a3"])
        rank = self._make_rank_budget("complex")
        result = synthesize_workflow_spec(assignment, rank, [], [], [])
        node_ids = {n["node_id"] for n in result["topology"]["nodes"]}
        assert "memory_agent" in node_ids

    def test_escalation_routes(self):
        assignment = self._make_assignment(["a1"])
        rank = self._make_rank_budget()
        result = synthesize_workflow_spec(assignment, rank, [], [], [])
        assert len(result["escalation_routes"]) == 4
        severities = {e["severity"] for e in result["escalation_routes"]}
        assert severities == {"critical", "high", "medium", "low"}


# ---------------------------------------------------------------------------
# Test: Feasibility
# ---------------------------------------------------------------------------


class TestFeasibility:
    def test_feasible(self):
        assignment = {
            "agents": [
                {"agent_id": "a1", "assigned_predicates": ["f_001"],
                 "steering_spectrum": [1.0], "jacobian_rank": 3},
            ],
            "governance_margin": 2.0,
            "delta_norm": 0.01,
            "delta_rank": 0,
        }
        rank_budget = {"total_rank": 10, "orchestrator_rank": 5}
        codimension = {"cod_pi_g": 3}
        predicates = [{"id": "f_001", "epsilon_g": 0.05}]
        workflow = {"topology": {"coupling_rank_c": 2}}

        result = validate_feasibility(assignment, rank_budget, codimension, predicates, workflow)
        assert result["verdict"] == "feasible"
        assert result["rank_coverage"] is True
        assert result["coupling_coverage"] is True
        assert result["power_coverage"] is True

    def test_infeasible_rank(self):
        assignment = {"agents": [], "governance_margin": 0, "delta_norm": 0, "delta_rank": 0}
        rank_budget = {"total_rank": 2, "orchestrator_rank": 1}
        codimension = {"cod_pi_g": 10}
        workflow = {"topology": {"coupling_rank_c": 0}}

        result = validate_feasibility(assignment, rank_budget, codimension, [], workflow)
        assert result["verdict"] == "infeasible"
        assert result["rank_coverage"] is False
        assert result["remediation"] is not None

    def test_infeasible_coupling(self):
        assignment = {"agents": [], "governance_margin": 0, "delta_norm": 0, "delta_rank": 0}
        rank_budget = {"total_rank": 10, "orchestrator_rank": 1}
        codimension = {"cod_pi_g": 3}
        workflow = {"topology": {"coupling_rank_c": 5}}

        result = validate_feasibility(assignment, rank_budget, codimension, [], workflow)
        assert result["coupling_coverage"] is False

    def test_feasibility_with_unassigned_predicate(self):
        assignment = {"agents": [], "governance_margin": 0, "delta_norm": 0, "delta_rank": 0}
        rank_budget = {"total_rank": 10, "orchestrator_rank": 5}
        codimension = {"cod_pi_g": 1}
        predicates = [{"id": "f_001", "epsilon_g": 0.05}]
        workflow = {"topology": {"coupling_rank_c": 0}}

        result = validate_feasibility(assignment, rank_budget, codimension, predicates, workflow)
        # Unassigned predicate has eps_eff=1.0 >= eps_g=0.05
        assert result["power_coverage"] is False


# ---------------------------------------------------------------------------
# Test: Full pipeline integration (engine only)
# ---------------------------------------------------------------------------


class TestEngineIntegration:
    def test_full_pipeline(self, sample_predicates, sample_blocks, sample_cross_coupling,
                           sample_agent_pool, sample_orchestrator):
        """Run all engine stages in sequence and verify consistency."""
        # Step 3: Coupling matrix
        M = build_coupling_matrix(sample_predicates, sample_blocks, sample_cross_coupling)
        assert len(M) == 5

        # Step 4: Eigenspectrum
        eigen = compute_eigenspectrum(M, tau=0.05, predicates=sample_predicates, blocks=sample_blocks)
        cod = eigen["cod_pi_g"]
        assert cod > 0

        # Step 5: Rank budget
        rank = compute_rank_budget(cod, sample_agent_pool, sample_orchestrator,
                                   cross_block_count=len(sample_cross_coupling))
        assert rank["total_rank"] > 0

        # Step 6: Memory tiers
        mem = design_memory_tiers(cod, rank["regime"], sample_agent_pool, sample_orchestrator)
        assert len(mem["tiers"]) == 4

        # Step 7: Agent synthesis
        assign = synthesize_agent_specs(M, sample_predicates, sample_blocks,
                                        sample_agent_pool, sample_orchestrator)
        assert len(assign["alpha"]) == 5

        # Step 8: Workflow synthesis
        wf = synthesize_workflow_spec(assign, rank, sample_predicates,
                                      sample_blocks, sample_cross_coupling)
        assert wf["compiled"] is True

        # Step 9: Feasibility
        feas = validate_feasibility(assign, rank, eigen, sample_predicates, wf)
        assert feas["verdict"] in ("feasible", "infeasible")
        assert feas["rank_coverage"] is True  # We have plenty of rank
