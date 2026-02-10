"""Tests for hierarchy computation engine."""

import os
import pytest
import numpy as np
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "1")

from src.hierarchy.engine import (
    build_coupling_matrix,
    check_o3_rank,
    compute_cod_g,
    compute_eigenspectrum,
    evaluate_gate,
    verify_feasibility,
)
from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyOrchestrator,
    HierarchyPredicate,
)


def _make_predicate(index, level=0, block="A", agent="a1", eps_dmg=0.01, variance=0.04,
                    current_value=None, module_id=None):
    return HierarchyPredicate(
        index=index, name=f"pred_{index}", level=level, block=block,
        pass_condition="test", variance=variance, epsilon_dmg=eps_dmg,
        agent_id=agent, module_id=module_id, current_value=current_value,
    )


class TestBuildCouplingMatrix:
    def test_diagonal_identity(self):
        preds = [_make_predicate(1), _make_predicate(2)]
        M = build_coupling_matrix(preds, [])
        assert M.shape == (2, 2)
        np.testing.assert_array_equal(np.diag(M), [1.0, 1.0])

    def test_single_axis(self):
        preds = [_make_predicate(1), _make_predicate(2)]
        axes = [CouplingAxis(1, 2, 0.6, "intra-block")]
        M = build_coupling_matrix(preds, axes)
        assert M[0, 1] == pytest.approx(0.6)
        assert M[1, 0] == pytest.approx(0.6)  # symmetric

    def test_three_predicates(self):
        preds = [_make_predicate(1), _make_predicate(2), _make_predicate(3)]
        axes = [
            CouplingAxis(1, 2, 0.6, "intra-block"),
            CouplingAxis(2, 3, 0.4, "intra-block"),
        ]
        M = build_coupling_matrix(preds, axes)
        assert M.shape == (3, 3)
        assert M[0, 1] == pytest.approx(0.6)
        assert M[1, 2] == pytest.approx(0.4)
        assert M[0, 2] == pytest.approx(0.0)  # no direct coupling


class TestComputeEigenspectrum:
    def test_identity_matrix(self):
        M = np.eye(3)
        results = compute_eigenspectrum(M, tau=0.5)
        assert len(results) == 3
        for val, vec in results:
            assert val == pytest.approx(1.0)

    def test_threshold_filtering(self):
        M = np.diag([0.5, 0.005, 1.0])
        results = compute_eigenspectrum(M, tau=0.01)
        assert len(results) == 2  # 0.005 is below tau
        assert results[0][0] == pytest.approx(1.0)
        assert results[1][0] == pytest.approx(0.5)

    def test_correlated_matrix(self):
        M = np.array([
            [1.0, 0.8],
            [0.8, 1.0],
        ])
        results = compute_eigenspectrum(M, tau=0.01)
        # Should get 2 eigenvalues: 1.8 and 0.2
        assert len(results) == 2
        assert results[0][0] == pytest.approx(1.8, rel=0.01)
        assert results[1][0] == pytest.approx(0.2, rel=0.01)


class TestComputeCodG:
    def test_empty(self):
        assert compute_cod_g([]) == 0

    def test_with_eigenvalues(self):
        evs = [Eigenvalue(i, 0.1 * i, [], "", "celestial") for i in range(1, 5)]
        assert compute_cod_g(evs) == 4


