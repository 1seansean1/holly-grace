"""Parse Task_Manifest.md into structured data for tracking and Gantt generation.

Extracts task IDs, names, slice/step groupings, and critical paths from the
markdown table format used in the manifest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# ── Data structures ──────────────────────────────────────────

@dataclass(frozen=True)
class TaskEntry:
    """Single task from the manifest."""

    task_id: str  # e.g. "1.5", "3a.8", "5a.3"
    mp: str  # methodology principle number
    name: str  # short task description
    step_id: str  # e.g. "1", "3a", "5a"
    slice_num: int  # 1-15

    @property
    def sort_key(self) -> tuple[int, str, int]:
        """Sort key: (slice, step_alpha, sub_id)."""
        m = re.match(r"(\d+a?)\.(\d+)", self.task_id)
        if m:
            return (self.slice_num, m.group(1), int(m.group(2)))
        return (self.slice_num, self.step_id, 0)


@dataclass
class StepGroup:
    """A step within a slice (e.g. Step 1 — Extract)."""

    step_id: str  # "1", "2", "3a", "5a"
    name: str  # "Extract (SAD → architecture.yaml)"
    tasks: list[TaskEntry] = field(default_factory=list)


@dataclass
class SliceGroup:
    """A slice (1-15) containing steps."""

    slice_num: int
    phase: str  # "Phase A Spiral", "Phase B", etc.
    title: str  # full title after "—"
    steps: list[StepGroup] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)  # ordered task IDs
    total_tasks: int = 0


@dataclass
class Manifest:
    """Parsed task manifest."""

    slices: list[SliceGroup] = field(default_factory=list)
    tasks: dict[str, TaskEntry] = field(default_factory=dict)  # task_id → TaskEntry
    all_critical_path_ids: set[str] = field(default_factory=set)

    @property
    def total_tasks(self) -> int:
        return len(self.tasks)

    def tasks_in_slice(self, slice_num: int) -> list[TaskEntry]:
        return sorted(
            [t for t in self.tasks.values() if t.slice_num == slice_num],
            key=lambda t: t.sort_key,
        )


# ── Regexes ──────────────────────────────────────────────────

_RE_SLICE = re.compile(
    r"^## Slice (\d+)\s*[\u2014\u2013-]\s*(.+)$"
)
_RE_STEP = re.compile(
    r"^####\s+Step\s+(\d+a?)\s*[\u2014\u2013-]\s*(.+)$"
)
_RE_TASK_ROW = re.compile(
    r"^\|\s*(\d+a?\.\d+)\s*\|\s*(\d+)\s*\|\s*(.+?)\s*\|"
)
_RE_CRITICAL_PATH = re.compile(
    r"^(\d+a?\.\d+(?:\s*[→→]\s*\d+a?\.\d+)+)\s*$"
)


def _parse_critical_path_line(line: str) -> list[str]:
    """Parse a critical path line like '1.5 → 1.6 → 1.7' into task IDs."""
    stripped = line.strip()
    if not stripped or not re.match(r"\d+a?\.\d+", stripped):
        return []
    # Split on arrow variants
    parts = re.split(r"\s*[→→]\s*", stripped)
    ids = [p.strip() for p in parts if p.strip()]
    # Validate all parts are task IDs
    if all(re.match(r"^\d+a?\.\d+$", p) for p in ids):
        return ids
    return []


def parse_manifest(source: str) -> Manifest:
    """Parse Task_Manifest.md content into a Manifest."""
    manifest = Manifest()
    current_slice: SliceGroup | None = None
    current_step: StepGroup | None = None
    in_critical_path_block = False
    lines = source.splitlines()

    for _i, line in enumerate(lines):
        stripped = line.strip()

        # Slice header
        m_slice = _RE_SLICE.match(stripped)
        if m_slice:
            current_slice = SliceGroup(
                slice_num=int(m_slice.group(1)),
                phase="",
                title=m_slice.group(2).strip(),
            )
            manifest.slices.append(current_slice)
            current_step = None
            in_critical_path_block = False
            continue

        # Step header
        m_step = _RE_STEP.match(stripped)
        if m_step and current_slice is not None:
            current_step = StepGroup(
                step_id=m_step.group(1),
                name=m_step.group(2).strip(),
            )
            current_slice.steps.append(current_step)
            in_critical_path_block = False
            continue

        # Critical path section
        if stripped == "### Critical Path":
            in_critical_path_block = True
            continue

        if in_critical_path_block and current_slice is not None:
            # Look for the path line inside a code block or bare
            if stripped.startswith("```"):
                continue
            path_ids = _parse_critical_path_line(stripped)
            if path_ids:
                current_slice.critical_path = path_ids
                manifest.all_critical_path_ids.update(path_ids)
                in_critical_path_block = False
            continue

        # Task row
        m_task = _RE_TASK_ROW.match(stripped)
        if m_task and current_slice is not None:
            task_id = m_task.group(1)
            mp = m_task.group(2)
            name = m_task.group(3).strip()
            # Clean markdown from name
            name = re.sub(r"`([^`]+)`", r"\1", name)
            name = re.sub(r"\*\*([^*]+)\*\*", r"\1", name)

            step_id = current_step.step_id if current_step else ""
            entry = TaskEntry(
                task_id=task_id,
                mp=mp,
                name=name,
                step_id=step_id,
                slice_num=current_slice.slice_num,
            )
            manifest.tasks[task_id] = entry
            if current_step is not None:
                current_step.tasks.append(entry)
            current_slice.total_tasks += 1

    return manifest


def parse_manifest_file(path: Path) -> Manifest:
    """Parse a Task_Manifest.md file."""
    return parse_manifest(path.read_text(encoding="utf-8"))
