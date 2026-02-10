"""End-to-end proof: Solana Mining Terrestrial Module.

Demonstrates the full goal hierarchy lifecycle:
1. Define a new Terrestrial module with 5 predicates (f38–f42)
2. Register predicates, block, agent, module, coupling axes
3. Compute eigenspectrum — verify new eigenvalues appear
4. Verify feasibility (Statement 55) still passes
5. Evaluate gate — show L5 gate is open
6. Fail a Celestial predicate → L5 gate closes → mining blocked
7. Restore predicate → gate reopens
8. Deactivate module → verify cleanup
"""

import os
from copy import deepcopy

import pytest

os.environ.setdefault("TESTING", "1")

from src.hierarchy.engine import (
    build_coupling_matrix,
    compute_cod_g,
    compute_eigenspectrum,
    evaluate_gate,
    verify_feasibility,
)
from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    GateStatus,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyPredicate,
    TerrestrialModule,
)
from src.hierarchy.seed import (
    _AGENTS,
    _BLOCKS,
    _COUPLING_AXES,
    _EIGENVALUES,
    _MODULES,
    _ORCHESTRATORS,
    _PREDICATES,
)

# ======================================================================
# Solana Mining Module definition
# ======================================================================

# 5 new predicates at Level 5 (Profit class) — indices f38–f42
SOLANA_PREDICATES = [
    HierarchyPredicate(
        38, "Hash-rate efficiency", 5, "K",
        "Mining output per kWh ≥ industry median for selected algorithm",
        0.10, 0.12, "a10", "solana-mining",
    ),
    HierarchyPredicate(
        39, "Wallet security", 5, "K",
        "All Solana wallets use hardware signing; no hot-wallet private keys in memory",
        0.05, 0.10, "a10", "solana-mining",
    ),
    HierarchyPredicate(
        40, "Staking yield", 5, "K",
        "Annualized staking APY ≥ network average minus 1σ",
        0.08, 0.15, "a10", "solana-mining",
    ),
    HierarchyPredicate(
        41, "Validator uptime", 5, "K",
        "Solana validator node uptime ≥ 99.5% over trailing 7 days",
        0.03, 0.10, "a10", "solana-mining",
    ),
    HierarchyPredicate(
        42, "Energy ROI", 5, "K",
        "Net SOL revenue exceeds electricity + hardware depreciation cost",
        0.12, 0.15, "a10", "solana-mining",
    ),
]

SOLANA_BLOCK = HierarchyBlock(
    "K", "Solana Mining", 5, [38, 39, 40, 41, 42], 3, "solana-mining",
)

SOLANA_AGENT = HierarchyAgent(
    "a10", "Solana Mining Agent", [38, 39, 40, 41, 42], 3, 4, 8e3, "terrestrial",
)

SOLANA_MODULE = TerrestrialModule(
    "solana-mining", "Solana Mining", 5, "Active",
    [38, 39, 40, 41, 42], "a10", [],
)

# Intra-block coupling within Solana predicates
SOLANA_COUPLING = [
    CouplingAxis(38, 42, 0.7, "intra-block"),   # hash-rate ↔ energy ROI (high)
    CouplingAxis(40, 42, 0.6, "intra-block"),   # staking yield ↔ energy ROI
    CouplingAxis(38, 40, 0.4, "intra-block"),   # hash-rate ↔ staking yield
    CouplingAxis(39, 41, 0.3, "intra-block"),   # wallet security ↔ validator uptime
    CouplingAxis(38, 41, 0.5, "intra-block"),   # hash-rate ↔ validator uptime
    # Cross-block: Solana mining → existing profit block
    CouplingAxis(42, 24, 0.5, "terrestrial-internal", "TC-2"),  # energy ROI → revenue growth
    # Downward from self-preservation → Solana
    CouplingAxis(19, 38, 0.4, "downward", "DC-2"),  # system health → hash-rate
]

# New eigenvalue for the Solana mining mode
SOLANA_EIGENVALUE = Eigenvalue(
    20, 0.45, [38, 40, 42],
    "Solana mining profitability mode — hash-rate/yield/ROI triad",
    "terrestrial",
)


