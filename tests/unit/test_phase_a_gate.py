"""Unit tests for Phase A gate checklist.

Task 11.3 — Verify the Phase A gate evaluates all Slice 2 critical-path
tasks and produces the correct gate report.

Tests cover:
- All 10 gate items are evaluated
- Critical-path tasks produce PASS when done
- Missing tasks produce FAIL
- Auto-checked items (9.2, 10.2, 11.1, 11.3) use correct logic
- Self-referential 11.3 passes when audit is clean
- Report rendering produces correct markdown
- Live codebase gate report passes
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from holly.arch.gate_report import (
    evaluate_phase_a_gate,
    render_phase_a_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def _all_done_statuses() -> dict:
    """Return task_statuses with all Slice 2 critical-path tasks done."""
    return {
        "5.5": {"status": "done", "note": "49 ICD models"},
        "5.6": {"status": "done", "note": "49 ICDs in arch.yaml"},
        "5.8": {"status": "done", "note": "ICD Schema Registry"},
        "7.1": {"status": "done", "note": "AST scanner"},
        "7.2": {"status": "done", "note": "ICD-aware detection"},
        "8.3": {"status": "done", "note": "Contract fixtures"},
        "9.2": {"status": "done", "note": "Fitness functions (67 tests)"},
        "10.2": {"status": "done", "note": "RTM generator (30 tests)"},
        "11.1": {"status": "done", "note": "CI gate pipeline (28 tests)"},
        "11.3": {"status": "done", "note": "Phase A gate"},
    }


def _load_status_yaml() -> dict:
    """Load tasks from status.yaml, normalising keys to strings."""
    path = REPO_ROOT / "docs" / "status.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw = data.get("tasks", {})
    # YAML parses bare "5.5" as float 5.5 — normalise to str.
    return {str(k): v for k, v in raw.items()}


# ═══════════════════════════════════════════════════════════
# Gate item evaluation tests
# ═══════════════════════════════════════════════════════════


class TestGateItemCount:
    """Verify the gate evaluates all expected items."""

    def test_ten_items_evaluated(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert len(report.items) == 10

    def test_slice_id_is_2(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.slice_id == 2

    def test_gate_name(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert "Phase A" in report.gate_name


class TestAllPass:
    """Verify gate passes when all tasks are done."""

    def test_all_pass_verdict(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(
            statuses, test_count=1421, audit_pass=True, gate_pass=True,
        )
        assert report.all_pass is True
        assert report.failed == 0
        assert report.passed == 10

    def test_all_pass_no_waived(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(
            statuses, test_count=1421, audit_pass=True,
        )
        assert report.waived == 0


class TestFailures:
    """Verify gate fails when critical tasks are missing."""

    def test_missing_icd_models_fails(self) -> None:
        statuses = _all_done_statuses()
        statuses["5.5"] = "pending"
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.all_pass is False
        failed_ids = [i.task_id for i in report.items if i.verdict == "FAIL"]
        assert "5.5" in failed_ids

    def test_missing_scanner_fails(self) -> None:
        statuses = _all_done_statuses()
        statuses["7.1"] = "pending"
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.all_pass is False
        failed_ids = [i.task_id for i in report.items if i.verdict == "FAIL"]
        assert "7.1" in failed_ids

    def test_missing_fitness_fails(self) -> None:
        statuses = _all_done_statuses()
        statuses["9.2"] = "pending"
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.all_pass is False

    def test_missing_rtm_fails(self) -> None:
        statuses = _all_done_statuses()
        statuses["10.2"] = "pending"
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.all_pass is False

    def test_missing_ci_gate_fails(self) -> None:
        statuses = _all_done_statuses()
        statuses["11.1"] = "pending"
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert report.all_pass is False

    def test_all_missing_produces_10_failures(self) -> None:
        report = evaluate_phase_a_gate({}, test_count=0, audit_pass=False)
        assert report.failed == 10
        assert report.passed == 0


class TestAutoChecks:
    """Verify auto-checked items use correct logic."""

    def test_fitness_needs_tests(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=0, audit_pass=True)
        fitness = next(i for i in report.items if i.task_id == "9.2")
        assert fitness.verdict == "FAIL"

    def test_rtm_needs_tests(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=0, audit_pass=True)
        rtm = next(i for i in report.items if i.task_id == "10.2")
        assert rtm.verdict == "FAIL"

    def test_ci_gate_done_without_gate_pass(self) -> None:
        """CI gate marked done passes even without gate_pass flag."""
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(
            statuses, test_count=1421, audit_pass=True, gate_pass=False,
        )
        ci = next(i for i in report.items if i.task_id == "11.1")
        assert ci.verdict == "PASS"

    def test_ci_gate_with_gate_pass(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(
            statuses, test_count=1421, audit_pass=True, gate_pass=True,
        )
        ci = next(i for i in report.items if i.task_id == "11.1")
        assert ci.verdict == "PASS"
        assert "live codebase" in ci.evidence

    def test_self_referential_11_3_audit_clean(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        gate = next(i for i in report.items if i.task_id == "11.3")
        assert gate.verdict == "PASS"

    def test_self_referential_11_3_audit_dirty(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=False)
        gate = next(i for i in report.items if i.task_id == "11.3")
        assert gate.verdict == "FAIL"


# ═══════════════════════════════════════════════════════════
# Report rendering
# ═══════════════════════════════════════════════════════════


class TestReportRendering:
    """Verify report markdown output."""

    def test_pass_report_contains_verdict(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        md = render_phase_a_report(report)
        assert "Phase A Gate Report" in md
        assert "PASS" in md
        assert "Phase B unlocked" in md

    def test_fail_report_contains_blocked(self) -> None:
        report = evaluate_phase_a_gate({}, test_count=0, audit_pass=False)
        md = render_phase_a_report(report)
        assert "FAIL" in md
        assert "Phase B blocked" in md

    def test_report_contains_all_task_ids(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        md = render_phase_a_report(report)
        for tid in ["5.5", "5.6", "5.8", "7.1", "7.2", "8.3", "9.2", "10.2", "11.1", "11.3"]:
            assert tid in md

    def test_report_contains_table_header(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        md = render_phase_a_report(report)
        assert "| Task | Name | Verdict | Evidence |" in md

    def test_report_summary_line(self) -> None:
        statuses = _all_done_statuses()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        md = render_phase_a_report(report)
        assert "10 passed, 0 failed" in md


# ═══════════════════════════════════════════════════════════
# Live codebase tests
# ═══════════════════════════════════════════════════════════


class TestLiveCodebase:
    """Run the Phase A gate against actual status.yaml."""

    def test_gate_passes(self) -> None:
        """All Slice 2 critical-path tasks are done → gate passes."""
        statuses = _load_status_yaml()
        report = evaluate_phase_a_gate(
            statuses, test_count=1421, audit_pass=True, gate_pass=True,
        )
        if not report.all_pass:
            failed = [f"{i.task_id}: {i.evidence}" for i in report.items if i.verdict == "FAIL"]
            pytest.fail(
                "Phase A gate FAILED on live codebase:\n" + "\n".join(failed)
            )

    def test_ten_items_evaluated(self) -> None:
        statuses = _load_status_yaml()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        assert len(report.items) == 10

    def test_report_renders(self) -> None:
        statuses = _load_status_yaml()
        report = evaluate_phase_a_gate(statuses, test_count=1421, audit_pass=True)
        md = render_phase_a_report(report)
        assert "Phase A Gate Report" in md
        assert len(md) > 200
