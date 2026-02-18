"""Mermaid Gantt chart rendering validator.

Validates generated mermaid Gantt charts for structural correctness
before they are written to disk. Catches issues that would cause
silent rendering failures in mermaid.js:

1. Undefined alias references (task references an alias not emitted)
2. Circular dependencies (A → B → A)
3. Unicode characters in labels (not all renderers handle these)
4. Label truncation leaving broken text
5. Duplicate aliases
6. Missing required header fields
7. Multiple after references (mermaid only supports `after <single_id>`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GanttIssue:
    """A single validation issue found in a Gantt chart."""

    severity: str  # "error" | "warning"
    line_num: int
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] line {self.line_num}: {self.message}"


@dataclass
class GanttValidationResult:
    """Result of validating a mermaid Gantt chart."""

    issues: list[GanttIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no errors (warnings are acceptable)."""
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[GanttIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[GanttIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def __str__(self) -> str:
        if not self.issues:
            return "Gantt validation: OK"
        lines = [f"Gantt validation: {len(self.errors)} errors, {len(self.warnings)} warnings"]
        for issue in self.issues:
            lines.append(f"  {issue}")
        return "\n".join(lines)


# Regex to extract task alias from a gantt task line
# Pattern: <label> :<tags>, <alias>, <start_or_after>, <duration>
_ALIAS_PATTERN = re.compile(
    r"^\s+.+\s+:"  # label + colon
    r"(?:done,\s*|active,\s*|crit,\s*)*"  # optional status tags
    r"(t\w+)"  # capture alias
)

# Pattern to extract `after alias1, alias2` references
_AFTER_PATTERN = re.compile(r"\bafter\s+(t[\w,\s]+?)(?:,\s*\d)")

# Individual alias within after clause
_AFTER_ALIAS = re.compile(r"t\w+")


def validate_gantt(source: str) -> GanttValidationResult:
    """Validate a mermaid Gantt chart string for rendering correctness.

    Checks performed:
    - Required header fields (gantt, dateFormat, title)
    - Alias uniqueness (no duplicate task aliases)
    - Alias reference integrity (all `after tX_Y` references resolve)
    - Cycle detection in dependency graph
    - Unicode characters in task labels (warning)
    - Label truncation artifacts (trailing spaces, dangling punctuation)
    """
    result = GanttValidationResult()
    lines = source.split("\n")

    if not lines:
        result.issues.append(GanttIssue("error", 0, "Empty Gantt source"))
        return result

    # ── Header checks ────────────────────────────────────────
    has_gantt = False
    has_dateformat = False
    has_title = False

    for _i, line in enumerate(lines[:10], start=1):
        stripped = line.strip()
        if stripped == "gantt":
            has_gantt = True
        elif stripped.startswith("dateFormat"):
            has_dateformat = True
        elif stripped.startswith("title"):
            has_title = True

    if not has_gantt:
        result.issues.append(GanttIssue("error", 1, "Missing 'gantt' declaration"))
    if not has_dateformat:
        result.issues.append(GanttIssue("error", 1, "Missing 'dateFormat' declaration"))
    if not has_title:
        result.issues.append(GanttIssue("warning", 1, "Missing 'title' declaration"))

    # ── Extract defined aliases and after-references ──────────
    defined_aliases: dict[str, int] = {}  # alias → line number
    after_refs: list[tuple[int, str]] = []  # (line_number, alias_ref)
    # Also build adjacency for cycle detection: alias → set of dep aliases
    adjacency: dict[str, set[str]] = {}

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("section") or stripped in (
            "gantt", "excludes weekends",
        ) or stripped.startswith("dateFormat") or stripped.startswith("axisFormat") or stripped.startswith("title"):
            continue

        # Extract defined alias
        alias_match = _ALIAS_PATTERN.match(line)
        if alias_match:
            alias = alias_match.group(1)
            if alias in defined_aliases:
                result.issues.append(GanttIssue(
                    "error", i,
                    f"Duplicate alias '{alias}' (first defined on line {defined_aliases[alias]})",
                ))
            defined_aliases[alias] = i
            adjacency.setdefault(alias, set())

        # Extract after references
        after_match = _AFTER_PATTERN.search(line)
        if after_match and alias_match:
            after_str = after_match.group(1)
            dep_aliases = _AFTER_ALIAS.findall(after_str)
            current_alias = alias_match.group(1)
            # Mermaid Gantt only supports `after <single_id>` — multiple
            # IDs in a single after clause cause a parse crash.
            if len(dep_aliases) > 1:
                result.issues.append(GanttIssue(
                    "error", i,
                    f"Multiple after references ({', '.join(dep_aliases)}) - "
                    f"mermaid only supports 'after <single_id>'",
                ))
            for dep_alias in dep_aliases:
                after_refs.append((i, dep_alias))
                adjacency.setdefault(current_alias, set()).add(dep_alias)

        # ── Unicode check ────────────────────────────────────
        # Check label portion (before the colon) for problematic unicode
        colon_idx = line.find(":")
        if colon_idx > 0:
            label_part = line[:colon_idx].strip()
            if re.search(r"[\u2190-\u21ff\u2014\u2013]", label_part):
                result.issues.append(GanttIssue(
                    "warning", i,
                    f"Unicode arrow/dash in label may not render: '{label_part[:40]}...'",
                ))

        # ── Truncation artifacts ─────────────────────────────
        if colon_idx > 0:
            label_part = line[:colon_idx].strip()
            if label_part.endswith((" ", "-", "→", "(", ",")):
                result.issues.append(GanttIssue(
                    "warning", i,
                    f"Label appears truncated: '...{label_part[-20:]}'",
                ))

    # ── Undefined alias references ───────────────────────────
    for line_num, ref_alias in after_refs:
        if ref_alias not in defined_aliases:
            result.issues.append(GanttIssue(
                "error", line_num,
                f"Undefined alias reference '{ref_alias}' in 'after' clause",
            ))

    # ── Cycle detection (DFS-based) ──────────────────────────
    cycles = _detect_cycles(adjacency)
    for cycle in cycles:
        cycle_str = " → ".join(cycle)
        result.issues.append(GanttIssue(
            "error", 0,
            f"Circular dependency detected: {cycle_str}",
        ))

    return result


def _detect_cycles(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in the dependency graph using DFS.

    Returns a list of cycles found. Each cycle is a list of aliases
    forming the cycle (e.g., ['t33_4', 't33_5', 't33_4']).
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in adjacency}
    cycles: list[list[str]] = []
    path: list[str] = []
    seen_cycles: set[frozenset[str]] = set()

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        for dep in adjacency.get(node, set()):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                # Found a cycle — extract it
                cycle_start = path.index(dep)
                cycle = [*path[cycle_start:], dep]
                cycle_key = frozenset(cycle)
                if cycle_key not in seen_cycles:
                    seen_cycles.add(cycle_key)
                    cycles.append(cycle)
            elif color[dep] == WHITE:
                dfs(dep)
        path.pop()
        color[node] = BLACK

    for node in adjacency:
        if color[node] == WHITE:
            dfs(node)

    return cycles


def validate_gantt_file(path: str) -> GanttValidationResult:
    """Validate a mermaid Gantt chart file."""
    from pathlib import Path as _Path

    p = _Path(path)
    if not p.exists():
        result = GanttValidationResult()
        result.issues.append(GanttIssue("error", 0, f"File not found: {path}"))
        return result
    return validate_gantt(p.read_text(encoding="utf-8"))