def _all_predicates():
    """All predicates including Solana — deep-copied to avoid test pollution."""
    return [deepcopy(p) for p in _PREDICATES] + [deepcopy(p) for p in SOLANA_PREDICATES]


def _all_blocks():
    return [deepcopy(b) for b in _BLOCKS] + [deepcopy(SOLANA_BLOCK)]


def _all_agents():
    return [deepcopy(a) for a in _AGENTS] + [deepcopy(SOLANA_AGENT)]


def _all_coupling():
    return [deepcopy(a) for a in _COUPLING_AXES] + [deepcopy(a) for a in SOLANA_COUPLING]


def _all_eigenvalues():
    return [deepcopy(e) for e in _EIGENVALUES] + [deepcopy(SOLANA_EIGENVALUE)]


def _all_modules():
    return [deepcopy(m) for m in _MODULES] + [deepcopy(SOLANA_MODULE)]


# ======================================================================
# Tests
# ======================================================================


class TestSolanaModuleDefinition:
    """Verify the Solana module is self-consistent."""

    def test_five_predicates(self):
        assert len(SOLANA_PREDICATES) == 5

    def test_predicate_indices(self):
        assert [p.index for p in SOLANA_PREDICATES] == [38, 39, 40, 41, 42]

    def test_all_level_5(self):
        for p in SOLANA_PREDICATES:
            assert p.level == 5

    def test_all_block_K(self):
        for p in SOLANA_PREDICATES:
            assert p.block == "K"

    def test_all_assigned_to_a10(self):
        for p in SOLANA_PREDICATES:
            assert p.agent_id == "a10"

    def test_all_module_id(self):
        for p in SOLANA_PREDICATES:
            assert p.module_id == "solana-mining"

    def test_epsilon_floors(self):
        """L5 predicates must have eps_dmg >= 0.10."""
        for p in SOLANA_PREDICATES:
            assert p.epsilon_dmg >= 0.10, f"f{p.index} eps_dmg={p.epsilon_dmg} < 0.10"

    def test_block_covers_all_predicates(self):
        assert set(SOLANA_BLOCK.predicate_indices) == {38, 39, 40, 41, 42}

    def test_agent_covers_all_predicates(self):
        assert set(SOLANA_AGENT.predicates) == {38, 39, 40, 41, 42}

    def test_module_covers_all_predicates(self):
        assert set(SOLANA_MODULE.predicate_indices) == {38, 39, 40, 41, 42}

    def test_no_upward_channels(self):
        """Solana mining has no upward coupling to Celestial."""
        assert SOLANA_MODULE.upward_channels == []


class TestSolanaEigenspectrum:
    """Verify Solana predicates integrate into the coupling matrix and eigenspectrum."""

    def test_coupling_matrix_size(self):
        """Matrix grows from 37×37 to 42×42."""
        M = build_coupling_matrix(_all_predicates(), _all_coupling())
        assert M.shape == (42, 42)

    def test_coupling_matrix_symmetric(self):
        M = build_coupling_matrix(_all_predicates(), _all_coupling())
        assert (M == M.T).all()

    def test_coupling_matrix_diagonal_ones(self):
        M = build_coupling_matrix(_all_predicates(), _all_coupling())
        for i in range(42):
            assert M[i, i] == 1.0

    def test_intra_block_coupling_exists(self):
        """Hash-rate ↔ Energy ROI should have ρ=0.7."""
        M = build_coupling_matrix(_all_predicates(), _all_coupling())
        # Index 38 maps to position 37 (0-indexed), 42 to 41
        assert M[37, 41] == 0.7
        assert M[41, 37] == 0.7

    def test_eigenspectrum_count_increases(self):
        """Adding correlated predicates should produce more significant eigenvalues."""
        # Original
        M_orig = build_coupling_matrix(list(_PREDICATES), list(_COUPLING_AXES))
        eigs_orig = compute_eigenspectrum(M_orig)

        # With Solana
        M_new = build_coupling_matrix(_all_predicates(), _all_coupling())
        eigs_new = compute_eigenspectrum(M_new)

        assert len(eigs_new) > len(eigs_orig)

    def test_cod_g_increases(self):
        """cod(G) grows from 19 to 20 with the Solana eigenvalue."""
        assert compute_cod_g(_all_eigenvalues()) == 20

    def test_solana_eigenvalue_is_terrestrial(self):
        assert SOLANA_EIGENVALUE.layer == "terrestrial"

    def test_solana_eigenvalue_value(self):
        """λ₂₀ = 0.45 (between existing λ₁ profit at 0.52 and λ₂ org-health at 0.48)."""
        assert SOLANA_EIGENVALUE.value == 0.45


