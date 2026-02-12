"""The 9 IM pipeline tools — callable by Holly via function calling.

Each tool operates on a shared IMWorkspace. Tools must be called in
dependency order (the output of each tool is the input of the next).

Tool 1: im_parse_goal_tuple
Tool 2: im_generate_failure_predicates
Tool 3: im_build_coupling_model
Tool 4: im_estimate_codimension
Tool 5: im_rank_budget_and_regime
Tool 6: im_memory_tier_design
Tool 7: im_synthesize_agent_specs
Tool 8: im_synthesize_workflow_spec
Tool 9: im_validate_feasibility

Plus utility tools:
  im_list_workspaces
  im_get_workspace
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Tool 1: Parse Goal Tuple
# ──────────────────────────────────────────────────────────────

def im_parse_goal_tuple(raw_intent: str, context: str = "") -> dict:
    """Parse natural-language intent into G⁰ preference and G¹ candidates.

    Creates a new IM workspace and uses an LLM to decompose the user's
    goal into structured G¹ tuples with failure predicates, tolerances,
    horizons, and measurement maps.

    Args:
        raw_intent: User's natural-language goal description.
        context: Optional domain context or constraints.
    """
    from src.im.store import create_workspace, get_workspace, update_workspace, log_audit

    # Create workspace
    ws_id = create_workspace(raw_intent, created_by="holly_grace")
    ws = get_workspace(ws_id)
    if not ws:
        return {"error": "Failed to create workspace"}

    # Use LLM to parse goal into G¹ candidates
    g1_candidates = _llm_parse_goal(raw_intent, context)

    ws.goal_tuple = {
        "g0_preference": raw_intent,
        "g1_candidates": g1_candidates,
        "ambiguities": _detect_ambiguities(g1_candidates),
        "selected_g1_index": 0 if len(g1_candidates) == 1 else None,
    }
    ws.stage = "goal_parsed"
    update_workspace(ws)

    log_audit(ws_id, "goal_parsed", "im_parse_goal_tuple",
              input_summary=raw_intent[:200],
              output_summary=f"{len(g1_candidates)} G¹ candidates generated")

    return {
        "workspace_id": ws_id,
        "goal_tuple": ws.goal_tuple,
        "stage": ws.stage,
    }


def _llm_parse_goal(raw_intent: str, context: str) -> list[dict]:
    """Use Anthropic API to parse goal into G¹ candidates."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        prompt = f"""You are a formal goal specification engine implementing the Informational Monism Architecture Selection Rule.

Given this natural-language goal description, produce 1-3 candidate G¹ specifications.

Each G¹ = (F_G, ε_G, T, m_G) where:
- F_G: list of candidate failure predicates (things that can go wrong)
- ε_G: tolerated failure probability (0.0 to 1.0, lower = stricter)
- T: evaluation horizon in seconds
- m_G: measurement map (how to check pass/fail)

Goal: {raw_intent}
{f"Context: {context}" if context else ""}

Respond with a JSON array of G¹ candidates. Each candidate:
{{
  "failure_predicates": ["description of each failure mode"],
  "epsilon_g": 0.05,
  "horizon_t": 3600,
  "measurement_map": "description of how to measure"
}}

Return ONLY the JSON array, no markdown."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        # Parse JSON
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        candidates = json.loads(text)
        if isinstance(candidates, list):
            return candidates
        return [candidates]
    except Exception as e:
        logger.warning("LLM goal parsing failed, using rule-based fallback: %s", e)
        return _rule_based_parse(raw_intent)


def _rule_based_parse(raw_intent: str) -> list[dict]:
    """Fallback: rule-based goal parsing when LLM is unavailable."""
    return [{
        "failure_predicates": [
            f"System fails to achieve: {raw_intent[:100]}",
            "Response quality below acceptable threshold",
            "Processing exceeds time budget",
        ],
        "epsilon_g": 0.05,
        "horizon_t": 3600,
        "measurement_map": "Binary pass/fail evaluation of goal completion",
    }]


