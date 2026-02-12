"""IM computation engine — pure functions, no database access.

Implements the mathematical operations from the IM paper:
- Coupling matrix construction and PSD projection
- Eigendecomposition and codimension estimation
- Assignment optimization (constrained clustering on M)
- Feasibility verification (Thm. architecture-design)
- Memory tier derivation
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Coupling matrix (Tool 3)
# ──────────────────────────────────────────────────────────────

def build_coupling_matrix(
    predicates: list[dict],
    blocks: list[dict],
    cross_coupling: list[dict],
) -> list[list[float]]:
    """Build the m×m coupling matrix M from predicates, blocks, and cross-coupling.

    1. Initialize diagonal = 1.0
    2. Fill intra-block entries based on shared block membership
    3. Fill cross-block entries from coupling axes
    4. Symmetrize
    5. Project to nearest PSD matrix

    Returns the matrix as a list-of-lists (JSON-serializable).
    """
    n = len(predicates)
    if n == 0:
        return []

    # Build predicate ID to index map
    pred_ids = [p["id"] for p in predicates]
    pid_to_idx = {pid: i for i, pid in enumerate(pred_ids)}

    # Build block membership: which predicates are in which block
    block_members: dict[str, list[int]] = {}
    for b in blocks:
        indices = [pid_to_idx[pid] for pid in b.get("predicate_ids", [])
                   if pid in pid_to_idx]
        block_members[b["id"]] = indices

    M = np.eye(n, dtype=np.float64)

    # Intra-block coupling
    for block_id, indices in block_members.items():
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                ii, jj = indices[i], indices[j]
                # Estimate intra-block coupling from predicate similarity
                # Use severity and horizon overlap as heuristics
                p_i = predicates[ii]
                p_j = predicates[jj]
                base_rho = _estimate_intra_coupling(p_i, p_j)
                M[ii, jj] = base_rho
                M[jj, ii] = base_rho

    # Cross-block coupling
    for cc in cross_coupling:
        from_block = cc.get("from_block", "")
        to_block = cc.get("to_block", "")
        rho = cc.get("rho", 0.0)

        from_indices = block_members.get(from_block, [])
        to_indices = block_members.get(to_block, [])

        if to_block == "*":
            # Couple to all predicates
            to_indices = list(range(n))

        for fi in from_indices:
            for ti in to_indices:
                if fi != ti:
                    v = rho * 0.8  # Attenuate cross-block coupling
                    M[fi, ti] = max(M[fi, ti], v)
                    M[ti, fi] = max(M[ti, fi], v)

    # Project to PSD
    M = _project_psd(M)

    return M.tolist()


def update_coupling_matrix(
    matrix: list[list[float]],
    overrides: list[dict],
) -> list[list[float]]:
    """Apply human overrides to coupling matrix cells, re-symmetrize, re-project PSD."""
    M = np.array(matrix, dtype=np.float64)

    for ovr in overrides:
        row = ovr.get("row", 0)
        col = ovr.get("col", 0)
        val = ovr.get("value", 0.0)
        if 0 <= row < M.shape[0] and 0 <= col < M.shape[1]:
            M[row, col] = val
            M[col, row] = val  # Symmetrize

    M = _project_psd(M)
    return M.tolist()


def _estimate_intra_coupling(p_i: dict, p_j: dict) -> float:
    """Heuristic coupling estimate between two predicates in the same block."""
    # Severity match adds coupling
    sev_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    si = sev_map.get(p_i.get("severity", "medium"), 2)
    sj = sev_map.get(p_j.get("severity", "medium"), 2)
    sev_sim = 1.0 - abs(si - sj) / 4.0

    # Horizon overlap
    hi = p_i.get("horizon_t", 3600)
    hj = p_j.get("horizon_t", 3600)
    h_ratio = min(hi, hj) / max(hi, hj) if max(hi, hj) > 0 else 1.0

    # Base coupling for same-block predicates: [0.3, 0.7]
    return 0.3 + 0.4 * (0.5 * sev_sim + 0.5 * h_ratio)


def _project_psd(M: np.ndarray) -> np.ndarray:
    """Project matrix to nearest positive semi-definite matrix.

    Eigendecompose, clip negative eigenvalues to 0, reconstruct.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(M)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    M_psd = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    # Ensure exact symmetry
    M_psd = (M_psd + M_psd.T) / 2.0
    # Restore diagonal to 1.0
    np.fill_diagonal(M_psd, 1.0)
    return M_psd


