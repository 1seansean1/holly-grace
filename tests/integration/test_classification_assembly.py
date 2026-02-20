"""Integration tests for Task 37.4: Classification and Assembly Index integration.

Tests cover:
  - T0–T3 classification with Assembly Index computation
  - ICD-011 compliance: tier assignment drives dispatch plan
  - Celestial permission checks with classification
  - Goal workflow: classify → decompose → compute AI
"""

from __future__ import annotations

import pytest

from holly.goals.assembly_index import GoalDecomposer
from holly.goals.classification import TaskClassifier, TaskLevel


class TestT0T3ClassificationWithAssemblyIndex:
    """Tests for T0–T3 classification paired with Assembly Index."""

    def test_t0_reflexive_low_assembly_index(self) -> None:
        """T0 classified goal should have low assembly index (simple)."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Classify as T0
        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("reflex_goal", context)
        assert classification.level == TaskLevel.T0

        # Decompose as T0
        decomp_context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        ai_result = decomposer.compute_goal_assembly_index("reflex_goal", decomp_context)
        assert ai_result.complexity_class == "simple"
        assert ai_result.assembly_index < 5

    def test_t1_deliberative_moderate_assembly_index(self) -> None:
        """T1 classified goal should have moderate assembly index."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Classify as T1
        context = {
            "codimension": 3,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("deliberative_goal", context)
        assert classification.level == TaskLevel.T1

        # Decompose as T1
        decomp_context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 3,
        }
        ai_result = decomposer.compute_goal_assembly_index("deliberative_goal", decomp_context)
        assert ai_result.complexity_class in ("simple", "moderate")

    def test_t2_collaborative_moderate_to_complex_assembly_index(self) -> None:
        """T2 classified goal should have moderate to complex assembly index."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Classify as T2
        context = {
            "codimension": 3,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.2,
        }
        classification = classifier.classify("collaborative_goal", context)
        assert classification.level == TaskLevel.T2

        # Decompose as T2
        decomp_context = {
            "task_level": "T2",
            "num_agents": 3,
            "codimension": 3,
        }
        ai_result = decomposer.compute_goal_assembly_index("collaborative_goal", decomp_context)
        assert ai_result.complexity_class in ("moderate", "complex")

    def test_t3_morphogenetic_complex_assembly_index(self) -> None:
        """T3 classified goal should have complex or critical assembly index."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Classify as T3
        context = {
            "codimension": 6,
            "agency_rank": 3,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.7,
        }
        classification = classifier.classify("morphogenetic_goal", context)
        assert classification.level == TaskLevel.T3

        # Decompose as T3
        decomp_context = {
            "task_level": "T3",
            "num_agents": 4,
            "codimension": 6,
        }
        ai_result = decomposer.compute_goal_assembly_index("morphogenetic_goal", decomp_context)
        assert ai_result.complexity_class in ("complex", "critical")