def _detect_ambiguities(candidates: list[dict]) -> list[str]:
    """Detect specification ambiguities in G¹ candidates."""
    ambiguities = []
    for i, c in enumerate(candidates):
        if c.get("epsilon_g") is None:
            ambiguities.append(f"Candidate {i}: missing tolerance ε_G")
        if c.get("horizon_t") is None:
            ambiguities.append(f"Candidate {i}: missing evaluation horizon T")
        if not c.get("measurement_map"):
            ambiguities.append(f"Candidate {i}: no measurement map defined")
        preds = c.get("failure_predicates", [])
        if len(preds) < 2:
            ambiguities.append(f"Candidate {i}: only {len(preds)} failure predicate(s) — may be under-specified")
    return ambiguities


# ──────────────────────────────────────────────────────────────
# Tool 2: Generate Failure Predicates
# ──────────────────────────────────────────────────────────────

def im_generate_failure_predicates(
    workspace_id: str,
    g1_index: int = 0,
    domain_hints: list[str] | None = None,
) -> dict:
    """Decompose selected G¹ into failure predicates, blocks, and coupling axes.

    Args:
        workspace_id: The workspace to operate on.
        g1_index: Which G¹ candidate to use (default 0).
        domain_hints: Optional domain-specific predicate templates.
    """
    from src.im.store import get_workspace, update_workspace, log_audit

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    g1_candidates = ws.goal_tuple.get("g1_candidates", [])
    if g1_index >= len(g1_candidates):
        return {"error": f"G¹ index {g1_index} out of range (have {len(g1_candidates)})"}

    selected = g1_candidates[g1_index]
    ws.goal_tuple["selected_g1_index"] = g1_index

    # Generate predicates via LLM
    result = _llm_generate_predicates(ws.raw_intent, selected, domain_hints)

    ws.predicates = result["predicates"]
    ws.predicate_blocks = result["blocks"]
    ws.cross_block_coupling = result["cross_coupling"]
    ws.stage = "predicates_generated"
    update_workspace(ws)

    log_audit(workspace_id, "predicates_generated", "im_generate_failure_predicates",
              input_summary=f"G¹ index {g1_index}",
              output_summary=f"{len(ws.predicates)} predicates, {len(ws.predicate_blocks)} blocks")

    return {
        "workspace_id": workspace_id,
        "predicates": ws.predicates,
        "predicate_blocks": ws.predicate_blocks,
        "cross_block_coupling": ws.cross_block_coupling,
        "quality_summary": _assess_quality(ws.predicates),
    }


def _llm_generate_predicates(
    raw_intent: str,
    g1: dict,
    domain_hints: list[str] | None,
) -> dict:
    """Use LLM to generate failure predicates from G¹."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        hints_text = "\n".join(f"- {h}" for h in (domain_hints or []))
        hints_section = ("Domain hints:\n" + hints_text) if hints_text else ""
        prompt = f"""You are a formal failure predicate generator for the Informational Monism framework.

Given this goal and G¹ specification, generate:
1. A set of failure predicates (each with id, name, description, block_id, epsilon_g, horizon_t, severity, measurement_map)
2. Predicate blocks (groups of related predicates)
3. Cross-block coupling axes

Goal: {raw_intent}
G¹: {json.dumps(g1)}
{hints_section}

Respond with JSON:
{{
  "predicates": [
    {{"id": "f_001", "name": "...", "description": "...", "block_id": "BLK_A",
      "epsilon_g": 0.05, "horizon_t": 3600, "severity": "high",
      "measurement_map": "...", "quality_assessment": "Falsifiable, Observable, Actionable"}}
  ],
  "blocks": [
    {{"id": "BLK_A", "name": "...", "predicate_ids": ["f_001", "f_002"], "intra_rank": 2}}
  ],
  "cross_coupling": [
    {{"from_block": "BLK_A", "to_block": "BLK_B", "rho": 0.5,
      "mechanism": "...", "direction": "A → B"}}
  ]
}}

Generate 6-15 predicates in 3-6 blocks. Severity: critical/high/medium/low.
Return ONLY JSON, no markdown."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        return {
            "predicates": result.get("predicates", []),
            "blocks": result.get("blocks", []),
            "cross_coupling": result.get("cross_coupling", []),
        }
    except Exception as e:
        logger.warning("LLM predicate generation failed, using fallback: %s", e)
        return _fallback_predicates(raw_intent, g1)


