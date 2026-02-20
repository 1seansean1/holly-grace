"""Unit tests for APS Assembly Index Validator.

Tests cover:
  - APSValidationViolation: violation creation and formatting
  - APSValidationReport: report structure and is_valid property
  - APSValidator_Monotonicity: T0 ≤ T1 ≤ T2 ≤ T3 invariant
  - APSValidator_Bounds: ICD-011 bounds checking
  - APSValidator_Consistency: deterministic decomposition
  - APSValidator_Completeness: well-formed decomposition steps
"""

from __future__ import annotations

import pytest

from holly.goals.aps_validator import (
    APSValidator,
    APSValidationReport,
    APSValidationViolation,
)
from holly.goals.assembly_index import AssemblyIndexResult, AssemblyStep


class TestAPSValidationViolation:
    """Test APSValidationViolation dataclass."""

    def test_violation_creation(self) -> None:
        """Test creating a basic violation."""
        v = APSValidationViolation(
            violation_type="monotonicity",
            description="T0.AI > T1.AI",
            task_level="T0/T1",
            expected="T0.AI ≤ T1.AI",
            actual="T0.AI=5, T1.AI=3",
        )
        assert v.violation_type == "monotonicity"
        assert v.task_level == "T0/T1"

    def test_violation_str_format(self) -> None:
        """Test string representation of violation."""
        v = APSValidationViolation(
            violation_type="bound",
            description="T2.AI out of bounds",
            task_level="T2",
            expected="5 ≤ AI ≤ 19",
            actual="AI=25",
        )
        str_repr = str(v)
        assert "BOUND" in str_repr
        assert "T2" in str_repr
        assert "5 ≤ AI ≤ 19" in str_repr

    def test_violation_types(self) -> None:
        """Test all valid violation types."""
        types = ["monotonicity", "bound", "consistency", "completeness"]
        for vtype in types:
            v = APSValidationViolation(
                violation_type=vtype,
                description="test",
                task_level="T0",
                expected="x",
                actual="y",
            )
            assert v.violation_type == vtype


class TestAPSValidationReport:
    """Test APSValidationReport dataclass."""

    def test_empty_report(self) -> None:
        """Test creating a valid report with no violations."""
        report = APSValidationReport(
            total_tasks_checked=4,
            violations=[],
            monotonicity_valid=True,
            bounds_valid=True,
            consistency_valid=True,
        )
        assert report.is_valid is True
        assert len(report.violations) == 0

    def test_report_with_violations(self) -> None:
        """Test report with violations is invalid."""
        v = APSValidationViolation(
            violation_type="monotonicity",
            description="test",
            task_level="T0",
            expected="x",
            actual="y",
        )
        report = APSValidationReport(
            total_tasks_checked=4,
            violations=[v],
            monotonicity_valid=False,
        )
        assert report.is_valid is False
        assert len(report.violations) == 1

    def test_report_str_format(self) -> None:
        """Test string representation of report."""
        report = APSValidationReport(
            total_tasks_checked=4,
            violations=[],
            monotonicity_valid=True,
            bounds_valid=True,
            consistency_valid=True,
        )
        str_repr = str(report)
        assert "VALID" in str_repr
        assert "4" in str_repr
        assert "Monotonicity" in str_repr

    def test_report_total_tasks(self) -> None:
        """Test total_tasks_checked field."""
        for count in [1, 2, 3, 4]:
            report = APSValidationReport(total_tasks_checked=count)
            assert report.total_tasks_checked == count


class TestAPSValidator_Monotonicity:
    """Test monotonicity validation: T0.AI ≤ T1.AI ≤ T2.AI ≤ T3.AI."""

    def test_valid_monotonic_sequence(self) -> None:
        """Test valid increasing sequence T0 ≤ T1 ≤ T2 ≤ T3."""
        validator = APSValidator()
        results = {"T0": 2, "T1": 5, "T2": 10, "T3": 15}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0

    def test_valid_equal_adjacent(self) -> None:
        """Test valid sequence with equal adjacent values."""
        validator = APSValidator()
        results = {"T0": 3, "T1": 3, "T2": 10, "T3": 10}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0

    def test_violation_t0_greater_than_t1(self) -> None:
        """Test violation when T0.AI > T1.AI."""
        validator = APSValidator()
        results = {"T0": 5, "T1": 3, "T2": 10, "T3": 15}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 1
        assert violations[0].violation_type == "monotonicity"
        assert "T0" in violations[0].task_level and "T1" in violations[0].task_level

    def test_violation_t1_greater_than_t2(self) -> None:
        """Test violation when T1.AI > T2.AI."""
        validator = APSValidator()
        results = {"T0": 2, "T1": 15, "T2": 10, "T3": 15}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 1
        assert violations[0].violation_type == "monotonicity"

    def test_violation_t2_greater_than_t3(self) -> None:
        """Test violation when T2.AI > T3.AI."""
        validator = APSValidator()
        results = {"T0": 2, "T1": 5, "T2": 20, "T3": 10}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 1
        assert violations[0].violation_type == "monotonicity"

    def test_multiple_violations(self) -> None:
        """Test detection of multiple monotonicity violations."""
        validator = APSValidator()
        results = {"T0": 10, "T1": 5, "T2": 3, "T3": 1}
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 3  # T0>T1, T1>T2, T2>T3

    def test_partial_results(self) -> None:
        """Test monotonicity with missing levels."""
        validator = APSValidator()
        results = {"T0": 2, "T2": 10, "T3": 15}  # Missing T1
        violations = validator.validate_monotonicity(results)
        assert len(violations) == 0


