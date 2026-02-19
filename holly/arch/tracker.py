"""Development status tracker: merges Task Manifest + status.yaml → mermaid Gantt.

The status.yaml file is the single source of truth for task completion status.
The Task_Manifest.md provides structure (slices, steps, critical paths, names).
This module merges both and emits a mermaid Gantt chart.

Status lifecycle: pending → active → done | blocked
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    from strenum import StrEnum  # type: ignore[no-redef]
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

from holly.arch.dependencies import DependencyGraph, build_dependency_graph
from holly.arch.gantt_validator import validate_gantt
from holly.arch.manifest_parser import Manifest, parse_manifest_file


class TaskStatus(StrEnum):
    """Task completion status."""

    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class TaskState:
    """Runtime state for a single task."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    commit: str = ""
    date_completed: str = ""
    note: str = ""


@dataclass
class StatusRegistry:
    """Merged view of manifest structure + task states."""

    manifest: Manifest
    states: dict[str, TaskState] = field(default_factory=dict)

    def state_of(self, task_id: str) -> TaskState:
        return self.states.get(task_id, TaskState(task_id=task_id))

    def slice_progress(self, slice_num: int) -> tuple[int, int]:
        """Return (done_count, total_count) for a slice."""
        tasks = self.manifest.tasks_in_slice(slice_num)
        done = sum(1 for t in tasks if self.state_of(t.task_id).status == TaskStatus.DONE)
        return done, len(tasks)

    def overall_progress(self) -> tuple[int, int]:
        """Return (done_count, total_count) overall.

        Only counts tasks that exist in the manifest to prevent phantom
        task IDs in status.yaml from inflating done count beyond total.
        """
        manifest_ids = set(self.manifest.tasks.keys())
        done = sum(
            1
            for tid, s in self.states.items()
            if s.status == TaskStatus.DONE and tid in manifest_ids
        )
        return done, self.manifest.total_tasks

    @property
    def summary_lines(self) -> list[str]:
        """One-line summary per slice."""
        lines: list[str] = []
        for sl in self.manifest.slices:
            done, total = self.slice_progress(sl.slice_num)
            pct = (done / total * 100) if total else 0
            bar = _progress_bar(done, total)
            lines.append(f"Slice {sl.slice_num:>2} {bar} {done:>3}/{total:<3} ({pct:5.1f}%) {sl.title}")
        done_all, total_all = self.overall_progress()
        pct_all = (done_all / total_all * 100) if total_all else 0
        lines.append(f"{'TOTAL':>8} {_progress_bar(done_all, total_all)} {done_all:>3}/{total_all:<3} ({pct_all:5.1f}%)")
        return lines


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    """ASCII progress bar."""
    if total == 0:
        return "[" + " " * width + "]"
    filled = int(width * done / total)
    return "[" + "#" * filled + "." * (width - filled) + "]"


# ── status.yaml I/O ─────────────────────────────────────────