def _fallback_predicates(raw_intent: str, g1: dict) -> dict:
    """Rule-based fallback predicate generation."""
    preds_raw = g1.get("failure_predicates", [])
    predicates = []
    for i, desc in enumerate(preds_raw):
        predicates.append({
            "id": f"f_{i+1:03d}",
            "name": desc[:50],
            "description": desc,
            "block_id": "BLK_A",
            "epsilon_g": g1.get("epsilon_g", 0.05),
            "horizon_t": g1.get("horizon_t", 3600),
            "severity": "high" if i == 0 else "medium",
            "measurement_map": g1.get("measurement_map", ""),
            "quality_assessment": "Generated from G¹ (fallback)",
        })
    blocks = [{
        "id": "BLK_A",
        "name": "Primary Goal Block",
        "predicate_ids": [p["id"] for p in predicates],
        "intra_rank": min(len(predicates), 3),
    }]
    return {"predicates": predicates, "blocks": blocks, "cross_coupling": []}


def _assess_quality(predicates: list[dict]) -> dict:
    """Assess predicate quality across four axes."""
    strong = moderate = weak = 0
    for p in predicates:
        qa = p.get("quality_assessment", "")
        if "Falsifiable" in qa and "Observable" in qa:
            strong += 1
        elif qa:
            moderate += 1
        else:
            weak += 1
    return {"strong": strong, "moderate": moderate, "weak": weak, "total": len(predicates)}


# ──────────────────────────────────────────────────────────────
# Tool 3: Build Coupling Model
# ──────────────────────────────────────────────────────────────

def im_build_coupling_model(
    workspace_id: str,
    mode: str = "generate",
    overrides: list[dict] | None = None,
    lock: bool = False,
) -> dict:
    """Build or update the coupling matrix M = Cov_ν(g).

    Args:
        workspace_id: The workspace to operate on.
        mode: 'generate' (initial) or 'update' (apply overrides).
        overrides: Cell-level overrides [{row, col, value}].
        lock: Set True to lock the matrix (no more edits).
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import build_coupling_matrix, update_coupling_matrix

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    if mode == "generate":
        M = build_coupling_matrix(ws.predicates, ws.predicate_blocks, ws.cross_block_coupling)
        ws.coupling_matrix = {
            "M": M,
            "human_overrides": [],
            "locked": lock,
            "reference_distribution": "Estimated from predicate structure",
        }
    elif mode == "update":
        if ws.coupling_matrix.get("locked"):
            return {"error": "Coupling matrix is locked. Unlock before editing."}
        existing_M = ws.coupling_matrix.get("M", [])
        if not existing_M:
            return {"error": "No coupling matrix to update. Run with mode='generate' first."}
        M = update_coupling_matrix(existing_M, overrides or [])
        all_overrides = ws.coupling_matrix.get("human_overrides", []) + (overrides or [])
        ws.coupling_matrix = {
            "M": M,
            "human_overrides": all_overrides,
            "locked": lock,
            "reference_distribution": ws.coupling_matrix.get("reference_distribution", ""),
        }
    else:
        return {"error": f"Unknown mode: {mode}. Use 'generate' or 'update'."}

    ws.stage = "coupling_built"
    update_workspace(ws)

    log_audit(workspace_id, "coupling_built", "im_build_coupling_model",
              input_summary=f"mode={mode}, overrides={len(overrides or [])}",
              output_summary=f"{len(ws.predicates)}×{len(ws.predicates)} matrix, locked={lock}")

    return {
        "workspace_id": workspace_id,
        "coupling_matrix": {
            "dimensions": f"{len(ws.predicates)}×{len(ws.predicates)}",
            "locked": ws.coupling_matrix.get("locked", False),
            "human_overrides_count": len(ws.coupling_matrix.get("human_overrides", [])),
        },
    }


# ──────────────────────────────────────────────────────────────
# Tool 4: Estimate Codimension
# ──────────────────────────────────────────────────────────────

def im_estimate_codimension(
    workspace_id: str,
    tau: float = 0.05,
    k_preloaded: list[dict] | None = None,
) -> dict:
    """Compute cod_π(G) = rank_τ(M), eigenspectrum, and per-predicate dim*(G).

    Args:
        workspace_id: The workspace to operate on.
        tau: Eigenvalue threshold (default 0.05).
        k_preloaded: Optional pre-loaded K entries that reduce codimension.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import compute_eigenspectrum

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    M = ws.coupling_matrix.get("M", [])
    if not M:
        return {"error": "No coupling matrix. Run im_build_coupling_model first."}

    result = compute_eigenspectrum(M, tau, ws.predicates, ws.predicate_blocks)

    # If K_preloaded provided, compute conditional codimension
    cod_given_k0 = None
    if k_preloaded:
        k0_reduction = sum(k.get("cod_reduction", 0) for k in k_preloaded)
        cod_given_k0 = max(1, result["cod_pi_g"] - int(k0_reduction))

    ws.codimension = {
        **result,
        "cod_pi_g_given_k0": cod_given_k0,
    }
    ws.stage = "codimension_estimated"
    update_workspace(ws)

    log_audit(workspace_id, "codimension_estimated", "im_estimate_codimension",
              input_summary=f"τ={tau}",
              output_summary=f"cod_π(G)={result['cod_pi_g']}, {len(result['eigenspectrum'])} eigenvalues")

    return {
        "workspace_id": workspace_id,
        "codimension": ws.codimension,
    }


