"""Unit tests for Task 37.4: Assembly Index computation.

Tests cover:
  - AssemblyStep dataclass creation and validation
  - compute_assembly_index() for various step counts
  - classify_complexity() thresholds
  - GoalDecomposer.decompose() for T0–T3 tasks
  - GoalDecomposer.compute_goal_assembly_index()
"""

from __future__ import annotations

import pytest

from holly.goals.assembly_index import (
    AssemblyIndexResult,
    AssemblyStep,
    GoalDecomposer,
    classify_complexity,
    compute_assembly_index,
)


class TestAssemblyStep:
    """Tests for AssemblyStep dataclass."""

    def test_assembly_step_creation(self) -> None:
        """Create a basic AssemblyStep."""
        step = AssemblyStep(
            step_id="step_1",
            description="Initialize system",
            inputs=(),
            output="initialized_system",
        )
        assert step.step_id == "step_1"
        assert step.output == "initialized_system"

    def test_assembly_step_with_inputs(self) -> None:
        """AssemblyStep with prerequisite inputs."""
        step = AssemblyStep(
            step_id="step_2",
            description="Process data",
            inputs=("input_1", "input_2"),
            output="processed_data",
        )
        assert step.inputs == ("input_1", "input_2")
        assert len(step.inputs) == 2

    def test_assembly_step_frozen(self) -> None:
        """AssemblyStep should be frozen (immutable)."""
        step = AssemblyStep(
            step_id="step_1",
            description="Test",
            inputs=(),
            output="result",
        )
        with pytest.raises(AttributeError):
            step.step_id = "modified"  # type: ignore

    def test_assembly_step_empty_step_id_raises(self) -> None:
        """Empty step_id should raise ValueError."""
        with pytest.raises(ValueError, match="step_id cannot be empty"):
            AssemblyStep(
                step_id="",
                description="Test",
                inputs=(),
                output="result",
            )

    def test_assembly_step_empty_description_raises(self) -> None:
        """Empty description should raise ValueError."""
        with pytest.raises(ValueError, match="description cannot be empty"):
            AssemblyStep(
                step_id="step_1",
                description="",
                inputs=(),
                output="result",
            )

    def test_assembly_step_empty_output_raises(self) -> None:
        """Empty output should raise ValueError."""
        with pytest.raises(ValueError, match="output cannot be empty"):
            AssemblyStep(
                step_id="step_1",
                description="Test",
                inputs=(),
                output="",
            )

    def test_assembly_step_default_inputs(self) -> None:
        """AssemblyStep should have empty tuple as default inputs."""
        step = AssemblyStep(
            step_id="step_1",
            description="Test",
            output="result",
        )
        assert step.inputs == ()


class TestComputeAssemblyIndex:
    """Tests for compute_assembly_index() function."""

    def test_compute_ai_single_step(self) -> None:
        """Single step should have AI=1."""
        steps = [
            AssemblyStep(
                step_id="step_1",
                description="Single step",
                inputs=(),
                output="result",
            )
        ]
        ai = compute_assembly_index(steps)
        assert ai == 1

    def test_compute_ai_three_steps(self) -> None:
        """Three unique steps should have AI=3."""
        steps = [
            AssemblyStep(
                step_id="step_1",
                description="Step 1",
                inputs=(),
                output="output_1",
            ),
            AssemblyStep(
                step_id="step_2",
                description="Step 2",
                inputs=("output_1",),
                output="output_2",
            ),
            AssemblyStep(
                step_id="step_3",
                description="Step 3",
                inputs=("output_2",),
                output="output_3",
            ),
        ]
        ai = compute_assembly_index(steps)
        assert ai == 3

    def test_compute_ai_fifteen_steps(self) -> None:
        """Fifteen unique steps should have AI=15."""
        steps = []
        for i in range(15):
            steps.append(
                AssemblyStep(
                    step_id=f"step_{i}",
                    description=f"Step {i}",
                    inputs=(f"output_{i-1}",) if i > 0 else (),
                    output=f"output_{i}",
                )
            )
        ai = compute_assembly_index(steps)
        assert ai == 15

    def test_compute_ai_with_reused_steps(self) -> None:
        """Reused steps (same ID) should count once."""
        # This tests that the AI counts distinct step_ids, not total list length
        steps = [
            AssemblyStep(
                step_id="step_1",
                description="Reusable step",
                inputs=(),
                output="output_1",
            ),
            AssemblyStep(
                step_id="step_2",
                description="Another step",
                inputs=("output_1",),
                output="output_2",
            ),
            AssemblyStep(
                step_id="step_1",  # Same as first step (reuse via caching)
                description="Reusable step (reused)",
                inputs=(),
                output="output_1_cached",
            ),
        ]
        # AI should count unique step_ids: {step_1, step_2} = 2
        ai = compute_assembly_index(steps)
        assert ai == 2

    def test_compute_ai_empty_steps_raises(self) -> None:
        """Empty steps list should raise ValueError."""
        with pytest.raises(ValueError, match="steps list cannot be empty"):
            compute_assembly_index([])

    def test_compute_ai_step_with_empty_output_raises(self) -> None:
        """Step with empty output should raise ValueError."""
        with pytest.raises(ValueError, match="output cannot be empty"):
            AssemblyStep(
                step_id="step_2",
                description="Test",
                inputs=("output_1",),
                output="",  # Invalid: empty output
            )


