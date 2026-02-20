"""Phase D → Phase E Goal Chain Verification.

Implements the formal goal chain that governs the transition from Phase D
(Safety) to Phase E (Core L2 Deployment). Defines phase goals with
preconditions and postconditions, validates chain consistency, and verifies
readiness for phase transition.

This module operationalizes the phase boundary as a directed acyclic graph
of goals where Phase D postconditions must match Phase E preconditions.

References:
  - Task 33.4: Phase D gate checklist
  - Task 33.2: Safety argument graph
  - Goal Hierarchy Formal Spec: Section 1.4 (Hierarchical Composition)
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Optional


@dataclasses.dataclass(slots=True)
class PhaseGoal:
    """A single goal node in the phase goal chain.

    Represents a measurable objective within a phase, with explicit
    preconditions and postconditions. Each goal is assigned a SIL level
    to track safety integrity across the phase boundary.

    Attributes:
        goal_id: Unique identifier (e.g., "D.G1", "E.G1")
        phase: Phase identifier ("D" or "E")
        description: Human-readable description of the goal
        preconditions: List of prerequisite condition identifiers that must be satisfied
            before this goal can be attempted
        postconditions: List of outcomes/guarantees that this goal provides upon completion
        sil_level: Safety Integrity Level (1-3)
    """

    goal_id: str
    phase: str
    description: str
    preconditions: list[str] = dataclasses.field(default_factory=list)
    postconditions: list[str] = dataclasses.field(default_factory=list)
    sil_level: int = 2

    def __post_init__(self) -> None:
        """Validate goal structure."""
        if self.phase not in ("D", "E"):
            raise ValueError(f"Invalid phase: {self.phase}. Must be 'D' or 'E'.")
        if not self.goal_id:
            raise ValueError("goal_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if self.sil_level not in (1, 2, 3):
            raise ValueError(f"Invalid SIL level: {self.sil_level}")

    def __repr__(self) -> str:
        return f"PhaseGoal({self.goal_id}@SIL-{self.sil_level})"


@dataclasses.dataclass(slots=True)
class PhaseGoalChain:
    """Directed acyclic graph of goals across phase boundary.

    Represents the complete chain of goals from Phase D through Phase E,
    with explicit transitions between them. Ensures that the postconditions
    of Phase D goals align with the preconditions of Phase E goals.

    Attributes:
        goals: List of PhaseGoal nodes in the chain
        transitions: Dictionary mapping goal_id → next_goal_id for chain ordering
    """

    goals: list[PhaseGoal] = dataclasses.field(default_factory=list)
    transitions: dict[str, str] = dataclasses.field(default_factory=dict)

    def add_goal(self, goal: PhaseGoal) -> None:
        """Add a goal to the chain.

        Args:
            goal: PhaseGoal to add

        Raises:
            ValueError: If goal_id already exists
        """
        for g in self.goals:
            if g.goal_id == goal.goal_id:
                raise ValueError(f"Goal {goal.goal_id} already exists")
        self.goals.append(goal)

    def add_transition(self, from_goal: str, to_goal: str) -> None:
        """Add a transition between goals.

        Args:
            from_goal: Source goal_id
            to_goal: Target goal_id

        Raises:
            ValueError: If either goal_id doesn't exist
        """
        goal_ids = {g.goal_id for g in self.goals}
        if from_goal not in goal_ids:
            raise ValueError(f"Goal {from_goal} not found")
        if to_goal not in goal_ids:
            raise ValueError(f"Goal {to_goal} not found")
        self.transitions[from_goal] = to_goal

    def get_goal(self, goal_id: str) -> Optional[PhaseGoal]:
        """Retrieve a goal by ID.

        Args:
            goal_id: Goal identifier

        Returns:
            PhaseGoal if found, None otherwise
        """
        for g in self.goals:
            if g.goal_id == goal_id:
                return g
        return None

    def goals_by_phase(self, phase: str) -> list[PhaseGoal]:
        """Get all goals for a specific phase.

        Args:
            phase: Phase identifier ("D" or "E")

        Returns:
            List of PhaseGoal objects in that phase
        """
        return [g for g in self.goals if g.phase == phase]


@dataclasses.dataclass(slots=True)
class GoalChainValidator:
    """Validates the structure and consistency of a PhaseGoalChain.

    Performs checks for:
    - All preconditions are postconditions of preceding goals
    - No cycles in the transition graph
    - Continuous chain (no orphaned goals)
    - SIL levels maintained across transitions
    """

    chain: PhaseGoalChain

    def validate(self) -> tuple[bool, list[str]]:
        """Perform all validations.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: list[str] = []

        errors.extend(self._check_preconditions())
        errors.extend(self._check_cycles())
        errors.extend(self._check_continuity())
        errors.extend(self._check_sil_integrity())

        return len(errors) == 0, errors

    def _check_preconditions(self) -> list[str]:
        """Check all preconditions are satisfied by previous goals."""
        errors: list[str] = []
        goal_postconditions: dict[str, set[str]] = {}

        # Build postcondition sets
        for goal in self.chain.goals:
            goal_postconditions[goal.goal_id] = set(goal.postconditions)

        # Check each goal's preconditions
        for goal in self.chain.goals:
            available_postconditions: set[str] = set()

            # Collect all postconditions from preceding goals
            for other_goal in self.chain.goals:
                if other_goal.goal_id in self.chain.transitions:
                    if self.chain.transitions[other_goal.goal_id] == goal.goal_id:
                        available_postconditions.update(other_goal.postconditions)

            # Check all preconditions are available
            required_preconditions = set(goal.preconditions)
            missing = required_preconditions - available_postconditions

            if missing and goal.preconditions:
                errors.append(
                    f"{goal.goal_id}: missing preconditions {missing}"
                )

        return errors

    def _check_cycles(self) -> list[str]:
        """Check for cycles in the transition graph using DFS."""
        errors: list[str] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def has_cycle(goal_id: str) -> bool:
            visited.add(goal_id)
            rec_stack.add(goal_id)

            if goal_id in self.chain.transitions:
                next_id = self.chain.transitions[goal_id]
                if next_id not in visited:
                    if has_cycle(next_id):
                        return True
                elif next_id in rec_stack:
                    return True

            rec_stack.remove(goal_id)
            return False

        for goal in self.chain.goals:
            if goal.goal_id not in visited:
                if has_cycle(goal.goal_id):
                    errors.append(f"Cycle detected from {goal.goal_id}")

        return errors

    def _check_continuity(self) -> list[str]:
        """Check that all goals are part of a continuous chain."""
        errors: list[str] = []

        if not self.chain.goals:
            return errors

        # Find starting nodes (no incoming edges)
        all_goal_ids = {g.goal_id for g in self.chain.goals}
        targets = set(self.chain.transitions.values())
        starts = all_goal_ids - targets

        if not starts:
            errors.append("No starting node (all goals have incoming edges)")
            return errors

        # Follow chain from each start
        visited: set[str] = set()
        for start in starts:
            current = start
            while current:
                visited.add(current)
                current = self.chain.transitions.get(current)

        # Check all goals are visited
        unvisited = all_goal_ids - visited
        if unvisited:
            errors.append(f"Orphaned goals not in chain: {unvisited}")

        return errors

    def _check_sil_integrity(self) -> list[str]:
        """Check SIL levels don't decrease across phase boundary."""
        errors: list[str] = []

        phase_d_goals = self.chain.goals_by_phase("D")
        phase_e_goals = self.chain.goals_by_phase("E")

        if not phase_d_goals or not phase_e_goals:
            return errors

        min_d_sil = min(g.sil_level for g in phase_d_goals)
        max_e_sil = max(g.sil_level for g in phase_e_goals)

        # Phase E should not exceed Phase D SIL
        if max_e_sil > min_d_sil:
            errors.append(
                f"SIL integrity violation: Phase E max ({max_e_sil}) > "
                f"Phase D min ({min_d_sil})"
            )

        return errors


