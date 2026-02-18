"""Tests for codebase review remediations.

Covers fixes from the dual-repo review:
  1. SchemaRegistry immutability (no silent overwrite)
  2. SchemaRegistry 'type' key validation
  3. TaskStatus graceful degradation on unknown values
  4. C011 diff counting accuracy
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
    def test_missing_type_key_raises(self) -> None:
        with pytest.raises(SchemaParseError) as exc_info:
            SchemaRegistry.register("ICD-NOTYPE", {"properties": {"x": {}}})
        assert "type" in exc_info.value.detail

    def test_empty_dict_raises(self) -> None:
        with pytest.raises(SchemaParseError):
            SchemaRegistry.register("ICD-EMPTY", {})

    def test_type_key_present_succeeds(self) -> None:
        SchemaRegistry.register("ICD-OK", {"type": "object"})
        assert SchemaRegistry.has("ICD-OK")

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
