"""Computation engine for the goal hierarchy.

Pure functions: take data, return results. No database access.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    FeasibilityResult,
    GateStatus,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyOrchestrator,
    HierarchyPredicate,
)

logger = logging.getLogger(__name__)


def build_coupling_matrix(
    predicates: list[HierarchyPredicate],
    axes: list[CouplingAxis],
) -> np.ndarray:
    """Build the full m×m coupling matrix from predicates and axes.

    Returns a symmetric matrix where M[i][j] = ρ between predicate indices.
    Diagonal is always 1.0. Indices are mapped 0..len(predicates)-1 based on
    sorted predicate index.
    """
    idx_map = {p.index: i for i, p in enumerate(sorted(predicates, key=lambda x: x.index))}
    n = len(predicates)
    M = np.eye(n, dtype=np.float64)

    for ax in axes:
        i = idx_map.get(ax.source_predicate)
        j = idx_map.get(ax.target_predicate)
        if i is not None and j is not None:
            M[i, j] = ax.rho
            M[j, i] = ax.rho  # symmetric

    return M


def compute_eigenspectrum(
    matrix: np.ndarray,
    tau: float = 0.01,
) -> list[tuple[float, np.ndarray]]:
    """Compute eigenvalues of the symmetric coupling matrix.

    Returns list of (eigenvalue, eigenvector) tuples for eigenvalues >= tau,
    sorted descending by eigenvalue.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)

    # Filter by threshold and sort descending
    results = []
    for i in range(len(eigenvalues)):
        if eigenvalues[i] >= tau:
            results.append((float(eigenvalues[i]), eigenvectors[:, i]))

    results.sort(key=lambda x: -x[0])
    return results


def compute_cod_g(eigenvalues: list[Eigenvalue]) -> int:
    """Count significant eigenvalues = codimension of G."""
    return len(eigenvalues)


def verify_feasibility(
    predicates: list[HierarchyPredicate],
    blocks: list[HierarchyBlock],
    agents: list[HierarchyAgent],
    orchestrators: list[HierarchyOrchestrator],
    eigenvalues: list[Eigenvalue],
    axes: list[CouplingAxis],
) -> FeasibilityResult:
    """Statement 55 verification: rank coverage, coupling coverage, epsilon tolerances.

    Three checks:
    1. Rank coverage: Σr_a + ΣR_orchestrator ≥ cod(G)
    2. Coupling coverage: All cross-block axes are governed by some orchestrator
    3. Epsilon check: ε_eff < ε_dmg for all predicates
    """
    now = datetime.now(timezone.utc)
    details: dict = {}

    # 1. Rank coverage
    sum_agent_ranks = sum(a.rank for a in agents)
    sum_orch_ranks = sum(o.rank for o in orchestrators)
    total_rank = sum_agent_ranks + sum_orch_ranks
    cod_g = len(eigenvalues)
    rank_pass = total_rank >= cod_g
    details["rank"] = {
        "agent_ranks": sum_agent_ranks,
        "orchestrator_ranks": sum_orch_ranks,
        "total": total_rank,
        "cod_g": cod_g,
        "margin": total_rank - cod_g,
    }

    # 2. Coupling coverage
    # Check that all cross-block axes have a governing orchestrator
    cross_block_axes = [a for a in axes if a.axis_type != "intra-block"]
    governed_agents_all = set()
    for o in orchestrators:
        for ga in o.governed_agents:
            governed_agents_all.add(ga)

    # Build predicate-to-agent map
    pred_to_agent = {p.index: p.agent_id for p in predicates}
    ungoverned = []
    for ax in cross_block_axes:
        src_agent = pred_to_agent.get(ax.source_predicate, "")
        tgt_agent = pred_to_agent.get(ax.target_predicate, "")
        if src_agent not in governed_agents_all and tgt_agent not in governed_agents_all:
            ungoverned.append(f"f{ax.source_predicate}->f{ax.target_predicate}")

    coupling_pass = len(ungoverned) == 0
    details["coupling"] = {
        "cross_block_axes": len(cross_block_axes),
        "ungoverned": ungoverned,
    }

    # 3. Epsilon check
    # ε_eff approximated as variance * sigma_max^(-1) for each predicate's agent
    agent_map = {a.agent_id: a for a in agents}
    epsilon_failures = []
    for p in predicates:
        agent = agent_map.get(p.agent_id)
        if agent and agent.sigma_max > 0:
            eps_eff = p.variance / agent.sigma_max
            if eps_eff >= p.epsilon_dmg:
                epsilon_failures.append({
                    "predicate": p.index,
                    "eps_eff": round(eps_eff, 6),
                    "eps_dmg": p.epsilon_dmg,
                })
    epsilon_pass = len(epsilon_failures) == 0
    details["epsilon"] = {
        "failures": epsilon_failures,
    }

    overall = rank_pass and coupling_pass and epsilon_pass

    return FeasibilityResult(
        timestamp=now,
        rank_coverage=rank_pass,
        coupling_coverage=coupling_pass,
        epsilon_check=epsilon_pass,
        overall=overall,
        details=details,
    )


def evaluate_gate(predicates: list[HierarchyPredicate]) -> dict[int, GateStatus]:
    """Evaluate the lexicographic gate for each level.

    GATE(L) = open iff all predicates at levels 0..L-1 currently pass.
    A predicate passes if current_value is None (unobserved → assumed passing)
    or current_value > (1 - epsilon_dmg).
    """
    now = datetime.now(timezone.utc)

    # Group predicates by level
    by_level: dict[int, list[HierarchyPredicate]] = {}
    for p in predicates:
        by_level.setdefault(p.level, []).append(p)

    max_level = max(p.level for p in predicates) if predicates else 0
    gate: dict[int, GateStatus] = {}

    for level in range(max_level + 1):
        failing = []
        # Check all predicates at levels BELOW this one
        for check_level in range(level):
            for p in by_level.get(check_level, []):
                if p.current_value is not None:
                    threshold = 1.0 - p.epsilon_dmg
                    if p.current_value < threshold:
                        failing.append(p.index)

        gate[level] = GateStatus(
            level=level,
            is_open=len(failing) == 0,
            failing_predicates=failing,
            timestamp=now,
        )

    return gate


def check_o3_rank(
    upward_channels: int,
    cross_module_axes: int,
    o3_rank: int,
) -> dict:
    """Check O₃ rank requirement: R_O3 ≥ C_upward + C_cross_module."""
    required = upward_channels + cross_module_axes
    passes = o3_rank >= required
    return {
        "o3_rank": o3_rank,
        "upward_channels": upward_channels,
        "cross_module_axes": cross_module_axes,
        "required": required,
        "margin": o3_rank - required,
        "passes": passes,
    }