@dataclasses.dataclass(slots=True)
class TransitionReadinessReport:
    """Assessment of readiness to transition between phases.

    Captures the complete status of phase transition, identifying which
    goals are met, which are pending, and what blockers exist.

    Attributes:
        phase_from: Source phase ("D")
        phase_to: Target phase ("E")
        goals_met: List of satisfied goal_ids
        goals_pending: List of unsatisfied goal_ids
        blockers: List of blocking conditions preventing transition
        ready: True if transition can proceed
        assessed_at: Timestamp of assessment
        sil_min: Minimum SIL level across met goals
    """

    phase_from: str
    phase_to: str
    goals_met: list[str] = dataclasses.field(default_factory=list)
    goals_pending: list[str] = dataclasses.field(default_factory=list)
    blockers: list[str] = dataclasses.field(default_factory=list)
    ready: bool = False
    assessed_at: datetime = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    sil_min: int = 2

    @property
    def completion_percentage(self) -> float:
        """Percentage of phase goals met.

        Returns:
            Float from 0.0 to 1.0
        """
        total = len(self.goals_met) + len(self.goals_pending)
        if total == 0:
            return 0.0
        return len(self.goals_met) / total

    def __repr__(self) -> str:
        status = "READY" if self.ready else "BLOCKED"
        return (
            f"TransitionReadinessReport({self.phase_from}→{self.phase_to} "
            f"{status} {self.completion_percentage*100:.0f}%)"
        )


