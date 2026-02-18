"""Tests for holly.arch.registry — Task 2.8 hot-reload with validation.

Covers:
- Successful reload propagates new document
- Generation counter increments on each reload
- Invalid YAML on reload retains old state (old document + old generation)
- Missing file on reload retains old state
- reload() on uninitialized registry behaves like initial load
- Identity preserved: same singleton object after reload
- Thread-safety under concurrent reload + get
- reload() after configure() to new path
- Lookups (Task 2.7) reflect reloaded data
- Integration with real architecture.yaml reload cycle
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
import yaml

from holly.arch.registry import (
    ArchitectureRegistry,
    RegistryValidationError,
)
from holly.arch.schema import ArchitectureDocument


# ── Helpers ────────────────────────────────────────────


def _write_yaml(path: Path, *, sad_version: str = "0.1.0.5", comp_id: str = "K1",
                comp_name: str = "Schema Validation") -> Path:
    """Write a minimal valid architecture.yaml with configurable fields."""
    data = {
        "metadata": {
            "sad_version": sad_version,
            "sad_file": "test.mermaid",
            "chart_type": "flowchart",
            "chart_direction": "TB",
            "generated_by": "test",
            "schema_version": "1.0.0",
        },
        "layers": {},
        "components": {
            comp_id: {
                "id": comp_id,
                "name": comp_name,
                "layer": "L1",
                "subgraph_id": "KERNEL",
                "source": {"file": "test.mermaid", "line": 1, "raw": comp_id},
            },
        },
        "connections": [],
        "kernel_invariants": [],
    }
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    return path


# ── Fixtures ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Ensure every test starts with a clean singleton."""
    ArchitectureRegistry.reset()
    ArchitectureRegistry._yaml_path = None
    yield
    ArchitectureRegistry.reset()
    ArchitectureRegistry._yaml_path = None


@pytest.fixture()
def yaml_v1(tmp_path: Path) -> Path:
    """A valid YAML file — version 1."""
    return _write_yaml(tmp_path / "architecture.yaml",
                       sad_version="1.0.0", comp_id="K1",
                       comp_name="Schema Validation V1")


@pytest.fixture()
def yaml_v2(tmp_path: Path) -> Path:
    """A valid YAML file — version 2 (different content)."""
    return _write_yaml(tmp_path / "architecture_v2.yaml",
                       sad_version="2.0.0", comp_id="K1",
                       comp_name="Schema Validation V2")


@pytest.fixture()
def yaml_file(tmp_path: Path) -> Path:
    """A mutable YAML file that tests can overwrite in place."""
    return _write_yaml(tmp_path / "architecture.yaml",
                       sad_version="1.0.0", comp_id="K1",
                       comp_name="Original")