class TestAPSValidator_Bounds:
    """Test ICD-011 bounds validation."""

    def test_all_levels_within_bounds(self) -> None:
        """Test valid AI values within all bounds."""
        validator = APSValidator()
        results = {"T0": 2, "T1": 5, "T2": 10, "T3": 15}
        violations = validator.validate_bounds(results)
        assert len(violations) == 0

    def test_t0_lower_bound(self) -> None:
        """Test T0.AI at lower bound (1)."""
        validator = APSValidator()
        results = {"T0": 1}
        violations = validator.validate_bounds(results)
        assert len(violations) == 0

    def test_t0_upper_bound(self) -> None:
        """Test T0.AI at upper bound (4)."""
        validator = APSValidator()
        results = {"T0": 4}
        violations = validator.validate_bounds(results)
        assert len(violations) == 0

    def test_t0_below_lower_bound(self) -> None:
        """Test T0.AI below lower bound."""
        validator = APSValidator()
        results = {"T0": 0}
        violations = validator.validate_bounds(results)
        assert len(violations) == 1
        assert violations[0].violation_type == "bound"
        assert violations[0].task_level == "T0"

    def test_t0_above_upper_bound(self) -> None:
        """Test T0.AI above upper bound."""
        validator = APSValidator()
        results = {"T0": 5}
        violations = validator.validate_bounds(results)
        assert len(violations) == 1
        assert violations[0].task_level == "T0"

    def test_t1_within_bounds(self) -> None:
        """Test T1.AI within [3, 9]."""
        validator = APSValidator()
        for ai in [3, 5, 9]:
            results = {"T1": ai}
            violations = validator.validate_bounds(results)
            assert len(violations) == 0

    def test_t1_out_of_bounds(self) -> None:
        """Test T1.AI out of [3, 9]."""
        validator = APSValidator()
        for ai in [2, 10]:
            results = {"T1": ai}
            violations = validator.validate_bounds(results)
            assert len(violations) == 1

    def test_t2_within_bounds(self) -> None:
        """Test T2.AI within [5, 19]."""
        validator = APSValidator()
        for ai in [5, 12, 19]:
            results = {"T2": ai}
            violations = validator.validate_bounds(results)
            assert len(violations) == 0

    def test_t2_out_of_bounds(self) -> None:
        """Test T2.AI out of [5, 19]."""
        validator = APSValidator()
        for ai in [4, 20]:
            results = {"T2": ai}
            violations = validator.validate_bounds(results)
            assert len(violations) == 1

    def test_t3_within_bounds(self) -> None:
        """Test T3.AI within [10, ∞)."""
        validator = APSValidator()
        for ai in [10, 50, 999]:
            results = {"T3": ai}
            violations = validator.validate_bounds(results)
            assert len(violations) == 0

    def test_t3_below_lower_bound(self) -> None:
        """Test T3.AI below lower bound."""
        validator = APSValidator()
        results = {"T3": 9}
        violations = validator.validate_bounds(results)
        assert len(violations) == 1

    def test_multiple_bound_violations(self) -> None:
        """Test multiple levels out of bounds."""
        validator = APSValidator()
        results = {"T0": 10, "T1": 1, "T2": 100, "T3": 5}
        violations = validator.validate_bounds(results)
        assert len(violations) == 4


class TestAPSValidator_Consistency:
    """Test consistency validation: same context → same AI."""

    def test_consistent_results(self) -> None:
        """Test decomposer producing consistent results."""

        class MockDecomposer:
            def decompose(self, context):
                return AssemblyIndexResult(
                    pattern_id="test",
                    assembly_index=5,
                    steps=[AssemblyStep(
                        step_id="s1",
                        description="step1",
                        output="out1"
                    )],
                    complexity_class="moderate",
                )

        validator = APSValidator()
        decomposer = MockDecomposer()
        context = {"goal_id": "test"}
        violations = validator.validate_consistency(decomposer, context, runs=10)
        assert len(violations) == 0

    def test_inconsistent_results(self) -> None:
        """Test decomposer producing inconsistent results."""

        class InconsistentDecomposer:
            def __init__(self):
                self.call_count = 0

            def decompose(self, context):
                self.call_count += 1
                ai = 5 if self.call_count % 2 == 0 else 3
                return AssemblyIndexResult(
                    pattern_id="test",
                    assembly_index=ai,
                    steps=[AssemblyStep(
                        step_id=f"s{self.call_count}",
                        description="step",
                        output="out"
                    )],
                    complexity_class="moderate",
                )

        validator = APSValidator()
        decomposer = InconsistentDecomposer()
        context = {"goal_id": "test"}
        violations = validator.validate_consistency(decomposer, context, runs=10)
        assert len(violations) == 1
        assert violations[0].violation_type == "consistency"

    def test_decomposer_exception(self) -> None:
        """Test handling of decomposer exceptions."""

        class FaultyDecomposer:
            def decompose(self, context):
                raise RuntimeError("Decomposition failed")

        validator = APSValidator()
        decomposer = FaultyDecomposer()
        context = {"goal_id": "test"}
        violations = validator.validate_consistency(decomposer, context, runs=5)
        assert len(violations) == 1
        assert violations[0].violation_type == "consistency"
        assert "exception" in violations[0].description.lower()

    def test_single_run_no_violation(self) -> None:
        """Test that single run (runs=1) produces no violations."""

        class MockDecomposer:
            def decompose(self, context):
                return AssemblyIndexResult(
                    pattern_id="test",
                    assembly_index=5,
                    steps=[],
                    complexity_class="moderate",
                )

        validator = APSValidator()
        decomposer = MockDecomposer()
        context = {"goal_id": "test"}
        violations = validator.validate_consistency(decomposer, context, runs=1)
        assert len(violations) == 0