@dataclasses.dataclass(slots=True)
class PhaseTransitionVerifier:
    """Verifies readiness for Phase D → Phase E transition.

    Implements the actual transition gate logic by checking:
    1. All Phase D goals are satisfied
    2. All Phase E prerequisites are met
    3. SIL levels are maintained
    4. No critical blockers exist
    """

    chain: PhaseGoalChain
    satisfied_goals: set[str] = dataclasses.field(default_factory=set)

    def mark_goal_satisfied(self, goal_id: str) -> None:
        """Mark a goal as satisfied.

        Args:
            goal_id: Goal to mark as satisfied

        Raises:
            ValueError: If goal_id not found
        """
        if not self.chain.get_goal(goal_id):
            raise ValueError(f"Goal {goal_id} not found in chain")
        self.satisfied_goals.add(goal_id)

    def check_d_goals_met(self) -> tuple[bool, list[str]]:
        """Check if all Phase D goals are satisfied.

        Returns:
            Tuple of (all_met, unsatisfied_goal_ids)
        """
        phase_d_goals = self.chain.goals_by_phase("D")
        unsatisfied = [
            g.goal_id for g in phase_d_goals if g.goal_id not in self.satisfied_goals
        ]
        return len(unsatisfied) == 0, unsatisfied

    def check_e_prerequisites(self) -> tuple[bool, list[str]]:
        """Check if all Phase E prerequisites are available.

        Verifies that Phase E preconditions are covered by Phase D postconditions
        or preceding Phase E goals.

        Returns:
            Tuple of (all_available, missing_prerequisites)
        """
        phase_e_goals = self.chain.goals_by_phase("E")
        available_postconditions: set[str] = set()

        # Collect all Phase D postconditions
        for goal in self.chain.goals_by_phase("D"):
            available_postconditions.update(goal.postconditions)

        # Collect postconditions from satisfied Phase E goals
        for goal in phase_e_goals:
            if goal.goal_id in self.satisfied_goals:
                available_postconditions.update(goal.postconditions)

        missing_prerequisites: list[str] = []
        for goal in phase_e_goals:
            required = set(goal.preconditions)
            missing = required - available_postconditions
            if missing:
                missing_prerequisites.extend(
                    [f"{goal.goal_id}:{p}" for p in missing]
                )

        return len(missing_prerequisites) == 0, missing_prerequisites

    def verify_transition(self) -> TransitionReadinessReport:
        """Verify complete readiness for Phase D → Phase E transition.

        Performs comprehensive checks and returns a detailed report.

        Returns:
            TransitionReadinessReport with full assessment
        """
        # Check Phase D goals
        d_all_met, d_unsatisfied = self.check_d_goals_met()

        # Check Phase E prerequisites
        e_ready, e_missing = self.check_e_prerequisites()

        # Validate chain structure
        validator = GoalChainValidator(self.chain)
        chain_valid, chain_errors = validator.validate()

        # Build blockers list
        blockers: list[str] = []
        if not d_all_met:
            blockers.extend([f"Phase D unsatisfied: {g}" for g in d_unsatisfied])
        if not e_ready:
            blockers.extend([f"Phase E prerequisite missing: {p}" for p in e_missing])
        if not chain_valid:
            blockers.extend(chain_errors)

        # Determine if transition is ready
        ready = len(blockers) == 0 and d_all_met and e_ready

        # Calculate minimum SIL of satisfied goals
        sil_min = 2
        if self.satisfied_goals:
            satisfied_sil_levels = [
                g.sil_level
                for g in self.chain.goals
                if g.goal_id in self.satisfied_goals
            ]
            if satisfied_sil_levels:
                sil_min = min(satisfied_sil_levels)

        return TransitionReadinessReport(
            phase_from="D",
            phase_to="E",
            goals_met=list(self.satisfied_goals),
            goals_pending=d_unsatisfied + [
                g.goal_id
                for g in self.chain.goals_by_phase("E")
                if g.goal_id not in self.satisfied_goals
            ],
            blockers=blockers,
            ready=ready,
            sil_min=sil_min,
        )