# ──────────────────────────────────────────────────────────────
# Tool 5: Rank Budget and Regime
# ──────────────────────────────────────────────────────────────

def im_rank_budget_and_regime(
    workspace_id: str,
    agent_pool: list[dict] | None = None,
    orchestrator: dict | None = None,
) -> dict:
    """Compute rank budget allocation and regime classification.

    Args:
        workspace_id: The workspace to operate on.
        agent_pool: Agent specifications [{agent_id, model_family, jacobian_rank, steering_spectrum, context_window}].
        orchestrator: Orchestrator spec {model_family, jacobian_rank, steering_spectrum}.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import compute_rank_budget

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    cod_pi_g = ws.codimension.get("cod_pi_g", 0)
    if cod_pi_g == 0:
        return {"error": "No codimension computed. Run im_estimate_codimension first."}

    # Default agent pool if not provided
    if not agent_pool:
        agent_pool = _default_agent_pool(cod_pi_g)
    if not orchestrator:
        orchestrator = {"model_family": "Claude Opus 4.6", "jacobian_rank": 5,
                       "steering_spectrum": [1.0, 0.8, 0.6, 0.4, 0.2]}

    cross_count = len(ws.cross_block_coupling)
    result = compute_rank_budget(cod_pi_g, agent_pool, orchestrator, cross_count)

    ws.rank_budget = {
        "agent_pool": agent_pool,
        "orchestrator": orchestrator,
        **result,
    }
    ws.stage = "rank_budgeted"
    update_workspace(ws)

    log_audit(workspace_id, "rank_budgeted", "im_rank_budget_and_regime",
              input_summary=f"{len(agent_pool)} agents, orch_rank={orchestrator.get('jacobian_rank')}",
              output_summary=f"regime={result['regime']}, surplus={result['rank_surplus_or_deficit']}")

    return {
        "workspace_id": workspace_id,
        "rank_budget": ws.rank_budget,
    }


def _default_agent_pool(cod_pi_g: int) -> list[dict]:
    """Generate a reasonable default agent pool based on codimension."""
    n_agents = max(2, min(8, cod_pi_g // 2))
    pool = []
    models = ["GPT-4o", "GPT-4o-mini", "Claude Sonnet 4.5", "Claude Haiku 4.5"]
    for i in range(n_agents):
        pool.append({
            "agent_id": f"agent_{i+1}",
            "name": f"Task Agent {i+1}",
            "model_family": models[i % len(models)],
            "jacobian_rank": max(1, 3 - (i // 2)),
            "steering_spectrum": [1.0, 0.7, 0.4][:max(1, 3 - (i // 2))],
            "context_window": 200000,
        })
    return pool


# ──────────────────────────────────────────────────────────────
# Tool 6: Memory Tier Design
# ──────────────────────────────────────────────────────────────

def im_memory_tier_design(workspace_id: str) -> dict:
    """Design memory subsystem: tiers, K-scopes, crystallisation policy.

    Args:
        workspace_id: The workspace to operate on.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import design_memory_tiers

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    cod_pi_g = ws.codimension.get("cod_pi_g", 0)
    regime = ws.rank_budget.get("regime", "medium")
    agent_pool = ws.rank_budget.get("agent_pool", [])
    orchestrator = ws.rank_budget.get("orchestrator", {})

    result = design_memory_tiers(cod_pi_g, regime, agent_pool, orchestrator)

    ws.memory = result
    ws.stage = "memory_designed"
    update_workspace(ws)

    log_audit(workspace_id, "memory_designed", "im_memory_tier_design",
              input_summary=f"cod={cod_pi_g}, regime={regime}",
              output_summary=f"{len(result.get('tiers', []))} tiers, regime={regime}")

    return {
        "workspace_id": workspace_id,
        "memory": ws.memory,
    }


