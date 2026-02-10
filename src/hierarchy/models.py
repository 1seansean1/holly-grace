"""Data models for the goal hierarchy system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class HierarchyPredicate:
    """A single predicate in the goal hierarchy (f1..f37+)."""
    index: int
    name: str
    level: int
    block: str
    pass_condition: str
    variance: float
    epsilon_dmg: float
    agent_id: str
    module_id: str | None = None
    current_value: float | None = None
    last_observed: datetime | None = None


@dataclass
class CouplingAxis:
    """A coupling relationship between two predicates."""
    source_predicate: int
    target_predicate: int
    rho: float
    axis_type: str  # intra-block, cross-block, upward, downward, terrestrial-internal
    channel_id: str | None = None  # UC-1, UC-2, DC-1, TC-1, or None


@dataclass
class HierarchyBlock:
    """A block of correlated predicates."""
    block_id: str
    name: str
    level: int
    predicate_indices: list[int] = field(default_factory=list)
    rank: int = 0
    module_id: str | None = None


@dataclass
class HierarchyAgent:
    """An agent assigned to govern predicates."""
    agent_id: str
    name: str
    predicates: list[int] = field(default_factory=list)
    rank: int = 0
    capacity: int = 0
    sigma_max: float = 0.0
    layer: str = "celestial"


@dataclass
class HierarchyOrchestrator:
    """An orchestrator governing agents and cross-block coupling."""
    orchestrator_id: str
    name: str
    rank: int = 0
    governed_agents: list[str] = field(default_factory=list)
    role: str = ""


@dataclass
class TerrestrialModule:
    """A Terrestrial goal module (Level 5 or 6)."""
    module_id: str
    name: str
    level: int
    status: str = "Active"
    predicate_indices: list[int] = field(default_factory=list)
    agent_id: str = ""
    upward_channels: list[str] = field(default_factory=list)


@dataclass
class Eigenvalue:
    """An eigenvalue from the coupling matrix decomposition."""
    index: int
    value: float
    dominant_predicates: list[int] = field(default_factory=list)
    interpretation: str = ""
    layer: str = "celestial"


@dataclass
class FeasibilityResult:
    """Result of a feasibility verification (Statement 55)."""
    timestamp: datetime | None = None
    rank_coverage: bool = False
    coupling_coverage: bool = False
    epsilon_check: bool = False
    overall: bool = False
    details: dict = field(default_factory=dict)


@dataclass
class GateStatus:
    """Gate status for a single level."""
    level: int
    is_open: bool = True
    failing_predicates: list[int] = field(default_factory=list)
    timestamp: datetime | None = None