def build_phase_d_e_chain() -> PhaseGoalChain:
    """Build the complete Phase D → Phase E goal chain.

    Constructs the formal goal chain that governs the phase transition,
    defining all Phase D goals (D.G1–D.G4) and Phase E startup goals,
    with explicit preconditions and postconditions.

    Returns:
        PhaseGoalChain fully instantiated with all goals and transitions
    """
    chain = PhaseGoalChain()

    # Phase D Goals

    # D.G1: Safety layer infrastructure deployed
    d_g1 = PhaseGoal(
        goal_id="D.G1",
        phase="D",
        description="Safety layer infrastructure deployed: redaction, guardrails, "
        "governance, secret scanner, egress all implemented and integrated",
        preconditions=[],
        postconditions=[
            "redaction_deployed",
            "guardrails_deployed",
            "governance_deployed",
            "secret_scanner_deployed",
            "egress_deployed",
        ],
        sil_level=2,
    )

    # D.G2: All 49 ICDs integrated into safety case
    d_g2 = PhaseGoal(
        goal_id="D.G2",
        phase="D",
        description="All 49 ICDs integrated into Phase D safety case with 100% coverage",
        preconditions=[
            "redaction_deployed",
            "guardrails_deployed",
            "governance_deployed",
            "secret_scanner_deployed",
            "egress_deployed",
        ],
        postconditions=[
            "icd_coverage_100",
            "safety_argument_complete",
            "icd_trace_matrix_complete",
        ],
        sil_level=2,
    )

    # D.G3: Phase D gate checklist passed
    d_g3 = PhaseGoal(
        goal_id="D.G3",
        phase="D",
        description="Phase D gate checklist complete: all critical-path tasks 27.4–33.x done, "
        "FMEA consolidated, safety case structured, artifacts traceable",
        preconditions=[
            "icd_coverage_100",
            "safety_argument_complete",
            "icd_trace_matrix_complete",
        ],
        postconditions=[
            "fmea_consolidated",
            "safety_case_structured",
            "artifacts_traceable",
            "gate_passed",
        ],
        sil_level=2,
    )

    # D.G4: SIL-2 verification maintained
    d_g4 = PhaseGoal(
        goal_id="D.G4",
        phase="D",
        description="SIL-2 verification maintained through all Phase D modules: "
        "redaction, guardrails, governance, secret scanner, egress all pass SIL-2 criteria",
        preconditions=[
            "fmea_consolidated",
            "safety_case_structured",
            "artifacts_traceable",
            "gate_passed",
        ],
        postconditions=[
            "sil2_verified",
            "phase_d_complete",
        ],
        sil_level=2,
    )

    # Phase E Goals (startup prerequisites)

    # E.G1: Deployment infrastructure prepared
    e_g1 = PhaseGoal(
        goal_id="E.G1",
        phase="E",
        description="Deployment infrastructure and prerequisites verified for Phase E core L2 "
        "deployment (conversation interface, intent classifier, goal decomposer, APS controller)",
        preconditions=[
            "sil2_verified",
            "phase_d_complete",
        ],
        postconditions=[
            "deployment_ready",
            "l2_infrastructure_ready",
        ],
        sil_level=2,
    )

    # E.G2: Safety hooks integrated into L2
    e_g2 = PhaseGoal(
        goal_id="E.G2",
        phase="E",
        description="Phase D safety outputs (redaction rules, guardrails, governance policies) "
        "integrated as enforcement hooks in Phase E conversation processing",
        preconditions=[
            "deployment_ready",
            "l2_infrastructure_ready",
        ],
        postconditions=[
            "safety_hooks_integrated",
            "l2_enforcement_active",
        ],
        sil_level=2,
    )

    # Add all goals to chain
    for goal in [d_g1, d_g2, d_g3, d_g4, e_g1, e_g2]:
        chain.add_goal(goal)

    # Add transitions
    chain.add_transition("D.G1", "D.G2")
    chain.add_transition("D.G2", "D.G3")
    chain.add_transition("D.G3", "D.G4")
    chain.add_transition("D.G4", "E.G1")
    chain.add_transition("E.G1", "E.G2")

    return chain