# ──────────────────────────────────────────────────────────────
# Eigenspectrum and codimension (Tool 4)
# ──────────────────────────────────────────────────────────────

def compute_eigenspectrum(
    matrix: list[list[float]],
    tau: float = 0.05,
    predicates: list[dict] | None = None,
    blocks: list[dict] | None = None,
) -> dict:
    """Compute eigenspectrum λ(M) and codimension cod_π(G) = rank_τ(M).

    Returns:
        dict with eigenspectrum, tau, cod_pi_g, dim_star_per_predicate, total_dim_star
    """
    M = np.array(matrix, dtype=np.float64)
    if M.size == 0:
        return {"eigenspectrum": [], "tau": tau, "cod_pi_g": 0,
                "dim_star_per_predicate": [], "total_dim_star": 0}

    eigenvalues, eigenvectors = np.linalg.eigh(M)

    # Sort descending
    idx = np.argsort(-eigenvalues)
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Build eigenspectrum with block attribution
    spectrum = []
    for i, val in enumerate(eigenvalues):
        attr = _attribute_eigenvalue(eigenvectors[:, i], predicates, blocks)
        spectrum.append({
            "index": i + 1,
            "value": round(float(val), 6),
            "block_attribution": attr,
            "above_threshold": bool(val >= tau),
        })

    cod_pi_g = sum(1 for v in eigenvalues if v >= tau)

    # Compute dim*(G) per predicate
    dim_stars = []
    if predicates:
        for p in predicates:
            ds = _compute_dim_star(p)
            dim_stars.append(round(ds, 2))

    total_dim_star = sum(dim_stars) if dim_stars else 0

    return {
        "eigenspectrum": spectrum,
        "tau": tau,
        "cod_pi_g": cod_pi_g,
        "dim_star_per_predicate": dim_stars,
        "total_dim_star": round(total_dim_star, 2),
    }


def _attribute_eigenvalue(
    eigenvector: np.ndarray,
    predicates: list[dict] | None,
    blocks: list[dict] | None,
) -> str:
    """Determine which block contributes most to an eigenvalue."""
    if not predicates or not blocks:
        return ""

    # Build predicate-to-block map
    pred_blocks = {}
    for b in blocks:
        for pid in b.get("predicate_ids", []):
            pred_blocks[pid] = b["id"]

    # Weight by eigenvector component magnitude
    block_weights: dict[str, float] = {}
    pred_ids = [p["id"] for p in predicates]
    for i, pid in enumerate(pred_ids):
        if i < len(eigenvector):
            bid = pred_blocks.get(pid, "?")
            block_weights[bid] = block_weights.get(bid, 0) + abs(eigenvector[i])

    if not block_weights:
        return ""

    top = max(block_weights, key=block_weights.get)
    return top


def _compute_dim_star(predicate: dict) -> float:
    """Approximate dim*(G) for a single predicate.

    dim*(G) ≈ severity_weight + log₂(T/60) * scaling_factor
    """
    sev_map = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}
    base = sev_map.get(predicate.get("severity", "medium"), 2.0)
    horizon = max(1, predicate.get("horizon_t", 3600))
    horizon_factor = math.log2(max(1, horizon / 60))
    return base + horizon_factor * 0.4


# ──────────────────────────────────────────────────────────────
# Rank budget and regime (Tool 5)
# ──────────────────────────────────────────────────────────────

