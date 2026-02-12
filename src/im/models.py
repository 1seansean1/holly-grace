"""Data models for IM workspace pipeline.

Maps directly to the plan's §2 Shared Data Model, translated from TypeScript
interfaces to Python dataclasses to match Holly Grace's existing patterns
(see src/hierarchy/models.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class WorkspaceStage(str, Enum):
    """Pipeline stage the workspace is currently at."""
    CREATED = "created"
    GOAL_PARSED = "goal_parsed"
    PREDICATES_GENERATED = "predicates_generated"
    COUPLING_BUILT = "coupling_built"
    CODIMENSION_ESTIMATED = "codimension_estimated"
    RANK_BUDGETED = "rank_budgeted"
    MEMORY_DESIGNED = "memory_designed"
    AGENTS_SYNTHESIZED = "agents_synthesized"
    WORKFLOW_SYNTHESIZED = "workflow_synthesized"
    FEASIBILITY_VALIDATED = "feasibility_validated"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Regime(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class TopologyPattern(str, Enum):
    FLAT = "flat"
    PIPELINE = "pipeline"
    HIERARCHICAL = "hierarchical"
    MESH = "mesh"
    HYBRID = "hybrid"


class Verdict(str, Enum):
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


# ──────────────────────────────────────────────────────────────
# Stage 1: Goal parsing
# ──────────────────────────────────────────────────────────────

@dataclass
class G1Tuple:
    """A candidate G¹ specification (Def. G1 from the paper)."""
    failure_predicates: list[str] = field(default_factory=list)
    epsilon_g: float = 0.05
    horizon_t: int = 3600
    measurement_map: str = ""


@dataclass
class GoalTuple:
    """Stage 1 output: G⁰ preference + candidate G¹ tuples."""
    g0_preference: str = ""
    g1_candidates: list[dict] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    selected_g1_index: int | None = None


# ──────────────────────────────────────────────────────────────
# Stage 2: Failure predicates
# ──────────────────────────────────────────────────────────────

@dataclass
class IMPredicate:
    """A failure predicate f_i (Def. goal-predicate-set).

    Distinct from HierarchyPredicate which represents Holly's own
    celestial/terrestrial predicates. IMPredicate is per-workspace.
    """
    id: str                   # e.g., "f_001"
    name: str
    description: str = ""
    block_id: str = ""
    epsilon_g: float = 0.05   # per-predicate tolerance
    horizon_t: int = 3600     # evaluation horizon (seconds)
    severity: str = "medium"  # critical|high|medium|low
    measurement_map: str = ""
    dim_star: float | None = None
    quality_assessment: str = ""


@dataclass
class IMBlock:
    """A block of correlated predicates (Def. assignment)."""
    id: str                   # e.g., "BLK_A"
    name: str = ""
    predicate_ids: list[str] = field(default_factory=list)
    intra_rank: int | None = None


@dataclass
class CrossBlockCoupling:
    """A coupling relationship between blocks."""
    from_block: str
    to_block: str
    rho: float = 0.0         # coupling strength ∈ [0,1]
    mechanism: str = ""
    direction: str = ""


# ──────────────────────────────────────────────────────────────
# Stage 3: Coupling matrix
# ──────────────────────────────────────────────────────────────

@dataclass
class MatrixOverride:
    """A human edit to a coupling matrix cell."""
    row: int
    col: int
    value: float


@dataclass
class CouplingMatrix:
    """The coupling matrix M = Cov_ν(g) (Def. goal-coupling-matrix)."""
    m: list[list[float]] = field(default_factory=list)
    human_overrides: list[dict] = field(default_factory=list)
    locked: bool = False
    reference_distribution: str = ""


# ──────────────────────────────────────────────────────────────
# Stage 4: Codimension
# ──────────────────────────────────────────────────────────────

@dataclass
class IMEigenvalue:
    """An eigenvalue from the coupling matrix decomposition."""
    index: int
    value: float
    block_attribution: str = ""


@dataclass
class Codimension:
    """Codimension estimate (Def. codimension, goal-complexity)."""
    eigenspectrum: list[dict] = field(default_factory=list)
    tau: float = 0.05
    cod_pi_g: int = 0
    cod_pi_g_given_k0: int | None = None
    dim_star_per_predicate: list[float] = field(default_factory=list)
    total_dim_star: float = 0.0


# ──────────────────────────────────────────────────────────────
# Stage 5: Rank budget
# ──────────────────────────────────────────────────────────────

@dataclass
class IMAgentSpec:
    """An agent specification for the workspace."""
    agent_id: str
    name: str = ""
    model_family: str = ""
    context_window: int = 200000
    jacobian_rank: int = 1
    steering_spectrum: list[float] = field(default_factory=list)
    assigned_predicates: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    blanket_level: int = 0


@dataclass
class IMOrchestratorSpec:
    """An orchestrator specification."""
    model_family: str = ""
    jacobian_rank: int = 1
    steering_spectrum: list[float] = field(default_factory=list)


@dataclass
class RankBudget:
    """Rank budget and regime classification (Thm. architecture-design)."""
    agent_pool: list[dict] = field(default_factory=list)
    orchestrator: dict = field(default_factory=dict)
    regime: str = "simple"
    regime_rationale: str = ""
    total_rank: int = 0
    cod_pi_g: int = 0
    rank_surplus_or_deficit: int = 0
    orch_rank_lower_bound: int = 0
    coupling_rank_by_topology: dict = field(default_factory=dict)
    self_mgmt_threshold: int = 0
    max_agent_rank: int = 0
    remediation: str | None = None


# ──────────────────────────────────────────────────────────────
# Stage 6: Memory architecture
# ──────────────────────────────────────────────────────────────

@dataclass
class MemoryTier:
    """A memory tier (Def. mem-tiers)."""
    tier: str                 # M0, M1, M2, M3
    scope: str = ""
    cod_target: str = ""
    content: str = ""
    manager: str = ""
    persistence: str = ""
    capacity: str = ""


@dataclass
class KEntry:
    """A shared-context K entry (Thm. codim-reduction)."""
    name: str
    resolves: str = ""
    cod_reduction: float = 0.0
    tier: str = ""


@dataclass
class CrystallisationPolicy:
    """Crystallisation policy (Def. crystallise)."""
    primary_criterion: str = ""
    secondary_criterion: str = ""
    reject_criterion: str = ""


@dataclass
class MemoryArchitecture:
    """Full memory architecture output."""
    tiers: list[dict] = field(default_factory=list)
    k_preloaded: list[dict] = field(default_factory=list)
    k_runtime_candidates: list[dict] = field(default_factory=list)
    crystallisation_policy: dict = field(default_factory=dict)
    right_sizing: dict = field(default_factory=dict)
    audit_schedule: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────
# Stage 7: Assignment
# ──────────────────────────────────────────────────────────────

@dataclass
class Assignment:
    """Predicate-to-agent assignment (Def. assignment)."""
    alpha: list[dict] = field(default_factory=list)
    j_alpha: list[list[float]] = field(default_factory=list)
    agents: list[dict] = field(default_factory=list)
    delta: list[list[float]] = field(default_factory=list)
    delta_rank: int = 0
    delta_norm: float = 0.0
    governance_margin: float = 0.0


# ──────────────────────────────────────────────────────────────
# Stage 8: Workflow spec
# ──────────────────────────────────────────────────────────────

@dataclass
class TopologyNode:
    """A node in the workflow topology."""
    node_id: str
    agent_id: str = ""
    role: str = ""


@dataclass
class TopologyEdge:
    """An edge in the workflow topology."""
    source: str
    target: str
    protocol: str = "async"
    capacity: int = 0


@dataclass
class WorkflowSpec:
    """Complete workflow specification (Thm. architecture-selection)."""
    topology: dict = field(default_factory=dict)
    channels: list[dict] = field(default_factory=list)
    blanket_levels: list[dict] = field(default_factory=list)
    morphology_params: dict = field(default_factory=dict)
    logic_profiles: list[dict] = field(default_factory=list)
    escalation_routes: list[dict] = field(default_factory=list)
    compiled: bool = False
    validation_errors: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Stage 9: Feasibility
# ──────────────────────────────────────────────────────────────

@dataclass
class Feasibility:
    """Feasibility validation result (Thm. feasibility, architecture-design)."""
    rank_coverage: bool = False
    coupling_coverage: bool = False
    power_coverage: bool = False
    governance_margin: float = 0.0
    epsilon_effective: list[float] = field(default_factory=list)
    epsilon_damage: list[float] = field(default_factory=list)
    axes_violating_power: list[str] = field(default_factory=list)
    delta_norm: float = 0.0
    delta_rank: int = 0
    verdict: str = "infeasible"
    remediation: dict | None = None


# ──────────────────────────────────────────────────────────────
# The Workspace — accumulates state across the pipeline
# ──────────────────────────────────────────────────────────────

@dataclass
class IMWorkspace:
    """The canonical shared data structure across all 9 tools.

    Each tool reads from and writes back to the workspace.
    Maps to plan §2.1 Workspace Schema.
    """
    workspace_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 1
    stage: str = "created"

    # Stage 0: Raw intent
    raw_intent: str = ""

    # Stage 1: Goal tuple
    goal_tuple: dict = field(default_factory=dict)

    # Stage 2: Failure predicates
    predicates: list[dict] = field(default_factory=list)
    predicate_blocks: list[dict] = field(default_factory=list)
    cross_block_coupling: list[dict] = field(default_factory=list)

    # Stage 3: Coupling matrix
    coupling_matrix: dict = field(default_factory=dict)

    # Stage 4: Codimension
    codimension: dict = field(default_factory=dict)

    # Stage 5: Rank budget
    rank_budget: dict = field(default_factory=dict)

    # Stage 6: Memory architecture
    memory: dict = field(default_factory=dict)

    # Stage 7: Assignment
    assignment: dict = field(default_factory=dict)

    # Stage 8: Workflow spec
    workflow: dict = field(default_factory=dict)

    # Stage 9: Feasibility
    feasibility: dict = field(default_factory=dict)

    # Metadata
    created_by: str = "holly_grace"
    metadata: dict = field(default_factory=dict)