# ──────────────────────────────────────────────────────────────
# Tool 7: Synthesize Agent Specs
# ──────────────────────────────────────────────────────────────

def im_synthesize_agent_specs(workspace_id: str) -> dict:
    """Compute optimal assignment α*: {f_i} → {a_j} and per-agent specs.

    Args:
        workspace_id: The workspace to operate on.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import synthesize_agent_specs

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    M = ws.coupling_matrix.get("M", [])
    if not M:
        return {"error": "No coupling matrix. Run im_build_coupling_model first."}

    agent_pool = ws.rank_budget.get("agent_pool", [])
    orchestrator = ws.rank_budget.get("orchestrator", {})

    result = synthesize_agent_specs(M, ws.predicates, ws.predicate_blocks,
                                    agent_pool, orchestrator)

    ws.assignment = result
    ws.stage = "agents_synthesized"
    update_workspace(ws)

    log_audit(workspace_id, "agents_synthesized", "im_synthesize_agent_specs",
              input_summary=f"{len(agent_pool)} agents, {len(ws.predicates)} predicates",
              output_summary=f"Δ_norm={result.get('delta_norm', 0):.4f}, γ={result.get('governance_margin', 0)}")

    return {
        "workspace_id": workspace_id,
        "assignment": {
            "alpha_count": len(result.get("alpha", [])),
            "delta_rank": result.get("delta_rank", 0),
            "delta_norm": result.get("delta_norm", 0),
            "governance_margin": result.get("governance_margin", 0),
            "agents": result.get("agents", []),
        },
    }


# ──────────────────────────────────────────────────────────────
# Tool 8: Synthesize Workflow Spec
# ──────────────────────────────────────────────────────────────

def im_synthesize_workflow_spec(workspace_id: str) -> dict:
    """Synthesize complete workflow specification.

    Args:
        workspace_id: The workspace to operate on.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import synthesize_workflow_spec

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    result = synthesize_workflow_spec(
        ws.assignment, ws.rank_budget, ws.predicates,
        ws.predicate_blocks, ws.cross_block_coupling,
    )

    ws.workflow = result
    ws.stage = "workflow_synthesized"
    update_workspace(ws)

    topo = result.get("topology", {})
    log_audit(workspace_id, "workflow_synthesized", "im_synthesize_workflow_spec",
              input_summary=f"assignment: {len(ws.assignment.get('alpha', []))} mappings",
              output_summary=f"topology={topo.get('pattern')}, nodes={len(topo.get('nodes', []))}, compiled={result.get('compiled')}")

    return {
        "workspace_id": workspace_id,
        "workflow": {
            "topology_pattern": topo.get("pattern"),
            "node_count": len(topo.get("nodes", [])),
            "edge_count": len(topo.get("edges", [])),
            "compiled": result.get("compiled", False),
            "validation_errors": result.get("validation_errors", []),
        },
    }


# ──────────────────────────────────────────────────────────────
# Tool 9: Validate Feasibility
# ──────────────────────────────────────────────────────────────

