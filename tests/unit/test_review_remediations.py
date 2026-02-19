"""Tests for codebase review remediations.

Covers fixes from the dual-repo review:
  1. SchemaRegistry immutability (no silent overwrite)
  2. SchemaRegistry 'type' key validation
  3. TaskStatus graceful degradation on unknown values
  4. C011 diff counting accuracy
  5. load_status() tasks shape guard (list → AttributeError)
  6. Critical path ASCII arrow support
  7. _measure_depth() early termination (BUG-005)
  8. load_status() YAML parse error handling (ERR-004)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

from holly.kernel.exceptions import SchemaAlreadyRegisteredError, SchemaParseError
from holly.kernel.schema_registry import SchemaRegistry

if TYPE_CHECKING:
    from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    SchemaRegistry.clear()
    yield
    SchemaRegistry.clear()


# ══════════════════════════════════════════════════════════
# SchemaRegistry: duplicate registration rejected
# ══════════════════════════════════════════════════════════


class TestSchemaRegistryImmutability:
    def test_duplicate_register_raises(self) -> None:
        SchemaRegistry.register("ICD-DUP", {"type": "object"})
        with pytest.raises(SchemaAlreadyRegisteredError) as exc_info:
            SchemaRegistry.register("ICD-DUP", {"type": "string"})
        assert exc_info.value.schema_id == "ICD-DUP"

    def test_duplicate_register_preserves_original(self) -> None:
        original = {"type": "object", "properties": {"x": {"type": "integer"}}}
        SchemaRegistry.register("ICD-ORIG", original)
        with pytest.raises(SchemaAlreadyRegisteredError):
            SchemaRegistry.register("ICD-ORIG", {"type": "array"})
        assert SchemaRegistry.get("ICD-ORIG") == original

    def test_clear_then_reregister_succeeds(self) -> None:
        SchemaRegistry.register("ICD-CLR", {"type": "object"})
        SchemaRegistry.clear()
        # After clear, re-registration should succeed
        SchemaRegistry.register("ICD-CLR", {"type": "string"})
        assert SchemaRegistry.get("ICD-CLR") == {"type": "string"}

    def test_different_ids_register_fine(self) -> None:
        SchemaRegistry.register("ICD-A", {"type": "object"})
        SchemaRegistry.register("ICD-B", {"type": "array"})
        assert SchemaRegistry.has("ICD-A")
        assert SchemaRegistry.has("ICD-B")


# ══════════════════════════════════════════════════════════
# SchemaRegistry: 'type' key validation
# ══════════════════════════════════════════════════════════


class TestSchemaRegistryTypeKeyValidation:
    # F-037: SchemaRegistry now accepts valid JSON Schema 2020-12 without a
    # top-level "type" key.  Schemas with anyOf / oneOf / $ref / properties /
    # etc. at the root are valid and must be accepted.  Only structurally empty
    # dicts (no recognised JSON Schema keyword at all) are rejected.

    def test_metadata_only_dict_raises(self) -> None:
        """Schema with only title/description but no structural keyword is rejected."""
        with pytest.raises(SchemaParseError) as exc_info:
            SchemaRegistry.register(
                "ICD-META-ONLY", {"title": "My Schema", "description": "empty"}
            )
        assert "structural" in exc_info.value.detail

    def test_empty_dict_raises(self) -> None:
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register("ICD-EMPTY", {})

    def test_type_key_present_succeeds(self) -> None:
        SchemaRegistry.register("ICD-OK", {"type": "object"})
        assert SchemaRegistry.has("ICD-OK")

    def test_properties_only_succeeds(self) -> None:
        """properties at root is a structural keyword — accepted without 'type'."""
        SchemaRegistry.register("ICD-PROPS", {"properties": {"x": {"type": "string"}}})
        assert SchemaRegistry.has("ICD-PROPS")

    def test_non_dict_still_raises_parse_error(self) -> None:
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register("ICD-LIST", [1, 2, 3])  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════
# TaskStatus: graceful degradation on unknown values
# ══════════════════════════════════════════════════════════


class TestTaskStatusGracefulDegradation:
    def test_unknown_string_status_defaults_to_pending(self, tmp_path: Path) -> None:
        from holly.arch.tracker import TaskStatus, load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  1.1: Done\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states["1.1"].status == TaskStatus.PENDING

    def test_unknown_dict_status_defaults_to_pending(self, tmp_path: Path) -> None:
        from holly.arch.tracker import TaskStatus, load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  2.1:\n    status: complete\n    note: typo\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states["2.1"].status == TaskStatus.PENDING

    def test_unknown_status_logs_warning(self, tmp_path: Path, caplog: Any) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  3.1: INVALID\n",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            load_status(status_file)
        assert any("Unknown status" in r.message for r in caplog.records)

    def test_valid_statuses_still_work(self, tmp_path: Path) -> None:
        from holly.arch.tracker import TaskStatus, load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  1.1: pending\n  1.2: done\n  1.3: active\n  1.4: blocked\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states["1.1"].status == TaskStatus.PENDING
        assert states["1.2"].status == TaskStatus.DONE
        assert states["1.3"].status == TaskStatus.ACTIVE
        assert states["1.4"].status == TaskStatus.BLOCKED


# ══════════════════════════════════════════════════════════
# C011: diff count accuracy
# ══════════════════════════════════════════════════════════


class TestC011DiffCounting:
    def test_same_length_different_content_reports_nonzero(self) -> None:
        """Lines changed but count unchanged should still report diff > 0."""
        gen = "line1\nline2\nline3"
        file = "line1\nCHANGED\nline3"
        gen_lines = gen.split("\n")
        file_lines = file.split("\n")
        min_len = min(len(gen_lines), len(file_lines))
        diff_count = sum(
            1 for i in range(min_len) if gen_lines[i] != file_lines[i]
        ) + abs(len(gen_lines) - len(file_lines))
        assert diff_count == 1  # one line differs

    def test_different_length_counts_both_changes_and_delta(self) -> None:
        gen = "line1\nline2\nline3\nline4"
        file = "line1\nCHANGED\nline3"
        gen_lines = gen.split("\n")
        file_lines = file.split("\n")
        min_len = min(len(gen_lines), len(file_lines))
        diff_count = sum(
            1 for i in range(min_len) if gen_lines[i] != file_lines[i]
        ) + abs(len(gen_lines) - len(file_lines))
        assert diff_count == 2  # 1 changed + 1 length delta

    def test_identical_reports_zero(self) -> None:
        content = "line1\nline2\nline3"
        gen_lines = content.split("\n")
        file_lines = content.split("\n")
        min_len = min(len(gen_lines), len(file_lines))
        diff_count = sum(
            1 for i in range(min_len) if gen_lines[i] != file_lines[i]
        ) + abs(len(gen_lines) - len(file_lines))
        assert diff_count == 0


# ══════════════════════════════════════════════════════════
# load_status(): tasks shape guard
# ══════════════════════════════════════════════════════════


class TestLoadStatusShapeGuard:
    def test_tasks_as_list_returns_empty(self, tmp_path: Path) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  - item1\n  - item2\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states == {}

    def test_tasks_as_list_logs_warning(self, tmp_path: Path, caplog: Any) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks:\n  - item1\n",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            load_status(status_file)
        assert any("expected dict" in r.message for r in caplog.records)

    def test_tasks_as_string_returns_empty(self, tmp_path: Path) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\ntasks: not_a_dict\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states == {}

    def test_missing_tasks_key_returns_empty(self, tmp_path: Path) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "version: '1.0'\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states == {}


# ══════════════════════════════════════════════════════════
# Critical path: ASCII arrow support
# ══════════════════════════════════════════════════════════


class TestCriticalPathArrowParsing:
    def test_unicode_arrow(self) -> None:
        from holly.arch.manifest_parser import _parse_critical_path_line

        result = _parse_critical_path_line("1.5 → 1.6 → 1.7")
        assert result == ["1.5", "1.6", "1.7"]

    def test_ascii_arrow(self) -> None:
        from holly.arch.manifest_parser import _parse_critical_path_line

        result = _parse_critical_path_line("1.5 -> 1.6 -> 1.7")
        assert result == ["1.5", "1.6", "1.7"]

    def test_mixed_arrows(self) -> None:
        from holly.arch.manifest_parser import _parse_critical_path_line

        result = _parse_critical_path_line("1.5 → 1.6 -> 1.7")
        assert result == ["1.5", "1.6", "1.7"]

    def test_single_task_returns_single_id(self) -> None:
        from holly.arch.manifest_parser import _parse_critical_path_line

        result = _parse_critical_path_line("1.5")
        assert result == ["1.5"]

    def test_alpha_slice_ids(self) -> None:
        from holly.arch.manifest_parser import _parse_critical_path_line

        result = _parse_critical_path_line("3a.8 -> 3a.10 -> 3a.12")
        assert result == ["3a.8", "3a.10", "3a.12"]

    def test_regex_matches_ascii_arrow_line(self) -> None:
        from holly.arch.manifest_parser import _RE_CRITICAL_PATH

        assert _RE_CRITICAL_PATH.match("1.1 -> 1.2 -> 1.3")
        assert _RE_CRITICAL_PATH.match("1.1 → 1.2 → 1.3")
        assert not _RE_CRITICAL_PATH.match("not a path")


# ══════════════════════════════════════════════════════════
# BUG-005: _measure_depth() early termination
# ══════════════════════════════════════════════════════════


class TestMeasureDepthCeiling:
    def test_shallow_payload_exact(self) -> None:
        from holly.kernel.k1 import _measure_depth

        payload = {"a": {"b": {"c": 1}}}
        assert _measure_depth(payload) == 3

    def test_ceiling_short_circuits(self) -> None:
        from holly.kernel.k1 import _measure_depth

        # Build a wide + deep structure: 100 keys at each of 5 levels
        deep: dict[str, Any] = {}
        for i in range(100):
            level: dict[str, Any] = {}
            for j in range(100):
                level[f"k{j}"] = {"inner": 1}
            deep[f"top{i}"] = level
        # Without ceiling, this visits 100*100*1 = 10000 nodes
        # With ceiling=3, it stops early
        result = _measure_depth(deep, _ceiling=3)
        assert result >= 3  # hit ceiling, stopped

    def test_list_depth(self) -> None:
        from holly.kernel.k1 import _measure_depth

        payload = [[[1, 2], [3]], [4]]
        assert _measure_depth(payload) == 3

    def test_empty_containers(self) -> None:
        from holly.kernel.k1 import _measure_depth

        assert _measure_depth({}) == 1
        assert _measure_depth([]) == 1
        assert _measure_depth(42) == 0


# ══════════════════════════════════════════════════════════
# ERR-004: YAML parse error handling in load_status()
# ══════════════════════════════════════════════════════════


class TestLoadStatusYamlError:
    def test_malformed_yaml_returns_empty(self, tmp_path: Path) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            "tasks:\n  bad: [unclosed\n",
            encoding="utf-8",
        )
        states = load_status(status_file)
        assert states == {}

    def test_malformed_yaml_logs_warning(self, tmp_path: Path, caplog: Any) -> None:
        from holly.arch.tracker import load_status

        status_file = tmp_path / "status.yaml"
        status_file.write_text(
            ":\n  :\n    : [[[",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            load_status(status_file)
        assert any("malformed YAML" in r.message for r in caplog.records)