def load_status(path: Path) -> dict[str, TaskState]:
    """Load docs/status.yaml into a dict of TaskState."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        logging.getLogger(__name__).warning(
            "status.yaml is malformed YAML — returning empty status",
        )
        return {}
    if not isinstance(data, dict):
        return {}
    tasks_raw = data.get("tasks", {})
    if not isinstance(tasks_raw, dict):
        logging.getLogger(__name__).warning(
            "status.yaml 'tasks' is %s, expected dict — returning empty",
            type(tasks_raw).__name__,
        )
        return {}
    states: dict[str, TaskState] = {}
    _log = logging.getLogger(__name__)
    for task_id, info in tasks_raw.items():
        tid = str(task_id)
        try:
            if isinstance(info, str):
                states[tid] = TaskState(task_id=tid, status=TaskStatus(info))
            elif isinstance(info, dict):
                states[tid] = TaskState(
                    task_id=tid,
                    status=TaskStatus(info.get("status", "pending")),
                    commit=str(info.get("commit", "")),
                    date_completed=str(info.get("date", "")),
                    note=str(info.get("note", "")),
                )
        except ValueError:
            raw = info if isinstance(info, str) else info.get("status", info)
            _log.warning("Unknown status %r for task %s — defaulting to pending", raw, tid)
            states[tid] = TaskState(task_id=tid, status=TaskStatus.PENDING)
    return states


def save_status(states: dict[str, TaskState], path: Path) -> None:
    """Write status.yaml from task states."""
    tasks_out: dict[str, Any] = {}
    for tid in sorted(states.keys(), key=_task_sort_key):
        s = states[tid]
        if s.status == TaskStatus.PENDING and not s.note:
            tasks_out[tid] = s.status.value
        else:
            entry: dict[str, str] = {"status": s.status.value}
            if s.commit:
                entry["commit"] = s.commit
            if s.date_completed:
                entry["date"] = s.date_completed
            if s.note:
                entry["note"] = s.note
            tasks_out[tid] = entry

    data = {
        "version": "1.0",
        "generated": date.today().isoformat(),
        "tasks": tasks_out,
    }
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _task_sort_key(task_id: str) -> tuple[str, int]:
    """Sort key for task IDs like '1.5', '3a.8'."""
    m = re.match(r"(\d+a?)\.(\d+)", task_id)
    if m:
        return (m.group(1), int(m.group(2)))
    return (task_id, 0)


# ── Gantt generation ─────────────────────────────────────────

def _mermaid_safe(text: str) -> str:
    """Escape text for mermaid labels.

    Rules:
    - Replace colons (mermaid delimiter) with dashes
    - Replace quotes with single quotes
    - Normalize unicode arrows to ASCII
    - Truncate to 60 chars at word boundary to avoid broken labels
    """
    text = text.replace('"', "'").replace(":", " -")
    # Normalize unicode arrows/dashes to ASCII equivalents
    text = text.replace("→", "->").replace("←", "<-").replace("↔", "<->")
    text = text.replace("\u21d2", "=>").replace("\u2014", "-").replace("\u2013", "-")
    # Normalize comparison/math operators that break cp1252 consoles
    text = text.replace("\u2265", ">=").replace("\u2264", "<=").replace("\u2260", "!=")
    # Truncate at word boundary
    if len(text) > 60:
        truncated = text[:57]
        # Find last space to avoid mid-word cut
        last_space = truncated.rfind(" ")
        if last_space > 40:
            truncated = truncated[:last_space]
        text = truncated
    return text


def _task_gantt_status(state: TaskState, is_critical: bool) -> str:
    """Map task state to mermaid Gantt status tag."""
    if state.status == TaskStatus.DONE:
        return "done, "
    if state.status == TaskStatus.ACTIVE:
        return "active, "
    if is_critical:
        return "crit, "
    return ""


def generate_gantt(
    registry: StatusRegistry,
    dep_graph: DependencyGraph | None = None,
) -> str:
    """Generate mermaid Gantt chart from status registry.

    If dep_graph is provided, uses `after` syntax for dependencies and
    estimated durations. Otherwise falls back to date-based placeholders.
    """
    lines: list[str] = []
    lines.append("gantt")
    lines.append("    title Holly Grace - Development Progress")
    lines.append("    dateFormat YYYY-MM-DD")
    lines.append("    axisFormat %b %d")
    lines.append("    excludes weekends")
    lines.append("")

    today = date.today().isoformat()

    for sl in registry.manifest.slices:
        done, total = registry.slice_progress(sl.slice_num)
        pct = int(done / total * 100) if total else 0
        lines.append(f"    section Slice {sl.slice_num} ({pct}%)")

        crit_set = set(sl.critical_path)
        tasks = registry.manifest.tasks_in_slice(sl.slice_num)

        for task in tasks:
            state = registry.state_of(task.task_id)
            is_crit = task.task_id in crit_set
            status_tag = _task_gantt_status(state, is_crit)
            label = _mermaid_safe(f"{task.task_id} {task.name}")
            task_alias = f"t{task.task_id.replace('.', '_')}"
            duration = dep_graph.durations.get(task.task_id, "1d") if dep_graph else "1d"

            if state.status == TaskStatus.DONE and state.date_completed:
                lines.append(
                    f"    {label} :{status_tag}{task_alias}, {state.date_completed}, {duration}"
                )
            elif dep_graph and dep_graph.has_deps(task.task_id):
                # Mermaid Gantt only supports `after <single_id>`.
                # Use the last dependency (latest-finishing in topo order).
                deps = dep_graph.deps_of(task.task_id)
                last_dep_alias = f"t{deps[-1].replace('.', '_')}"
                lines.append(
                    f"    {label} :{status_tag}{task_alias}, after {last_dep_alias}, {duration}"
                )
            else:
                lines.append(
                    f"    {label} :{status_tag}{task_alias}, {today}, {duration}"
                )

    lines.append("")
    return "\n".join(lines)


def generate_gantt_critical_only(
    registry: StatusRegistry,
    dep_graph: DependencyGraph | None = None,
) -> str:
    """Generate a compact Gantt showing only critical-path tasks per slice.

    Unlike the full Gantt, this only emits critical-path tasks. Therefore
    `after` references must be filtered to only include aliases that are
    actually emitted in this chart (otherwise mermaid silently fails).
    """
    lines: list[str] = []
    lines.append("gantt")
    lines.append("    title Holly Grace - Critical Path Progress")
    lines.append("    dateFormat YYYY-MM-DD")
    lines.append("    axisFormat %b %d")
    lines.append("    excludes weekends")
    lines.append("")

    today = date.today().isoformat()

    # Collect the set of all task IDs that will appear in this chart
    emitted_ids: set[str] = set()
    for sl in registry.manifest.slices:
        emitted_ids.update(sl.critical_path)

    for sl in registry.manifest.slices:
        if not sl.critical_path:
            continue
        done_crit = sum(
            1 for tid in sl.critical_path
            if registry.state_of(tid).status == TaskStatus.DONE
        )
        total_crit = len(sl.critical_path)
        pct = int(done_crit / total_crit * 100) if total_crit else 0
        lines.append(f"    section Slice {sl.slice_num} ({pct}%)")

        for task_id in sl.critical_path:
            task = registry.manifest.tasks.get(task_id)
            if not task:
                continue
            state = registry.state_of(task_id)
            status_tag = _task_gantt_status(state, is_critical=True)
            label = _mermaid_safe(f"{task.task_id} {task.name}")
            task_alias = f"t{task.task_id.replace('.', '_')}"
            duration = dep_graph.durations.get(task_id, "1d") if dep_graph else "1d"

            if state.status == TaskStatus.DONE and state.date_completed:
                lines.append(
                    f"    {label} :{status_tag}{task_alias}, {state.date_completed}, {duration}"
                )
            elif dep_graph and dep_graph.has_deps(task_id):
                # FILTER: only reference aliases that are emitted in this chart
                valid_deps = [
                    d for d in dep_graph.deps_of(task_id)
                    if d in emitted_ids
                ]
                if valid_deps:
                    # Mermaid Gantt only supports `after <single_id>`.
                    last_dep_alias = f"t{valid_deps[-1].replace('.', '_')}"
                    lines.append(
                        f"    {label} :{status_tag}{task_alias}, after {last_dep_alias}, {duration}"
                    )
                else:
                    lines.append(
                        f"    {label} :{status_tag}{task_alias}, {today}, {duration}"
                    )
            else:
                lines.append(
                    f"    {label} :{status_tag}{task_alias}, {today}, {duration}"
                )

    lines.append("")
    return "\n".join(lines)


def generate_summary_table(registry: StatusRegistry) -> str:
    """Generate markdown summary table."""
    lines: list[str] = []
    lines.append("| Slice | Phase | Done | Total | Progress | Critical Path |")
    lines.append("|------:|-------|-----:|------:|---------:|---------------|")

    for sl in registry.manifest.slices:
        done, total = registry.slice_progress(sl.slice_num)
        pct = int(done / total * 100) if total else 0
        bar = _progress_bar(done, total, width=10)

        crit_done = sum(
            1 for tid in sl.critical_path
            if registry.state_of(tid).status == TaskStatus.DONE
        )
        crit_total = len(sl.critical_path)
        crit_str = f"{crit_done}/{crit_total}" if crit_total else "—"

        lines.append(
            f"| {sl.slice_num} | {sl.title[:40]} | {done} | {total} | {pct}% {bar} | {crit_str} |"
        )

    done_all, total_all = registry.overall_progress()
    pct_all = int(done_all / total_all * 100) if total_all else 0
    lines.append(
        f"| **Σ** | **All** | **{done_all}** | **{total_all}** | **{pct_all}%** | |"
    )
    return "\n".join(lines)


def generate_task_detail_table(
    registry: StatusRegistry,
    dep_graph: DependencyGraph | None = None,
) -> str:
    """Generate a per-task markdown table with status, duration, and dependencies.

    This table can be appended to the task manifest or used standalone.
    """
    lines: list[str] = []
    lines.append("| ID | Task | Status | Duration | Dependencies | Commit |")
    lines.append("|---:|------|--------|----------|-------------|--------|")

    for sl in registry.manifest.slices:
        lines.append(f"| | **Slice {sl.slice_num}** | | | | |")
        tasks = registry.manifest.tasks_in_slice(sl.slice_num)
        crit_set = set(sl.critical_path)

        for task in tasks:
            state = registry.state_of(task.task_id)
            status = state.status.value
            if task.task_id in crit_set:
                status += " (crit)"

            duration = dep_graph.durations.get(task.task_id, "1d") if dep_graph else "1d"
            deps = ", ".join(dep_graph.deps_of(task.task_id)) if dep_graph else ""
            commit = state.commit[:7] if state.commit else ""
            name = task.name[:50]

            lines.append(
                f"| {task.task_id} | {name} | {status} | {duration} | {deps} | {commit} |"
            )

    return "\n".join(lines)


# ── High-level API ───────────────────────────────────────────

def build_registry(
    manifest_path: Path,
    status_path: Path,
) -> StatusRegistry:
    """Build a StatusRegistry from manifest + status files."""
    manifest = parse_manifest_file(manifest_path)
    states = load_status(status_path)
    return StatusRegistry(manifest=manifest, states=states)


def generate_progress_report(
    manifest_path: Path,
    status_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """Generate all tracking artifacts.

    Returns dict of artifact_name → output_path.
    Raises ValueError if generated Gantt charts fail rendering validation.
    """
    registry = build_registry(manifest_path, status_path)
    dep_graph = build_dependency_graph(registry.manifest)
    outputs: dict[str, Path] = {}

    # Full Gantt (with dependencies and durations)
    gantt_source = generate_gantt(registry, dep_graph)
    gantt_validation = validate_gantt(gantt_source)
    if not gantt_validation.ok:
        msg = f"Full Gantt rendering validation failed:\n{gantt_validation}"
        raise ValueError(msg)

    gantt_path = output_dir / "GANTT.mermaid"
    gantt_path.write_text(gantt_source, encoding="utf-8")
    outputs["gantt"] = gantt_path

    # Critical-path Gantt (with dependencies and durations)
    crit_source = generate_gantt_critical_only(registry, dep_graph)
    crit_validation = validate_gantt(crit_source)
    if not crit_validation.ok:
        msg = f"Critical-path Gantt rendering validation failed:\n{crit_validation}"
        raise ValueError(msg)

    crit_path = output_dir / "GANTT_critical.mermaid"
    crit_path.write_text(crit_source, encoding="utf-8")
    outputs["gantt_critical"] = crit_path

    # Summary table
    summary_path = output_dir / "PROGRESS.md"
    header = (
        f"# Holly Grace - Development Progress\n\n"
        f"_Generated: {date.today().isoformat()}_\n\n"
    )
    detail_header = "\n\n## Task Detail\n\n"
    summary_path.write_text(
        header
        + generate_summary_table(registry)
        + detail_header
        + generate_task_detail_table(registry, dep_graph)
        + "\n",
        encoding="utf-8",
    )
    outputs["summary"] = summary_path

    # Store validation results for reporting
    outputs["_gantt_validation"] = gantt_path  # signals validation passed
    outputs["_crit_validation"] = crit_path

    return outputs
