"""Task dependency graph and duration estimation for Gantt generation.

Dependencies are derived from three sources:
1. Critical path chains (explicit linear ordering per slice)
2. Step-internal ordering (tasks within the same step are sequential by ID)
3. Inter-slice gates (slice N+1 depends on slice N's gate task)

Duration estimation uses an MP-based model:
- MP column encodes the methodology principle (1-14)
- SIL level of the slice applies a rigor multiplier
- Verification method column modulates effort
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from holly.arch.manifest_parser import Manifest, TaskEntry

# ── Duration estimation model ────────────────────────────────

# Base hours per methodology principle (MP).
# MP8 = arch-as-code (implementation), MP7 = TLA+ (formal), etc.
MP_BASE_HOURS: dict[str, float] = {
    "1": 1.0,    # Ontological — review/mapping
    "2": 1.0,    # Arch description — review/mapping
    "3": 1.0,    # Quality — ADR/review
    "4": 1.0,    # Lifecycle — process assignment
    "5": 2.0,    # SIL — designation + verification
    "6": 3.0,    # FMEA — failure analysis
    "7": 8.0,    # TLA+ — formal specification + model check
    "8": 4.0,    # Arch-as-code — implementation
    "9": 2.0,    # Traceability chain — linking + CI check
    "10": 4.0,   # EDDOps — eval infrastructure
    "11": 3.0,   # Constitution — predicate implementation
    "12": 4.0,   # Defense-in-depth — security implementation
    "13": 2.0,   # Spiral — gate ceremony
    "14": 2.0,   # Deploy — operational
}

# SIL multiplier: higher SIL = more rigorous verification
SIL_MULTIPLIER: dict[int, float] = {
    1: 1.0,
    2: 1.2,
    3: 1.5,
}

# Verification method effort modifier
VERIFICATION_EFFORT: dict[str, float] = {
    "review": 0.8,
    "integration test": 1.0,
    "property-based test": 1.3,
    "model check": 1.5,
    "ci check": 0.9,
    "test": 1.0,
    "report": 0.7,
    "demonstration": 0.8,
}

# Slice → SIL mapping (from README task manifest summary)
SLICE_SIL: dict[int, int] = {
    1: 3, 2: 2, 3: 3, 4: 2, 5: 3,
    6: 2, 7: 2, 8: 3, 9: 2, 10: 2,
    11: 2, 12: 2, 13: 1, 14: 1, 15: 3,
}


def estimate_duration_hours(task: TaskEntry, sil: int = 2) -> float:
    """Estimate task duration in hours based on MP, SIL, and task characteristics.

    Returns a float representing estimated hours. Minimum 0.5h, maximum 16h.
    """
    base = MP_BASE_HOURS.get(task.mp, 2.0)
    sil_mult = SIL_MULTIPLIER.get(sil, 1.0)
    hours = base * sil_mult
    return max(0.5, min(16.0, round(hours * 2) / 2))  # round to 0.5h


def estimate_duration_days(task: TaskEntry, sil: int = 2) -> str:
    """Estimate task duration as a mermaid-compatible duration string.

    Converts hours to working days (8h/day). Minimum 0.5d (half day).
    Returns format like '1d', '2d', '0.5d'.
    """
    hours = estimate_duration_hours(task, sil)
    days = hours / 8.0
    # Round to nearest 0.5d, minimum 0.5d
    days = max(0.5, round(days * 2) / 2)
    if days == int(days):
        return f"{int(days)}d"
    return f"{days:.1f}d"


# ── Dependency graph ─────────────────────────────────────────

@dataclass
class DependencyGraph:
    """Task dependency DAG derived from manifest structure."""

    # task_id → list of predecessor task_ids
    predecessors: dict[str, list[str]] = field(default_factory=dict)
    # task_id → estimated duration string (mermaid format)
    durations: dict[str, str] = field(default_factory=dict)

    def deps_of(self, task_id: str) -> list[str]:
        """Return predecessor task IDs for a given task."""
        return self.predecessors.get(task_id, [])

    def has_deps(self, task_id: str) -> bool:
        return bool(self.predecessors.get(task_id))


def _task_id_sort_key(task_id: str) -> tuple[str, int]:
    """Sort key for task IDs like '1.5', '3a.8'."""
    m = re.match(r"(\d+a?)\.(\d+)", task_id)
    if m:
        return (m.group(1), int(m.group(2)))
    return (task_id, 0)


def build_dependency_graph(manifest: Manifest) -> DependencyGraph:
    """Build a dependency graph from the manifest.

    Dependency sources (in priority order):
    1. Critical path chains — explicit `A → B` means B depends on A
    2. Step-internal ordering — within each step, tasks are sequential by ID
       (task N.2 depends on N.1, etc.)
    3. Inter-slice gates — each slice's last critical-path task gates the next slice

    This produces a DAG where each task has at most a few predecessors.
    """
    graph = DependencyGraph()
    all_task_ids = set(manifest.tasks.keys())

    # Source 1: Critical path chains — strongest signal
    crit_edges: dict[str, set[str]] = {tid: set() for tid in all_task_ids}

    for sl in manifest.slices:
        if len(sl.critical_path) >= 2:
            for i in range(1, len(sl.critical_path)):
                pred = sl.critical_path[i - 1]
                succ = sl.critical_path[i]
                if succ in crit_edges:
                    crit_edges[succ].add(pred)

    # Source 2: Step-internal sequential ordering
    step_edges: dict[str, set[str]] = {tid: set() for tid in all_task_ids}

    for sl in manifest.slices:
        for step in sl.steps:
            sorted_tasks = sorted(step.tasks, key=lambda t: t.sort_key)
            for i in range(1, len(sorted_tasks)):
                pred_id = sorted_tasks[i - 1].task_id
                succ_id = sorted_tasks[i].task_id
                # Only add step-internal deps if not already covered by critical path
                if pred_id not in crit_edges.get(succ_id, set()):
                    step_edges[succ_id].add(pred_id)

    # Source 3: Inter-slice gates — last critical-path task of slice N
    # gates the first critical-path task of slice N+1
    gate_edges: dict[str, set[str]] = {tid: set() for tid in all_task_ids}

    sorted_slices = sorted(manifest.slices, key=lambda s: s.slice_num)
    for i in range(1, len(sorted_slices)):
        prev_sl = sorted_slices[i - 1]
        curr_sl = sorted_slices[i]
        if prev_sl.critical_path and curr_sl.critical_path:
            gate_task = prev_sl.critical_path[-1]
            entry_task = curr_sl.critical_path[0]
            if entry_task in gate_edges:
                gate_edges[entry_task].add(gate_task)

    # Merge all dependency sources
    for tid in all_task_ids:
        deps: list[str] = []
        # Critical path deps first (highest priority)
        deps.extend(sorted(crit_edges.get(tid, set()), key=_task_id_sort_key))
        # Step-internal deps (only if not redundant with critical path)
        for step_dep in sorted(step_edges.get(tid, set()), key=_task_id_sort_key):
            if step_dep not in crit_edges.get(tid, set()):
                deps.append(step_dep)
        # Inter-slice gate deps
        for gate_dep in sorted(gate_edges.get(tid, set()), key=_task_id_sort_key):
            if gate_dep not in crit_edges.get(tid, set()):
                deps.append(gate_dep)

        if deps:
            graph.predecessors[tid] = deps

    # Estimate durations
    for tid, task in manifest.tasks.items():
        sil = SLICE_SIL.get(task.slice_num, 2)
        graph.durations[tid] = estimate_duration_days(task, sil)

    return graph
