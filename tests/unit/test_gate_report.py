"""Unit tests: Spiral gate report generator.

Task 3a.12 — Validate gate report evaluation logic and rendering.

Acceptance criteria:
  AC1: All items pass → report.all_pass is True
  AC2: Any FAIL → report.all_pass is False
  AC3: Non-critical pending tasks → WAIVED (not FAIL)
  AC4: Critical pending tasks → FAIL
  AC5: Report renders valid markdown with correct structure
  AC6: Auto-checked tasks use test_count and audit_pass
"""

from __future__ import annotations

from holly.arch.gate_report import (
    GateItem,
    GateReport,
    evaluate_gate,
    render_report,
)

# ── GateReport dataclass tests ──────────────────────────────────


class TestGateReport:
    """GateReport property calculations."""

    def test_empty_report_all_pass(self) -> None:
        r = GateReport(slice_id=1, gate_name="test", date="2026-01-01")
        assert r.all_pass is True
        assert r.passed == 0
        assert r.failed == 0

    def test_all_pass_verdicts(self) -> None:
        r = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("a", "A", "ac", "PASS"),
            GateItem("b", "B", "ac", "PASS"),
        ])
        assert r.all_pass is True
        assert r.passed == 2

    def test_one_fail_blocks(self) -> None:
        r = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("a", "A", "ac", "PASS"),
            GateItem("b", "B", "ac", "FAIL"),
        ])
        assert r.all_pass is False
        assert r.failed == 1

    def test_waived_does_not_block(self) -> None:
        r = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("a", "A", "ac", "PASS"),
            GateItem("b", "B", "ac", "WAIVED"),
        ])
        assert r.all_pass is True
        assert r.waived == 1

    def test_skip_does_not_block(self) -> None:
        r = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("a", "A", "ac", "PASS"),
            GateItem("b", "B", "ac", "SKIP"),
        ])
        assert r.all_pass is True
        assert r.skipped == 1


# ── evaluate_gate tests ─────────────────────────────────────────


class TestEvaluateGate:
    """Gate evaluation logic."""

    def _all_done_statuses(self) -> dict[str, dict[str, str]]:
        """Return statuses where all 3a.* tasks are done."""
        return {
            f"3a.{i}": {"status": "done", "note": f"Task 3a.{i} done"}
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        }

    def test_all_done_all_pass(self) -> None:
        """AC1: All tasks done + tests + audit → all pass."""
        statuses = self._all_done_statuses()
        report = evaluate_gate(statuses, test_count=302, audit_pass=True)
        assert report.all_pass is True
        assert report.failed == 0

    def test_critical_task_missing_fails(self) -> None:
        """AC4: Critical-path task not done → FAIL."""
        statuses = self._all_done_statuses()
        statuses["3a.8"] = {"status": "pending", "note": ""}
        report = evaluate_gate(statuses, test_count=302, audit_pass=True)
        assert report.all_pass is False
        fail_ids = [i.task_id for i in report.items if i.verdict == "FAIL"]
        assert "3a.8" in fail_ids

    def test_non_critical_pending_is_waived(self) -> None:
        """AC3: Non-critical pending → WAIVED, not FAIL."""
        # Only critical tasks done, non-critical pending
        statuses: dict[str, dict[str, str]] = {}
        for task_id in ["3a.8", "3a.10", "3a.12"]:
            statuses[task_id] = {"status": "done", "note": "done"}
        # All others are absent → pending
        report = evaluate_gate(statuses, test_count=302, audit_pass=True)
        for item in report.items:
            if item.task_id in {"3a.1", "3a.2", "3a.3", "3a.4", "3a.5",
                                "3a.6", "3a.7", "3a.9", "3a.11"}:
                assert item.verdict == "WAIVED", f"{item.task_id} should be WAIVED"

    def test_audit_fail_causes_gate_fail(self) -> None:
        """AC6: audit_pass=False → 3a.12 auto-check FAIL."""
        statuses = self._all_done_statuses()
        report = evaluate_gate(statuses, test_count=302, audit_pass=False)
        gate_item = next(i for i in report.items if i.task_id == "3a.12")
        assert gate_item.verdict == "FAIL"

    def test_zero_test_count_fails_auto_tasks(self) -> None:
        """AC6: test_count=0 → auto-checked tasks FAIL."""
        statuses = self._all_done_statuses()
        report = evaluate_gate(statuses, test_count=0, audit_pass=True)
        k8_item = next(i for i in report.items if i.task_id == "3a.10")
        assert k8_item.verdict == "FAIL"

    def test_report_has_12_items(self) -> None:
        """All 12 gate items are evaluated."""
        statuses = self._all_done_statuses()
        report = evaluate_gate(statuses, test_count=302, audit_pass=True)
        assert len(report.items) == 12

    def test_report_metadata(self) -> None:
        """Report has correct metadata."""
        statuses = self._all_done_statuses()
        report = evaluate_gate(statuses, test_count=302, audit_pass=True)
        assert report.slice_id == 1
        assert report.gate_name == "Step 3a Spiral Gate"


# ── render_report tests ──────────────────────────────────────────


class TestRenderReport:
    """Report rendering to markdown."""

    def test_pass_report_contains_unlocked(self) -> None:
        """AC5: Passing report says Slice 2 unlocked."""
        report = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("3a.1", "A", "ac", "PASS", "evidence"),
        ])
        md = render_report(report)
        assert "PASS" in md
        assert "Slice 2 unlocked" in md

    def test_fail_report_contains_blocked(self) -> None:
        """AC5: Failing report says Slice 2 blocked."""
        report = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("3a.1", "A", "ac", "FAIL", "not done"),
        ])
        md = render_report(report)
        assert "FAIL" in md
        assert "Slice 2 blocked" in md

    def test_report_has_table(self) -> None:
        """AC5: Report contains a markdown table."""
        report = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("3a.1", "Task A", "ac1", "PASS", "evidence A"),
        ])
        md = render_report(report)
        assert "| Task | Name | Verdict | Evidence |" in md
        assert "3a.1" in md
        assert "Task A" in md

    def test_waived_section_rendered(self) -> None:
        """AC5: Waived items get a rationale section."""
        report = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("3a.1", "A", "ac", "WAIVED", "deferred"),
        ])
        md = render_report(report)
        assert "Waived Items Rationale" in md
        assert "deferred" in md

    def test_no_waived_section_when_none(self) -> None:
        """AC5: No waived section when all pass."""
        report = GateReport(slice_id=1, gate_name="test", date="2026-01-01", items=[
            GateItem("3a.1", "A", "ac", "PASS", "ok"),
        ])
        md = render_report(report)
        assert "Waived Items Rationale" not in md
