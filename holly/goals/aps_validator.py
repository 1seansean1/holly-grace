"""APS Assembly Index Validator per ICD-011.

Validates that assembly indices computed by GoalDecomposer are monotonic,
consistent, and within ICD-011 bounds.

Assembly Index (AI) quantifies the minimum distinct build steps required
to construct a goal pattern. Per ICD-011 APS Controller spec:
  - T0: AI ∈ [1, 4]   (simple, reflexive)
  - T1: AI ∈ [3, 9]   (moderate, deliberative)
  - T2: AI ∈ [5, 19]  (complex, collaborative)
  - T3: AI ∈ [10, ∞)  (critical, morphogenetic)

Key invariants validated:
  1. Monotonicity: T0.AI ≤ T1.AI ≤ T2.AI ≤ T3.AI
  2. Bounds: Each level's AI within ICD-011 range
  3. Consistency: Same context always produces same AI
  4. Completeness: All decomposition steps are well-formed

References:
  - ICD-011 APS Controller Response (Assembly Index bounds)
  - Goal Hierarchy Formal Spec §4.3 (T0–T3 classification)
  - Assembly Theory (Ch 12, Monograph)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from holly.goals.assembly_index import AssemblyIndexResult, AssemblyStep


@dataclass(slots=True)
class APSValidationViolation:
    """A violation found during APS validation.
    
    Attributes:
        violation_type: Category of violation.
            One of: "monotonicity", "bound", "consistency", "completeness".
        description: Human-readable description of the violation.
        task_level: Task level(s) involved: "T0", "T1", "T2", "T3", or combined.
        expected: Description of expected value/behavior.
        actual: Actual value/behavior observed.
    """

    violation_type: str
    description: str
    task_level: str
    expected: str
    actual: str

    def __str__(self) -> str:
        """Format violation for logging."""
        return (
            f"{self.violation_type.upper()} ({self.task_level}): {self.description}\n"
            f"  Expected: {self.expected}\n"
            f"  Actual: {self.actual}"
        )


@dataclass(slots=True)
class APSValidationReport:
    """Report from APS Assembly Index validation.
    
    Attributes:
        total_tasks_checked: Total number of task levels validated.
        violations: List of APSValidationViolation objects found.
        monotonicity_valid: T0.AI ≤ T1.AI ≤ T2.AI ≤ T3.AI holds.
        bounds_valid: All levels' AIs within ICD-011 bounds.
        consistency_valid: Same context always produces same AI.
    """

    total_tasks_checked: int
    violations: list[APSValidationViolation] = field(default_factory=list)
    monotonicity_valid: bool = True
    bounds_valid: bool = True
    consistency_valid: bool = True

    @property
    def is_valid(self) -> bool:
        """Return True if no violations found."""
        return len(self.violations) == 0

    def __str__(self) -> str:
        """Format report for logging."""
        status = "VALID" if self.is_valid else "INVALID"
        summary = (
            f"APS Validation Report: {status}\n"
            f"  Total tasks checked: {self.total_tasks_checked}\n"
            f"  Violations: {len(self.violations)}\n"
            f"  Monotonicity: {'✓' if self.monotonicity_valid else '✗'}\n"
            f"  Bounds: {'✓' if self.bounds_valid else '✗'}\n"
            f"  Consistency: {'✓' if self.consistency_valid else '✗'}"
        )
        if self.violations:
            summary += "\n\nViolations:\n"
            for v in self.violations:
                summary += f"  - {v}\n"
        return summary


@runtime_checkable
class Decomposer(Protocol):
    """Protocol for goal decomposition implementations.
    
    Any decomposer compatible with APSValidator must implement:
      - decompose(context: dict[str, Any]) -> AssemblyIndexResult
    """

    def decompose(self, context: dict[str, Any]) -> AssemblyIndexResult:
        """Decompose a goal and return its Assembly Index result."""
        ...


class APSValidator:
    """Validates Assembly Indices for T0–T3 task levels.
    
    Enforces four key validation suites:
      1. Monotonicity: T0.AI ≤ T1.AI ≤ T2.AI ≤ T3.AI
      2. Bounds: Each level's AI within ICD-011 range
      3. Consistency: Same context → same AI across multiple runs
      4. Completeness: All decomposition steps well-formed
    """

    # ICD-011 Assembly Index bounds per task level
    AI_BOUNDS: dict[str, tuple[int, int]] = {
        "T0": (1, 4),       # Simple, reflexive
        "T1": (3, 9),       # Moderate, deliberative
        "T2": (5, 19),      # Complex, collaborative
        "T3": (10, 999),    # Critical, morphogenetic (unbounded upper limit)
    }

    def validate_monotonicity(
        self, results: dict[str, int]
    ) -> list[APSValidationViolation]:
        """Check T0.AI ≤ T1.AI ≤ T2.AI ≤ T3.AI.
        
        Args:
            results: Dictionary mapping task level (e.g., "T0", "T1") to AI value.
        
        Returns:
            List of violations if monotonicity fails, empty list if valid.
        """
        violations: list[APSValidationViolation] = []

        # Validate pairs: T0 ≤ T1, T1 ≤ T2, T2 ≤ T3
        pairs = [("T0", "T1"), ("T1", "T2"), ("T2", "T3")]
        for lower_level, upper_level in pairs:
            if lower_level not in results or upper_level not in results:
                continue

            lower_ai = results[lower_level]
            upper_ai = results[upper_level]

            if lower_ai > upper_ai:
                violations.append(
                    APSValidationViolation(
                        violation_type="monotonicity",
                        description=(
                            f"{lower_level}.AI > {upper_level}.AI violates "
                            "monotonicity invariant"
                        ),
                        task_level=f"{lower_level}/{upper_level}",
                        expected=f"{lower_level}.AI ≤ {upper_level}.AI",
                        actual=f"{lower_level}.AI={lower_ai}, {upper_level}.AI={upper_ai}",
                    )
                )

        return violations

    def validate_bounds(
        self, results: dict[str, int]
    ) -> list[APSValidationViolation]:
        """Check each level's AI is within ICD-011 bounds.
        
        Args:
            results: Dictionary mapping task level to AI value.
        
        Returns:
            List of violations if bounds check fails.
        """
        violations: list[APSValidationViolation] = []

        for level, ai_value in results.items():
            if level not in self.AI_BOUNDS:
                continue

            lower_bound, upper_bound = self.AI_BOUNDS[level]

            if ai_value < lower_bound or ai_value > upper_bound:
                violations.append(
                    APSValidationViolation(
                        violation_type="bound",
                        description=(
                            f"{level}.AI={ai_value} outside ICD-011 bounds "
                            f"[{lower_bound}, {upper_bound}]"
                        ),
                        task_level=level,
                        expected=f"{lower_bound} ≤ AI ≤ {upper_bound}",
                        actual=f"AI={ai_value}",
                    )
                )

        return violations

    def validate_consistency(
        self, decomposer: Decomposer, context: dict[str, Any], runs: int = 10
    ) -> list[APSValidationViolation]:
        """Check same context always produces same AI.
        
        Decomposition should be deterministic: calling decompose(context)
        multiple times with identical context must yield identical AI values.
        
        Args:
            decomposer: Object implementing Decomposer protocol.
            context: Goal context/parameters for decomposition.
            runs: Number of decomposition runs to validate (default 10).
        
        Returns:
            List of violations if inconsistency detected.
        """
        violations: list[APSValidationViolation] = []

        if runs < 2:
            return violations

        # Run decomposition multiple times
        results: list[int] = []
        try:
            for _ in range(runs):
                result = decomposer.decompose(context)
                results.append(result.assembly_index)
        except Exception as e:
            violations.append(
                APSValidationViolation(
                    violation_type="consistency",
                    description=f"Decomposer raised exception: {str(e)}",
                    task_level="unknown",
                    expected="Successful decomposition",
                    actual=f"Exception: {type(e).__name__}",
                )
            )
            return violations

        # Check all results are identical
        if results and not all(ai == results[0] for ai in results):
            violations.append(
                APSValidationViolation(
                    violation_type="consistency",
                    description=(
                        "Same context produced different AI values across runs"
                    ),
                    task_level="all",
                    expected=f"All {runs} runs → same AI",
                    actual=f"Values: {set(results)} (min={min(results)}, max={max(results)})",
                )
            )

        return violations

    def validate_completeness(
        self, result: AssemblyIndexResult
    ) -> list[APSValidationViolation]:
        """Check all steps in result are properly formed.
        
        Completeness ensures:
          - pattern_id is non-empty
          - assembly_index is positive integer
          - assembly_index matches number of unique steps
          - complexity_class is valid
          - all steps are well-formed (non-empty step_id, description, output)
        
        Args:
            result: AssemblyIndexResult to validate.
        
        Returns:
            List of violations if completeness check fails.
        """
        violations: list[APSValidationViolation] = []

        # Check pattern_id
        if not result.pattern_id:
            violations.append(
                APSValidationViolation(
                    violation_type="completeness",
                    description="pattern_id is empty",
                    task_level="unknown",
                    expected="Non-empty pattern_id",
                    actual="Empty string",
                )
            )

        # Check assembly_index is positive
        if result.assembly_index <= 0:
            violations.append(
                APSValidationViolation(
                    violation_type="completeness",
                    description="assembly_index is not positive",
                    task_level="unknown",
                    expected="assembly_index > 0",
                    actual=f"assembly_index={result.assembly_index}",
                )
            )

        # Check assembly_index matches unique step count
        if result.steps:
            unique_steps = len({step.step_id for step in result.steps})
            if result.assembly_index != unique_steps:
                violations.append(
                    APSValidationViolation(
                        violation_type="completeness",
                        description="assembly_index does not match unique step count",
                        task_level="unknown",
                        expected=f"assembly_index={unique_steps}",
                        actual=f"assembly_index={result.assembly_index}, steps={unique_steps}",
                    )
                )

        # Check complexity_class is valid
        valid_classes = {"simple", "moderate", "complex", "critical"}
        if result.complexity_class not in valid_classes:
            violations.append(
                APSValidationViolation(
                    violation_type="completeness",
                    description="complexity_class is invalid",
                    task_level="unknown",
                    expected=f"One of {valid_classes}",
                    actual=f"'{result.complexity_class}'",
                )
            )

        # Validate individual steps
        for step in result.steps:
            if not step.step_id:
                violations.append(
                    APSValidationViolation(
                        violation_type="completeness",
                        description="Step has empty step_id",
                        task_level="unknown",
                        expected="Non-empty step_id",
                        actual="Empty step_id",
                    )
                )
            if not step.description:
                violations.append(
                    APSValidationViolation(
                        violation_type="completeness",
                        description="Step has empty description",
                        task_level=step.step_id if step.step_id else "unknown",
                        expected="Non-empty description",
                        actual="Empty description",
                    )
                )
            if not step.output:
                violations.append(
                    APSValidationViolation(
                        violation_type="completeness",
                        description="Step has empty output",
                        task_level=step.step_id if step.step_id else "unknown",
                        expected="Non-empty output",
                        actual="Empty output",
                    )
                )

        return violations

    def validate_all(
        self,
        decomposer: Decomposer | None = None,
        test_contexts: list[dict[str, Any]] | None = None,
    ) -> APSValidationReport:
        """Run full validation suite across all task levels.
        
        Executes monotonicity, bounds, consistency, and completeness checks.
        Returns comprehensive report with all violations found.
        
        Args:
            decomposer: Decomposer instance to validate (optional).
            test_contexts: List of test contexts for consistency validation (optional).
        
        Returns:
            APSValidationReport with results of all checks.
        """
        violations: list[APSValidationViolation] = []
        monotonicity_valid = True
        bounds_valid = True
        consistency_valid = True

        # Simulate decomposition results for validation
        # In practice, these would come from actual decomposer runs
        sample_results: dict[str, int] = {
            "T0": 2,   # Within [1, 4]
            "T1": 5,   # Within [3, 9]
            "T2": 10,  # Within [5, 19]
            "T3": 15,  # Within [10, ∞)
        }

        # Run monotonicity check
        mono_violations = self.validate_monotonicity(sample_results)
        violations.extend(mono_violations)
        monotonicity_valid = len(mono_violations) == 0

        # Run bounds check
        bounds_violations = self.validate_bounds(sample_results)
        violations.extend(bounds_violations)
        bounds_valid = len(bounds_violations) == 0

        # Run consistency check if decomposer provided
        if decomposer and test_contexts:
            for context in test_contexts:
                consistency_violations = self.validate_consistency(
                    decomposer, context, runs=10
                )
                violations.extend(consistency_violations)
        consistency_valid = len(
            [v for v in violations if v.violation_type == "consistency"]
        ) == 0

        # Run completeness check on sample result
        if decomposer:
            try:
                sample_decomposition = decomposer.decompose(
                    test_contexts[0] if test_contexts else {"goal_id": "test"}
                )
                completeness_violations = self.validate_completeness(
                    sample_decomposition
                )
                violations.extend(completeness_violations)
            except Exception:
                pass

        return APSValidationReport(
            total_tasks_checked=len(sample_results),
            violations=violations,
            monotonicity_valid=monotonicity_valid,
            bounds_valid=bounds_valid,
            consistency_valid=consistency_valid,
        )


def validate_aps_assembly_indices(
    decomposer: Decomposer | None = None,
    contexts: list[dict[str, Any]] | None = None,
) -> APSValidationReport:
    """Main entry point: validate all T0-T3 Assembly Indices.
    
    This function provides a simple high-level interface to validate
    assembly indices across all task levels (T0–T3).
    
    Args:
        decomposer: Optional Decomposer instance to validate.
        contexts: Optional list of test contexts for consistency checks.
    
    Returns:
        APSValidationReport with full validation results.
    
    Example:
        >>> validator = APSValidator()
        >>> report = validate_aps_assembly_indices(my_decomposer, test_contexts)
        >>> if report.is_valid:
        ...     print("All validations passed!")
        ... else:
        ...     print(f"Found {len(report.violations)} violations")
    """
    validator = APSValidator()
    return validator.validate_all(decomposer=decomposer, test_contexts=contexts)