@pytest.fixture()
def real_yaml() -> Path | None:
    """Return path to real architecture.yaml if it exists."""
    candidates = [
        Path("docs/architecture.yaml"),
        Path.cwd() / "docs" / "architecture.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ── Successful reload ──────────────────────────────────


class TestReloadSuccess:
    """Reload with valid YAML propagates new document."""

    def test_reload_changes_document(self, yaml_file: Path) -> None:
        """After overwriting the YAML and calling reload(), document reflects new content."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        assert reg.document.metadata.sad_version == "1.0.0"
        assert reg.document.components["K1"].name == "Original"

        # Overwrite in place with new content.
        _write_yaml(yaml_file, sad_version="2.0.0", comp_id="K1",
                     comp_name="Reloaded")
        reg2 = ArchitectureRegistry.reload()

        assert reg2.document.metadata.sad_version == "2.0.0"
        assert reg2.document.components["K1"].name == "Reloaded"

    def test_reload_returns_same_singleton(self, yaml_file: Path) -> None:
        """reload() returns the same object identity — no new instance created."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        reg2 = ArchitectureRegistry.reload()
        assert reg is reg2

    def test_reload_document_via_get(self, yaml_file: Path) -> None:
        """After reload(), subsequent get() returns the updated document."""
        ArchitectureRegistry.configure(yaml_file)
        ArchitectureRegistry.get()

        _write_yaml(yaml_file, sad_version="3.0.0", comp_id="K1",
                     comp_name="Via Get")
        ArchitectureRegistry.reload()

        reg = ArchitectureRegistry.get()
        assert reg.document.metadata.sad_version == "3.0.0"

    def test_reload_adds_new_component(self, tmp_path: Path) -> None:
        """reload() picks up a component added to the YAML."""
        p = tmp_path / "architecture.yaml"
        # Start with K1 only.
        _write_yaml(p, comp_id="K1", comp_name="K1 Original")
        ArchitectureRegistry.configure(p)
        reg = ArchitectureRegistry.get()
        assert "K1" in reg.document.components
        assert "K2" not in reg.document.components

        # Add K2.
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        data["components"]["K2"] = {
            "id": "K2",
            "name": "Permission Gating",
            "layer": "L1",
            "subgraph_id": "KERNEL",
            "source": {"file": "test.mermaid", "line": 2, "raw": "K2"},
        }
        p.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
        ArchitectureRegistry.reload()

        assert "K2" in reg.document.components
        assert reg.document.components["K2"].name == "Permission Gating"


# ── Generation counter ─────────────────────────────────


class TestGenerationCounter:
    """The generation counter tracks reload cycles."""

    def test_initial_generation_is_one(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        assert reg.generation == 1

    def test_reload_increments_generation(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        assert reg.generation == 1

        ArchitectureRegistry.reload()
        assert reg.generation == 2

        ArchitectureRegistry.reload()
        assert reg.generation == 3

    def test_generation_monotonic(self, yaml_file: Path) -> None:
        """Five successive reloads produce generations 1..6."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        gens = [reg.generation]
        for _ in range(5):
            ArchitectureRegistry.reload()
            gens.append(reg.generation)
        assert gens == [1, 2, 3, 4, 5, 6]


# ── Failed reload retains old state ────────────────────


class TestReloadFailureRetainsState:
    """Invalid YAML on reload must not corrupt existing state."""

    def test_invalid_yaml_retains_old_document(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        old_version = reg.document.metadata.sad_version
        old_gen = reg.generation

        # Corrupt the file.
        yaml_file.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(RegistryValidationError):
            ArchitectureRegistry.reload()

        # Old state retained.
        assert reg.document.metadata.sad_version == old_version
        assert reg.generation == old_gen

    def test_schema_violation_retains_old_document(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        old_gen = reg.generation

        # Write valid YAML but invalid schema.
        yaml_file.write_text(
            yaml.dump({"metadata": {"sad_version": "bad"}}),
            encoding="utf-8",
        )
        with pytest.raises(RegistryValidationError):
            ArchitectureRegistry.reload()

        assert reg.generation == old_gen
        assert "K1" in reg.document.components

    def test_missing_file_retains_old_document(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        old_gen = reg.generation

        # Delete the file.
        yaml_file.unlink()
        with pytest.raises(FileNotFoundError):
            ArchitectureRegistry.reload()

        assert reg.generation == old_gen
        assert reg.document.metadata.sad_version == "1.0.0"

    def test_reload_succeeds_after_failed_reload(self, yaml_file: Path) -> None:
        """A failed reload doesn't poison subsequent reloads."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()

        # Corrupt → fail.
        yaml_file.write_text("bad: yaml: content:", encoding="utf-8")
        with pytest.raises((RegistryValidationError, Exception)):
            ArchitectureRegistry.reload()

        # Fix → succeed.
        _write_yaml(yaml_file, sad_version="9.0.0", comp_id="K1",
                     comp_name="Fixed")
        ArchitectureRegistry.reload()
        assert reg.document.metadata.sad_version == "9.0.0"
        assert reg.generation == 2


# ── Uninitialized reload ──────────────────────────────


class TestReloadUninitialized:
    """reload() on a fresh (never-loaded) registry."""

    def test_reload_without_prior_get(self, yaml_file: Path) -> None:
        """reload() can serve as the initial load."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.reload()
        assert isinstance(reg.document, ArchitectureDocument)
        assert reg.generation == 1
        assert ArchitectureRegistry.is_loaded()

    def test_reload_uninitialized_then_get(self, yaml_file: Path) -> None:
        """After reload() initializes, get() returns the same instance."""
        ArchitectureRegistry.configure(yaml_file)
        reg1 = ArchitectureRegistry.reload()
        reg2 = ArchitectureRegistry.get()
        assert reg1 is reg2


# ── Thread safety ─────────────────────────────────────


class TestReloadThreadSafety:
    """Concurrent reload + get operations."""

    def test_concurrent_reload_and_get(self, yaml_file: Path) -> None:
        """Mixed reload/get threads all see consistent state."""
        ArchitectureRegistry.configure(yaml_file)
        ArchitectureRegistry.get()

        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def reload_worker() -> None:
            try:
                barrier.wait(timeout=5)
                ArchitectureRegistry.reload()
            except Exception as e:
                errors.append(e)

        def get_worker() -> None:
            try:
                barrier.wait(timeout=5)
                reg = ArchitectureRegistry.get()
                # Must always be a valid document.
                assert isinstance(reg.document, ArchitectureDocument)
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reload_worker) for _ in range(4)]
            + [threading.Thread(target=get_worker) for _ in range(4)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_reloads_monotonic_generation(self, yaml_file: Path) -> None:
        """Serial reloads after concurrent ones still have monotonic generation."""
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        initial_gen = reg.generation

        # Fire several concurrent reloads.
        barrier = threading.Barrier(4)

        def worker() -> None:
            barrier.wait(timeout=5)
            ArchitectureRegistry.reload()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert reg.generation > initial_gen


# ── Lookups reflect reloaded data ─────────────────────


class TestReloadedLookups:
    """Task 2.7 lookups work correctly on reloaded data."""

    def test_get_component_after_reload(self, yaml_file: Path) -> None:
        ArchitectureRegistry.configure(yaml_file)
        reg = ArchitectureRegistry.get()
        assert reg.get_component("K1").name == "Original"

        _write_yaml(yaml_file, comp_id="K1", comp_name="Updated")
        ArchitectureRegistry.reload()
        assert reg.get_component("K1").name == "Updated"


# ── Integration with real architecture.yaml ───────────


class TestReloadIntegration:
    """Integration tests with the real architecture.yaml."""

    def test_real_yaml_reload_cycle(self, real_yaml: Path | None) -> None:
        """Load → reload → verify component count unchanged."""
        if real_yaml is None:
            pytest.skip("docs/architecture.yaml not found")
        ArchitectureRegistry.configure(real_yaml)
        reg = ArchitectureRegistry.get()
        count_before = reg.document.component_count
        gen_before = reg.generation

        ArchitectureRegistry.reload()

        assert reg.document.component_count == count_before
        assert reg.generation == gen_before + 1

    def test_real_yaml_generation_starts_at_one(self, real_yaml: Path | None) -> None:
        if real_yaml is None:
            pytest.skip("docs/architecture.yaml not found")
        ArchitectureRegistry.configure(real_yaml)
        reg = ArchitectureRegistry.get()
        assert reg.generation == 1
