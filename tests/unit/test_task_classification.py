"""Unit tests for Task 37.4: T0–T3 task classification.

Tests cover:
  - TaskLevel enum (T0–T3 values)
  - TaskClassification dataclass
  - TaskClassifier.classify() logic
  - TaskClassifier.required_checks()
  - TaskClassifier.is_permitted()
  - ICD-011 compliance (Celestial level requirements)
"""

from __future__ import annotations

import pytest

from holly.goals.classification import (
    ClassificationResult,
    TaskClassification,
    TaskClassifier,
    TaskLevel,
)


class TestTaskLevel:
    """Tests for TaskLevel enum."""

    def test_task_level_t0_value(self) -> None:
        """T0 should have value 0."""
        assert TaskLevel.T0.value == 0

    def test_task_level_t1_value(self) -> None:
        """T1 should have value 1."""
        assert TaskLevel.T1.value == 1

    def test_task_level_t2_value(self) -> None:
        """T2 should have value 2."""
        assert TaskLevel.T2.value == 2

    def test_task_level_t3_value(self) -> None:
        """T3 should have value 3."""
        assert TaskLevel.T3.value == 3

    def test_task_level_names(self) -> None:
        """TaskLevel enum should have all four members."""
        names = {level.name for level in TaskLevel}
        assert names == {"T0", "T1", "T2", "T3"}

    def test_task_level_description_t0(self) -> None:
        """T0 description should reference reflexive execution."""
        assert "Reflexive" in TaskLevel.T0.description
        assert "single agent" in TaskLevel.T0.description.lower()

    def test_task_level_description_t1(self) -> None:
        """T1 description should reference deliberative planning."""
        assert "Deliberative" in TaskLevel.T1.description
        assert "multi-step" in TaskLevel.T1.description.lower()

    def test_task_level_description_t2(self) -> None:
        """T2 description should reference collaborative execution."""
        assert "Collaborative" in TaskLevel.T2.description
        assert "multiple agents" in TaskLevel.T2.description.lower()

    def test_task_level_description_t3(self) -> None:
        """T3 description should reference morphogenetic topology."""
        assert "Morphogenetic" in TaskLevel.T3.description
        assert "dynamic" in TaskLevel.T3.description.lower()


class TestTaskClassification:
    """Tests for TaskClassification dataclass."""

    def test_classification_frozen(self) -> None:
        """TaskClassification should be frozen (immutable)."""
        classification = TaskClassification(
            task_id="test_task",
            level=TaskLevel.T0,
            required_celestial_levels=(0,),
            rationale="Test",
        )
        with pytest.raises(AttributeError):
            classification.task_id = "modified"  # type: ignore

    def test_classification_creation_t0(self) -> None:
        """Create a T0 classification."""
        classification = TaskClassification(
            task_id="task_1",
            level=TaskLevel.T0,
            required_celestial_levels=(0,),
            rationale="Safety-critical",
        )
        assert classification.task_id == "task_1"
        assert classification.level == TaskLevel.T0
        assert classification.required_celestial_levels == (0,)

    def test_classification_creation_t3(self) -> None:
        """Create a T3 classification with all Celestial levels."""
        classification = TaskClassification(
            task_id="task_2",
            level=TaskLevel.T3,
            required_celestial_levels=(0, 1, 2, 3, 4),
            rationale="Morphogenetic",
        )
        assert classification.level == TaskLevel.T3
        assert len(classification.required_celestial_levels) == 5

    def test_classification_str_representation(self) -> None:
        """String representation should include task ID and level."""
        classification = TaskClassification(
            task_id="task_1",
            level=TaskLevel.T1,
            required_celestial_levels=(0, 1),
            rationale="Deliberative planning",
        )
        str_repr = str(classification)
        assert "task_1" in str_repr
        assert "T1" in str_repr
        assert "0,1" in str_repr