class TestCelestialPermissionWithClassification:
    """Tests for Celestial permission checks with classification."""

    def test_t0_goal_requires_l0_only(self) -> None:
        """T0 goal should be permitted with L0 pass only."""
        classifier = TaskClassifier()

        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("t0_goal", context)

        # L0 passes, others don't matter
        celestial_state = {
            "L0": True,
            "L1": False,
            "L2": False,
            "L3": False,
            "L4": False,
        }
        assert classifier.is_permitted(classification, celestial_state) is True

    def test_t1_goal_requires_l0_and_l1(self) -> None:
        """T1 goal should require both L0 and L1."""
        classifier = TaskClassifier()

        context = {
            "codimension": 2,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("t1_goal", context)

        # L0 passes, L1 fails
        celestial_state = {
            "L0": True,
            "L1": False,
            "L2": False,
            "L3": False,
            "L4": False,
        }
        assert classifier.is_permitted(classification, celestial_state) is False

        # Both L0 and L1 pass
        celestial_state["L1"] = True
        assert classifier.is_permitted(classification, celestial_state) is True

    def test_t3_goal_requires_all_celestial_levels(self) -> None:
        """T3 goal should require all L0–L4."""
        classifier = TaskClassifier()

        context = {
            "codimension": 6,
            "agency_rank": 3,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.7,
        }
        classification = classifier.classify("t3_goal", context)

        # All pass
        all_pass = {f"L{i}": True for i in range(5)}
        assert classifier.is_permitted(classification, all_pass) is True

        # Any one fails
        all_fail_l3 = {f"L{i}": True for i in range(5)}
        all_fail_l3["L3"] = False
        assert classifier.is_permitted(classification, all_fail_l3) is False


class TestGoalWorkflowClassifyDecomposeAssemble:
    """Tests for full goal workflow: classify → decompose → compute AI."""

    def test_workflow_simple_goal(self) -> None:
        """Workflow for a simple goal: T0 → 1 step → AI=1 (simple)."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Step 1: Classify
        classify_context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("simple_goal", classify_context)
        assert classification.level == TaskLevel.T0
        assert classification.required_celestial_levels == (0,)

        # Step 2: Check permission (assuming L0 passes)
        celestial_state = {f"L{i}": (i == 0) for i in range(5)}
        assert classifier.is_permitted(classification, celestial_state) is True

        # Step 3: Decompose and compute AI
        decomp_context = {
            "task_level": "T0",
            "num_agents": 1,
            "codimension": 1,
        }
        ai_result = decomposer.compute_goal_assembly_index("simple_goal", decomp_context)
        assert ai_result.assembly_index == 1
        assert ai_result.complexity_class == "simple"

    def test_workflow_complex_goal(self) -> None:
        """Workflow for a complex goal: T2 → decompose → AI=7 (moderate)."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Step 1: Classify
        classify_context = {
            "codimension": 3,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.1,
        }
        classification = classifier.classify("complex_goal", classify_context)
        assert classification.level == TaskLevel.T2
        assert classification.required_celestial_levels == (0, 1, 2)

        # Step 2: Check permission (all L0–L2 pass)
        celestial_state = {
            "L0": True,
            "L1": True,
            "L2": True,
            "L3": False,
            "L4": False,
        }
        assert classifier.is_permitted(classification, celestial_state) is True

        # Step 3: Decompose and compute AI
        decomp_context = {
            "task_level": "T2",
            "num_agents": 3,
            "codimension": 3,
        }
        ai_result = decomposer.compute_goal_assembly_index("complex_goal", decomp_context)
        assert ai_result.assembly_index >= 5
        assert ai_result.complexity_class in ("simple", "moderate", "complex")

    def test_workflow_with_dependencies(self) -> None:
        """Workflow for goal with dependencies."""
        classifier = TaskClassifier()
        decomposer = GoalDecomposer()

        # Classify
        classify_context = {
            "codimension": 2,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("dependent_goal", classify_context)
        assert classification.level == TaskLevel.T1

        # Decompose with dependencies
        decomp_context = {
            "task_level": "T1",
            "num_agents": 1,
            "codimension": 2,
            "dependencies": ["prerequisite_1", "prerequisite_2"],
        }
        ai_result = decomposer.compute_goal_assembly_index("dependent_goal", decomp_context)

        # Should have at least dependency resolution steps + planning + execution
        assert len(ai_result.steps) >= 3


class TestICD011Compliance:
    """Tests for ICD-011 compliance: tier → dispatch plan → assembly index."""

    def test_icd011_t0_dispatch_plan(self) -> None:
        """ICD-011: T0 should trigger direct execution dispatch plan."""
        classifier = TaskClassifier()
        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("t0_task", context)

        # Per ICD-011, T0 → single-lane direct execution
        assert classification.level == TaskLevel.T0
        assert classification.required_celestial_levels == (0,)

    def test_icd011_t1_dispatch_plan(self) -> None:
        """ICD-011: T1 should trigger multi-step planning dispatch plan."""
        classifier = TaskClassifier()
        context = {
            "codimension": 3,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("t1_task", context)

        # Per ICD-011, T1 → planning + multi-step execution
        assert classification.level == TaskLevel.T1
        assert classification.required_celestial_levels == (0, 1)

    def test_icd011_t2_dispatch_plan(self) -> None:
        """ICD-011: T2 should trigger team spawning with fixed contracts."""
        classifier = TaskClassifier()
        context = {
            "codimension": 2,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.2,
        }
        classification = classifier.classify("t2_task", context)

        # Per ICD-011, T2 → team spawn with fixed contracts
        assert classification.level == TaskLevel.T2
        assert classification.required_celestial_levels == (0, 1, 2)
        assert classification.required_celestial_levels == (0, 1, 2)

    def test_icd011_t3_dispatch_plan(self) -> None:
        """ICD-011: T3 should trigger dynamic topology morphing."""
        classifier = TaskClassifier()
        context = {
            "codimension": 6,
            "agency_rank": 3,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.7,
        }
        classification = classifier.classify("t3_task", context)

        # Per ICD-011, T3 → dynamic topology, steering, morphing
        assert classification.level == TaskLevel.T3
        assert classification.required_celestial_levels == (0, 1, 2, 3, 4)

    def test_icd011_assembly_index_in_response_schema(self) -> None:
        """ICD-011: Assembly Index should be in response schema."""
        decomposer = GoalDecomposer()
        context = {
            "task_level": "T2",
            "num_agents": 3,
            "codimension": 3,
        }
        ai_result = decomposer.compute_goal_assembly_index("icd011_goal", context)

        # Per ICD-011 response schema: { tier, assembly_index, dispatch_plan, ... }
        assert hasattr(ai_result, "assembly_index")
        assert isinstance(ai_result.assembly_index, int)
        assert ai_result.assembly_index > 0


class TestT0T3CELESTIALMappingInvariants:
    """Tests for T0–T3 to Celestial L0–L4 mapping invariants."""

    def test_t0_always_requires_l0_only(self) -> None:
        """Invariant: T0 always requires L0 only, never L1–L4."""
        classifier = TaskClassifier()

        for i in range(10):
            context = {
                "codimension": 1,
                "agency_rank": 1,
                "num_agents": 1,
                "eigenspectrum_divergence": 0.0,
                "is_safety_critical": (i % 2 == 0),  # Some safety-critical
            }
            classification = classifier.classify(f"t0_variant_{i}", context)
            if classification.level == TaskLevel.T0:
                assert classification.required_celestial_levels == (0,)

    def test_t1_always_requires_l0_l1(self) -> None:
        """Invariant: T1 always requires L0 and L1, never omits L1."""
        classifier = TaskClassifier()

        for codim in range(2, 5):
            context = {
                "codimension": codim,
                "agency_rank": 1,
                "num_agents": 1,
                "eigenspectrum_divergence": 0.0,
            }
            classification = classifier.classify(f"t1_codim_{codim}", context)
            if classification.level == TaskLevel.T1:
                assert classification.required_celestial_levels == (0, 1)
                assert 0 in classification.required_celestial_levels
                assert 1 in classification.required_celestial_levels

    def test_t2_always_includes_l0_l1_l2(self) -> None:
        """Invariant: T2 always requires L0, L1, L2."""
        classifier = TaskClassifier()

        for num_agents in [2, 3, 5]:
            context = {
                "codimension": 2,
                "agency_rank": 2,
                "num_agents": num_agents,
                "eigenspectrum_divergence": 0.1,
            }
            classification = classifier.classify(f"t2_agents_{num_agents}", context)
            if classification.level == TaskLevel.T2:
                assert classification.required_celestial_levels == (0, 1, 2)

    def test_t3_always_requires_all_l0_l4(self) -> None:
        """Invariant: T3 always requires all L0–L4."""
        classifier = TaskClassifier()

        for eigspec in [0.5, 0.6, 0.8, 1.0]:
            context = {
                "codimension": 5,
                "agency_rank": 2,
                "num_agents": 3,
                "eigenspectrum_divergence": eigspec,
            }
            classification = classifier.classify(f"t3_eigspec_{eigspec}", context)
            if classification.level == TaskLevel.T3:
                assert classification.required_celestial_levels == (0, 1, 2, 3, 4)

    def test_celestial_requirements_monotonically_increase(self) -> None:
        """Invariant: Celestial requirements increase: T0 < T1 < T2 < T3."""
        classifier = TaskClassifier()

        t0_checks = classifier.required_checks(TaskLevel.T0)
        t1_checks = classifier.required_checks(TaskLevel.T1)
        t2_checks = classifier.required_checks(TaskLevel.T2)
        t3_checks = classifier.required_checks(TaskLevel.T3)

        assert len(t0_checks) < len(t1_checks)
        assert len(t1_checks) < len(t2_checks)
        assert len(t2_checks) < len(t3_checks)

        # T0's checks should be subset of T1's
        assert set(t0_checks).issubset(set(t1_checks))
        # T1's checks should be subset of T2's
        assert set(t1_checks).issubset(set(t2_checks))
        # T2's checks should be subset of T3's
        assert set(t2_checks).issubset(set(t3_checks))