class TestEvaluateGate:
    def test_all_unobserved_gates_open(self):
        preds = [
            _make_predicate(1, level=0),
            _make_predicate(6, level=1),
            _make_predicate(10, level=2),
        ]
        gate = evaluate_gate(preds)
        assert len(gate) == 3
        for gs in gate.values():
            assert gs.is_open is True

    def test_gate_closes_on_failure(self):
        preds = [
            _make_predicate(1, level=0, eps_dmg=0.01, current_value=0.5),  # fails: 0.5 < 0.99
            _make_predicate(6, level=1),
        ]
        gate = evaluate_gate(preds)
        assert gate[0].is_open is True  # level 0 has no levels below it
        assert gate[1].is_open is False  # level 1 gate closed: f1 failing at L0
        assert gate[1].failing_predicates == [1]

    def test_gate_open_when_within_tolerance(self):
        preds = [
            _make_predicate(1, level=0, eps_dmg=0.20, current_value=0.85),  # passes: 0.85 >= 0.80
            _make_predicate(6, level=1),
        ]
        gate = evaluate_gate(preds)
        assert gate[1].is_open is True

    def test_multiple_failures(self):
        preds = [
            _make_predicate(1, level=0, eps_dmg=0.01, current_value=0.5),
            _make_predicate(2, level=0, eps_dmg=0.01, current_value=0.3),
            _make_predicate(6, level=1),
        ]
        gate = evaluate_gate(preds)
        assert gate[1].is_open is False
        assert set(gate[1].failing_predicates) == {1, 2}

    def test_terrestrial_gate(self):
        preds = [
            _make_predicate(1, level=0, current_value=1.0),  # L0 passes
            _make_predicate(6, level=1, current_value=1.0),  # L1 passes
            _make_predicate(10, level=2, current_value=1.0),  # L2 passes
            _make_predicate(14, level=3, current_value=1.0),  # L3 passes
            _make_predicate(19, level=4, eps_dmg=0.10, current_value=0.5),  # L4 fails
            _make_predicate(24, level=5),  # L5 should be gated
        ]
        gate = evaluate_gate(preds)
        assert gate[5].is_open is False  # L5 closed because L4 failed
        assert gate[5].failing_predicates == [19]


class TestVerifyFeasibility:
    def _simple_system(self):
        preds = [_make_predicate(1, agent="a1")]
        blocks = [HierarchyBlock("A", "Test", 0, [1], 1)]
        agents = [HierarchyAgent("a1", "Agent 1", [1], 1, 1, 1e4, "celestial")]
        orchestrators = [HierarchyOrchestrator("O1", "Governor", 2, ["a1"], "test")]
        eigenvalues = [Eigenvalue(1, 0.5, [1], "test mode", "celestial")]
        axes = []
        return preds, blocks, agents, orchestrators, eigenvalues, axes

    def test_simple_pass(self):
        result = verify_feasibility(*self._simple_system())
        assert result.overall is True
        assert result.rank_coverage is True
        assert result.coupling_coverage is True
        assert result.epsilon_check is True

    def test_rank_failure(self):
        preds, blocks, agents, orchestrators, eigenvalues, axes = self._simple_system()
        # Add many eigenvalues to exceed rank
        eigenvalues = [Eigenvalue(i, 0.1, [], "", "celestial") for i in range(1, 20)]
        result = verify_feasibility(preds, blocks, agents, orchestrators, eigenvalues, axes)
        assert result.rank_coverage is False
        assert result.overall is False

    def test_epsilon_failure(self):
        preds = [_make_predicate(1, agent="a1", variance=100.0, eps_dmg=0.001)]
        blocks = [HierarchyBlock("A", "Test", 0, [1], 1)]
        agents = [HierarchyAgent("a1", "Agent 1", [1], 1, 1, 10.0, "celestial")]  # low sigma
        orchestrators = [HierarchyOrchestrator("O1", "Gov", 2, ["a1"], "test")]
        eigenvalues = [Eigenvalue(1, 0.5, [1], "test", "celestial")]
        result = verify_feasibility(preds, blocks, agents, orchestrators, eigenvalues, [])
        assert result.epsilon_check is False


class TestCheckO3Rank:
    def test_pass(self):
        result = check_o3_rank(2, 1, 3)
        assert result["passes"] is True
        assert result["margin"] == 0

    def test_fail(self):
        result = check_o3_rank(2, 2, 3)
        assert result["passes"] is False
        assert result["margin"] == -1

    def test_comfortable(self):
        result = check_o3_rank(2, 1, 5)
        assert result["passes"] is True
        assert result["margin"] == 2