class TestSolanaFeasibility:
    """Verify Statement 55 feasibility with the Solana module added."""

    def test_feasibility_passes(self):
        """Full hierarchy + Solana mining still feasible."""
        result = verify_feasibility(
            _all_predicates(),
            _all_blocks(),
            _all_agents(),
            list(_ORCHESTRATORS),
            _all_eigenvalues(),
            _all_coupling(),
        )
        assert result.overall is True
        assert result.rank_coverage is True
        assert result.coupling_coverage is True
        assert result.epsilon_check is True

    def test_rank_coverage_margin(self):
        """Σ(agent ranks) + Σ(orch ranks) ≥ cod(G) = 20."""
        result = verify_feasibility(
            _all_predicates(), _all_blocks(), _all_agents(),
            list(_ORCHESTRATORS), _all_eigenvalues(), _all_coupling(),
        )
        rank_info = result.details["rank"]
        # Original: agents=23, orch=12, total=35 vs cod(G)=19
        # With Solana: agents=26 (+3 from a10), orch=12, total=38 vs cod(G)=20
        assert rank_info["total"] >= rank_info["cod_g"]
        assert rank_info["margin"] >= 0

    def test_epsilon_check_passes(self):
        """All Solana predicates have variance/sigma_max < eps_dmg."""
        result = verify_feasibility(
            _all_predicates(), _all_blocks(), _all_agents(),
            list(_ORCHESTRATORS), _all_eigenvalues(), _all_coupling(),
        )
        # Verify no Solana predicates are in epsilon failures
        eps_failures = result.details["epsilon"]["failures"]
        solana_fails = [f for f in eps_failures if f["predicate"] in {38, 39, 40, 41, 42}]
        assert len(solana_fails) == 0


class TestSolanaGateBehavior:
    """Verify the lexicographic gate blocks/allows mining based on Celestial health."""

    def test_gate_open_when_celestial_passing(self):
        """All predicates unobserved → all gates open (including L5 for mining)."""
        preds = _all_predicates()
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True
        assert gate[5].failing_predicates == []

    def test_gate_open_with_observations(self):
        """Set all Celestial to 1.0 → L5 gate stays open."""
        preds = _all_predicates()
        for p in preds:
            if p.level <= 4:
                p.current_value = 1.0
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True

    def test_gate_closes_when_conscience_fails(self):
        """Fail a Level 1 (Conscience) predicate → L5 gate closes → mining blocked."""
        preds = _all_predicates()
        # f6 = "Principled alignment" at Level 1, eps_dmg=0.02
        for p in preds:
            if p.index == 6:
                p.current_value = 0.5  # Way below threshold (1.0 - 0.02 = 0.98)
        gate = evaluate_gate(preds)
        # L5 gate checks levels 0..4 — Level 1 failing means L2+ gates close
        assert gate[5].is_open is False
        assert 6 in gate[5].failing_predicates

    def test_gate_closes_when_nonmaleficence_fails(self):
        """Fail a Level 2 (Nonmaleficence) predicate → L5 gate closes."""
        preds = _all_predicates()
        # f10 = "No intended harm" at Level 2, eps_dmg=0.02
        for p in preds:
            if p.index == 10:
                p.current_value = 0.0  # Complete failure
        gate = evaluate_gate(preds)
        assert gate[5].is_open is False
        assert 10 in gate[5].failing_predicates

    def test_gate_stays_open_if_l5_predicate_fails(self):
        """A Level 5 predicate failing does NOT close the L5 gate.

        This is key: L5 gate only checks levels 0..4.
        A failing Solana predicate (L5) doesn't close its own gate.
        """
        preds = _all_predicates()
        # Fail f38 (hash-rate efficiency) at Level 5
        for p in preds:
            if p.index == 38:
                p.current_value = 0.0
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True  # L5 gate still open

    def test_l6_gate_closes_when_l5_fails(self):
        """A Level 5 predicate failing DOES close the L6 gate.

        L6 gate checks levels 0..5. So Solana mining predicate failure
        blocks Personality execution but not other mining.
        """
        preds = _all_predicates()
        for p in preds:
            if p.index == 38:
                p.current_value = 0.0  # hash-rate fails
        gate = evaluate_gate(preds)
        assert gate[6].is_open is False
        assert 38 in gate[6].failing_predicates

    def test_gate_reopens_after_recovery(self):
        """Fail then restore a predicate → gate reopens."""
        preds = _all_predicates()
        # Fail
        for p in preds:
            if p.index == 6:
                p.current_value = 0.5
        gate = evaluate_gate(preds)
        assert gate[5].is_open is False

        # Restore
        for p in preds:
            if p.index == 6:
                p.current_value = 1.0
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True