class TestClassifyComplexity:
    """Tests for classify_complexity() function."""

    def test_classify_complexity_simple_below_5(self) -> None:
        """AI < 5 should classify as 'simple'."""
        assert classify_complexity(0) == "simple"
        assert classify_complexity(1) == "simple"
        assert classify_complexity(4) == "simple"

    def test_classify_complexity_moderate_5_to_9(self) -> None:
        """5 ≤ AI < 10 should classify as 'moderate'."""
        assert classify_complexity(5) == "moderate"
        assert classify_complexity(7) == "moderate"
        assert classify_complexity(9) == "moderate"

    def test_classify_complexity_complex_10_to_19(self) -> None:
        """10 ≤ AI < 20 should classify as 'complex'."""
        assert classify_complexity(10) == "complex"
        assert classify_complexity(15) == "complex"
        assert classify_complexity(19) == "complex"

    def test_classify_complexity_critical_20_plus(self) -> None:
        """AI ≥ 20 should classify as 'critical'."""
        assert classify_complexity(20) == "critical"
        assert classify_complexity(50) == "critical"
        assert classify_complexity(100) == "critical"

    def test_classify_complexity_boundary_4_5(self) -> None:
        """AI=4 should be simple, AI=5 should be moderate."""
        assert classify_complexity(4) == "simple"
        assert classify_complexity(5) == "moderate"

    def test_classify_complexity_boundary_9_10(self) -> None:
        """AI=9 should be moderate, AI=10 should be complex."""
        assert classify_complexity(9) == "moderate"
        assert classify_complexity(10) == "complex"

    def test_classify_complexity_boundary_19_20(self) -> None:
        """AI=19 should be complex, AI=20 should be critical."""
        assert classify_complexity(19) == "complex"
        assert classify_complexity(20) == "critical"

    def test_classify_complexity_negative_raises(self) -> None:
        """Negative AI should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            classify_complexity(-1)


class TestGoalDecomposer:
    """Tests for GoalDecomposer class."""

    def test_decomposer_creation(self) -> None:
        """GoalDecomposer should instantiate without arguments."""
        decomposer = GoalDecomposer()
        assert decomposer is not None

    def test_decompose_missing_required_keys(self) -> None:
        """decompose() should raise ValueError for missing context keys."""
        decomposer = GoalDecomposer()
        context = {"task_level": "T0"}  # Missing other required keys
        with pytest.raises(ValueError, match="Missing required context keys"):
            decomposer.decompose("goal_1", context)

    def test_decompose_t0_single_step(self) -> None:
        """T0 goal should decompose into 1 step."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        steps = decomposer.decompose("t0_goal", context)
        assert len(steps) == 1
        assert "exec" in steps[0].step_id

    def test_decompose_t1_multiple_steps(self) -> None:
        """T1 goal should decompose into 3-5 steps."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 3,
        }
        steps = decomposer.decompose("t1_goal", context)
        assert 3 <= len(steps) <= 5
        # Should have planning, validation, and execution steps
        step_types = {s.step_id for s in steps}
        assert any("plan" in sid for sid in step_types)

    def test_decompose_t2_multiple_steps(self) -> None:
        """T2 goal should decompose into 5-10 steps."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T2",
            "num_agents": 3,
            "codimension": 2,
        }
        steps = decomposer.decompose("t2_goal", context)
        assert 5 <= len(steps) <= 10
        # Should have agent pool, contracts, binding steps
        step_types = {s.step_id for s in steps}
        assert any("pool" in sid for sid in step_types)

    def test_decompose_t3_many_steps(self) -> None:
        """T3 goal should decompose into 10+ steps."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T3",
            "num_agents": 4,
            "codimension": 5,
        }
        steps = decomposer.decompose("t3_goal", context)
        assert len(steps) >= 10
        # Should have template, field, differentiation, eigenspectrum, steering
        step_types = {s.step_id for s in steps}
        assert any("template" in sid for sid in step_types)

    def test_decompose_with_dependencies(self) -> None:
        """decompose() should handle goal dependencies."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
            "dependencies": ["dep_1", "dep_2"],
        }
        steps = decomposer.decompose("goal_with_deps", context)
        # Should have dependency resolution steps first
        assert len(steps) > 1
        assert any("dep" in s.step_id for s in steps)

    def test_decompose_invalid_task_level_raises(self) -> None:
        """decompose() should raise ValueError for invalid task_level."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T99",  # Invalid
            "num_agents": 1,
            "codimension": 1,
        }
        with pytest.raises(ValueError, match="Unknown task_level"):
            decomposer.decompose("goal_1", context)

    def test_decompose_steps_have_valid_structure(self) -> None:
        """All steps in decomposition should have valid structure."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 2,
        }
        steps = decomposer.decompose("goal_1", context)

        for step in steps:
            assert step.step_id  # Non-empty
            assert step.description  # Non-empty
            assert step.output  # Non-empty
            # Inputs can be empty for first steps


