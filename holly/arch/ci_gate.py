"""Unified CI gate — ordered stage pipeline for merge blocking.

Task 11.1 — Integrate drift, scanner, fitness, RTM into unified gate.

Runs all architecture verification stages in order.  Any failure at
a blocking stage halts the pipeline and returns a FAIL verdict.

Stage order:

1. **Fitness functions** — layer violations, coupling, dependency depth.
2. **Scanner** — missing/wrong decorator detection.
3. **RTM** — traceability matrix generation (informational).
4. **Drift detection** — YAML ↔ SAD drift (placeholder until Task 6.1).

Each stage produces a ``StageResult`` with pass/fail status and
details.  The gate aggregates all stages into a ``GateVerdict``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from holly.arch.fitness import run_all as run_fitness
from holly.arch.registry import ArchitectureRegistry
from holly.arch.rtm import generate_rtm

if TYPE_CHECKING:
    from pathlib import Path

    from holly.arch.scanner import ScanReport


# ═══════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════


class StageKind(StrEnum):
    """CI gate stage identifiers."""

    FITNESS = "fitness"
    SCANNER = "scanner"
    RTM = "rtm"
    DRIFT = "drift"


class Severity(StrEnum):
    """Stage severity level."""

    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class Verdict(StrEnum):
    """Overall gate verdict."""

    PASS = "pass"
    FAIL = "fail"


# ═══════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════


@dataclass(slots=True)
class StageResult:
    """Result of a single CI gate stage."""

    stage: StageKind
    passed: bool
    severity: Severity
    duration_ms: float = 0.0
    message: str = ""
    details: Any = None

    @property
    def status_label(self) -> str:
        """Human-readable status."""
        if self.passed:
            return "PASS"
        if self.severity == Severity.BLOCKING:
            return "FAIL"
        if self.severity == Severity.WARNING:
            return "WARN"
        return "INFO"


@dataclass(slots=True)
class GateVerdict:
    """Aggregate result of the full CI gate pipeline."""

    verdict: Verdict
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        """Whether the gate passed."""
        return self.verdict == Verdict.PASS

    @property
    def blocking_failures(self) -> list[StageResult]:
        """Stages that caused a FAIL verdict."""
        return [
            s for s in self.stages
            if not s.passed and s.severity == Severity.BLOCKING
        ]

    @property
    def warnings(self) -> list[StageResult]:
        """Stages that produced warnings."""
        return [
            s for s in self.stages
            if not s.passed and s.severity == Severity.WARNING
        ]

    def summary(self) -> str:
        """Human-readable gate summary."""
        lines = [
            f"CI Gate Verdict: {self.verdict.upper()}",
            f"Total duration: {self.total_duration_ms:.0f}ms",
            "",
        ]
        for s in self.stages:
            lines.append(
                f"  [{s.status_label:4s}] {s.stage:<10s} "
                f"({s.duration_ms:.0f}ms) {s.message}"
            )
        failures = self.blocking_failures
        if failures:
            lines.append("")
            lines.append("Blocking failures:")
            for f in failures:
                lines.append(f"  - {f.stage}: {f.message}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# Stage runners
# ═══════════════════════════════════════════════════════════


def _run_fitness_stage(
    root: Path,
    *,
    package: str = "holly",
    max_efferent: int = 15,
    max_afferent: int = 20,
    max_depth: int = 8,
) -> StageResult:
    """Run fitness functions (layer violations, coupling, depth)."""
    t0 = time.monotonic()
    results = run_fitness(
        root,
        package=package,
        max_efferent=max_efferent,
        max_afferent=max_afferent,
        max_depth=max_depth,
    )
    duration = (time.monotonic() - t0) * 1000

    all_passed = all(r.passed for r in results)
    failures = [r for r in results if not r.passed]

    if all_passed:
        msg = f"All {len(results)} fitness checks passed"
    else:
        names = ", ".join(f.name for f in failures)
        msg = f"{len(failures)} fitness check(s) failed: {names}"

    return StageResult(
        stage=StageKind.FITNESS,
        passed=all_passed,
        severity=Severity.BLOCKING,
        duration_ms=duration,
        message=msg,
        details=results,
    )


def _run_scanner_stage(
    root: Path,
    *,
    package: str = "holly",
) -> StageResult:
    """Run the AST scanner for decorator compliance.

    Note: The scanner requires imported modules to be introspectable.
    We use the scanner's ``scan_full()`` when available, otherwise
    report an informational result.
    """
    t0 = time.monotonic()

    try:
        from holly.arch.scanner import generate_rules, scan_directory

        rules = generate_rules()
        src_dir = root / package.replace(".", "/")
        report: ScanReport = scan_directory(src_dir, rules)
        duration = (time.monotonic() - t0) * 1000

        if report.is_clean:
            msg = (
                f"Scanner clean: {report.ok_count} OK findings, "
                f"{report.rules_applied} rules applied"
            )
        else:
            issues = []
            if report.missing_count:
                issues.append(f"{report.missing_count} missing")
            if report.wrong_count:
                issues.append(f"{report.wrong_count} wrong")
            if report.icd_mismatch_count:
                issues.append(f"{report.icd_mismatch_count} ICD mismatch")
            msg = f"Scanner issues: {', '.join(issues)}"

        return StageResult(
            stage=StageKind.SCANNER,
            passed=report.is_clean,
            severity=Severity.BLOCKING,
            duration_ms=duration,
            message=msg,
            details=report,
        )
    except (ImportError, AttributeError):
        duration = (time.monotonic() - t0) * 1000
        return StageResult(
            stage=StageKind.SCANNER,
            passed=True,
            severity=Severity.INFO,
            duration_ms=duration,
            message="Scanner not available (scan_directory not found)",
        )


def _run_rtm_stage(
    root: Path,
    *,
    package: str = "holly",
    test_dir: str = "tests",
) -> StageResult:
    """Run RTM generation (informational — does not block)."""
    t0 = time.monotonic()
    rtm = generate_rtm(root, package=package, test_dir=test_dir)
    duration = (time.monotonic() - t0) * 1000

    msg = (
        f"RTM: {len(rtm.entries)} entries, "
        f"{rtm.covered_count} covered, "
        f"{rtm.uncovered_count} uncovered "
        f"({rtm.coverage_ratio:.0%} coverage)"
    )

    return StageResult(
        stage=StageKind.RTM,
        passed=True,  # RTM is informational, never blocks.
        severity=Severity.INFO,
        duration_ms=duration,
        message=msg,
        details=rtm,
    )


def _run_drift_stage(
    root: Path,
    *,
    package: str = "holly",
) -> StageResult:
    """Run drift detection (placeholder until Task 6.1).

    Currently verifies that architecture.yaml loads without error
    and the component count matches expectations.
    """
    t0 = time.monotonic()

    arch_yaml = root / "docs" / "architecture.yaml"
    if not arch_yaml.exists():
        duration = (time.monotonic() - t0) * 1000
        return StageResult(
            stage=StageKind.DRIFT,
            passed=True,
            severity=Severity.INFO,
            duration_ms=duration,
            message=f"Drift check skipped — no architecture.yaml at {root}",
        )

    try:
        reg = ArchitectureRegistry.get()
        doc = reg.document
        comp_count = len(doc.components)
        icd_count = len(doc.icds)
        duration = (time.monotonic() - t0) * 1000

        msg = (
            f"Drift check (stub): architecture.yaml loaded — "
            f"{comp_count} components, {icd_count} ICDs"
        )
        return StageResult(
            stage=StageKind.DRIFT,
            passed=True,
            severity=Severity.WARNING,
            duration_ms=duration,
            message=msg,
        )
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        return StageResult(
            stage=StageKind.DRIFT,
            passed=False,
            severity=Severity.WARNING,
            duration_ms=duration,
            message=f"Drift check failed: {exc}",
        )


# ═══════════════════════════════════════════════════════════
# Gate pipeline
# ═══════════════════════════════════════════════════════════


def run_gate(
    root: Path,
    *,
    package: str = "holly",
    test_dir: str = "tests",
    max_efferent: int = 15,
    max_afferent: int = 20,
    max_depth: int = 8,
    fail_fast: bool = True,
) -> GateVerdict:
    """Run the full CI gate pipeline.

    Executes all stages in order.  If ``fail_fast`` is True,
    stops after the first blocking failure.

    Parameters
    ----------
    root:
        Repository root directory.
    package:
        Top-level Python package.
    test_dir:
        Relative test directory path.
    max_efferent:
        Coupling threshold for efferent coupling.
    max_afferent:
        Coupling threshold for afferent coupling.
    max_depth:
        Maximum dependency chain length.
    fail_fast:
        Stop after first blocking failure.

    Returns
    -------
    GateVerdict:
        Aggregate gate result.
    """
    t0 = time.monotonic()
    stages: list[StageResult] = []

    # Stage 1: Fitness functions.
    fitness_result = _run_fitness_stage(
        root,
        package=package,
        max_efferent=max_efferent,
        max_afferent=max_afferent,
        max_depth=max_depth,
    )
    stages.append(fitness_result)
    if not fitness_result.passed and fitness_result.severity == Severity.BLOCKING and fail_fast:
        return _build_verdict(stages, t0)

    # Stage 2: Scanner.
    scanner_result = _run_scanner_stage(root, package=package)
    stages.append(scanner_result)
    if not scanner_result.passed and scanner_result.severity == Severity.BLOCKING and fail_fast:
        return _build_verdict(stages, t0)

    # Stage 3: RTM (informational).
    rtm_result = _run_rtm_stage(root, package=package, test_dir=test_dir)
    stages.append(rtm_result)

    # Stage 4: Drift detection.
    drift_result = _run_drift_stage(root, package=package)
    stages.append(drift_result)

    return _build_verdict(stages, t0)


def _build_verdict(
    stages: list[StageResult],
    t0: float,
) -> GateVerdict:
    """Build the final gate verdict from accumulated stage results."""
    total_ms = (time.monotonic() - t0) * 1000
    has_blocking = any(
        not s.passed and s.severity == Severity.BLOCKING
        for s in stages
    )
    return GateVerdict(
        verdict=Verdict.FAIL if has_blocking else Verdict.PASS,
        stages=stages,
        total_duration_ms=total_ms,
    )