class TestAPSValidator_Completeness:
    """Test completeness validation: well-formed decomposition steps."""

    def test_valid_result(self) -> None:
        """Test valid AssemblyIndexResult."""
        result = AssemblyIndexResult(
            pattern_id="goal1",
            assembly_index=3,
            steps=[
                AssemblyStep("s1", "Step 1", (), "out1"),
                AssemblyStep("s2", "Step 2", ("out1",), "out2"),
                AssemblyStep("s3", "Step 3", ("out2",), "out3"),
            ],
            complexity_class="moderate",
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        assert len(violations) == 0

    def test_empty_pattern_id(self) -> None:
        """Test violation for empty pattern_id."""
        result = AssemblyIndexResult(
            pattern_id="",
            assembly_index=1,
            steps=[AssemblyStep("s1", "Step 1", (), "out1")],
            complexity_class="simple",
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        assert any(v.violation_type == "completeness" for v in violations)

    def test_non_positive_assembly_index(self) -> None:
        """Test violation for non-positive assembly_index."""
        for ai in [0, -1]:
            result = AssemblyIndexResult(
                pattern_id="goal1",
                assembly_index=ai,
                steps=[AssemblyStep("s1", "Step 1", (), "out1")],
                complexity_class="simple",
            )
            validator = APSValidator()
            violations = validator.validate_completeness(result)
            assert len(violations) >= 1
            assert any(v.violation_type == "completeness" for v in violations)

    def test_ai_step_count_mismatch(self) -> None:
        """Test violation when AI doesn't match unique step count."""
        result = AssemblyIndexResult(
            pattern_id="goal1",
            assembly_index=2,  # Says 2 unique steps
            steps=[
                AssemblyStep("s1", "Step 1", (), "out1"),
                AssemblyStep("s2", "Step 2", ("out1",), "out2"),
                AssemblyStep("s3", "Step 3", ("out2",), "out3"),
            ],  # But has 3
            complexity_class="complex",
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        assert len(violations) >= 1

    def test_invalid_complexity_class(self) -> None:
        """Test violation for invalid complexity_class."""
        result = AssemblyIndexResult(
            pattern_id="goal1",
            assembly_index=1,
            steps=[AssemblyStep("s1", "Step 1", (), "out1")],
            complexity_class="invalid",
        )
        validator = APSValidator()
        violations = validator.validate_completeness(result)
        assert any(v.violation_type == "completeness" for v in violations)

    def test_valid_complexity_classes(self) -> None:
        """Test all valid complexity classes."""
        for cls in ["simple", "moderate", "complex", "critical"]:
            result = AssemblyIndexResult(
                pattern_id="goal1",
                assembly_index=1,
                steps=[AssemblyStep("s1", "Step 1", (), "out1")],
                complexity_class=cls,
            )
            validator = APSValidator()
            violations = validator.validate_completeness(result)
            assert len(violations) == 0


class TestAPSValidator_Integration:
    """Integration tests for full validation."""

    def test_validate_all_valid(self) -> None:
        """Test validate_all with no violations."""
        validator = APSValidator()
        report = validator.validate_all()
        assert report.is_valid is True
        assert report.monotonicity_valid is True
        assert report.bounds_valid is True

    def test_validate_all_report_structure(self) -> None:
        """Test validate_all returns proper report."""
        validator = APSValidator()
        report = validator.validate_all()
        assert isinstance(report, APSValidationReport)
        assert report.total_tasks_checked == 4
        assert isinstance(report.violations, list)

    def test_ai_bounds_constants(self) -> None:
        """Test AI_BOUNDS constants match spec."""
        validator = APSValidator()
        assert validator.AI_BOUNDS["T0"] == (1, 4)
        assert validator.AI_BOUNDS["T1"] == (3, 9)
        assert validator.AI_BOUNDS["T2"] == (5, 19)
        assert validator.AI_BOUNDS["T3"] == (10, 999)
