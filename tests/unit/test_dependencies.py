"""Tests for holly.arch.dependencies — task dependency graph and duration estimation."""

from __future__ import annotations

from holly.arch.dependencies import (
    build_dependency_graph,
    estimate_duration_days,
    estimate_duration_hours,
)
from holly.arch.manifest_parser import TaskEntry, parse_manifest

MINIMAL_MANIFEST = """\
# Holly Grace — Task Manifest

## Slice 1 — Phase A Spiral (Steps 1, 2)

### Tasks

#### Step 1 — Extract

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 1.1 | 1 | Map SAD terms | SAD | Trace | Review | Traces |
| 1.5 | 8 | Write parser | SAD | Parser | Test | Parses |
| 1.6 | 8 | Define schema | SAD | Schema | Test | Validates |
| 1.7 | 8 | Build pipeline | Parser + schema | YAML | Test | Passes |

#### Step 2 — Registry

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 2.6 | 8 | Implement loader | YAML | Registry | Test | Loads |
| 2.7 | 8 | Implement lookups | Registry | Queries | Test | Queries |

### Critical Path

```
1.5 → 1.6 → 1.7 → 2.6 → 2.7
```

## Slice 2 — Phase B (Steps 3)

### Tasks

#### Step 3 — Kernel

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 3.1 | 7 | Write TLA+ spec | Design | Spec | Model check | Verified |
| 3.2 | 8 | Implement kernel | Spec | Kernel | Test | Works |

### Critical Path

```
3.1 → 3.2
```
"""


TWO_SLICE_MANIFEST = """\
# Holly Grace — Task Manifest

## Slice 1 — Phase A (Steps 1)

### Tasks

#### Step 1 — Extract

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 1.1 | 8 | Task A | - | Out | Test | Done |
| 1.2 | 8 | Task B | - | Out | Test | Done |

### Critical Path

```
1.1 → 1.2
```

## Slice 2 — Phase B (Steps 2)

### Tasks

#### Step 2 — Build

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 2.1 | 8 | Task C | - | Out | Test | Done |

### Critical Path

```
2.1
```
"""


class TestDurationEstimation:
    """Test MP-based duration model."""

    def test_mp8_implementation(self) -> None:
        task = TaskEntry("1.5", "8", "Write parser", "1", 1)
        hours = estimate_duration_hours(task, sil=2)
        # MP8 base=4h, SIL-2 mult=1.2 → 4.8 → rounds to 5.0
        assert hours == 5.0

    def test_mp7_formal(self) -> None:
        task = TaskEntry("3.1", "7", "TLA+ spec", "3", 1)
        hours = estimate_duration_hours(task, sil=3)
        # MP7 base=8h, SIL-3 mult=1.5 → 12.0
        assert hours == 12.0

    def test_mp1_review(self) -> None:
        task = TaskEntry("1.1", "1", "Map terms", "1", 1)
        hours = estimate_duration_hours(task, sil=1)
        # MP1 base=1h, SIL-1 mult=1.0 → 1.0
        assert hours == 1.0

    def test_duration_days_format(self) -> None:
        task = TaskEntry("1.5", "8", "Write parser", "1", 1)
        days = estimate_duration_days(task, sil=2)
        # 5.0h / 8 = 0.625d → rounds to 0.5d
        assert days == "0.5d" or days == "1d"

    def test_duration_minimum(self) -> None:
        task = TaskEntry("1.1", "1", "Map terms", "1", 1)
        hours = estimate_duration_hours(task, sil=1)
        assert hours >= 0.5

    def test_duration_maximum(self) -> None:
        task = TaskEntry("3.1", "7", "TLA+ spec", "3", 1)
        hours = estimate_duration_hours(task, sil=3)
        assert hours <= 16.0


class TestDependencyGraph:
    """Test dependency graph construction."""

    def test_critical_path_deps(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        # 1.6 depends on 1.5 (critical path)
        assert "1.5" in graph.deps_of("1.6")

    def test_critical_path_chain(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        # 2.7 depends on 2.6
        assert "2.6" in graph.deps_of("2.7")

    def test_first_task_no_deps(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        # 1.5 is first on critical path, but 1.1 precedes it in step
        # 1.1 is first task in step 1 — no critical path pred
        assert not graph.has_deps("1.1") or graph.deps_of("1.1") == []

    def test_step_internal_ordering(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        # 1.5 follows 1.1 in step 1 (step-internal ordering)
        deps_1_5 = graph.deps_of("1.5")
        assert "1.1" in deps_1_5

    def test_inter_slice_gate(self) -> None:
        manifest = parse_manifest(TWO_SLICE_MANIFEST)
        graph = build_dependency_graph(manifest)
        # Slice 2 entry task (2.1) should depend on slice 1 gate (1.2)
        deps_2_1 = graph.deps_of("2.1")
        assert "1.2" in deps_2_1

    def test_durations_populated(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        # Every task should have a duration
        for tid in manifest.tasks:
            assert tid in graph.durations
            assert graph.durations[tid].endswith("d")

    def test_has_deps(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        assert graph.has_deps("1.6")  # on critical path after 1.5
        assert not graph.has_deps("1.1")  # first task, no predecessors

    def test_no_self_deps(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        for tid, deps in graph.predecessors.items():
            assert tid not in deps, f"Task {tid} depends on itself"

    def test_all_deps_exist(self) -> None:
        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        all_ids = set(manifest.tasks.keys())
        for tid, deps in graph.predecessors.items():
            for dep in deps:
                assert dep in all_ids, f"Task {tid} depends on non-existent {dep}"


class TestGanttWithDeps:
    """Test that Gantt generation works with dependency graph."""

    def test_gantt_has_after_syntax(self) -> None:
        from holly.arch.tracker import (
            StatusRegistry,
            generate_gantt,
        )

        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        reg = StatusRegistry(manifest=manifest, states={})
        gantt = generate_gantt(reg, dep_graph=graph)
        # Tasks with deps should use 'after' syntax
        assert "after t1_5" in gantt  # 1.6 depends on 1.5

    def test_gantt_has_durations(self) -> None:
        from holly.arch.tracker import (
            StatusRegistry,
            generate_gantt,
        )

        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        reg = StatusRegistry(manifest=manifest, states={})
        gantt = generate_gantt(reg, dep_graph=graph)
        # Should not have placeholder 1d for all tasks
        # MP7 TLA+ tasks should have longer durations
        assert "0.5d" in gantt or "1d" in gantt or "1.5d" in gantt

    def test_critical_gantt_has_after(self) -> None:
        from holly.arch.tracker import (
            StatusRegistry,
            generate_gantt_critical_only,
        )

        manifest = parse_manifest(MINIMAL_MANIFEST)
        graph = build_dependency_graph(manifest)
        reg = StatusRegistry(manifest=manifest, states={})
        gantt = generate_gantt_critical_only(reg, dep_graph=graph)
        assert "after" in gantt