def im_validate_feasibility(workspace_id: str) -> dict:
    """Final feasibility check — Thm. architecture-design.

    Args:
        workspace_id: The workspace to operate on.
    """
    from src.im.store import get_workspace, update_workspace, log_audit
    from src.im.engine import validate_feasibility

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    result = validate_feasibility(
        ws.assignment, ws.rank_budget, ws.codimension,
        ws.predicates, ws.workflow,
    )

    ws.feasibility = result
    ws.stage = "feasibility_validated"
    update_workspace(ws)

    log_audit(workspace_id, "feasibility_validated", "im_validate_feasibility",
              input_summary="Full pipeline check",
              output_summary=f"verdict={result['verdict']}, γ={result.get('governance_margin', 0)}")

    return {
        "workspace_id": workspace_id,
        "feasibility": result,
    }


# ──────────────────────────────────────────────────────────────
# Utility tools
# ──────────────────────────────────────────────────────────────

def im_list_workspaces(limit: int = 20) -> dict:
    """List all IM workspaces.

    Args:
        limit: Maximum number of workspaces to return.
    """
    from src.im.store import list_workspaces
    workspaces = list_workspaces(limit=limit)
    return {"workspaces": workspaces, "count": len(workspaces)}


def im_get_workspace(workspace_id: str) -> dict:
    """Get full workspace state including all pipeline stages.

    Args:
        workspace_id: The workspace ID to fetch.
    """
    from src.im.store import get_workspace, get_audit_trail

    ws = get_workspace(workspace_id)
    if not ws:
        return {"error": f"Workspace {workspace_id} not found"}

    audit = get_audit_trail(workspace_id)

    return {
        "workspace_id": ws.workspace_id,
        "stage": ws.stage,
        "version": ws.version,
        "raw_intent": ws.raw_intent,
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
        "goal_tuple": ws.goal_tuple,
        "predicate_count": len(ws.predicates),
        "block_count": len(ws.predicate_blocks),
        "coupling_locked": ws.coupling_matrix.get("locked", False),
        "codimension": ws.codimension.get("cod_pi_g"),
        "regime": ws.rank_budget.get("regime"),
        "verdict": ws.feasibility.get("verdict"),
        "audit_trail": audit,
    }


def im_run_full_pipeline(
    raw_intent: str,
    context: str = "",
    agent_pool: list[dict] | None = None,
    orchestrator: dict | None = None,
    tau: float = 0.05,
) -> dict:
    """Run the complete IM pipeline from natural language to feasibility verdict.

    Convenience tool that calls all 9 tools in sequence.

    Args:
        raw_intent: User's natural-language goal description.
        context: Optional domain context.
        agent_pool: Optional custom agent pool.
        orchestrator: Optional custom orchestrator spec.
        tau: Eigenvalue threshold (default 0.05).
    """
    # Tool 1: Parse goal
    result = im_parse_goal_tuple(raw_intent, context)
    if "error" in result:
        return result
    ws_id = result["workspace_id"]

    # Tool 2: Generate predicates
    result = im_generate_failure_predicates(ws_id)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 3: Build coupling model
    result = im_build_coupling_model(ws_id, mode="generate", lock=True)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 4: Estimate codimension
    result = im_estimate_codimension(ws_id, tau=tau)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 5: Rank budget
    result = im_rank_budget_and_regime(ws_id, agent_pool=agent_pool,
                                       orchestrator=orchestrator)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 6: Memory tier design
    result = im_memory_tier_design(ws_id)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 7: Agent synthesis
    result = im_synthesize_agent_specs(ws_id)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 8: Workflow synthesis
    result = im_synthesize_workflow_spec(ws_id)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Tool 9: Feasibility
    result = im_validate_feasibility(ws_id)
    if "error" in result:
        return {"workspace_id": ws_id, **result}

    # Return summary
    return {
        "workspace_id": ws_id,
        "verdict": result.get("feasibility", {}).get("verdict"),
        "stage": "feasibility_validated",
        "summary": im_get_workspace(ws_id),
    }


# ──────────────────────────────────────────────────────────────
# Tool registry for Holly
# ──────────────────────────────────────────────────────────────

IM_TOOLS = {
    "im_parse_goal_tuple": im_parse_goal_tuple,
    "im_generate_failure_predicates": im_generate_failure_predicates,
    "im_build_coupling_model": im_build_coupling_model,
    "im_estimate_codimension": im_estimate_codimension,
    "im_rank_budget_and_regime": im_rank_budget_and_regime,
    "im_memory_tier_design": im_memory_tier_design,
    "im_synthesize_agent_specs": im_synthesize_agent_specs,
    "im_synthesize_workflow_spec": im_synthesize_workflow_spec,
    "im_validate_feasibility": im_validate_feasibility,
    "im_list_workspaces": im_list_workspaces,
    "im_get_workspace": im_get_workspace,
    "im_run_full_pipeline": im_run_full_pipeline,
}