class TestSolanaCouplingIntegration:
    """Verify the Solana module's coupling relationships."""

    def test_energy_roi_to_revenue_growth(self):
        """TC-2: Energy ROI (f42) → Revenue growth (f24) via terrestrial-internal."""
        tc2 = [a for a in SOLANA_COUPLING if a.channel_id == "TC-2"]
        assert len(tc2) == 1
        assert tc2[0].source_predicate == 42
        assert tc2[0].target_predicate == 24
        assert tc2[0].rho == 0.5

    def test_system_health_to_hashrate(self):
        """DC-2: System health (f19) → Hash-rate (f38) via downward."""
        dc2 = [a for a in SOLANA_COUPLING if a.channel_id == "DC-2"]
        assert len(dc2) == 1
        assert dc2[0].source_predicate == 19
        assert dc2[0].target_predicate == 38
        assert dc2[0].axis_type == "downward"

    def test_no_upward_coupling(self):
        """Solana mining does NOT have upward coupling to Celestial.

        This is important: the upward coupling budget is 2 (UC-1, UC-2)
        and both are used by the Personality module. Solana mining stays
        fully within Terrestrial, so it doesn't consume upward budget.
        """
        upward = [a for a in SOLANA_COUPLING if a.axis_type == "upward"]
        assert len(upward) == 0

    def test_total_upward_budget_unchanged(self):
        """Adding Solana doesn't increase upward coupling count beyond 2."""
        all_axes = _all_coupling()
        upward = [a for a in all_axes if a.axis_type == "upward"]
        assert len(upward) == 2  # UC-1 and UC-2 from personality only


class TestSolanaModuleLifecycle:
    """Verify module CRUD operations work correctly."""

    def test_module_in_list(self):
        modules = _all_modules()
        ids = {m.module_id for m in modules}
        assert "solana-mining" in ids

    def test_module_level(self):
        assert SOLANA_MODULE.level == 5

    def test_module_status(self):
        assert SOLANA_MODULE.status == "Active"

    def test_deactivate_module(self):
        """Deactivating sets status to Inactive."""
        m = TerrestrialModule(
            "solana-mining", "Solana Mining", 5, "Active",
            [38, 39, 40, 41, 42], "a10", [],
        )
        m.status = "Inactive"
        assert m.status == "Inactive"

    def test_four_modules_total(self):
        """Original 3 + Solana = 4 modules."""
        assert len(_all_modules()) == 4

    def test_modules_are_profit_class(self):
        """All Level 5 modules are 'profit class'."""
        l5 = [m for m in _all_modules() if m.level == 5]
        assert len(l5) == 3  # profit-ecommerce, readiness-squadron, solana-mining