class TestTaskClassifier:
    """Tests for TaskClassifier.classify() and related methods."""

    def test_classifier_creation(self) -> None:
        """TaskClassifier should instantiate without arguments."""
        classifier = TaskClassifier()
        assert classifier is not None

    def test_classify_missing_required_keys(self) -> None:
        """classify() should raise ValueError for missing context keys."""
        classifier = TaskClassifier()
        context = {"codimension": 1}  # Missing other required keys
        with pytest.raises(ValueError, match="Missing required context keys"):
            classifier.classify("task_1", context)

    def test_classify_safety_critical_to_t0(self) -> None:
        """Safety-critical tasks should always classify as T0."""
        classifier = TaskClassifier()
        context = {
            "codimension": 10,  # Would normally be T3
            "agency_rank": 5,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.8,
            "is_safety_critical": True,
        }
        classification = classifier.classify("safety_task", context)
        assert classification.level == TaskLevel.T0
        assert classification.required_celestial_levels == (0,)
        assert "Safety-critical" in classification.rationale

    def test_classify_reflexive_to_t0(self) -> None:
        """Low-codim, single-agent tasks should classify as T0."""
        classifier = TaskClassifier()
        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("reflex_task", context)
        assert classification.level == TaskLevel.T0
        assert classification.required_celestial_levels == (0,)

    def test_classify_deliberative_to_t1(self) -> None:
        """Multi-step, single-agent tasks should classify as T1."""
        classifier = TaskClassifier()
        context = {
            "codimension": 3,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("deliberative_task", context)
        assert classification.level == TaskLevel.T1
        assert classification.required_celestial_levels == (0, 1)

    def test_classify_collaborative_to_t2(self) -> None:
        """Multi-agent tasks with fixed contracts should classify as T2."""
        classifier = TaskClassifier()
        context = {
            "codimension": 3,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.3,
        }
        classification = classifier.classify("collaborative_task", context)
        assert classification.level == TaskLevel.T2
        assert classification.required_celestial_levels == (0, 1, 2)

    def test_classify_morphogenetic_to_t3(self) -> None:
        """Dynamic topology tasks should classify as T3."""
        classifier = TaskClassifier()
        context = {
            "codimension": 6,
            "agency_rank": 3,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.7,
        }
        classification = classifier.classify("morphogenetic_task", context)
        assert classification.level == TaskLevel.T3
        assert classification.required_celestial_levels == (0, 1, 2, 3, 4)

    def test_classify_with_optional_fields(self) -> None:
        """classify() should handle optional context fields gracefully."""
        classifier = TaskClassifier()
        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
            # is_safety_critical is optional and defaults to False
        }
        classification = classifier.classify("task_optional", context)
        assert classification.level == TaskLevel.T0


class TestRequiredChecks:
    """Tests for TaskClassifier.required_checks()."""

    def test_required_checks_t0(self) -> None:
        """T0 should require only L0."""
        classifier = TaskClassifier()
        checks = classifier.required_checks(TaskLevel.T0)
        assert checks == (0,)

    def test_required_checks_t1(self) -> None:
        """T1 should require L0 and L1."""
        classifier = TaskClassifier()
        checks = classifier.required_checks(TaskLevel.T1)
        assert checks == (0, 1)

    def test_required_checks_t2(self) -> None:
        """T2 should require L0, L1, and L2."""
        classifier = TaskClassifier()
        checks = classifier.required_checks(TaskLevel.T2)
        assert checks == (0, 1, 2)

    def test_required_checks_t3(self) -> None:
        """T3 should require all L0–L4."""
        classifier = TaskClassifier()
        checks = classifier.required_checks(TaskLevel.T3)
        assert checks == (0, 1, 2, 3, 4)

    def test_required_checks_consistency(self) -> None:
        """Each tier's required checks should be monotonically increasing."""
        classifier = TaskClassifier()
        t0_checks = classifier.required_checks(TaskLevel.T0)
        t1_checks = classifier.required_checks(TaskLevel.T1)
        t2_checks = classifier.required_checks(TaskLevel.T2)
        t3_checks = classifier.required_checks(TaskLevel.T3)

        assert len(t0_checks) < len(t1_checks)
        assert len(t1_checks) < len(t2_checks)
        assert len(t2_checks) < len(t3_checks)


