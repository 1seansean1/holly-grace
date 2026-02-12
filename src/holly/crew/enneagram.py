"""Enneagram type assignments and morphogenetic sensitivity matrices.

Maps each crew agent to an enneagram type for team personality cohesion.
Defines coupling axes (sensitivity matrices) between crew members based
on complementary enneagram interactions.

Enneagram types:
1=Reformer, 2=Helper, 3=Achiever, 4=Individualist, 5=Investigator,
6=Loyalist, 7=Enthusiast, 8=Challenger, 9=Peacemaker

Design principles:
- Complement, don't duplicate: adjacent types cooperate best
- Integration arrows: stressed types move to their disintegration point
- Healthy teams mix thinking (5,6,7), feeling (2,3,4), and gut (8,9,1)
- Triad balance: each sub-team should span at least 2 triads
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ── Type definitions ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnneagramType:
    number: int
    name: str
    triad: str  # "thinking" | "feeling" | "gut"
    core_desire: str
    core_fear: str
    voice_traits: list[str]  # How this type communicates


ENNEAGRAM_TYPES: dict[int, EnneagramType] = {
    1: EnneagramType(1, "Reformer", "gut", "integrity", "corruption",
                     ["precise", "principled", "corrective", "measured"]),
    2: EnneagramType(2, "Helper", "feeling", "to be loved", "being unwanted",
                     ["warm", "supportive", "attentive", "encouraging"]),
    3: EnneagramType(3, "Achiever", "feeling", "to be valuable", "worthlessness",
                     ["confident", "goal-oriented", "efficient", "motivating"]),
    4: EnneagramType(4, "Individualist", "feeling", "identity", "no significance",
                     ["expressive", "authentic", "introspective", "creative"]),
    5: EnneagramType(5, "Investigator", "thinking", "competence", "uselessness",
                     ["analytical", "detached", "thorough", "precise"]),
    6: EnneagramType(6, "Loyalist", "thinking", "security", "abandonment",
                     ["cautious", "questioning", "reliable", "methodical"]),
    7: EnneagramType(7, "Enthusiast", "thinking", "satisfaction", "deprivation",
                     ["optimistic", "versatile", "spontaneous", "practical"]),
    8: EnneagramType(8, "Challenger", "gut", "self-protection", "being controlled",
                     ["direct", "decisive", "assertive", "confrontational"]),
    9: EnneagramType(9, "Peacemaker", "gut", "inner peace", "loss/separation",
                     ["calm", "mediating", "receptive", "reassuring"]),
}


# ── Crew agent type assignments ──────────────────────────────────────────

CREW_ENNEAGRAM_MAP: dict[str, int] = {
    # Thinking triad (5, 6, 7)
    "crew_architect": 5,         # Investigator: designs with analytical precision
    "crew_lead_researcher": 5,   # Investigator: deep research protocol
    "crew_epsilon_tuner": 6,     # Loyalist: cautious parameter guardian
    "crew_cyber_security": 6,    # Loyalist: security-conscious, questions everything
    "crew_tool_smith": 7,        # Enthusiast: creative tool builder
    # Feeling triad (2, 3, 4)
    "crew_program_manager": 3,   # Achiever: drives projects to completion
    "crew_strategic_advisor": 3, # Achiever: results-oriented strategy
    "crew_product_manager": 2,   # Helper: serves stakeholders and users
    "crew_mcp_creator": 4,       # Individualist: creative integrations
    # Gut triad (8, 9, 1)
    "crew_critic": 1,            # Reformer: principled review, high standards
    "crew_test_engineer": 1,     # Reformer: insists on correctness
    "crew_finance_officer": 6,   # Loyalist: fiscal responsibility and caution
    "crew_wise_old_man": 9,      # Peacemaker: calm wisdom, reconciles conflict
    "crew_system_engineer": 1,   # Reformer: documentation accuracy and order
    "crew_debugger": 8,           # Challenger: direct, decisive, confrontational diagnostics
}


# ── Sensitivity matrix (coupling axes) ───────────────────────────────────

@dataclass(frozen=True)
class CouplingAxis:
    """Defines how two crew members interact on a specific dimension."""
    agent_a: str
    agent_b: str
    axis: str          # What they share or complement
    strength: float    # 0.0 (weak) to 1.0 (strong)
    direction: str     # "synergy" | "tension" | "mentoring"


# Morphogenetic sensitivity matrix: how crew agents couple
SENSITIVITY_MATRIX: list[CouplingAxis] = [
    # --- Strong synergies (type-complementary pairs) ---
    CouplingAxis("crew_architect", "crew_critic", "design_review",
                 0.95, "tension"),  # 5↔1: Investigator designs, Reformer refines
    CouplingAxis("crew_architect", "crew_wiring_tech", "design_to_implementation",
                 0.90, "mentoring"),  # 5→7: Thinker guides builder
    CouplingAxis("crew_tool_smith", "crew_test_engineer", "build_verify",
                 0.85, "synergy"),  # 7↔1: Enthusiast builds, Reformer validates
    CouplingAxis("crew_program_manager", "crew_product_manager", "project_product_alignment",
                 0.90, "synergy"),  # 3↔2: Achiever drives, Helper prioritizes
    CouplingAxis("crew_strategic_advisor", "crew_finance_officer", "strategy_budget",
                 0.80, "tension"),  # 3↔6: Achiever pushes, Loyalist constrains
    CouplingAxis("crew_lead_researcher", "crew_wise_old_man", "knowledge_depth",
                 0.85, "synergy"),  # 5↔9: Deep thinker + calm elder
    CouplingAxis("crew_epsilon_tuner", "crew_finance_officer", "cost_epsilon_balance",
                 0.90, "synergy"),  # 6↔6: Both Loyalists — shared caution
    CouplingAxis("crew_cyber_security", "crew_critic", "security_review",
                 0.80, "synergy"),  # 6↔1: Both cautious + principled
    CouplingAxis("crew_mcp_creator", "crew_system_engineer", "integration_documentation",
                 0.75, "mentoring"),  # 4→1: Creator produces, Engineer documents

    # --- Creative tension (useful disagreement) ---
    CouplingAxis("crew_strategic_advisor", "crew_critic", "strategy_challenge",
                 0.70, "tension"),  # 3↔1: Bold plans challenged by standards
    CouplingAxis("crew_product_manager", "crew_finance_officer", "feature_vs_budget",
                 0.65, "tension"),  # 2↔6: User wants vs fiscal caution
    CouplingAxis("crew_tool_smith", "crew_cyber_security", "capability_vs_safety",
                 0.60, "tension"),  # 7↔6: Creative expansion vs security constraints

    # --- Mentoring relationships ---
    CouplingAxis("crew_wise_old_man", "crew_architect", "pattern_wisdom",
                 0.80, "mentoring"),  # 9→5: Peacemaker guides Investigator
    CouplingAxis("crew_lead_researcher", "crew_epsilon_tuner", "research_to_tuning",
                 0.75, "mentoring"),  # 5→6: Researcher informs Tuner

    # --- Debugger coupling axes ---
    CouplingAxis("crew_debugger", "crew_test_engineer", "failure_forensics",
                 0.90, "synergy"),  # 8↔1: Challenger finds bug, Reformer writes regression test
    CouplingAxis("crew_debugger", "crew_architect", "design_vs_reality",
                 0.85, "tension"),  # 8↔5: Debugger finds where implementation diverged from design
    CouplingAxis("crew_debugger", "crew_system_engineer", "state_inspection",
                 0.80, "synergy"),  # 8↔1: Debugger probes, Engineer documents findings
    CouplingAxis("crew_debugger", "crew_wise_old_man", "incident_history",
                 0.75, "mentoring"),  # 9→8: Elder provides historical context for recurring bugs
    CouplingAxis("crew_debugger", "crew_cyber_security", "security_escalation",
                 0.85, "synergy"),  # 8↔6: Challenger contains, Loyalist investigates compromise
]


def get_crew_type(agent_id: str) -> EnneagramType | None:
    """Get the enneagram type for a crew agent."""
    type_num = CREW_ENNEAGRAM_MAP.get(agent_id)
    if type_num is None:
        return None
    return ENNEAGRAM_TYPES.get(type_num)


def get_coupling_axes(agent_id: str) -> list[dict]:
    """Get all coupling axes involving a specific agent."""
    axes = []
    for ca in SENSITIVITY_MATRIX:
        if ca.agent_a == agent_id or ca.agent_b == agent_id:
            partner = ca.agent_b if ca.agent_a == agent_id else ca.agent_a
            axes.append({
                "partner": partner,
                "axis": ca.axis,
                "strength": ca.strength,
                "direction": ca.direction,
            })
    return axes


def build_enneagram_prompt_section(agent_id: str) -> str:
    """Build the enneagram personality section for a crew agent's prompt.

    Returns a string to append to the system prompt, or empty string if
    the agent has no enneagram assignment.
    """
    etype = get_crew_type(agent_id)
    if not etype:
        return ""

    axes = get_coupling_axes(agent_id)

    lines = [
        f"\n## Personality Profile (Enneagram {etype.number}: {etype.name})",
        f"Triad: {etype.triad.title()} | Core drive: {etype.core_desire} | Guard against: {etype.core_fear}",
        f"Communication style: {', '.join(etype.voice_traits)}.",
    ]

    if axes:
        lines.append("\n## Team Coupling")
        for ax in sorted(axes, key=lambda a: -a["strength"]):
            icon = {"synergy": "+", "tension": "~", "mentoring": ">"}[ax["direction"]]
            lines.append(f"  [{icon}] {ax['partner'].replace('crew_', '')}: "
                        f"{ax['axis']} (strength={ax['strength']})")

    return "\n".join(lines)


def get_team_balance_report() -> dict:
    """Analyze team balance across triads and types."""
    triad_counts: dict[str, int] = {"thinking": 0, "feeling": 0, "gut": 0}
    type_counts: dict[int, int] = {}

    for agent_id, type_num in CREW_ENNEAGRAM_MAP.items():
        etype = ENNEAGRAM_TYPES.get(type_num)
        if etype:
            triad_counts[etype.triad] = triad_counts.get(etype.triad, 0) + 1
            type_counts[type_num] = type_counts.get(type_num, 0) + 1

    return {
        "triad_balance": triad_counts,
        "type_distribution": {
            f"{num} ({ENNEAGRAM_TYPES[num].name})": count
            for num, count in sorted(type_counts.items())
        },
        "total_agents": len(CREW_ENNEAGRAM_MAP),
        "coupling_axes": len(SENSITIVITY_MATRIX),
        "avg_coupling_strength": round(
            sum(ca.strength for ca in SENSITIVITY_MATRIX) / len(SENSITIVITY_MATRIX), 2
        ) if SENSITIVITY_MATRIX else 0,
    }
