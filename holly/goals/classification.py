"""T0–T3 task classification per Goal Hierarchy §4.3.

Implements task-level classification for routing goals to appropriate
execution tier: T0 (reflexive), T1 (deliberative), T2 (collaborative),
or T3 (morphogenetic).

References:
  - Goal Hierarchy Formal Spec §4.3 (APS tier classification)
  - ICD-011 (APS Controller → Topology Manager)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskLevel(Enum):
    """T0–T3 task classification levels per Goal Hierarchy §3.x.
    
    Attributes:
        T0: Safety-critical, single-agent, reflexive (direct response).
            Requires Celestial L0 only.
        T1: Regulated, single-agent, deliberative (multi-step planning).
            Requires Celestial L0 + L1.
        T2: Standard, multi-agent, collaborative (fixed contracts).
            Requires Celestial L0 + L1 + L2.
        T3: Unrestricted, multi-agent, morphogenetic (dynamic topology).
            Requires all Celestial L0–L4.
    """

    T0 = 0  # Reflexive
    T1 = 1  # Deliberative
    T2 = 2  # Collaborative
    T3 = 3  # Morphogenetic

    @property
    def description(self) -> str:
        """Human-readable description of this task level."""
        descriptions = {
            TaskLevel.T0: "Reflexive: single agent, direct response",
            TaskLevel.T1: "Deliberative: single agent, multi-step planning",
            TaskLevel.T2: "Collaborative: multiple agents, fixed contracts",
            TaskLevel.T3: "Morphogenetic: multiple agents, dynamic topology",
        }
        return descriptions[self]


@dataclass(slots=True, frozen=True)
class TaskClassification:
    """Classification result for a task or operation.
    
    Attributes:
        task_id: Unique identifier for the task being classified.
        level: TaskLevel (T0–T3) assigned to this task.
        required_celestial_levels: Tuple of required Celestial check levels.
            T0 → (0,), T1 → (0, 1), T2 → (0, 1, 2), T3 → (0, 1, 2, 3, 4).
        rationale: Free-text explanation of the classification decision.
    """

    task_id: str
    level: TaskLevel
    required_celestial_levels: tuple[int, ...]
    rationale: str

    def __str__(self) -> str:
        """Format classification for logging."""
        levels_str = ",".join(str(l) for l in self.required_celestial_levels)
        return (
            f"Task {self.task_id}: {self.level.name} "
            f"(requires L{levels_str}) — {self.rationale}"
        )


@dataclass(slots=True, frozen=True)
class ClassificationResult:
    """Result of classifying a task.
    
    Attributes:
        task_id: Identifier of the classified task.
        classification: TaskClassification with level and details.
        celestial_checks_required: Count of Celestial checks needed.
    """

    task_id: str
    classification: TaskClassification
    celestial_checks_required: int


class TaskClassifier:
    """Classifies tasks/operations into T0–T3 levels per Goal Hierarchy.
    
    The TaskClassifier routes goals to the appropriate execution tier based on
    their structural properties (codimension, agency rank, topology dynamics).
    
    Per Goal Hierarchy §4.3:
      - T0: Single agent, codim(G) ≤ 1, rank_min ≤ 1
      - T1: Single agent, 1 < codim(G) ≤ 4, rank_min ≤ 1
      - T2: Multiple agents, rank_min ≥ 2, #agents ≥ 2
      - T3: Multiple agents, codim(G) > 4, eigenspectrum_divergence > θ
    """

    def __init__(self) -> None:
        """Initialize the TaskClassifier."""
        pass

    def classify(self, task_id: str, context: dict[str, Any]) -> TaskClassification:
        """Classify a task based on its context and structural properties.
        
        Args:
            task_id: Unique identifier for the task.
            context: Dictionary containing goal properties:
                - codimension: int (structural dimension of goal)
                - agency_rank: int (minimum rank of assigned agents)
                - num_agents: int (number of agents required)
                - eigenspectrum_divergence: float (topology adaptivity metric)
                - is_safety_critical: bool (requires T0 regardless)
        
        Returns:
            TaskClassification with assigned level and rationale.
        
        Raises:
            ValueError: If context is missing required keys.
        """
        required_keys = {
            "codimension",
            "agency_rank",
            "num_agents",
            "eigenspectrum_divergence",
        }
        if not required_keys.issubset(context.keys()):
            missing = required_keys - set(context.keys())
            raise ValueError(f"Missing required context keys: {missing}")

        codim = context["codimension"]
        agency_rank = context["agency_rank"]
        num_agents = context["num_agents"]
        eigspec = context["eigenspectrum_divergence"]
        is_safety = context.get("is_safety_critical", False)

        # Safety-critical tasks always go to T0
        if is_safety:
            return TaskClassification(
                task_id=task_id,
                level=TaskLevel.T0,
                required_celestial_levels=(0,),
                rationale="Safety-critical operation: T0 (L0 only)",
            )

        # T3: Multiple agents, high codimension, dynamic topology
        if num_agents >= 2 and codim > 4 and eigspec > 0.5:
            return TaskClassification(
                task_id=task_id,
                level=TaskLevel.T3,
                required_celestial_levels=(0, 1, 2, 3, 4),
                rationale=(
                    f"Morphogenetic: {num_agents} agents, codim={codim}, "
                    f"eigenspectrum={eigspec:.2f} → T3 (all L0–L4)"
                ),
            )

        # T2: Multiple agents, fixed contracts
        if num_agents >= 2 and agency_rank >= 2:
            return TaskClassification(
                task_id=task_id,
                level=TaskLevel.T2,
                required_celestial_levels=(0, 1, 2),
                rationale=(
                    f"Collaborative: {num_agents} agents, agency_rank={agency_rank} "
                    "→ T2 (L0–L2)"
                ),
            )

        # T1: Single agent, multi-step planning
        if codim > 1 and codim <= 4:
            return TaskClassification(
                task_id=task_id,
                level=TaskLevel.T1,
                required_celestial_levels=(0, 1),
                rationale=(
                    f"Deliberative: codim={codim}, single agent → "
                    "T1 (L0–L1)"
                ),
            )

        # T0: Single agent, reflexive
        return TaskClassification(
            task_id=task_id,
            level=TaskLevel.T0,
            required_celestial_levels=(0,),
            rationale="Reflexive: codim≤1, single agent → T0 (L0 only)",
        )

    def required_checks(self, level: TaskLevel) -> tuple[int, ...]:
        """Return required Celestial level checks for a given task level.
        
        Args:
            level: TaskLevel (T0–T3).
        
        Returns:
            Tuple of required Celestial check indices (0–4).
            T0 → (0,), T1 → (0, 1), T2 → (0, 1, 2), T3 → (0, 1, 2, 3, 4).
        """
        mapping = {
            TaskLevel.T0: (0,),
            TaskLevel.T1: (0, 1),
            TaskLevel.T2: (0, 1, 2),
            TaskLevel.T3: (0, 1, 2, 3, 4),
        }
        return mapping[level]

    def is_permitted(
        self, classification: TaskClassification, celestial_state: dict[str, bool]
    ) -> bool:
        """Check if a classified task is permitted given Celestial checks.
        
        Args:
            classification: TaskClassification with required_celestial_levels.
            celestial_state: Dict mapping Celestial level (0–4) to pass/fail bool.
                Keys: "L0", "L1", "L2", "L3", "L4".
        
        Returns:
            True if all required Celestial checks pass; False otherwise.
        
        Raises:
            ValueError: If required level is missing from celestial_state.
        """
        for level_idx in classification.required_celestial_levels:
            key = f"L{level_idx}"
            if key not in celestial_state:
                raise ValueError(
                    f"Missing Celestial state for level {key}. "
                    f"State keys: {list(celestial_state.keys())}"
                )
            if not celestial_state[key]:
                return False
        return True