class TestSolanaEndToEnd:
    """Full pipeline: predicates → coupling → eigenspectrum → feasibility → gate."""

    def test_full_pipeline(self):
        """Run the complete computation pipeline with Solana module."""
        preds = _all_predicates()
        axes = _all_coupling()
        agents = _all_agents()
        blocks = _all_blocks()
        orchs = list(_ORCHESTRATORS)
        eigs = _all_eigenvalues()

        # Step 1: Build coupling matrix
        M = build_coupling_matrix(preds, axes)
        assert M.shape == (42, 42)

        # Step 2: Compute eigenspectrum
        spectrum = compute_eigenspectrum(M)
        assert len(spectrum) > 0

        # Step 3: cod(G)
        cod_g = compute_cod_g(eigs)
        assert cod_g == 20

        # Step 4: Feasibility
        feasibility = verify_feasibility(preds, blocks, agents, orchs, eigs, axes)
        assert feasibility.overall is True

        # Step 5: Gate evaluation (all unobserved → open)
        gate = evaluate_gate(preds)
        for level in range(7):
            assert gate[level].is_open is True

        # Step 6: Set Solana predicates to observed values
        for p in preds:
            if p.index == 38:
                p.current_value = 0.92  # Hash-rate: 92% efficiency
            elif p.index == 39:
                p.current_value = 1.0   # Wallet security: fully secure
            elif p.index == 40:
                p.current_value = 0.88  # Staking yield: 88% of target
            elif p.index == 41:
                p.current_value = 0.995 # Validator uptime: 99.5%
            elif p.index == 42:
                p.current_value = 0.85  # Energy ROI: positive

        # Re-evaluate gate — should still be open (all values above thresholds)
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True
        assert gate[6].is_open is True

    def test_cascade_block_scenario(self):
        """Simulate: Conscience fails → L5 gate closes → Solana mining halted."""
        preds = _all_predicates()

        # Observe all Celestial as passing
        for p in preds:
            if p.level <= 4:
                p.current_value = 1.0
            if p.level >= 5:
                p.current_value = 0.9

        # Gate open
        gate = evaluate_gate(preds)
        assert gate[5].is_open is True

        # Now: Conscience predicate f7 (Level 1) drops
        for p in preds:
            if p.index == 7:
                p.current_value = 0.3  # Severe conscience violation

        gate = evaluate_gate(preds)
        # L1 gate still open (checks L0 only), but L2+ gates close
        assert gate[1].is_open is True   # L1 checks L0 → ok
        assert gate[2].is_open is False  # L2 checks L0+L1 → f7 fails
        assert gate[5].is_open is False  # L5 checks L0-L4 → f7 fails
        assert gate[6].is_open is False  # L6 checks L0-L5 → f7 fails

        # Solana mining blocked: gate[5].is_open is False
        # This means the scheduler would skip mining jobs

    def test_mining_profitable_scenario(self):
        """All Solana predicates well above threshold → mining approved."""
        preds = _all_predicates()
        solana_values = {
            38: 0.95,  # Hash-rate: excellent
            39: 1.00,  # Wallet: fully secure
            40: 0.92,  # Staking: strong yield
            41: 0.999, # Uptime: near-perfect
            42: 0.90,  # ROI: solidly positive
        }
        for p in preds:
            if p.index in solana_values:
                p.current_value = solana_values[p.index]

        gate = evaluate_gate(preds)
        # All passing — mining proceeds
        assert gate[5].is_open is True

        # Verify each Solana predicate passes individually
        for p in preds:
            if p.index in solana_values:
                threshold = 1.0 - p.epsilon_dmg
                assert p.current_value >= threshold, (
                    f"f{p.index} ({p.name}): {p.current_value} < {threshold}"
                )

    def test_mining_unprofitable_scenario(self):
        """Energy ROI drops below threshold → L6 gate affected."""
        preds = _all_predicates()
        for p in preds:
            if p.index == 42:  # Energy ROI
                p.current_value = 0.5  # Below 1.0 - 0.15 = 0.85

        gate = evaluate_gate(preds)
        # L5 gate still open (L5 checks L0-L4 only)
        assert gate[5].is_open is True
        # L6 gate closed (L6 checks L0-L5, f42 is at L5 and failing)
        assert gate[6].is_open is False
        assert 42 in gate[6].failing_predicates
