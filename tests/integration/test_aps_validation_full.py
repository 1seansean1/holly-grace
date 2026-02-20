"""Integration tests for APS Assembly Index Validator.

Tests full validation workflows including:
  - End-to-end validation with mock decomposers
  - Multi-level task validation (T0–T3)
  - Default context handling
  - Validation report generation and analysis
"""

from __future__ import annotations

import pytest

from holly.goals.aps_validator import (
    APSValidator,
    APSValidationReport,
    APSValidationViolation,
    validate_aps_assembly_indices,
)
from holly.goals.assembly_index import AssemblyIndexResult, AssemblyStep


class MockDecomposer:
    """Mock decomposer for testing."""

    def __init__(
        self,
        ai_by_level: dict[str, int] | None = None,
        consistent: bool = True,
        raise_exception: bool = False,
    ):
        """Initialize mock decomposer.
        
        Args:
            ai_by_level: Dictionary mapping task level to AI value.
            consistent: Whether to always return same result.
            raise_exception: Whether to raise exception on decompose.
        """
        self.ai_by_level = ai_by_level or {"T0": 2, "T1": 5, "T2": 10, "T3": 15}
        self.consistent = consistent
        self.raise_exception = raise_exception
        self.call_count = 0

    def decompose(self, context):
        """Decompose context and return AssemblyIndexResult."""
        if self.raise_exception:
            raise RuntimeError("Decomposition error")

        self.call_count += 1

        # Determine AI based on context or make it inconsistent if needed
        level = context.get("task_level", "T0")
        if level in self.ai_by_level:
            ai_value = self.ai_by_level[level]
        else:
            ai_value = 5

        # Make inconsistent if flag set
        if not self.consistent and self.call_count % 2 == 0:
            ai_value += 1

        steps = [
            AssemblyStep(f"s{i}", f"Step {i}", (), f"out{i}")
            for i in range(1, ai_value + 1)
        ]

        return AssemblyIndexResult(
            pattern_id=context.get("goal_id", "test"),
            assembly_index=ai_value,
            steps=steps,
            complexity_class="moderate",
        )


class TestAPSValidationFullFlow:
    """End-to-end validation tests."""

    def test_validate_function_no_args(self) -> None:
        """Test validate_aps_assembly_indices with no arguments."""
        report = validate_aps_assembly_indices()
        assert isinstance(report, APSValidationReport)
        assert report.total_tasks_checked > 0

    def test_validate_function_with_decomposer(self) -> None:
        """Test validate_aps_assembly_indices with decomposer."""
        decomposer = MockDecomposer()
        contexts = [{"goal_id": "test1", "task_level": "T0"}]
        report = validate_aps_assembly_indices(decomposer, contexts)
        assert isinstance(report, APSValidationReport)

    def test_validate_with_mock_decomposer(self) -> None:
        """Test full validation with mock decomposer."""
        decomposer = MockDecomposer()
        contexts = [{"goal_id": "test", "task_level": "T0"}]

        validator = APSValidator()
        report = validator.validate_all(decomposer, contexts)

        assert report.total_tasks_checked > 0
        assert isinstance(report.violations, list)


class TestMultiLevelValidation:
    """Test validation across T0–T3 task levels."""

    def test_all_levels_valid(self) -> None:
        """Test validation with all T0–T3 levels valid."""
        validator = APSValidator()

        # Validate each level separately
        for level, (lower, upper) in validator.AI_BOUNDS.items():
            mid_value = (lower + upper) // 2
            results = {level: mid_value}
            violations = validator.validate_bounds(results)
            assert len(violations) == 0

    def test_hierarchical_t0_to_t3(self) -> None:
        """Test monotonicity from T0 through T3."""
        validator = APSValidator()
        results = {
            "T0": 2,   # [1, 4]
            "T1": 5,   # [3, 9]
            "T2": 10,  # [5, 19]
            "T3": 15,  # [10, ∞)
        }
        mono_violations = validator.validate_monotonicity(results)
        bounds_violations = validator.validate_bounds(results)

        assert len(mono_violations) == 0
        assert len(bounds_violations) == 0

    def test_task_level_transitions(self) -> None:
        """Test valid transitions between task levels."""
        validator = APSValidator()

        # Test T0 → T1 transition
        t0_ai = 3
        t1_ai_min = 3  # Must be ≥ T0.AI and within [3, 9]
        t1_ai = max(t0_ai, t1_ai_min)

        results = {"T0": t0_ai, "T1": t1_ai}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0

        # Test T2 → T3 transition
        t2_ai = 10
        t3_ai_min = max(10, 10)  # T3 minimum is 10
        t3_ai = t3_ai_min

        results = {"T2": t2_ai, "T3": t3_ai}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0


