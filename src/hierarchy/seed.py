"""Seed the goal hierarchy from documented data.

Hardcodes all 37 predicates, 10 blocks, coupling axes, 9 agents,
3 orchestrators, 3 Terrestrial modules, and 19 eigenvalues from
the goal-hierarchy/ markdown documents.

Idempotent — uses upsert. Runs on startup if hierarchy_predicates is empty.
"""

from __future__ import annotations

import logging

from src.hierarchy.models import (
    CouplingAxis,
    Eigenvalue,
    GateStatus,
    HierarchyAgent,
    HierarchyBlock,
    HierarchyOrchestrator,
    HierarchyPredicate,
    TerrestrialModule,
)
from src.hierarchy.store import (
    get_all_predicates,
    update_gate_status,
    upsert_agent,
    upsert_block,
    upsert_coupling_axis,
    upsert_eigenvalue,
    upsert_module,
    upsert_orchestrator,
    upsert_predicate,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Predicates
# ======================================================================

_PREDICATES = [
    # Level 0 — Transcendent Orientation
    HierarchyPredicate(1,  "Truthfulness",           0, "A", "All outputs faithful to known facts; unknowns acknowledged",                    0.04, 0.01, "a1"),
    HierarchyPredicate(2,  "Humility",               0, "A", "Claims proportional to evidence; no assertion of certainty beyond warrant",      0.05, 0.01, "a1"),
    HierarchyPredicate(3,  "Benevolent intent",      0, "B", "Every action traceable to a benefit for some party",                            0.04, 0.01, "a2"),
    HierarchyPredicate(4,  "Fairness",               0, "B", "No systematic bias in treatment across persons, groups, or stakeholders",       0.06, 0.01, "a2"),
    HierarchyPredicate(5,  "Gratitude / Reverence",  0, "A", "Acknowledgment of gifts, dependencies, and what is owed to sources of capability", 0.03, 0.01, "a1"),

    # Level 1 — Conscience
    HierarchyPredicate(6,  "Value consistency",      1, "C", "Actions do not contradict previously stated or demonstrated values",             0.06, 0.02, "a3"),
    HierarchyPredicate(7,  "Commitment integrity",   1, "C", "Promises tracked and honored or explicitly renegotiated",                       0.07, 0.02, "a3"),
    HierarchyPredicate(8,  "Moral awareness",        1, "C", "Ethically salient features identified before action",                           0.08, 0.02, "a3"),
    HierarchyPredicate(9,  "Doubt integration",      1, "C", "When uncertain about morality, pause, seek input, or default to conservative",  0.09, 0.02, "a3"),

    # Level 2 — Nonmaleficence
    HierarchyPredicate(10, "No intended harm",        2, "D", "No action selected because it harms another or with harm as accepted means",    0.03, 0.03, "a4"),
    HierarchyPredicate(11, "Foreseeable harm check",  2, "D", "Proportionality analysis when action has foreseeable harmful side effects",     0.07, 0.03, "a4"),
    HierarchyPredicate(12, "Vulnerability awareness", 2, "D", "Extra scrutiny when actions affect vulnerable parties",                        0.06, 0.03, "a4"),
    HierarchyPredicate(13, "Deception prohibition",   2, "D", "No intentional creation of false beliefs for instrumental benefit",             0.04, 0.03, "a4"),

    # Level 3 — Legal Rights
    HierarchyPredicate(14, "Rights identification",   3, "E", "Applicable legal rights of affected parties identified to best knowledge",     0.08, 0.05, "a5"),
    HierarchyPredicate(15, "Compliance check",        3, "E", "Planned actions verified against identified rights; conflicts flagged",         0.07, 0.05, "a5"),
    HierarchyPredicate(16, "Privacy protection",      3, "E", "Personal data handled in compliance with applicable privacy law",              0.06, 0.05, "a5"),
    HierarchyPredicate(17, "IP respect",              3, "E", "Intellectual property rights respected; no unauthorized use",                  0.05, 0.05, "a5"),
    HierarchyPredicate(18, "Contractual fidelity",    3, "E", "Contractual obligations honored; breaches avoided or flagged",                 0.06, 0.05, "a5"),

    # Level 4 — Self-Preservation
    HierarchyPredicate(19, "Operational integrity",   4, "F", "Core systems, memory, and reasoning maintained within functional bounds",       0.05, 0.10, "a6"),
    HierarchyPredicate(20, "Resource sustainability", 4, "F", "Resource consumption does not exceed sustainable inflow",                       0.08, 0.10, "a6"),
    HierarchyPredicate(21, "Reputation protection",   4, "G", "Actions do not predictably degrade standing or trustworthiness",               0.07, 0.10, "a6"),
    HierarchyPredicate(22, "Security posture",        4, "F", "Attack surfaces minimized; credentials and keys protected",                    0.06, 0.10, "a6"),
    HierarchyPredicate(23, "Burnout prevention",      4, "F", "Workload on human collaborators does not exceed sustainable levels",            0.07, 0.10, "a6"),

    # Level 5 — Profit (profit-ecommerce module)
    HierarchyPredicate(24, "Revenue generation",     5, "H", "Revenue exceeds minimum threshold over rolling period",                         0.13, 0.20, "a7", "profit-ecommerce"),
    HierarchyPredicate(25, "Cost efficiency",        5, "H", "Operating costs within budget; no runaway resource consumption",                0.10, 0.20, "a7", "profit-ecommerce"),
    HierarchyPredicate(26, "Growth trajectory",      5, "H", "Key growth metrics on positive trend",                                         0.12, 0.20, "a7", "profit-ecommerce"),
    HierarchyPredicate(27, "Value delivery",         5, "H", "Customers report receiving value commensurate with price",                      0.09, 0.20, "a7", "profit-ecommerce"),
    HierarchyPredicate(28, "Risk-adjusted return",   5, "H", "Expected return exceeds cost of capital on risk-adjusted basis",                0.11, 0.20, "a7", "profit-ecommerce"),

    # Level 5 — Readiness (readiness-squadron module)
    HierarchyPredicate(33, "Deploy readiness",             5, "J", ">=90% medically cleared; >=85% fitness pass rate",                         0.08, 0.15, "a9", "readiness-squadron"),
    HierarchyPredicate(34, "Weapons system proficiency",   5, "J", ">=95% primary qual; >=85% secondary; zero overdue certifications",         0.10, 0.15, "a9", "readiness-squadron"),
    HierarchyPredicate(35, "Unit cohesion",                5, "J", "DEOCS >=65th pctl; voluntary attrition <5%; no unresolved complaints >30d", 0.12, 0.20, "a9", "readiness-squadron"),
    HierarchyPredicate(36, "Innovation and creativity",    5, "J", ">=2 proposals/flight/qtr; AAR >=90%; >=1 wargame/qtr",                    0.14, 0.25, "a9", "readiness-squadron"),
    HierarchyPredicate(37, "Empowerment",                  5, "J", "Climate survey >=70th pctl; delegation current; >=3 NCO/CGO actions/mo",  0.11, 0.20, "a9", "readiness-squadron"),

    # Level 6 — Personality (personality-humor module)
    HierarchyPredicate(29, "Humor appropriateness",    6, "I", "All humor passes harm/reputation screening before delivery",                   0.08, 0.50, "a8", "personality-humor"),
    HierarchyPredicate(30, "Engagement quality",       6, "I", "Audience engagement signals positive on personality-driven interactions",       0.10, 0.50, "a8", "personality-humor"),
    HierarchyPredicate(31, "Brand voice consistency",  6, "I", "Personality expression consistent with established brand voice",               0.07, 0.50, "a8", "personality-humor"),
    HierarchyPredicate(32, "Timing sense",             6, "I", "Personality expression occurs at contextually appropriate moments",             0.09, 0.50, "a8", "personality-humor"),
]

# ======================================================================
# Blocks
# ======================================================================

_BLOCKS = [
    HierarchyBlock("A", "Transcendent (truth/humility/gratitude)", 0, [1, 2, 5], 2),
    HierarchyBlock("B", "Transcendent (benevolence/fairness)",     0, [3, 4], 1),
    HierarchyBlock("C", "Conscience",                              1, [6, 7, 8, 9], 3),
    HierarchyBlock("D", "Nonmaleficence",                          2, [10, 11, 12, 13], 3),
    HierarchyBlock("E", "Legal rights",                            3, [14, 15, 16, 17, 18], 3),
    HierarchyBlock("F", "Self-preservation (ops)",                 4, [19, 20, 22, 23], 2),
    HierarchyBlock("G", "Self-preservation (reputation)",          4, [21], 1),
    HierarchyBlock("H", "Profit (e-commerce)",                     5, [24, 25, 26, 27, 28], 3, "profit-ecommerce"),
    HierarchyBlock("J", "Readiness (squadron)",                    5, [33, 34, 35, 36, 37], 3, "readiness-squadron"),
    HierarchyBlock("I", "Personality (humor)",                     6, [29, 30, 31, 32], 2, "personality-humor"),
]

# ======================================================================
# Coupling Axes
# ======================================================================

_COUPLING_AXES = [
    # Level 0 intra-block (A)
    CouplingAxis(1, 2, 0.6, "intra-block"),
    CouplingAxis(1, 5, 0.2, "intra-block"),
    CouplingAxis(2, 5, 0.5, "intra-block"),
    CouplingAxis(1, 3, 0.4, "intra-block"),
    CouplingAxis(1, 4, 0.3, "intra-block"),
    CouplingAxis(2, 3, 0.3, "intra-block"),
    CouplingAxis(2, 4, 0.2, "intra-block"),
    CouplingAxis(3, 4, 0.5, "intra-block"),
    CouplingAxis(3, 5, 0.3, "intra-block"),
    CouplingAxis(4, 5, 0.2, "intra-block"),

    # Level 1 intra-block (C)
    CouplingAxis(6, 7, 0.7, "intra-block"),
    CouplingAxis(6, 8, 0.5, "intra-block"),
    CouplingAxis(6, 9, 0.4, "intra-block"),
    CouplingAxis(7, 8, 0.4, "intra-block"),
    CouplingAxis(7, 9, 0.3, "intra-block"),
    CouplingAxis(8, 9, 0.6, "intra-block"),

    # Level 2 intra-block (D)
    CouplingAxis(10, 11, 0.5, "intra-block"),
    CouplingAxis(10, 12, 0.4, "intra-block"),
    CouplingAxis(10, 13, 0.6, "intra-block"),
    CouplingAxis(11, 12, 0.5, "intra-block"),
    CouplingAxis(11, 13, 0.4, "intra-block"),
    CouplingAxis(12, 13, 0.3, "intra-block"),

    # Level 3 intra-block (E)
    CouplingAxis(14, 15, 0.8, "intra-block"),
    CouplingAxis(14, 16, 0.5, "intra-block"),
    CouplingAxis(14, 17, 0.4, "intra-block"),
    CouplingAxis(14, 18, 0.5, "intra-block"),
    CouplingAxis(15, 16, 0.6, "intra-block"),
    CouplingAxis(15, 17, 0.5, "intra-block"),
    CouplingAxis(15, 18, 0.6, "intra-block"),
    CouplingAxis(16, 17, 0.3, "intra-block"),
    CouplingAxis(16, 18, 0.4, "intra-block"),
    CouplingAxis(17, 18, 0.5, "intra-block"),

    # Level 4 intra-block (F)
    CouplingAxis(19, 20, 0.5, "intra-block"),
    CouplingAxis(19, 22, 0.6, "intra-block"),
    CouplingAxis(19, 23, 0.3, "intra-block"),
    CouplingAxis(20, 22, 0.3, "intra-block"),
    CouplingAxis(20, 23, 0.5, "intra-block"),
    CouplingAxis(22, 23, 0.2, "intra-block"),
    # G is a singleton (f21), no intra-block
    # F-G cross (reputation)
    CouplingAxis(21, 19, 0.3, "intra-block"),
    CouplingAxis(21, 20, 0.4, "intra-block"),
    CouplingAxis(21, 22, 0.2, "intra-block"),
    CouplingAxis(21, 23, 0.2, "intra-block"),

    # Level 5 intra-block (H - profit)
    CouplingAxis(24, 25, 0.6, "intra-block"),
    CouplingAxis(24, 26, 0.7, "intra-block"),
    CouplingAxis(24, 27, 0.5, "intra-block"),
    CouplingAxis(24, 28, 0.8, "intra-block"),
    CouplingAxis(25, 26, 0.3, "intra-block"),
    CouplingAxis(25, 27, 0.4, "intra-block"),
    CouplingAxis(25, 28, 0.7, "intra-block"),
    CouplingAxis(26, 27, 0.5, "intra-block"),
    CouplingAxis(26, 28, 0.6, "intra-block"),
    CouplingAxis(27, 28, 0.4, "intra-block"),

    # Level 5 intra-block (J - readiness)
    CouplingAxis(33, 34, 0.6, "intra-block"),
    CouplingAxis(33, 35, 0.5, "intra-block"),
    CouplingAxis(33, 36, 0.3, "intra-block"),
    CouplingAxis(33, 37, 0.4, "intra-block"),
    CouplingAxis(34, 35, 0.4, "intra-block"),
    CouplingAxis(34, 36, 0.4, "intra-block"),
    CouplingAxis(34, 37, 0.3, "intra-block"),
    CouplingAxis(35, 36, 0.5, "intra-block"),
    CouplingAxis(35, 37, 0.7, "intra-block"),
    CouplingAxis(36, 37, 0.7, "intra-block"),

    # Level 6 intra-block (I - personality)
    CouplingAxis(29, 30, 0.4, "intra-block"),
    CouplingAxis(29, 31, 0.3, "intra-block"),
    CouplingAxis(29, 32, 0.5, "intra-block"),
    CouplingAxis(30, 31, 0.6, "intra-block"),
    CouplingAxis(30, 32, 0.3, "intra-block"),
    CouplingAxis(31, 32, 0.4, "intra-block"),

    # Cross-block / cross-level: Celestial internal
    CouplingAxis(8, 11, 0.6, "cross-block"),   # Moral awareness → Foreseeable harm (C→D)
    CouplingAxis(1, 15, 0.4, "cross-block"),   # Truthfulness → Compliance (A→E)
    CouplingAxis(10, 21, 0.5, "cross-block"),  # No intended harm → Reputation (D→G)
    CouplingAxis(15, 21, 0.6, "cross-block"),  # Compliance → Reputation (E→G)
    CouplingAxis(3, 12, 0.4, "cross-block"),   # Benevolent intent → Vulnerability (B→D)
    CouplingAxis(13, 16, 0.4, "cross-block"),  # Deception prohibition → Privacy (D→E)
    CouplingAxis(12, 4, 0.4, "cross-block"),   # Vulnerability awareness → Fairness (D→B)

    # Cross-layer: downward / terrestrial-internal / upward
    CouplingAxis(19, 24, 0.5, "downward", "DC-1"),   # System health → Profit (F→H)
    CouplingAxis(27, 30, 0.5, "terrestrial-internal", "TC-1"),  # Value delivery → Engagement (H→I)
    CouplingAxis(29, 10, 0.3, "upward", "UC-1"),      # Humor → Harm (I→D)
    CouplingAxis(29, 21, 0.4, "upward", "UC-2"),      # Humor → Reputation (I→G)
]

# ======================================================================
# Agents
# ======================================================================

_AGENTS = [
    HierarchyAgent("a1", "Transcendent Integrity Agent",  [1, 2, 5], 2, 3, 8e3, "celestial"),
    HierarchyAgent("a2", "Benevolence Agent",             [3, 4], 1, 2, 5e3, "celestial"),
    HierarchyAgent("a3", "Conscience Agent",              [6, 7, 8, 9], 3, 4, 1e4, "celestial"),
    HierarchyAgent("a4", "Nonmaleficence Agent",          [10, 11, 12, 13], 3, 4, 1e4, "celestial"),
    HierarchyAgent("a5", "Legal Rights Agent",            [14, 15, 16, 17, 18], 3, 5, 8e3, "celestial"),
    HierarchyAgent("a6", "Self-Preservation Agent",       [19, 20, 21, 22, 23], 3, 5, 5e3, "celestial"),
    HierarchyAgent("a7", "Profit Agent",                  [24, 25, 26, 27, 28], 3, 4, 1e4, "terrestrial"),
    HierarchyAgent("a8", "Personality Agent",             [29, 30, 31, 32], 2, 4, 6e3, "terrestrial"),
    HierarchyAgent("a9", "Squadron Readiness Agent",      [33, 34, 35, 36, 37], 3, 4, 1e4, "terrestrial"),
]

# ======================================================================
# Orchestrators
# ======================================================================

_ORCHESTRATORS = [
    HierarchyOrchestrator("O1", "Moral Governor", 6,
                          ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9"],
                          "Lexicographic gate enforcement; cross-level coupling; upward coupling final arbiter"),
    HierarchyOrchestrator("O2", "Moral Chain Governor", 3,
                          ["a1", "a2", "a3", "a4", "a5"],
                          "Celestial-internal L0→L1→L2→L3 moral chain"),
    HierarchyOrchestrator("O3", "Value Chain Governor", 3,
                          ["a6", "a7", "a8"],
                          "Cross-layer L4→L5→L6 + upward L6→L2,L4 coupling"),
]

# ======================================================================
# Terrestrial Modules
# ======================================================================

_MODULES = [
    TerrestrialModule("profit-ecommerce", "Profit (E-Commerce)", 5, "Active",
                      [24, 25, 26, 27, 28], "a7", []),
    TerrestrialModule("readiness-squadron", "Squadron Readiness", 5, "Active",
                      [33, 34, 35, 36, 37], "a9", []),
    TerrestrialModule("personality-humor", "Personality (Humor)", 6, "Active",
                      [29, 30, 31, 32], "a8", ["UC-1", "UC-2"]),
]

# ======================================================================
# Eigenvalues
# ======================================================================

_EIGENVALUES = [
    Eigenvalue(1,  0.52, [24, 26, 28], "Profit engine mode — revenue/growth/return triad", "terrestrial"),
    Eigenvalue(2,  0.48, [35, 36, 37], "Organizational health mode — cohesion/innovation/empowerment triad", "terrestrial"),
    Eigenvalue(3,  0.38, [14, 15, 18], "Legal compliance mode — rights/check/contract triad", "celestial"),
    Eigenvalue(4,  0.31, [6, 7, 8],    "Conscience coherence mode — values/commitment/awareness", "celestial"),
    Eigenvalue(5,  0.27, [1, 2],        "Truthfulness-humility mode — epistemic integrity", "celestial"),
    Eigenvalue(6,  0.23, [10, 11, 13],  "Harm prevention mode — intent/foresight/deception", "celestial"),
    Eigenvalue(7,  0.19, [19, 22],      "System integrity mode — operations/security", "celestial"),
    Eigenvalue(8,  0.16, [3, 4, 12],    "Benevolence-fairness-vulnerability mode", "celestial"),
    Eigenvalue(9,  0.14, [29, 32],      "Humor-timing mode — personality coherence", "terrestrial"),
    Eigenvalue(10, 0.11, [20, 23],      "Sustainability mode — resource/burnout", "celestial"),
    Eigenvalue(11, 0.09, [33, 34],      "Hard readiness mode — deploy fitness + weapons", "terrestrial"),
    Eigenvalue(12, 0.09, [16, 17],      "IP-privacy mode — data/property rights", "celestial"),
    Eigenvalue(13, 0.07, [30, 31],      "Brand mode — engagement/voice consistency", "terrestrial"),
    Eigenvalue(14, 0.06, [33],          "Individual medical — deploy readiness independent", "terrestrial"),
    Eigenvalue(15, 0.05, [27],          "Value delivery independent component", "terrestrial"),
    Eigenvalue(16, 0.04, [25],          "Cost efficiency independent component", "terrestrial"),
    Eigenvalue(17, 0.03, [5],           "Gratitude independent component", "celestial"),
    Eigenvalue(18, 0.03, [9],           "Doubt integration independent component", "celestial"),
    Eigenvalue(19, 0.02, [21],          "Reputation independent component", "celestial"),
]


def seed_hierarchy() -> None:
    """Seed the full goal hierarchy into the database. Idempotent."""
    existing = get_all_predicates()
    if existing:
        logger.info("Hierarchy already seeded (%d predicates), skipping", len(existing))
        return

    logger.info("Seeding goal hierarchy: %d predicates, %d blocks, %d axes, %d agents, "
                "%d orchestrators, %d modules, %d eigenvalues",
                len(_PREDICATES), len(_BLOCKS), len(_COUPLING_AXES), len(_AGENTS),
                len(_ORCHESTRATORS), len(_MODULES), len(_EIGENVALUES))

    for p in _PREDICATES:
        upsert_predicate(p)

    for b in _BLOCKS:
        upsert_block(b)

    for a in _COUPLING_AXES:
        upsert_coupling_axis(a)

    for ag in _AGENTS:
        upsert_agent(ag)

    for o in _ORCHESTRATORS:
        upsert_orchestrator(o)

    for m in _MODULES:
        upsert_module(m)

    for e in _EIGENVALUES:
        upsert_eigenvalue(e)

    # Initialize gate status: all levels open (no observations yet)
    for level in range(7):
        update_gate_status(GateStatus(level=level, is_open=True, failing_predicates=[]))

    logger.info("Goal hierarchy seeded successfully")
