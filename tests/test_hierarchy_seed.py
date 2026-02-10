"""Tests for hierarchy seed data consistency."""

import os
import pytest

os.environ.setdefault("TESTING", "1")

from src.hierarchy.seed import (
    _AGENTS,
    _BLOCKS,
    _COUPLING_AXES,
    _EIGENVALUES,
    _MODULES,
    _ORCHESTRATORS,
    _PREDICATES,
)


class TestSeedData:
    def test_predicate_count(self):
        """37 predicates total in the hierarchy."""
        assert len(_PREDICATES) == 37

    def test_predicate_indices_unique(self):
        indices = [p.index for p in _PREDICATES]
        assert len(set(indices)) == len(indices)

    def test_predicate_levels_valid(self):
        for p in _PREDICATES:
            assert 0 <= p.level <= 6

    def test_celestial_predicates_count(self):
        celestial = [p for p in _PREDICATES if p.level <= 4]
        assert len(celestial) == 23

    def test_terrestrial_predicates_count(self):
        terrestrial = [p for p in _PREDICATES if p.level >= 5]
        assert len(terrestrial) == 14

    def test_level0_count(self):
        l0 = [p for p in _PREDICATES if p.level == 0]
        assert len(l0) == 5

    def test_level5_count(self):
        l5 = [p for p in _PREDICATES if p.level == 5]
        assert len(l5) == 10  # 5 profit + 5 readiness

    def test_level6_count(self):
        l6 = [p for p in _PREDICATES if p.level == 6]
        assert len(l6) == 4

    def test_block_count(self):
        assert len(_BLOCKS) == 10

    def test_block_ids_unique(self):
        ids = [b.block_id for b in _BLOCKS]
        assert len(set(ids)) == len(ids)

    def test_all_predicates_in_blocks(self):
        block_preds = set()
        for b in _BLOCKS:
            block_preds.update(b.predicate_indices)
        pred_indices = {p.index for p in _PREDICATES}
        assert block_preds == pred_indices

    def test_agent_count(self):
        assert len(_AGENTS) == 9

    def test_agent_ids_unique(self):
        ids = [a.agent_id for a in _AGENTS]
        assert len(set(ids)) == len(ids)

    def test_all_predicates_assigned_to_agents(self):
        agent_preds = set()
        for a in _AGENTS:
            agent_preds.update(a.predicates)
        pred_indices = {p.index for p in _PREDICATES}
        assert agent_preds == pred_indices

    def test_orchestrator_count(self):
        assert len(_ORCHESTRATORS) == 3

    def test_orchestrator_ids(self):
        ids = {o.orchestrator_id for o in _ORCHESTRATORS}
        assert ids == {"O1", "O2", "O3"}

    def test_o1_governs_all_agents(self):
        o1 = next(o for o in _ORCHESTRATORS if o.orchestrator_id == "O1")
        assert len(o1.governed_agents) == 9

    def test_o3_rank(self):
        o3 = next(o for o in _ORCHESTRATORS if o.orchestrator_id == "O3")
        assert o3.rank == 3

    def test_module_count(self):
        assert len(_MODULES) == 3

    def test_module_ids(self):
        ids = {m.module_id for m in _MODULES}
        assert ids == {"profit-ecommerce", "readiness-squadron", "personality-humor"}

    def test_personality_has_upward_channels(self):
        pers = next(m for m in _MODULES if m.module_id == "personality-humor")
        assert "UC-1" in pers.upward_channels
        assert "UC-2" in pers.upward_channels

    def test_eigenvalue_count(self):
        assert len(_EIGENVALUES) == 19

    def test_eigenvalues_sorted_by_index(self):
        indices = [e.index for e in _EIGENVALUES]
        assert indices == sorted(indices)

    def test_eigenvalue_layers(self):
        celestial = [e for e in _EIGENVALUES if e.layer == "celestial"]
        terrestrial = [e for e in _EIGENVALUES if e.layer == "terrestrial"]
        assert len(celestial) == 11
        assert len(terrestrial) == 8

    def test_cod_g_is_19(self):
        """cod(G) = 19 (documented in goal-integration.md)."""
        assert len(_EIGENVALUES) == 19

    def test_epsilon_floors(self):
        """Level 5: eps_dmg >= 0.10, Level 6: eps_dmg >= 0.30."""
        for p in _PREDICATES:
            if p.level == 5:
                assert p.epsilon_dmg >= 0.10, f"f{p.index} eps_dmg={p.epsilon_dmg} < 0.10"
            if p.level == 6:
                assert p.epsilon_dmg >= 0.30, f"f{p.index} eps_dmg={p.epsilon_dmg} < 0.30"

    def test_upward_coupling_budget(self):
        """Only 2 upward channels allowed."""
        upward = [a for a in _COUPLING_AXES if a.axis_type == "upward"]
        assert len(upward) == 2

    def test_coupling_axes_rho_range(self):
        for a in _COUPLING_AXES:
            assert -1.0 <= a.rho <= 1.0, f"rho={a.rho} out of range"

    def test_rank_coverage_passes(self):
        """Statement 55: sum(agent ranks) + sum(orch ranks) >= cod(G)."""
        sum_agent = sum(a.rank for a in _AGENTS)
        sum_orch = sum(o.rank for o in _ORCHESTRATORS)
        cod_g = len(_EIGENVALUES)
        assert sum_agent + sum_orch >= cod_g, (
            f"Rank coverage fails: {sum_agent}+{sum_orch}={sum_agent + sum_orch} < {cod_g}"
        )
