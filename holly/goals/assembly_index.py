"""Assembly Index computation per Assembly Theory.

Implements assembly index (AI) as a measure of goal decomposition complexity.
Assembly Index quantifies the minimum number of distinct build steps required
to construct a goal pattern, with reuse through caching.

Per Assembly Theory (Ch 12, Monograph):
  AI(θ) = structural construction cost with subassembly reuse
  Measures: team topology complexity, agent binding requirements

References:
  - Monograph Glossary §12 (Assembly Index definition)
  - Goal Hierarchy Formal Spec §4.3 (Goal decomposition strategy)
  - ICD-011 (APS Controller response includes assembly_index)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class AssemblyStep:
    """A single build step in Assembly Theory decomposition.
    
    Attributes:
        step_id: Unique identifier for this build step.
        description: Human-readable description of the step.
        inputs: Tuple of IDs of prerequisite steps or atomic elements.
        output: ID of the element produced by this step.
    """

    step_id: str
    description: str
    inputs: tuple[str, ...] = field(default_factory=tuple)
    output: str = ""

    def __post_init__(self) -> None:
        """Validate step properties."""
        if not self.step_id:
            raise ValueError("step_id cannot be empty")
        if not self.description:
            raise ValueError("description cannot be empty")
        if not self.output:
            raise ValueError("output cannot be empty")


@dataclass(slots=True)
class AssemblyIndexResult:
    """Result of computing Assembly Index for a goal or pattern.
    
    Attributes:
        pattern_id: Identifier of the goal/pattern being decomposed.
        assembly_index: Computed AI (minimum distinct build steps).
        steps: Ordered list of AssemblyStep objects.
        complexity_class: Classification: "simple", "moderate", "complex", "critical".
    """

    pattern_id: str
    assembly_index: int
    steps: list[AssemblyStep] = field(default_factory=list)
    complexity_class: str = "simple"

    def __str__(self) -> str:
        """Format result for logging."""
        return (
            f"Pattern {self.pattern_id}: AI={self.assembly_index} "
            f"({self.complexity_class}) with {len(self.steps)} steps"
        )


def compute_assembly_index(steps: list[AssemblyStep]) -> int:
    """Compute Assembly Index: minimum distinct build steps.
    
    Assembly Index is the count of unique steps in the minimum copy-number
    pathway (i.e., reusing cached subassemblies).
    
    Args:
        steps: List of AssemblyStep objects forming the decomposition.
    
    Returns:
        Assembly Index (int): count of distinct steps.
    
    Raises:
        ValueError: If steps list is empty or contains invalid steps.
    """
    if not steps:
        raise ValueError("steps list cannot be empty")

    # Validate all steps have non-empty outputs
    for step in steps:
        if not step.output:
            raise ValueError(f"Step {step.step_id} has empty output")

    # Assembly Index = count of distinct steps (each step is counted once,
    # even if used multiple times via caching)
    unique_steps = {step.step_id for step in steps}
    return len(unique_steps)


def classify_complexity(assembly_index: int) -> str:
    """Map Assembly Index to complexity class per Goal Hierarchy thresholds.
    
    Thresholds:
        ai < 5 → "simple"
        5 ≤ ai < 10 → "moderate"
        10 ≤ ai < 20 → "complex"
        ai ≥ 20 → "critical"
    
    Args:
        assembly_index: Computed assembly index value.
    
    Returns:
        Complexity class string: "simple", "moderate", "complex", or "critical".
    
    Raises:
        ValueError: If assembly_index is negative.
    """
    if assembly_index < 0:
        raise ValueError(f"assembly_index cannot be negative: {assembly_index}")

    if assembly_index < 5:
        return "simple"
    elif assembly_index < 10:
        return "moderate"
    elif assembly_index < 20:
        return "complex"
    else:
        return "critical"


class GoalDecomposer:
    """Decomposes goals into Assembly Theory steps per Goal Hierarchy.
    
    The GoalDecomposer takes a goal specification and generates a list of
    assembly steps, then computes the assembly index.
    """

    def __init__(self) -> None:
        """Initialize the GoalDecomposer."""
        pass

    def decompose(self, goal_id: str, context: dict[str, Any]) -> list[AssemblyStep]:
        """Decompose a goal into its constituent assembly steps.
        
        The decomposition strategy is determined by the goal's task level (T0–T3):
        - T0 (reflexive): 1 step
        - T1 (deliberative): 3–5 steps
        - T2 (collaborative): 5–10 steps
        - T3 (morphogenetic): 10+ steps
        
        Args:
            goal_id: Identifier of the goal to decompose.
            context: Dictionary containing goal properties:
                - task_level: str ("T0", "T1", "T2", "T3")
                - num_agents: int (number of agents involved)
                - codimension: int (structural dimension)
                - dependencies: list[str] (IDs of prerequisite goals)
        
        Returns:
            List of AssemblyStep objects in dependency order.
        
        Raises:
            ValueError: If context is missing required keys.
        """
        required_keys = {"task_level", "num_agents", "codimension"}
        if not required_keys.issubset(context.keys()):
            missing = required_keys - set(context.keys())
            raise ValueError(f"Missing required context keys: {missing}")

        task_level = context["task_level"]
        num_agents = context.get("num_agents", 1)
        codim = context.get("codimension", 1)
        dependencies = context.get("dependencies", [])

        steps: list[AssemblyStep] = []

        # Add prerequisite steps for dependencies
        for i, dep_id in enumerate(dependencies):
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_dep_{i}",
                    description=f"Resolve dependency: {dep_id}",
                    inputs=(),
                    output=f"{goal_id}_resolved_dep_{i}",
                )
            )

        # Generate steps based on task level
        if task_level == "T0":
            # T0 (reflexive): single step, direct execution
            input_ids = tuple(s.output for s in steps) if steps else ()
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_exec",
                    description=f"Execute reflexive goal {goal_id}",
                    inputs=input_ids,
                    output=f"{goal_id}_result",
                )
            )

        elif task_level == "T1":
            # T1 (deliberative): 3–5 steps (planning, validation, execution chain)
            prev_output = steps[-1].output if steps else None
            base_inputs = (prev_output,) if prev_output else ()

            # Planning step
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_plan",
                    description=f"Plan multi-step execution for {goal_id}",
                    inputs=base_inputs,
                    output=f"{goal_id}_plan",
                )
            )

            # Validation step
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_validate",
                    description=f"Validate plan for {goal_id}",
                    inputs=(f"{goal_id}_plan",),
                    output=f"{goal_id}_validated_plan",
                )
            )

            # Execute steps (one per codimension)
            for i in range(min(codim, 3)):
                steps.append(
                    AssemblyStep(
                        step_id=f"{goal_id}_exec_{i}",
                        description=f"Execute phase {i} of {goal_id}",
                        inputs=(f"{goal_id}_validated_plan", f"{goal_id}_exec_{i-1}" if i > 0 else ""),
                        output=f"{goal_id}_phase_{i}",
                    )
                )

        elif task_level == "T2":
            # T2 (collaborative): 5–10 steps (team setup, binding, execution)
            prev_output = steps[-1].output if steps else None
            base_inputs = (prev_output,) if prev_output else ()

            # Agent pool initialization
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_agent_pool",
                    description=f"Initialize agent pool for {goal_id}",
                    inputs=base_inputs,
                    output=f"{goal_id}_pool",
                )
            )

            # Contract generation
            for i in range(min(num_agents, 4)):
                steps.append(
                    AssemblyStep(
                        step_id=f"{goal_id}_contract_{i}",
                        description=f"Generate contract for agent {i}",
                        inputs=(f"{goal_id}_pool",),
                        output=f"{goal_id}_contract_{i}",
                    )
                )

            # Topology binding
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_bind_topology",
                    description=f"Bind topology for {goal_id}",
                    inputs=tuple(f"{goal_id}_contract_{i}" for i in range(min(num_agents, 4))),
                    output=f"{goal_id}_topology",
                )
            )

            # Execution
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_execute",
                    description=f"Execute collaboratively: {goal_id}",
                    inputs=(f"{goal_id}_topology",),
                    output=f"{goal_id}_result",
                )
            )

        elif task_level == "T3":
            # T3 (morphogenetic): 10+ steps (dynamic topology, steering, morphing)
            prev_output = steps[-1].output if steps else None
            base_inputs = (prev_output,) if prev_output else ()

            # Template loading
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_template",
                    description=f"Load morphogenetic template for {goal_id}",
                    inputs=base_inputs,
                    output=f"{goal_id}_template",
                )
            )

            # Field initialization
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_field",
                    description=f"Initialize morphogenetic field for {goal_id}",
                    inputs=(f"{goal_id}_template",),
                    output=f"{goal_id}_field",
                )
            )

            # Agent differentiation steps
            for i in range(min(num_agents, 6)):
                steps.append(
                    AssemblyStep(
                        step_id=f"{goal_id}_differentiate_{i}",
                        description=f"Differentiate agent {i} from template",
                        inputs=(f"{goal_id}_field", f"{goal_id}_differentiate_{i-1}" if i > 0 else ""),
                        output=f"{goal_id}_agent_{i}",
                    )
                )

            # Eigenspectrum computation
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_eigenspectrum",
                    description=f"Compute eigenspectrum for {goal_id} team",
                    inputs=tuple(f"{goal_id}_agent_{i}" for i in range(min(num_agents, 6))),
                    output=f"{goal_id}_eigenspectrum",
                )
            )

            # Steering steps
            for i in range(2):
                steps.append(
                    AssemblyStep(
                        step_id=f"{goal_id}_steer_{i}",
                        description=f"Steer team topology iteration {i}",
                        inputs=(
                            f"{goal_id}_eigenspectrum",
                            f"{goal_id}_steer_{i-1}" if i > 0 else "",
                        ),
                        output=f"{goal_id}_steered_topology_{i}",
                    )
                )

            # Execution
            steps.append(
                AssemblyStep(
                    step_id=f"{goal_id}_execute",
                    description=f"Execute morphogenetically: {goal_id}",
                    inputs=(f"{goal_id}_steered_topology_1",),
                    output=f"{goal_id}_result",
                )
            )

        else:
            raise ValueError(f"Unknown task_level: {task_level}")

        return steps

    def compute_goal_assembly_index(
        self, goal_id: str, context: dict[str, Any]
    ) -> AssemblyIndexResult:
        """Compute Assembly Index for a goal.
        
        Decomposes the goal into steps, computes the assembly index,
        and classifies complexity.
        
        Args:
            goal_id: Identifier of the goal.
            context: Goal context (see decompose() documentation).
        
        Returns:
            AssemblyIndexResult with AI, steps, and complexity class.
        """
        steps = self.decompose(goal_id, context)
        ai = compute_assembly_index(steps)
        complexity = classify_complexity(ai)

        return AssemblyIndexResult(
            pattern_id=goal_id,
            assembly_index=ai,
            steps=steps,
            complexity_class=complexity,
        )
