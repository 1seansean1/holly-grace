"""Integration tests for unified CI gate.

Task 11.1 — Verify the CI gate pipeline integrates fitness, scanner,
RTM, and drift stages correctly.

Tests cover:
- Individual stage execution
- Ordered pipeline execution
- Fail-fast behaviour
- Blocking vs informational severity
- Gate verdict aggregation
- Summary report generation
- Live codebase pass
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from holly.arch.ci_gate import (
    GateVerdict,
    Severity,
    StageKind,
    StageResult,
    Verdict,
    _run_drift_stage,
    _run_fitness_stage,
    _run_rtm_stage,
    _run_scanner_stage,
    run_gate,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ═══════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════


def _write_module(root: Path, dotted: str, source: str) -> None:
    """Write a Python file at the path implied by *dotted*."""
    parts = dotted.split(".")
    folder = root.joinpath(*parts[:-1])
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(1, len(parts)):
        init = root.joinpath(*parts[:i]) / "__init__.py"
        if not init.exists():
            init.write_text("")
    (folder / f"{parts[-1]}.py").write_text(textwrap.dedent(source))


# ═══════════════════════════════════════════════════════════
# StageResult and GateVerdict data models
# ═══════════════════════════════════════════════════════════


class TestStageResult:
    """Test StageResult data model."""

    def test_pass_label(self) -> None:
        r = StageResult(stage=StageKind.FITNESS, passed=True, severity=Severity.BLOCKING)
        assert r.status_label == "PASS"

    def test_fail_label(self) -> None:
        r = StageResult(stage=StageKind.FITNESS, passed=False, severity=Severity.BLOCKING)
        assert r.status_label == "FAIL"

    def test_warn_label(self) -> None:
        r = StageResult(stage=StageKind.DRIFT, passed=False, severity=Severity.WARNING)
        assert r.status_label == "WARN"

    def test_info_label(self) -> None:
        r = StageResult(stage=StageKind.RTM, passed=False, severity=Severity.INFO)
        assert r.status_label == "INFO"


class TestGateVerdict:
    """Test GateVerdict data model."""

    def test_pass_verdict(self) -> None:
        v = GateVerdict(verdict=Verdict.PASS)
        assert v.passed is True

    def test_fail_verdict(self) -> None:
        v = GateVerdict(verdict=Verdict.FAIL)
        assert v.passed is False

    def test_blocking_failures(self) -> None:
        v = GateVerdict(
            verdict=Verdict.FAIL,
            stages=[
                StageResult(stage=StageKind.FITNESS, passed=False, severity=Severity.BLOCKING, message="bad"),
                StageResult(stage=StageKind.RTM, passed=True, severity=Severity.INFO),
            ],
        )
        assert len(v.blocking_failures) == 1
        assert v.blocking_failures[0].stage == StageKind.FITNESS

    def test_warnings(self) -> None:
        v = GateVerdict(
            verdict=Verdict.PASS,
            stages=[
                StageResult(stage=StageKind.DRIFT, passed=False, severity=Severity.WARNING, message="stale"),
            ],
        )
        assert len(v.warnings) == 1

    def test_summary_contains_verdict(self) -> None:
        v = GateVerdict(
            verdict=Verdict.PASS,
            stages=[
                StageResult(stage=StageKind.FITNESS, passed=True, severity=Severity.BLOCKING, message="ok"),
            ],
        )
        summary = v.summary()
        assert "PASS" in summary
        assert "fitness" in summary


# ═══════════════════════════════════════════════════════════
# Individual stage tests (synthetic)
# ═══════════════════════════════════════════════════════════


class TestFitnessStage:
    """Test fitness stage on synthetic trees."""

    def test_clean_tree_passes(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        result = _run_fitness_stage(tmp_path, package="holly")
        assert result.passed is True
        assert result.stage == StageKind.FITNESS
        assert result.severity == Severity.BLOCKING
        assert result.duration_ms >= 0

    def test_violation_fails(self, tmp_path: Path) -> None:
        """L1 importing L3 → fitness failure."""
        _write_module(tmp_path, "holly.kernel.k1", "from holly.engine.pipe import P\n")
        _write_module(tmp_path, "holly.engine.pipe", "P = 1\n")
        result = _run_fitness_stage(tmp_path, package="holly")
        assert result.passed is False
        assert "failed" in result.message.lower()


class TestScannerStage:
    """Test scanner stage."""

    def test_runs_without_error(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        result = _run_scanner_stage(tmp_path, package="holly")
        assert result.stage == StageKind.SCANNER
        assert result.duration_ms >= 0


class TestRTMStage:
    """Test RTM stage."""

    def test_runs_without_error(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("")
        (test_dir / "test_k1.py").write_text("def test_ok(): pass\n")
        result = _run_rtm_stage(tmp_path, package="holly", test_dir="tests")
        assert result.passed is True  # Always informational.
        assert result.stage == StageKind.RTM
        assert result.severity == Severity.INFO

    def test_message_contains_coverage(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        result = _run_rtm_stage(tmp_path, package="holly")
        assert "RTM" in result.message
        assert "coverage" in result.message.lower()


class TestDriftStage:
    """Test drift stage (stub)."""

    def test_runs_without_error(self, tmp_path: Path) -> None:
        result = _run_drift_stage(tmp_path, package="holly")
        assert result.stage == StageKind.DRIFT
        assert result.passed is True
        assert result.duration_ms >= 0

    def test_no_arch_yaml_returns_info(self, tmp_path: Path) -> None:
        """Without architecture.yaml at root, drift returns INFO (not WARNING).

        Guards against the singleton binding to the workspace registry instead
        of the target repo; tmp_path has no docs/architecture.yaml.
        """
        result = _run_drift_stage(tmp_path)
        assert result.severity == Severity.INFO
        assert result.passed is True
        assert "architecture.yaml" in result.message
        assert "48 components" not in result.message  # must NOT read workspace registry


# ═══════════════════════════════════════════════════════════
# Pipeline tests (synthetic)
# ═══════════════════════════════════════════════════════════


class TestRunGate:
    """Test the full gate pipeline."""

    def test_clean_tree_passes(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("")
        verdict = run_gate(tmp_path, package="holly", test_dir="tests")
        assert verdict.passed is True
        assert verdict.verdict == Verdict.PASS
        assert len(verdict.stages) == 4  # fitness, scanner, rtm, drift

    def test_four_stages_in_order(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        verdict = run_gate(tmp_path, package="holly")
        stage_kinds = [s.stage for s in verdict.stages]
        assert stage_kinds == [
            StageKind.FITNESS,
            StageKind.SCANNER,
            StageKind.RTM,
            StageKind.DRIFT,
        ]

    def test_fail_fast_stops_early(self, tmp_path: Path) -> None:
        """Layer violation → fail_fast stops after fitness stage."""
        _write_module(tmp_path, "holly.kernel.k1", "from holly.engine.pipe import P\n")
        _write_module(tmp_path, "holly.engine.pipe", "P = 1\n")
        verdict = run_gate(tmp_path, package="holly", fail_fast=True)
        assert verdict.passed is False
        # Should stop after fitness (stage 1).
        assert len(verdict.stages) == 1
        assert verdict.stages[0].stage == StageKind.FITNESS

    def test_no_fail_fast_runs_all(self, tmp_path: Path) -> None:
        """With fail_fast=False, all stages run even on failure."""
        _write_module(tmp_path, "holly.kernel.k1", "from holly.engine.pipe import P\n")
        _write_module(tmp_path, "holly.engine.pipe", "P = 1\n")
        verdict = run_gate(tmp_path, package="holly", fail_fast=False)
        assert verdict.passed is False
        assert len(verdict.stages) == 4  # All stages ran.

    def test_total_duration_positive(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        verdict = run_gate(tmp_path, package="holly")
        assert verdict.total_duration_ms > 0

    def test_summary_report(self, tmp_path: Path) -> None:
        _write_module(tmp_path, "holly.kernel.k1", "x = 1\n")
        verdict = run_gate(tmp_path, package="holly")
        summary = verdict.summary()
        assert "CI Gate Verdict" in summary
        assert "PASS" in summary


# ═══════════════════════════════════════════════════════════
# Live codebase tests
# ═══════════════════════════════════════════════════════════


class TestLiveCodebase:
    """Run the full CI gate against the actual Holly codebase."""

    def test_gate_passes(self) -> None:
        """The full gate pipeline passes on the live codebase."""
        verdict = run_gate(REPO_ROOT, package="holly", test_dir="tests")
        if not verdict.passed:
            pytest.fail(
                f"CI gate FAILED on live codebase:\n{verdict.summary()}"
            )

    def test_all_four_stages_run(self) -> None:
        """All four stages execute on the live codebase."""
        verdict = run_gate(REPO_ROOT, package="holly", test_dir="tests")
        assert len(verdict.stages) == 4

    def test_fitness_stage_passes(self) -> None:
        """Fitness functions pass on the live codebase."""
        result = _run_fitness_stage(REPO_ROOT, package="holly")
        assert result.passed is True

    def test_rtm_stage_informational(self) -> None:
        """RTM stage produces an informational result."""
        result = _run_rtm_stage(REPO_ROOT, package="holly", test_dir="tests")
        assert result.passed is True
        assert result.severity == Severity.INFO

    def test_drift_stage_loads_arch(self) -> None:
        """Drift stub loads architecture.yaml."""
        result = _run_drift_stage(REPO_ROOT, package="holly")
        assert "48 components" in result.message

    def test_summary_generated(self) -> None:
        """Gate summary report is non-empty."""
        verdict = run_gate(REPO_ROOT, package="holly", test_dir="tests")
        summary = verdict.summary()
        assert "CI Gate Verdict" in summary
        assert len(summary) > 100