IM_TOOL_SCHEMAS = [
    {
        "name": "im_parse_goal_tuple",
        "description": "Parse natural-language intent into G⁰ preference and G¹ candidates. Creates a new IM workspace. This is step 1 of the 9-step Architecture Selection pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_intent": {"type": "string", "description": "User's natural-language goal description"},
                "context": {"type": "string", "description": "Optional domain context or constraints"},
            },
            "required": ["raw_intent"],
        },
    },
    {
        "name": "im_generate_failure_predicates",
        "description": "Decompose selected G¹ into failure predicates, blocks, and coupling axes. Step 2 of the pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
                "g1_index": {"type": "integer", "description": "Which G¹ candidate to use (default 0)"},
                "domain_hints": {"type": "array", "items": {"type": "string"}, "description": "Domain-specific predicate templates"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_build_coupling_model",
        "description": "Build or update the coupling matrix M = Cov_ν(g). Step 3. Mode 'generate' creates initial matrix; 'update' applies human overrides.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
                "mode": {"type": "string", "enum": ["generate", "update"], "description": "Generate initial matrix or update with overrides"},
                "overrides": {"type": "array", "items": {"type": "object"}, "description": "Cell overrides [{row, col, value}]"},
                "lock": {"type": "boolean", "description": "Lock the matrix after this operation"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_estimate_codimension",
        "description": "Compute cod_π(G) = rank_τ(M), eigenspectrum λ(M), and per-predicate dim*(G). Step 4.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
                "tau": {"type": "number", "description": "Eigenvalue threshold (default 0.05)"},
                "k_preloaded": {"type": "array", "items": {"type": "object"}, "description": "Pre-loaded K entries [{name, resolves, cod_reduction}]"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_rank_budget_and_regime",
        "description": "Compute rank budget allocation and regime classification (simple/medium/complex). Step 5.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
                "agent_pool": {"type": "array", "items": {"type": "object"}, "description": "Agent specs [{agent_id, model_family, jacobian_rank, steering_spectrum, context_window}]"},
                "orchestrator": {"type": "object", "description": "Orchestrator spec {model_family, jacobian_rank, steering_spectrum}"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_memory_tier_design",
        "description": "Design memory subsystem: tier structure (M0-M3), K-scopes, crystallisation policy. Step 6.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_synthesize_agent_specs",
        "description": "Compute optimal predicate-to-agent assignment α* that minimizes infeasibility residual ‖Δ‖. Step 7.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_synthesize_workflow_spec",
        "description": "Synthesize complete workflow: topology, channels, blanket levels, escalation routes. Step 8.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_validate_feasibility",
        "description": "Final feasibility check (Thm. architecture-design). Checks rank coverage, coupling coverage, power coverage. Returns verdict: feasible or infeasible with remediation. Step 9.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The IM workspace ID"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_list_workspaces",
        "description": "List all IM design workspaces with their current pipeline stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max workspaces to return (default 20)"},
            },
        },
    },
    {
        "name": "im_get_workspace",
        "description": "Get full workspace state including all pipeline stages and audit trail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string", "description": "The workspace ID to fetch"},
            },
            "required": ["workspace_id"],
        },
    },
    {
        "name": "im_run_full_pipeline",
        "description": "Run the complete 9-step IM pipeline from natural language to feasibility verdict in one call. Convenience wrapper that calls all 9 tools in sequence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_intent": {"type": "string", "description": "User's natural-language goal description"},
                "context": {"type": "string", "description": "Optional domain context"},
                "agent_pool": {"type": "array", "items": {"type": "object"}, "description": "Custom agent pool (optional)"},
                "orchestrator": {"type": "object", "description": "Custom orchestrator spec (optional)"},
                "tau": {"type": "number", "description": "Eigenvalue threshold (default 0.05)"},
            },
            "required": ["raw_intent"],
        },
    },
]