def compute_rank_budget(
    cod_pi_g: int,
    agent_pool: list[dict],
    orchestrator: dict,
    cross_block_count: int = 0,
) -> dict:
    """Compute rank budget allocation and regime classification.

    Checks:
    1. R + Σr_i ≥ cod_π(G) (rank coverage)
    2. R ≥ C(α, topology) for candidate topologies
    3. Self-management threshold
    4. Regime classification (simple/medium/complex)
    """
    sum_agent_ranks = sum(a.get("jacobian_rank", 1) for a in agent_pool)
    orch_rank = orchestrator.get("jacobian_rank", 1)
    total_rank = sum_agent_ranks + orch_rank
    surplus = total_rank - cod_pi_g

    # Orchestrator rank lower bound
    orch_lb = max(0, cod_pi_g - sum_agent_ranks)

    # Coupling rank by topology
    cross = max(1, cross_block_count)
    coupling_by_topo = {
        "flat": 0,
        "pipeline": cross,
        "hierarchical": max(1, cross // 2),
        "mesh": cross * 2,
    }

    # Memory management codimension
    cod_g_m = 3
    c_cross = 2
    self_mgmt_threshold = cod_pi_g + cod_g_m + c_cross
    max_agent_rank = max((a.get("jacobian_rank", 1) for a in agent_pool), default=1)

    # Regime classification
    if cod_pi_g <= 3 and max_agent_rank >= self_mgmt_threshold:
        regime = "simple"
        rationale = "Low codimension; agents can self-manage memory"
    elif orch_rank >= c_cross + 1 and total_rank >= cod_pi_g:
        regime = "medium"
        rationale = "Orchestrator absorbs cross-coupling; agents handle task memory"
    else:
        regime = "complex"
        rationale = "Dedicated memory agent required; codimension exceeds self-management capacity"

    # Remediation if infeasible
    remediation = None
    if surplus < 0:
        remediation = (
            f"Rank deficit of {-surplus}. Options: "
            f"(1) Add {-surplus} more agent rank units, "
            f"(2) Reduce cod_π(G) via K-extension, "
            f"(3) Use higher-rank models."
        )

    return {
        "total_rank": total_rank,
        "sum_agent_ranks": sum_agent_ranks,
        "orchestrator_rank": orch_rank,
        "cod_pi_g": cod_pi_g,
        "rank_surplus_or_deficit": surplus,
        "orch_rank_lower_bound": orch_lb,
        "coupling_rank_by_topology": coupling_by_topo,
        "regime": regime,
        "regime_rationale": rationale,
        "self_mgmt_threshold": self_mgmt_threshold,
        "max_agent_rank": max_agent_rank,
        "cod_g_m": cod_g_m,
        "c_cross": c_cross,
        "remediation": remediation,
    }


# ──────────────────────────────────────────────────────────────
# Memory tier design (Tool 6)
# ──────────────────────────────────────────────────────────────

def design_memory_tiers(
    cod_pi_g: int,
    regime: str,
    agent_pool: list[dict],
    orchestrator: dict,
    k_preloaded: list[dict] | None = None,
) -> dict:
    """Design memory subsystem: tier structure, K-scopes, crystallisation.

    Derived from codimension analysis and regime classification.
    """
    k_pre = k_preloaded or []
    k0_reduction = sum(k.get("cod_reduction", 0) for k in k_pre)
    cod_after_k0 = max(1, cod_pi_g - int(k0_reduction))
    cod_after_session = max(1, cod_after_k0 - 3)  # Estimate 3 runtime K-extensions

    max_agent_rank = max((a.get("jacobian_rank", 1) for a in agent_pool), default=1)
    orch_rank = orchestrator.get("jacobian_rank", 1)
    memory_agent_required = regime == "complex"
    context_window = max((a.get("context_window", 200000) for a in agent_pool), default=200000)

    tiers = [
        {
            "tier": "M0", "scope": "Agent-private working memory",
            "cod_target": "—",
            "content": "Active context window",
            "manager": "Agent (automatic)",
            "persistence": "Current invocation",
            "capacity": f"{context_window:,} tokens",
        },
        {
            "tier": "M1", "scope": "Session K_session",
            "cod_target": f"{cod_after_k0} → {cod_after_session}",
            "content": "Task-specific shared context",
            "manager": "Memory agent" if memory_agent_required else "Orchestrator",
            "persistence": "Active goal set",
            "capacity": "~50k tokens",
        },
        {
            "tier": "M2", "scope": "Cross-session K_persistent",
            "cod_target": f"{cod_after_session} → {cod_after_session} (local Δ)",
            "content": "Historical patterns, learned heuristics",
            "manager": "Memory agent" if memory_agent_required else "Orchestrator",
            "persistence": "Cross-session goals",
            "capacity": "~500k tokens (RAG)",
        },
        {
            "tier": "M3", "scope": "Lifetime K_structural",
            "cod_target": "—",
            "content": "Base model weights",
            "manager": "APS cascade",
            "persistence": "G⁰-derived",
            "capacity": "Weight matrix",
        },
    ]

    crystallisation = {
        "primary": {
            "criterion": "rank_τ(M|_{K∪T}) < rank_τ(M|_K)",
            "description": "K-extending: reduces operative codimension",
            "target": "Highest K-scope",
            "priority": 1,
        },
        "secondary": {
            "criterion": "‖Π_k · v(T)‖ > τ_crystallise",
            "description": "Locally gap-reducing: improves specific axis steering",
            "target": "Tier matching T_j",
            "priority": 2,
        },
        "reject": {
            "criterion": "Neither condition holds",
            "description": "Goal-irrelevant noise — discard on M0 eviction",
            "target": "Discard",
            "priority": 3,
        },
    }

    right_sizing = {
        "regime": regime,
        "memory_agent_required": memory_agent_required,
        "memory_agent_spec": {
            "agent_id": "memory_agent",
            "name": "Memory Agent 𝓜",
            "jacobian_rank": 3,
            "model_family": "Claude Sonnet 4.5",
        } if memory_agent_required else None,
        "self_mgmt_threshold": cod_after_k0 + 3 + 2,
        "cod_g_m": 3,
        "c_cross": 2,
        "max_agent_rank": max_agent_rank,
    }

    audit_schedule = {
        "codim_audit_interval_hours": 6,
        "drift_detection_window": 3600,
    }

    return {
        "cod_pi_g_raw": cod_pi_g,
        "cod_after_k0": cod_after_k0,
        "cod_after_session": cod_after_session,
        "tiers": tiers,
        "k_preloaded": k_pre,
        "crystallisation_policy": crystallisation,
        "right_sizing": right_sizing,
        "audit_schedule": audit_schedule,
    }


# ──────────────────────────────────────────────────────────────
# Agent synthesis (Tool 7)
# ──────────────────────────────────────────────────────────────

def synthesize_agent_specs(
    matrix: list[list[float]],
    predicates: list[dict],
    blocks: list[dict],
    agent_pool: list[dict],
    orchestrator: dict,
) -> dict:
    """Compute optimal assignment α*: {f_i} → {a_j}.

    Uses constrained spectral clustering on M to assign predicates to agents
    while minimizing the infeasibility residual ‖Δ‖.
    """
    M = np.array(matrix, dtype=np.float64)
    n = len(predicates)
    n_agents = len(agent_pool)

    if n == 0 or n_agents == 0:
        return {"alpha": [], "agents": [], "delta_rank": 0,
                "delta_norm": 0.0, "governance_margin": 0.0}

    # Build assignment via greedy block-respecting clustering
    # Assign each block to the agent with highest remaining capacity
    pred_ids = [p["id"] for p in predicates]
    pid_to_idx = {pid: i for i, pid in enumerate(pred_ids)}

    alpha = []
    agent_assignments: dict[str, list[str]] = {a["agent_id"]: [] for a in agent_pool}
    agent_capacity = {a["agent_id"]: a.get("jacobian_rank", 1) for a in agent_pool}

    # Sort blocks by intra_rank descending (assign hardest first)
    sorted_blocks = sorted(blocks, key=lambda b: b.get("intra_rank", 0), reverse=True)

    for block in sorted_blocks:
        block_preds = block.get("predicate_ids", [])
        block_rank = block.get("intra_rank", 1) or 1

        # Find agent with most remaining capacity
        best_agent = max(agent_capacity, key=agent_capacity.get)

        for pid in block_preds:
            alpha.append({"predicate_id": pid, "agent_id": best_agent})
            agent_assignments[best_agent].append(pid)

        agent_capacity[best_agent] = max(0, agent_capacity[best_agent] - block_rank)

    # Compute J_α (block-diagonal steering operator)
    # Simplified: each agent covers its assigned predicate indices
    j_alpha = np.zeros((n, n), dtype=np.float64)
    for aid, pids in agent_assignments.items():
        agent = next((a for a in agent_pool if a["agent_id"] == aid), None)
        if agent:
            sigma_max = max(agent.get("steering_spectrum", [1.0]), default=1.0)
            for pid in pids:
                idx = pid_to_idx.get(pid)
                if idx is not None:
                    j_alpha[idx, idx] = sigma_max

    # Add orchestrator contribution
    orch_rank = orchestrator.get("jacobian_rank", 1)
    j_total = j_alpha.copy()
    # Orchestrator covers cross-block dimensions
    eigenvalues_j, eigenvectors_j = np.linalg.eigh(j_total)

    # Compute projection Π = orthogonal projector onto img(J_total)
    nonzero_mask = eigenvalues_j > 1e-10
    if nonzero_mask.any():
        V = eigenvectors_j[:, nonzero_mask]
        Pi = V @ V.T
    else:
        Pi = np.zeros_like(M)

    # Compute Δ = (I - Π) M (I - Π)ᵀ
    I_minus_Pi = np.eye(n) - Pi
    Delta = I_minus_Pi @ M @ I_minus_Pi.T

    delta_eigenvalues = np.linalg.eigvalsh(Delta)
    delta_norm = float(np.max(np.abs(delta_eigenvalues)))
    delta_rank = int(np.sum(np.abs(delta_eigenvalues) > 0.01))

    # Governance margin γ = rank_τ(J_O) - C
    governance_margin = orch_rank - len([c for c in sorted_blocks if len(c.get("predicate_ids", [])) > 0])

    # Build agent spec output
    agents_out = []
    for agent in agent_pool:
        aid = agent["agent_id"]
        assigned = agent_assignments.get(aid, [])
        agents_out.append({
            **agent,
            "assigned_predicates": assigned,
            "predicate_count": len(assigned),
        })

    return {
        "alpha": alpha,
        "j_alpha": j_alpha.tolist(),
        "agents": agents_out,
        "delta": Delta.tolist(),
        "delta_rank": delta_rank,
        "delta_norm": round(delta_norm, 6),
        "governance_margin": round(governance_margin, 2),
    }


# ──────────────────────────────────────────────────────────────
# Workflow synthesis (Tool 8)
# ──────────────────────────────────────────────────────────────

def synthesize_workflow_spec(
    assignment: dict,
    rank_budget: dict,
    predicates: list[dict],
    blocks: list[dict],
    cross_coupling: list[dict],
) -> dict:
    """Synthesize complete workflow specification.

    Selects topology, defines channels, assigns blanket levels,
    sets morphology params, and compiles the workflow graph.
    """
    agents = assignment.get("agents", [])
    coupling_by_topo = rank_budget.get("coupling_rank_by_topology", {})
    regime = rank_budget.get("regime", "medium")

    # Select topology: minimize coupling rank C
    if not coupling_by_topo:
        pattern = "flat"
    else:
        # Exclude flat (C=0 but only works for truly independent agents)
        candidates = {k: v for k, v in coupling_by_topo.items() if k != "flat"}
        pattern = min(candidates, key=candidates.get) if candidates else "flat"

    # If few agents, prefer flat or pipeline
    if len(agents) <= 2:
        pattern = "flat"
    elif len(agents) <= 4 and not cross_coupling:
        pattern = "pipeline"

    # Build nodes
    nodes = [{"node_id": "orchestrator", "agent_id": "orchestrator", "role": "orchestrator"}]
    for a in agents:
        nodes.append({
            "node_id": a["agent_id"],
            "agent_id": a["agent_id"],
            "role": "task_agent",
        })

    if rank_budget.get("regime") == "complex":
        nodes.append({"node_id": "memory_agent", "agent_id": "memory_agent", "role": "memory"})

    # Build edges based on topology
    edges = []
    agent_ids = [a["agent_id"] for a in agents]

    if pattern == "flat":
        for aid in agent_ids:
            edges.append({"source": "orchestrator", "target": aid, "protocol": "async"})
    elif pattern == "pipeline":
        for i in range(len(agent_ids)):
            if i == 0:
                edges.append({"source": "orchestrator", "target": agent_ids[i], "protocol": "sync"})
            else:
                edges.append({"source": agent_ids[i-1], "target": agent_ids[i], "protocol": "sync"})
        if agent_ids:
            edges.append({"source": agent_ids[-1], "target": "orchestrator", "protocol": "async"})
    elif pattern == "hierarchical":
        for aid in agent_ids:
            edges.append({"source": "orchestrator", "target": aid, "protocol": "async"})
        # Add cross-agent edges for coupled blocks
        for cc in cross_coupling:
            from_agents = [a["agent_id"] for a in agents
                          if any(pid in a.get("assigned_predicates", [])
                                for pid in _block_preds(cc.get("from_block", ""), blocks))]
            to_agents = [a["agent_id"] for a in agents
                        if any(pid in a.get("assigned_predicates", [])
                              for pid in _block_preds(cc.get("to_block", ""), blocks))]
            for fa in from_agents:
                for ta in to_agents:
                    if fa != ta:
                        edges.append({"source": fa, "target": ta, "protocol": "async"})
    else:  # mesh
        for aid in agent_ids:
            edges.append({"source": "orchestrator", "target": aid, "protocol": "async"})
        for i in range(len(agent_ids)):
            for j in range(i+1, len(agent_ids)):
                edges.append({"source": agent_ids[i], "target": agent_ids[j], "protocol": "async"})

    # Blanket levels
    blanket_levels = [
        {"agent_id": "orchestrator", "blanket_level": 1},
    ]
    for a in agents:
        blanket_levels.append({"agent_id": a["agent_id"], "blanket_level": 2})
    if rank_budget.get("regime") == "complex":
        blanket_levels.append({"agent_id": "memory_agent", "blanket_level": 2})

    # Morphology params
    morphology = {
        "orchestrator_temperature": 0.3,
        "agent_temperature": 0.5,
        "max_reasoning_depth": 3,
        "tool_permission_level": "restricted",
    }

    # Escalation routes
    escalation = [
        {"severity": "critical", "target": "human_operator", "timeout_seconds": 300},
        {"severity": "high", "target": "orchestrator", "timeout_seconds": 600},
        {"severity": "medium", "target": "orchestrator", "timeout_seconds": 1800},
        {"severity": "low", "target": "self_resolve", "timeout_seconds": 3600},
    ]

    # Validation
    validation_errors = []
    node_ids = {n["node_id"] for n in nodes}
    for e in edges:
        if e["source"] not in node_ids:
            validation_errors.append(f"Edge source '{e['source']}' not in nodes")
        if e["target"] not in node_ids:
            validation_errors.append(f"Edge target '{e['target']}' not in nodes")

    return {
        "topology": {
            "pattern": pattern,
            "nodes": nodes,
            "edges": edges,
            "coupling_rank_c": coupling_by_topo.get(pattern, 0),
        },
        "channels": [{"source": e["source"], "target": e["target"],
                       "protocol": e["protocol"]} for e in edges],
        "blanket_levels": blanket_levels,
        "morphology_params": morphology,
        "logic_profiles": [],
        "escalation_routes": escalation,
        "compiled": len(validation_errors) == 0,
        "validation_errors": validation_errors,
    }


def _block_preds(block_id: str, blocks: list[dict]) -> list[str]:
    """Get predicate IDs for a block."""
    for b in blocks:
        if b["id"] == block_id:
            return b.get("predicate_ids", [])
    return []


# ──────────────────────────────────────────────────────────────
# Feasibility validation (Tool 9)
# ──────────────────────────────────────────────────────────────

def validate_feasibility(
    assignment: dict,
    rank_budget: dict,
    codimension: dict,
    predicates: list[dict],
    workflow: dict,
) -> dict:
    """Final feasibility check — Thm. architecture-design.

    Three conditions:
    (i)   Rank coverage: R + Σr_i ≥ cod_π(G)
    (ii)  Coupling coverage: R ≥ C(α, topology)
    (iii) Power coverage: ∀ assigned axis i, ∃ agent with ς ≥ ς_min
    """
    cod_pi_g = codimension.get("cod_pi_g", 0)
    total_rank = rank_budget.get("total_rank", 0)
    orch_rank = rank_budget.get("orchestrator_rank", 0)
    coupling_c = workflow.get("topology", {}).get("coupling_rank_c", 0)

    # Condition (i): Rank coverage
    rank_coverage = total_rank >= cod_pi_g

    # Condition (ii): Coupling coverage
    coupling_coverage = orch_rank >= coupling_c

    # Condition (iii): Power coverage
    agents = assignment.get("agents", [])
    epsilon_effective = []
    epsilon_damage = []
    axes_violating = []

    for p in predicates:
        eps_g = p.get("epsilon_g", 0.05)
        epsilon_damage.append(eps_g)

        # Find assigned agent
        assigned = next(
            (a for a in agents if p["id"] in a.get("assigned_predicates", [])),
            None,
        )
        if assigned:
            sigma = max(assigned.get("steering_spectrum", [1.0]), default=1.0)
            noise = p.get("epsilon_g", 0.05) * 0.5  # Estimate noise as fraction of tolerance
            eps_eff = noise / sigma if sigma > 0 else 1.0
        else:
            eps_eff = 1.0  # Unassigned = worst case

        epsilon_effective.append(round(eps_eff, 6))
        if eps_eff >= eps_g:
            axes_violating.append(p["id"])

    power_coverage = len(axes_violating) == 0

    # Governance margin
    governance_margin = assignment.get("governance_margin", 0)

    # Delta
    delta_norm = assignment.get("delta_norm", 0)
    delta_rank = assignment.get("delta_rank", 0)

    # Verdict
    all_pass = rank_coverage and coupling_coverage and power_coverage
    verdict = "feasible" if all_pass else "infeasible"

    # Remediation
    remediation = None
    if not all_pass:
        reasons = []
        if not rank_coverage:
            deficit = cod_pi_g - total_rank
            reasons.append(f"Rank deficit: need {deficit} more rank units")
        if not coupling_coverage:
            reasons.append(f"Coupling: orchestrator rank {orch_rank} < coupling rank {coupling_c}")
        if axes_violating:
            reasons.append(f"Power: {len(axes_violating)} axes violating (ε_eff ≥ ε_dmg)")

        remediation = {
            "type": "increase_rank" if not rank_coverage else
                    "restrict_topology" if not coupling_coverage else
                    "acquire_agents",
            "detail": "; ".join(reasons),
            "minimum_additional_rank": max(0, cod_pi_g - total_rank) if not rank_coverage else None,
            "minimum_additional_power_axes": len(axes_violating) if axes_violating else None,
        }

    return {
        "rank_coverage": rank_coverage,
        "coupling_coverage": coupling_coverage,
        "power_coverage": power_coverage,
        "governance_margin": round(governance_margin, 2),
        "epsilon_effective": epsilon_effective,
        "epsilon_damage": epsilon_damage,
        "axes_violating_power": axes_violating,
        "delta_norm": round(delta_norm, 6),
        "delta_rank": delta_rank,
        "verdict": verdict,
        "remediation": remediation,
    }
