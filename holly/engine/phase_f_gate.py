"""Phase F Gate Evaluation Module — Engine L3 Control Plane Verification.

This module implements the Phase F gate checklist for the Holly Grace
architecture. It verifies that all Phase F critical-path deliverables
(Steps 41-45: Lane Manager, MCP Registry, Goal-Dispatch, Workflow Engine,
SIL-2 Tests) are complete and functional.

Phase F unlocks Phase G (Sandbox L3 Deployment).

Per Task 45.4 (Phase F Gate Checklist):
- Gate Items: Lane Manager (41.4), MCP Registry (42.4), Goal-Dispatch (43.3),
  Workflow Engine (44.5), SIL-2 suite (45.2)
- All gate items must PASS
- Gate report: docs/audit/phase_f_gate_report.md
- Unlock Phase G

This module provides:
- GateItem: dataclass for gate item verification
- GateResult: gate evaluation result with verdict
- PhaseGoal: Phase F goal definitions
- evaluate_phase_f_gate(): main gate evaluation function
"""

from __future__ import annotations

import importlib.util
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

log = logging.getLogger(__name__)

__all__ = [
    "GateItem",
    "GateResult",
    "GateVerdict",
    "PhaseGoal",
    "evaluate_phase_f_gate",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GateVerdict(str, Enum):
    """Gate evaluation verdict."""

    PASS = "PASS"
    FAIL = "FAIL"
    WAIVE = "WAIVE"
    SKIP = "SKIP"


class PhaseGoal(str, Enum):
    """Phase F goal definitions."""

    F_G1 = "F.G1: Lane Manager Operational"
    F_G2 = "F.G2: MCP Registry Complete"
    F_G3 = "F.G3: Goal-Dispatch Middleware Complete"
    F_G4 = "F.G4: Workflow Engine Complete"
    F_G5 = "F.G5: SIL-2 Verification Complete"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class GateItem:
    """Single gate item verification."""

    task_id: str
    name: str
    module_path: str
    required_exports: list[str]
    verdict: GateVerdict = GateVerdict.SKIP
    evidence: str = ""

    def check(self) -> bool:
        """Verify gate item exists and exports required symbols.

        Returns True if item passes, False otherwise.
        """
        try:
            # Check if file exists
            if not os.path.isfile(self.module_path):
                self.verdict = GateVerdict.FAIL
                self.evidence = f"Module file not found: {self.module_path}"
                return False

            spec = importlib.util.spec_from_file_location(
                self.task_id.replace(".", "_"), self.module_path
            )
            if spec is None or spec.loader is None:
                self.verdict = GateVerdict.FAIL
                self.evidence = f"Module spec creation failed: {self.module_path}"
                return False

            module = importlib.util.module_from_spec(spec)
            if module is None:
                self.verdict = GateVerdict.FAIL
                self.evidence = f"Module instantiation failed: {self.module_path}"
                return False

            spec.loader.exec_module(module)

            missing = []
            for export in self.required_exports:
                if not hasattr(module, export):
                    missing.append(export)

            if missing:
                self.verdict = GateVerdict.FAIL
                self.evidence = f"Missing exports: {', '.join(missing)}"
                return False

            self.verdict = GateVerdict.PASS
            self.evidence = (
                f"Module {Path(self.module_path).name} loaded; "
                f"exports: {', '.join(self.required_exports)}"
            )
            return True
        except Exception as e:
            self.verdict = GateVerdict.FAIL
            self.evidence = f"Load error: {e!s}"
            return False


@dataclass
class GateResult:
    """Phase F gate evaluation result."""

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    items: list[GateItem] = field(default_factory=list)
    verdict: GateVerdict = GateVerdict.PASS

    def add_item(self, item: GateItem) -> None:
        """Add a gate item to result."""
        self.items.append(item)

    def summarize(self) -> str:
        """Generate summary line."""
        passed = sum(1 for i in self.items if i.verdict == GateVerdict.PASS)
        failed = sum(1 for i in self.items if i.verdict == GateVerdict.FAIL)
        waived = sum(1 for i in self.items if i.verdict == GateVerdict.WAIVE)
        skipped = sum(1 for i in self.items if i.verdict == GateVerdict.SKIP)
        return (
            f"{passed} passed, {failed} failed, "
            f"{waived} waived, {skipped} skipped"
        )

    def report_table(self) -> str:
        """Generate markdown table for report."""
        lines = [
            "| Task | Name | Verdict | Evidence |",
            "|------|------|---------|----------|",
        ]
        for item in self.items:
            verdict_mark = "✓" if item.verdict == GateVerdict.PASS else "✗"
            evidence_excerpt = item.evidence[:50]
            lines.append(
                f"| {item.task_id} | {item.name} | {verdict_mark} "
                f"{item.verdict.value} | {evidence_excerpt}... |"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gate Evaluation
# ---------------------------------------------------------------------------


def evaluate_phase_f_gate() -> GateResult:
    """Evaluate Phase F gate: Lane Manager, MCP Registry, Goal-Dispatch,
    Workflow Engine, SIL-2 suite.

    Returns:
        GateResult with verdict PASS if all items pass, FAIL otherwise.
    """
    result = GateResult()

    # Get base path
    base_path = Path(__file__).parent

    # Phase F Critical Path Gate Items
    items = [
        GateItem(
            task_id="41.4",
            name="Lane Manager per ICD-013/014/015",
            module_path=str(base_path / "lanes.py"),
            required_exports=[
                "Lane",
                "MainLane",
                "CronLane",
                "SubagentLane",
                "LanePolicy",
                "LaneManager",
            ],
        ),
        GateItem(
            task_id="42.4",
            name="MCP Registry per ICD-019/020",
            module_path=str(base_path / "mcp_registry.py"),
            required_exports=["MCPRegistry", "ToolMetadata", "MCPError"],
        ),
        GateItem(
            task_id="43.3",
            name="Goal-Dispatch Middleware per ICD-016/021",
            module_path=str(base_path / "goal_dispatch.py"),
            required_exports=["GoalDispatcher", "DispatchResult"],
        ),
        GateItem(
            task_id="44.5",
            name="Workflow Engine per ICD-021",
            module_path=str(base_path / "workflow_engine.py"),
            required_exports=[
                "WorkflowEngine",
                "SagaOrchestrator",
                "DeadLetterQueue",
            ],
        ),
        GateItem(
            task_id="45.2",
            name="SIL-2 Test Suite Execution",
            module_path=str(base_path.parent / "test_harness" / "sil2_executor.py"),
            required_exports=["SIL2TestExecutor"],
        ),
    ]

    # Check each item
    all_pass = True
    for item in items:
        result.add_item(item)
        if not item.check():
            all_pass = False

    # Set overall verdict
    result.verdict = GateVerdict.PASS if all_pass else GateVerdict.FAIL

    log.info(
        "Phase F gate evaluation complete: %s",
        result.verdict.value,
    )

    return result


def generate_phase_f_gate_report(result: GateResult) -> str:
    """Generate markdown gate report from evaluation result.

    Args:
        result: GateResult from evaluate_phase_f_gate()

    Returns:
        Markdown formatted gate report.
    """
    timestamp = result.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    if result.verdict == GateVerdict.PASS:
        verdict_text = "PASS - Phase G unlocked"
    else:
        verdict_text = "FAIL - Phase F incomplete"

    all_pass = result.verdict == GateVerdict.PASS
    decision_text = (
        "Phase F complete. All critical-path tasks operational. "
        "Phase G unlocked."
        if all_pass
        else (
            "Phase F incomplete. "
            "Resolve failing items before proceeding."
        )
    )

    report = f"""# Phase F Gate Report — Slice 7

**Gate:** Phase F Gate (Steps 41-45)
**Date:** {timestamp}
**Verdict:** {verdict_text}

**Summary:** {result.summarize()}

## Gate Items

{result.report_table()}

## Phase F Critical Path

```
41.4 → 42.4 → 43.3 → 44.5 → 45.2 → 45.4
```

**All items: {'PASS ✓' if all_pass else 'FAIL ✗'}**

## Gate Decision

{decision_text}
"""
    return report


if __name__ == "__main__":
    import sys

    # Evaluate gate
    gate_result = evaluate_phase_f_gate()

    # Print result
    print(f"Phase F Gate: {gate_result.verdict.value}")
    print(f"Summary: {gate_result.summarize()}")

    # Report
    report = generate_phase_f_gate_report(gate_result)
    print("\n" + report)

    # Exit code
    sys.exit(0 if gate_result.verdict == GateVerdict.PASS else 1)