class TestIsPermitted:
    """Tests for TaskClassifier.is_permitted()."""

    def test_is_permitted_t0_with_l0_pass(self) -> None:
        """T0 task should be permitted when L0 passes."""
        classifier = TaskClassifier()
        classification = TaskClassification(
            task_id="t0_task",
            level=TaskLevel.T0,
            required_celestial_levels=(0,),
            rationale="Test",
        )
        celestial_state = {"L0": True, "L1": True, "L2": True, "L3": True, "L4": True}
        assert classifier.is_permitted(classification, celestial_state) is True

    def test_is_permitted_t0_with_l0_fail(self) -> None:
        """T0 task should not be permitted when L0 fails."""
        classifier = TaskClassifier()
        classification = TaskClassification(
            task_id="t0_task",
            level=TaskLevel.T0,
            required_celestial_levels=(0,),
            rationale="Test",
        )
        celestial_state = {"L0": False, "L1": True, "L2": True, "L3": True, "L4": True}
        assert classifier.is_permitted(classification, celestial_state) is False

    def test_is_permitted_t1_with_l0_pass_l1_fail(self) -> None:
        """T1 task should not be permitted if L1 fails."""
        classifier = TaskClassifier()
        classification = TaskClassification(
            task_id="t1_task",
            level=TaskLevel.T1,
            required_celestial_levels=(0, 1),
            rationale="Test",
        )
        celestial_state = {"L0": True, "L1": False, "L2": True, "L3": True, "L4": True}
        assert classifier.is_permitted(classification, celestial_state) is False

    def test_is_permitted_t3_requires_all_levels(self) -> None:
        """T3 task should require all L0–L4 to pass."""
        classifier = TaskClassifier()
        classification = TaskClassification(
            task_id="t3_task",
            level=TaskLevel.T3,
            required_celestial_levels=(0, 1, 2, 3, 4),
            rationale="Test",
        )
        all_pass = {f"L{i}": True for i in range(5)}
        assert classifier.is_permitted(classification, all_pass) is True

        # Fail just L4
        all_fail_l4 = {f"L{i}": True for i in range(4)}
        all_fail_l4["L4"] = False
        assert classifier.is_permitted(classification, all_fail_l4) is False

    def test_is_permitted_missing_celestial_state(self) -> None:
        """is_permitted() should raise ValueError for missing Celestial levels."""
        classifier = TaskClassifier()
        classification = TaskClassification(
            task_id="task",
            level=TaskLevel.T3,
            required_celestial_levels=(0, 1, 2, 3, 4),
            rationale="Test",
        )
        incomplete_state = {"L0": True, "L1": True}  # Missing L2, L3, L4
        with pytest.raises(ValueError, match="Missing Celestial state"):
            classifier.is_permitted(classification, incomplete_state)


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_classification_result_creation(self) -> None:
        """Create a ClassificationResult."""
        classification = TaskClassification(
            task_id="task_1",
            level=TaskLevel.T1,
            required_celestial_levels=(0, 1),
            rationale="Test",
        )
        result = ClassificationResult(
            task_id="task_1",
            classification=classification,
            celestial_checks_required=2,
        )
        assert result.task_id == "task_1"
        assert result.classification.level == TaskLevel.T1
        assert result.celestial_checks_required == 2