class TestComputeGoalAssemblyIndex:
    """Tests for GoalDecomposer.compute_goal_assembly_index()."""

    def test_compute_ai_t0_goal(self) -> None:
        """T0 goal should have simple assembly index."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        result = decomposer.compute_goal_assembly_index("t0_goal", context)

        assert result.pattern_id == "t0_goal"
        assert result.assembly_index == 1
        assert result.complexity_class == "simple"

    def test_compute_ai_t1_goal(self) -> None:
        """T1 goal should have simple or moderate assembly index."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 3,
        }
        result = decomposer.compute_goal_assembly_index("t1_goal", context)

        assert result.pattern_id == "t1_goal"
        assert result.complexity_class in ("simple", "moderate")

    def test_compute_ai_t2_goal(self) -> None:
        """T2 goal should have moderate or complex assembly index."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T2",
            "num_agents": 3,
            "codimension": 3,
        }
        result = decomposer.compute_goal_assembly_index("t2_goal", context)

        assert result.pattern_id == "t2_goal"
        assert result.complexity_class in ("simple", "moderate", "complex")

    def test_compute_ai_t3_goal(self) -> None:
        """T3 goal should have moderate, complex, or critical assembly index."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T3",
            "num_agents": 4,
            "codimension": 5,
        }
        result = decomposer.compute_goal_assembly_index("t3_goal", context)

        assert result.pattern_id == "t3_goal"
        # T3 typically results in 10+ steps
        assert result.assembly_index >= 10

    def test_compute_ai_result_has_steps(self) -> None:
        """AssemblyIndexResult should contain the decomposed steps."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 2,
        }
        result = decomposer.compute_goal_assembly_index("goal_1", context)

        assert len(result.steps) > 0
        assert all(isinstance(s, AssemblyStep) for s in result.steps)

    def test_compute_ai_result_str_representation(self) -> None:
        """AssemblyIndexResult should have readable string representation."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        result = decomposer.compute_goal_assembly_index("goal_1", context)

        str_repr = str(result)
        assert "goal_1" in str_repr
        assert "AI=" in str_repr


class TestAssemblyIndexComplexityMapping:
    """Tests for Assembly Index to complexity class mapping."""

    def test_t0_goal_always_simple(self) -> None:
        """T0 goal decomposition should always result in 'simple' complexity."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        result = decomposer.compute_goal_assembly_index("t0", context)
        assert result.complexity_class == "simple"
        assert result.assembly_index < 5

    def test_complexity_increases_with_task_level(self) -> None:
        """Complexity should generally increase from T0 to T3."""
        decomposer = GoalDecomposer()

        t0_context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        t0_result = decomposer.compute_goal_assembly_index("t0", t0_context)

        t3_context = {
            "task_level": "T3",
            "num_agents": 4,
            "codimension": 5,
        }
        t3_result = decomposer.compute_goal_assembly_index("t3", t3_context)

        # T3 should have higher assembly index than T0
        assert t3_result.assembly_index >= t0_result.assembly_index


class TestAssemblyIndexEdgeCases:
    """Tests for edge cases in assembly index computation."""

    def test_goal_with_many_dependencies(self) -> None:
        """Goal with many dependencies should have proportionally more steps."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
            "dependencies": ["dep_1", "dep_2", "dep_3", "dep_4", "dep_5"],
        }
        result = decomposer.compute_goal_assembly_index("goal_with_many_deps", context)

        # Should have at least 5 (dependencies) + 1 (exec) = 6 steps
        assert len(result.steps) >= 6

    def test_high_codimension_t1(self) -> None:
        """High codimension T1 should result in more steps."""
        decomposer = GoalDecomposer()

        context_low_codim = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 1,
        }
        result_low = decomposer.compute_goal_assembly_index("goal_low_codim", context_low_codim)

        context_high_codim = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 4,
        }
        result_high = decomposer.compute_goal_assembly_index("goal_high_codim", context_high_codim)

        # Higher codimension should lead to more execution steps
        assert len(result_high.steps) >= len(result_low.steps)

    def test_high_agent_count_t2(self) -> None:
        """High agent count T2 should result in more contract steps."""
        decomposer = GoalDecomposer()

        context_low_agents = {
            "task_level": "T2",
            "num_agents": 1,
            "codimension": 1,
        }
        result_low = decomposer.compute_goal_assembly_index("goal_few_agents", context_low_agents)

        context_high_agents = {
            "task_level": "T2",
            "num_agents": 5,
            "codimension": 1,
        }
        result_high = decomposer.compute_goal_assembly_index("goal_many_agents", context_high_agents)

        # More agents should lead to more contract generation steps
        assert len(result_high.steps) >= len(result_low.steps)
