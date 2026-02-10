"""Tests for hierarchy data models."""

import os
import pytest
from datetime import datetime, timezone

os.environ.setdefault("TESTING", "1")

from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    FeasibilityResult,
    GateStatus,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyOrchestrator,
    HierarchyPredicate,
    TerrestrialModule,
)


class TestHierarchyPredicate:
    def test_basic_construction(self):
        p = HierarchyPredicate(
            index=1, name="Truthfulness", level=0, block="A",
            pass_condition="All outputs faithful to known facts",
            variance=0.04, epsilon_dmg=0.01, agent_id="a1",
        )
        assert p.index == 1
        assert p.name == "Truthfulness"
        assert p.level == 0
        assert p.block == "A"
        assert p.epsilon_dmg == 0.01
        assert p.agent_id == "a1"
        assert p.module_id is None
        assert p.current_value is None

    def test_terrestrial_predicate(self):
        p = HierarchyPredicate(
            index=24, name="Revenue generation", level=5, block="H",
            pass_condition="Revenue exceeds threshold",
            variance=0.13, epsilon_dmg=0.20, agent_id="a7",
            module_id="profit-ecommerce",
        )
        assert p.module_id == "profit-ecommerce"

    def test_with_observation(self):
        now = datetime.now(timezone.utc)
        p = HierarchyPredicate(
            index=1, name="Truthfulness", level=0, block="A",
            pass_condition="All outputs faithful",
            variance=0.04, epsilon_dmg=0.01, agent_id="a1",
            current_value=0.95, last_observed=now,
        )
        assert p.current_value == 0.95
        assert p.last_observed == now


class TestCouplingAxis:
    def test_intra_block(self):
        a = CouplingAxis(1, 2, 0.6, "intra-block")
        assert a.source_predicate == 1
        assert a.target_predicate == 2
        assert a.rho == 0.6
        assert a.channel_id is None

    def test_upward_coupling(self):
        a = CouplingAxis(29, 10, 0.3, "upward", "UC-1")
        assert a.axis_type == "upward"
        assert a.channel_id == "UC-1"


class TestHierarchyBlock:
    def test_basic(self):
        b = HierarchyBlock("A", "Transcendent", 0, [1, 2, 5], 2)
        assert b.block_id == "A"
        assert len(b.predicate_indices) == 3
        assert b.rank == 2
        assert b.module_id is None

    def test_terrestrial_block(self):
        b = HierarchyBlock("H", "Profit", 5, [24, 25, 26, 27, 28], 3, "profit-ecommerce")
        assert b.module_id == "profit-ecommerce"


class TestHierarchyAgent:
    def test_celestial_agent(self):
        a = HierarchyAgent("a1", "Transcendent Integrity", [1, 2, 5], 2, 3, 8e3, "celestial")
        assert a.layer == "celestial"
        assert a.sigma_max == 8000.0

    def test_terrestrial_agent(self):
        a = HierarchyAgent("a7", "Profit Agent", [24, 25, 26, 27, 28], 3, 4, 1e4, "terrestrial")
        assert a.layer == "terrestrial"


class TestOrchestrator:
    def test_moral_governor(self):
        o = HierarchyOrchestrator(
            "O1", "Moral Governor", 6,
            ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9"],
            "Lexicographic gate enforcement",
        )
        assert o.rank == 6
        assert len(o.governed_agents) == 9


class TestTerrestrialModule:
    def test_basic(self):
        m = TerrestrialModule(
            "profit-ecommerce", "Profit (E-Commerce)", 5, "Active",
            [24, 25, 26, 27, 28], "a7", [],
        )
        assert m.status == "Active"
        assert len(m.predicate_indices) == 5

    def test_with_upward_channels(self):
        m = TerrestrialModule(
            "personality-humor", "Personality", 6, "Active",
            [29, 30, 31, 32], "a8", ["UC-1", "UC-2"],
        )
        assert len(m.upward_channels) == 2


class TestEigenvalue:
    def test_basic(self):
        e = Eigenvalue(1, 0.52, [24, 26, 28], "Profit engine mode", "terrestrial")
        assert e.value == 0.52
        assert e.layer == "terrestrial"


class TestFeasibilityResult:
    def test_pass(self):
        r = FeasibilityResult(
            rank_coverage=True, coupling_coverage=True,
            epsilon_check=True, overall=True,
        )
        assert r.overall is True

    def test_fail(self):
        r = FeasibilityResult(
            rank_coverage=True, coupling_coverage=False,
            epsilon_check=True, overall=False,
        )
        assert r.overall is False


class TestGateStatus:
    def test_open(self):
        gs = GateStatus(level=0, is_open=True, failing_predicates=[])
        assert gs.is_open is True

    def test_closed(self):
        gs = GateStatus(level=5, is_open=False, failing_predicates=[1, 2])
        assert gs.is_open is False
        assert gs.failing_predicates == [1, 2]