class TestICD011Compliance:
    """Tests for ICD-011 compliance (APS Controller tier assignment)."""

    def test_icd011_t0_celestial_l0_only(self) -> None:
        """ICD-011: T0 should require only Celestial L0."""
        classifier = TaskClassifier()
        context = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("safety_task", context)
        assert classification.required_celestial_levels == (0,)

    def test_icd011_t1_celestial_l0_l1(self) -> None:
        """ICD-011: T1 should require Celestial L0 and L1."""
        classifier = TaskClassifier()
        context = {
            "codimension": 2,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        classification = classifier.classify("deliberative_task", context)
        assert classification.required_celestial_levels == (0, 1)

    def test_icd011_t2_celestial_l0_l1_l2(self) -> None:
        """ICD-011: T2 should require Celestial L0, L1, and L2."""
        classifier = TaskClassifier()
        context = {
            "codimension": 2,
            "agency_rank": 2,
            "num_agents": 2,
            "eigenspectrum_divergence": 0.2,
        }
        classification = classifier.classify("collaborative_task", context)
        assert classification.required_celestial_levels == (0, 1, 2)

    def test_icd011_t3_celestial_all_l0_l4(self) -> None:
        """ICD-011: T3 should require all Celestial L0–L4."""
        classifier = TaskClassifier()
        context = {
            "codimension": 5,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.6,
        }
        classification = classifier.classify("morphogenetic_task", context)
        assert classification.required_celestial_levels == (0, 1, 2, 3, 4)

    def test_icd011_tier_routing_dispatch_plan(self) -> None:
        """ICD-011: Tier assignment should drive dispatch plan selection."""
        classifier = TaskClassifier()

        # T0: direct execution
        context_t0 = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        class_t0 = classifier.classify("t0_task", context_t0)
        assert class_t0.level == TaskLevel.T0

        # T1: planning + multi-step
        context_t1 = {
            "codimension": 3,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        class_t1 = classifier.classify("t1_task", context_t1)
        assert class_t1.level == TaskLevel.T1

        # T2: team-based fixed contracts
        context_t2 = {
            "codimension": 2,
            "agency_rank": 2,
            "num_agents": 3,
            "eigenspectrum_divergence": 0.2,
        }
        class_t2 = classifier.classify("t2_task", context_t2)
        assert class_t2.level == TaskLevel.T2

        # T3: dynamic topology
        context_t3 = {
            "codimension": 6,
            "agency_rank": 3,
            "num_agents": 4,
            "eigenspectrum_divergence": 0.7,
        }
        class_t3 = classifier.classify("t3_task", context_t3)
        assert class_t3.level == TaskLevel.T3


class TestT0T3ClassificationBoundaries:
    """Tests for T0–T3 classification boundary conditions."""

    def test_codimension_boundary_t0_t1(self) -> None:
        """codim=1 should be T0, codim=2 should be T1."""
        classifier = TaskClassifier()

        context_codim_1 = {
            "codimension": 1,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        assert classifier.classify("task_1", context_codim_1).level == TaskLevel.T0

        context_codim_2 = {
            "codimension": 2,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        assert classifier.classify("task_2", context_codim_2).level == TaskLevel.T1

    def test_codimension_boundary_t1_t3(self) -> None:
        """codim=4 with single agent should be T1; codim=5 with multi-agent should be T3."""
        classifier = TaskClassifier()

        context_codim_4 = {
            "codimension": 4,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        assert classifier.classify("task_1", context_codim_4).level == TaskLevel.T1

        context_codim_5 = {
            "codimension": 5,
            "agency_rank": 2,
            "num_agents": 2,
            "eigenspectrum_divergence": 0.6,
        }
        assert classifier.classify("task_2", context_codim_5).level == TaskLevel.T3

    def test_agency_rank_boundary_t1_t2(self) -> None:
        """agency_rank=1 should allow T1; agency_rank=2 with multi-agent should be T2."""
        classifier = TaskClassifier()

        context_rank_1 = {
            "codimension": 2,
            "agency_rank": 1,
            "num_agents": 1,
            "eigenspectrum_divergence": 0.0,
        }
        assert classifier.classify("task_1", context_rank_1).level == TaskLevel.T1

        context_rank_2 = {
            "codimension": 2,
            "agency_rank": 2,
            "num_agents": 2,
            "eigenspectrum_divergence": 0.0,
        }
        assert classifier.classify("task_2", context_rank_2).level == TaskLevel.T2

    def test_eigenspectrum_boundary_t2_t3(self) -> None:
        """eigenspec < 0.5 with high codim should be T2; > 0.5 should be T3."""
        classifier = TaskClassifier()

        context_low_eigen = {
            "codimension": 5,
            "agency_rank": 2,
            "num_agents": 2,
            "eigenspectrum_divergence": 0.3,
        }
        assert classifier.classify("task_1", context_low_eigen).level == TaskLevel.T2

        context_high_eigen = {
            "codimension": 5,
            "agency_rank": 2,
            "num_agents": 2,
            "eigenspectrum_divergence": 0.6,
        }
        assert classifier.classify("task_2", context_high_eigen).level == TaskLevel.T3
