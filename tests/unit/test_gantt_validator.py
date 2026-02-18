"""Tests for holly.arch.gantt_validator - mermaid Gantt rendering validation."""

from __future__ import annotations

from holly.arch.gantt_validator import validate_gantt

VALID_GANTT = """\
gantt
    title Holly Grace - Critical Path
    dateFormat YYYY-MM-DD
    axisFormat %b %d
    excludes weekends

    section Slice 1 (50%)
    1.5 Write SAD parser :done, t1_5, 2026-02-18, 1d
    1.6 Define schema :crit, t1_6, after t1_5, 0.5d
    1.7 Build pipeline :crit, t1_7, after t1_6, 1d
"""


class TestHeaderValidation:
    """Test mermaid header checks."""

    def test_valid_gantt_passes(self) -> None:
        result = validate_gantt(VALID_GANTT)
        assert result.ok

    def test_missing_gantt_declaration(self) -> None:
        source = """\
    title Test
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1, 2026-01-01, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Missing 'gantt'" in i.message for i in result.errors)

    def test_missing_dateformat(self) -> None:
        source = """\
gantt
    title Test
    section S1
    Task A :t1, 2026-01-01, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Missing 'dateFormat'" in i.message for i in result.errors)

    def test_empty_source(self) -> None:
        result = validate_gantt("")
        assert not result.ok


class TestAliasValidation:
    """Test alias uniqueness and reference integrity."""

    def test_duplicate_alias(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1_1, 2026-01-01, 1d
    Task B :t1_1, 2026-01-02, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Duplicate alias" in i.message for i in result.errors)

    def test_undefined_after_reference(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1_1, 2026-01-01, 1d
    Task B :t1_2, after t999_99, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Undefined alias" in i.message and "t999_99" in i.message
                    for i in result.errors)

    def test_multi_after_reference_is_error(self) -> None:
        """Mermaid Gantt only supports `after <single_id>`, not multiple."""
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1_1, 2026-01-01, 1d
    Task B :t1_2, 2026-01-01, 1d
    Task C :t1_3, after t1_1, t1_2, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Multiple after" in i.message for i in result.errors)

    def test_valid_after_references(self) -> None:
        result = validate_gantt(VALID_GANTT)
        assert not any("Undefined alias" in i.message for i in result.issues)


class TestCycleDetection:
    """Test circular dependency detection."""

    def test_no_cycle_in_valid_gantt(self) -> None:
        result = validate_gantt(VALID_GANTT)
        assert not any("Circular" in i.message for i in result.issues)

    def test_detects_simple_cycle(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1, after t2, 1d
    Task B :t2, after t1, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Circular dependency" in i.message for i in result.errors)

    def test_detects_three_node_cycle(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    Task A :t1, after t3, 1d
    Task B :t2, after t1, 1d
    Task C :t3, after t2, 1d
"""
        result = validate_gantt(source)
        assert not result.ok
        assert any("Circular dependency" in i.message for i in result.errors)


class TestUnicodeAndTruncation:
    """Test unicode and label truncation warnings."""

    def test_unicode_arrow_warning(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    1.5 Write parser (mermaid → AST) :t1_5, 2026-01-01, 1d
"""
        result = validate_gantt(source)
        warnings = [i for i in result.warnings if "Unicode" in i.message]
        assert len(warnings) > 0

    def test_truncation_warning(self) -> None:
        # Label ending with a dangling comma triggers truncation warning
        source = (
            "gantt\n"
            "    dateFormat YYYY-MM-DD\n"
            "    section S1\n"
            "    Implement spawn/steer/dissolve, contracts, eigenspectru, :t1_5, 2026-01-01, 1d\n"
        )
        result = validate_gantt(source)
        warnings = [i for i in result.warnings if "truncated" in i.message]
        assert len(warnings) > 0

    def test_clean_labels_no_warnings(self) -> None:
        source = """\
gantt
    dateFormat YYYY-MM-DD
    section S1
    1.5 Write parser :done, t1_5, 2026-01-01, 1d
    1.6 Define schema :crit, t1_6, after t1_5, 0.5d
"""
        result = validate_gantt(source)
        assert len(result.warnings) == 0 or all(
            "title" in w.message.lower() for w in result.warnings
        )


class TestDependencyGraphCycleBreaking:
    """Test that the dependency builder breaks cycles from the manifest."""

    def test_circular_manifest_deps_broken(self) -> None:
        """Regression: tasks 33.4 and 33.5 had circular deps in the manifest."""
        from holly.arch.dependencies import DependencyGraph, _break_cycles

        graph = DependencyGraph()
        graph.predecessors = {
            "33.4": ["33.5", "33.3"],
            "33.5": ["33.2", "33.4"],
        }
        _break_cycles(graph)

        # After cycle breaking, at least one edge in the cycle must be removed
        deps_33_4 = graph.predecessors.get("33.4", [])
        deps_33_5 = graph.predecessors.get("33.5", [])
        # Either 33.4 no longer depends on 33.5, or 33.5 no longer on 33.4
        assert not ("33.5" in deps_33_4 and "33.4" in deps_33_5), \
            "Cycle between 33.4 and 33.5 was not broken"

    def test_non_circular_preserved(self) -> None:
        """Non-circular deps must survive cycle breaking."""
        from holly.arch.dependencies import DependencyGraph, _break_cycles

        graph = DependencyGraph()
        graph.predecessors = {
            "2": ["1"],
            "3": ["2"],
            "4": ["3"],
        }
        _break_cycles(graph)
        assert graph.predecessors["2"] == ["1"]
        assert graph.predecessors["3"] == ["2"]
        assert graph.predecessors["4"] == ["3"]


class TestCriticalGanttFiltering:
    """Test that critical-only Gantt filters undefined alias references."""

    def test_critical_gantt_no_undefined_refs(self) -> None:
        """All `after` references in critical Gantt must resolve to emitted aliases."""
        from holly.arch.dependencies import build_dependency_graph
        from holly.arch.manifest_parser import parse_manifest
        from holly.arch.tracker import StatusRegistry, generate_gantt_critical_only

        manifest_text = """\
# Holly Grace - Task Manifest

## Slice 1 - Phase A (Steps 1, 2)

### Tasks

#### Step 1 - Extract

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 1.1 | 1 | Map terms | SAD | Trace | Review | Traces |
| 1.5 | 8 | Write parser | SAD | Parser | Test | Parses |

#### Step 2 - Registry

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 2.5 | 6 | Enumerate failures | Design | FMEA | Review | Done |
| 2.6 | 8 | Implement loader | YAML | Registry | Test | Loads |

### Critical Path

```
1.5 -> 2.6
```
"""
        manifest = parse_manifest(manifest_text)
        graph = build_dependency_graph(manifest)
        reg = StatusRegistry(manifest=manifest, states={})
        gantt = generate_gantt_critical_only(reg, dep_graph=graph)

        # Validate: no undefined refs
        result = validate_gantt(gantt)
        undefined = [i for i in result.errors if "Undefined alias" in i.message]
        assert not undefined, f"Undefined aliases in critical Gantt: {undefined}"
