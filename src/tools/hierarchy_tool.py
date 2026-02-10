"""Goal Hierarchy tools — read-only LangChain tools for querying the hierarchy.

Six tools for agents to check gate status, feasibility, predicates,
eigenspectrum, modules, and upward coupling budget.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GateLevelInput(BaseModel):
    level: Optional[int] = Field(default=None, description="Level to check (0-6), or omit for all levels")


@tool(args_schema=GateLevelInput)
def hierarchy_gate_status(level: Optional[int] = None) -> str:
    """Check if the lexicographic gate is open at a given level (0-6). Returns gate status with any failing predicates."""
    from src.hierarchy.engine import evaluate_gate
    from src.hierarchy.store import get_all_predicates

    predicates = get_all_predicates()
    if not predicates:
        return json.dumps({"error": "Hierarchy not seeded yet"})

    gate = evaluate_gate(predicates)

    if level is not None:
        gs = gate.get(level)
        if gs is None:
            return json.dumps({"error": f"No gate data for level {level}"})
        return json.dumps({
            "level": gs.level,
            "is_open": gs.is_open,
            "failing_predicates": gs.failing_predicates,
        })

    return json.dumps([{
        "level": gs.level,
        "is_open": gs.is_open,
        "failing_predicates": gs.failing_predicates,
    } for gs in sorted(gate.values(), key=lambda x: x.level)])


@tool
def hierarchy_feasibility_check() -> str:
    """Run full feasibility verification (Statement 55) and return pass/fail with details."""
    from src.hierarchy.engine import verify_feasibility
    from src.hierarchy.store import (
        get_all_agents,
        get_all_blocks,
        get_all_coupling_axes,
        get_all_eigenvalues,
        get_all_orchestrators,
        get_all_predicates,
    )

    predicates = get_all_predicates()
    blocks = get_all_blocks()
    agents = get_all_agents()
    orchestrators = get_all_orchestrators()
    eigenvalues = get_all_eigenvalues()
    axes = get_all_coupling_axes()

    result = verify_feasibility(predicates, blocks, agents, orchestrators, eigenvalues, axes)
    return json.dumps({
        "overall": result.overall,
        "rank_coverage": result.rank_coverage,
        "coupling_coverage": result.coupling_coverage,
        "epsilon_check": result.epsilon_check,
        "details": result.details,
    })


class PredicateInput(BaseModel):
    index: Optional[int] = Field(default=None, description="Predicate index (1-37+), or omit for all")
    level: Optional[int] = Field(default=None, description="Filter by level (0-6)")


@tool(args_schema=PredicateInput)
def hierarchy_predicate_status(index: Optional[int] = None, level: Optional[int] = None) -> str:
    """Get current status of one or all predicates. Includes current_value and last_observed."""
    from src.hierarchy.store import get_all_predicates, get_predicate, get_predicates_by_level

    if index is not None:
        p = get_predicate(index)
        if not p:
            return json.dumps({"error": f"No predicate with index {index}"})
        return json.dumps({
            "index": p.index, "name": p.name, "level": p.level, "block": p.block,
            "epsilon_dmg": p.epsilon_dmg, "current_value": p.current_value,
            "last_observed": p.last_observed.isoformat() if p.last_observed else None,
        })

    if level is not None:
        preds = get_predicates_by_level(level)
    else:
        preds = get_all_predicates()

    return json.dumps([{
        "index": p.index, "name": p.name, "level": p.level, "block": p.block,
        "epsilon_dmg": p.epsilon_dmg, "current_value": p.current_value,
        "last_observed": p.last_observed.isoformat() if p.last_observed else None,
    } for p in preds])


@tool
def hierarchy_eigenspectrum() -> str:
    """Get the eigenspectrum decomposition — eigenvalues with interpretations and cod(G)."""
    from src.hierarchy.store import get_all_eigenvalues

    eigenvalues = get_all_eigenvalues()
    return json.dumps({
        "cod_g": len(eigenvalues),
        "eigenvalues": [{
            "index": e.index, "value": e.value, "layer": e.layer,
            "dominant_predicates": e.dominant_predicates,
            "interpretation": e.interpretation,
        } for e in eigenvalues],
    })


@tool
def hierarchy_module_list() -> str:
    """List all Terrestrial modules with their status, predicate counts, and agent assignments."""
    from src.hierarchy.store import list_modules

    modules = list_modules()
    return json.dumps([{
        "module_id": m.module_id, "name": m.name, "level": m.level,
        "status": m.status, "predicate_count": len(m.predicate_indices),
        "predicate_indices": m.predicate_indices,
        "agent_id": m.agent_id, "upward_channels": m.upward_channels,
    } for m in modules])


@tool
def hierarchy_upward_coupling_budget() -> str:
    """Check remaining upward coupling budget — used/max channels and O3 rank status."""
    from src.hierarchy.engine import check_o3_rank
    from src.hierarchy.store import get_all_coupling_axes, get_all_orchestrators, list_modules

    axes = get_all_coupling_axes()
    orchestrators = get_all_orchestrators()
    modules = list_modules()

    upward_axes = [a for a in axes if a.axis_type == "upward"]
    cross_module_axes = [a for a in axes if a.axis_type == "terrestrial-internal"]

    o3 = next((o for o in orchestrators if o.orchestrator_id == "O3"), None)
    o3_rank = o3.rank if o3 else 0

    rank_check = check_o3_rank(len(upward_axes), len(cross_module_axes), o3_rank)

    return json.dumps({
        "upward_channels": {
            "used": len(upward_axes),
            "max": 2,
            "channels": [{"source": a.source_predicate, "target": a.target_predicate,
                          "rho": a.rho, "channel_id": a.channel_id} for a in upward_axes],
        },
        "o3_rank_check": rank_check,
        "modules_with_upward": [{
            "module_id": m.module_id,
            "upward_channels": m.upward_channels,
        } for m in modules if m.upward_channels],
    })