class TestConsistencyValidation:
    """Test consistency validation across multiple runs."""

    def test_consistent_decomposer(self) -> None:
        """Test consistent decomposer produces valid report."""
        decomposer = MockDecomposer(consistent=True)
        validator = APSValidator()
        context = {"goal_id": "test", "task_level": "T0"}

        violations = validator.validate_consistency(decomposer, context, runs=10)
        assert len(violations) == 0

    def test_inconsistent_decomposer(self) -> None:
        """Test inconsistent decomposer detected."""
        decomposer = MockDecomposer(consistent=False)
        validator = APSValidator()
        context = {"goal_id": "test", "task_level": "T0"}

        violations = validator.validate_consistency(decomposer, context, runs=10)
        assert len(violations) == 1
        assert violations[0].violation_type == "consistency"

    def test_multiple_contexts_consistency(self) -> None:
        """Test consistency validation across multiple contexts."""
        decomposer = MockDecomposer()
        validator = APSValidator()

        contexts = [
            {"goal_id": f"goal{i}", "task_level": level}
            for i, level in enumerate(["T0", "T1", "T2", "T3"])
        ]

        for context in contexts:
            violations = validator.validate_consistency(decomposer, context, runs=5)
            assert len(violations) == 0


class TestCompletenessValidation:
    """Test completeness validation of decomposition results."""

    def test_complete_result(self) -> None:
        """Test validation of complete AssemblyIndexResult."""
        result = AssemblyIndexResult(
            pattern_id="goal1",
            assembly_index=3,
            steps=[
                AssemblyStep("s1", "Step 1", (), "out1"),
                AssemblyStep("s2", "Step 2", ("out1",), "out2"),
                AssemblyStep("s3", "Step 3", ("out2",), "out3"),
            ],
            complexity_class="complex",
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        assert len(violations) == 0

    def test_multiple_completeness_violations(self) -> None:
        """Test detection of multiple completeness violations."""
        result = AssemblyIndexResult(
            pattern_id="",  # Invalid: empty
            assembly_index=-1,  # Invalid: negative
            steps=[AssemblyStep("s1", "Step", (), "out1")],  # Valid step
            complexity_class="invalid",  # Invalid: not in valid set
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        # Should have violations for empty pattern_id, negative AI, invalid complexity
        assert len(violations) >= 2


class TestValidationReportAnalysis:
    """Test analysis of validation reports."""

    def test_report_is_valid_property(self) -> None:
        """Test is_valid property."""
        # Valid report
        report = APSValidationReport(
            total_tasks_checked=4,
            violations=[],
            monotonicity_valid=True,
            bounds_valid=True,
            consistency_valid=True,
        )
        assert report.is_valid is True

        # Invalid report
        v = APSValidationViolation("mono", "test", "T0", "x", "y")
        report = APSValidationReport(
            total_tasks_checked=4,
            violations=[v],
        )
        assert report.is_valid is False

    def test_report_with_zero_violations(self) -> None:
        """Test report with exactly zero violations."""
        report = APSValidationReport(total_tasks_checked=4)
        assert len(report.violations) == 0
        assert report.is_valid is True

    def test_report_with_multiple_violations(self) -> None:
        """Test report with multiple different violation types."""
        violations = [
            APSValidationViolation("monotonicity", "desc1", "T0", "x", "y"),
            APSValidationViolation("bound", "desc2", "T1", "x", "y"),
            APSValidationViolation("consistency", "desc3", "T0", "x", "y"),
            APSValidationViolation("completeness", "desc4", "T2", "x", "y"),
        ]

        report = APSValidationReport(
            total_tasks_checked=4,
            violations=violations,
            monotonicity_valid=False,
            bounds_valid=False,
            consistency_valid=False,
        )

        assert len(report.violations) == 4
        assert report.is_valid is False
        # Check that violation types are present in report
        violation_types = {v.violation_type for v in report.violations}
        assert "monotonicity" in violation_types
        assert "bound" in violation_types
        assert "consistency" in violation_types
        assert "completeness" in violation_types


class TestDefaultContexts:
    """Test validation with default contexts."""

    def test_validate_all_default_contexts(self) -> None:
        """Test validate_all with default (no explicit) contexts."""
        decomposer = MockDecomposer()
        validator = APSValidator()

        report = validator.validate_all(decomposer=decomposer, test_contexts=None)
        assert isinstance(report, APSValidationReport)

    def test_empty_context_list(self) -> None:
        """Test validation with empty context list."""
        decomposer = MockDecomposer()
        validator = APSValidator()

        report = validator.validate_all(decomposer=decomposer, test_contexts=[])
        assert isinstance(report, APSValidationReport)

    def test_single_context(self) -> None:
        """Test validation with single context."""
        decomposer = MockDecomposer()
        validator = APSValidator()
        contexts = [{"goal_id": "test"}]

        report = validator.validate_all(decomposer=decomposer, test_contexts=contexts)
        assert isinstance(report, APSValidationReport)

    def test_multiple_contexts(self) -> None:
        """Test validation with multiple contexts."""
        decomposer = MockDecomposer()
        validator = APSValidator()
        contexts = [
            {"goal_id": f"goal{i}"}
            for i in range(5)
        ]

        report = validator.validate_all(decomposer=decomposer, test_contexts=contexts)
        assert isinstance(report, APSValidationReport)


class TestMonotonicityInvariants:
    """Test specific monotonicity invariants."""

    def test_t0_less_than_t1(self) -> None:
        """Test T0.AI < T1.AI (strict for different ranges)."""
        validator = APSValidator()
        # T0 max is 4, T1 min is 3, so overlap exists
        # But generally T0 < T1
        results = {"T0": 2, "T1": 5}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0

    def test_t1_less_than_t2(self) -> None:
        """Test T1.AI ≤ T2.AI."""
        validator = APSValidator()
        results = {"T1": 5, "T2": 10}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0

    def test_t2_less_than_t3(self) -> None:
        """Test T2.AI ≤ T3.AI."""
        validator = APSValidator()
        results = {"T2": 10, "T3": 15}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0


class TestBoundsInvariants:
    """Test specific boundary conditions."""

    def test_t0_boundary_values(self) -> None:
        """Test T0 at exact boundaries."""
        validator = APSValidator()
        # T0: [1, 4]
        valid_values = [1, 2, 3, 4]
        for ai in valid_values:
            violations = validator.validate_bounds({"T0": ai})
            assert len(violations) == 0

        invalid_values = [0, 5]
        for ai in invalid_values:
            violations = validator.validate_bounds({"T0": ai})
            assert len(violations) == 1

    def test_t1_boundary_values(self) -> None:
        """Test T1 at exact boundaries."""
        validator = APSValidator()
        # T1: [3, 9]
        valid_values = [3, 5, 9]
        for ai in valid_values:
            violations = validator.validate_bounds({"T1": ai})
            assert len(violations) == 0

        invalid_values = [2, 10]
        for ai in invalid_values:
            violations = validator.validate_bounds({"T1": ai})
            assert len(violations) == 1

    def test_t3_unbounded_upper(self) -> None:
        """Test T3 has reasonable upper limit in implementation."""
        validator = APSValidator()
        # T3: [10, 999) as currently bounded in code
        for ai in [10, 100, 500, 999]:
            violations = validator.validate_bounds({"T3": ai})
            assert len(violations) == 0
