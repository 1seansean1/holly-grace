"""Integration tests for ICD-aware wrong-decorator detection (Task 7.2).

These tests load real architecture.yaml with 49 ICD entries and verify
that the scanner detects wrong/mismatched decorators against ICD contracts.
"""

from __future__ import annotations

import textwrap
import types
from pathlib import Path

import pytest

from holly.arch.decorators import kernel_boundary
from holly.arch.registry import ArchitectureRegistry
from holly.arch.scanner import (
    FindingKind,
    ScanReport,
    _build_icd_index,
    generate_rules,
    scan_full,
    scan_module_icd,
    scan_source_icd,
    validate_icd_schema_ref,
)

# ── Fixtures ─────────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCH_YAML = REPO_ROOT / "docs" / "architecture.yaml"


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Reset registry before and after each test."""
    ArchitectureRegistry.reset()
    yield  # type: ignore[misc]
    ArchitectureRegistry.reset()


@pytest.fixture()
def registry() -> ArchitectureRegistry:
    """Load real architecture.yaml into the registry."""
    if not ARCH_YAML.exists():
        pytest.skip("architecture.yaml not found — run extraction first")
    ArchitectureRegistry.configure(ARCH_YAML)
    return ArchitectureRegistry.get()


@pytest.fixture()
def rules(registry: ArchitectureRegistry) -> list:
    """Generate rules from real architecture.yaml."""
    return generate_rules(registry)


@pytest.fixture()
def icd_index(registry: ArchitectureRegistry) -> dict:
    """Build ICD index from real architecture.yaml."""
    return _build_icd_index(registry)


# ── Real YAML integration tests ─────────────────────


class TestICDAwareRulesFromRealYAML:
    """Verify that rules generated from real YAML include ICD metadata."""

    def test_rules_have_icd_ids(self, rules: list) -> None:
        """At least some rules should have associated ICD IDs."""
        rules_with_icds = [r for r in rules if r.icd_ids]
        assert len(rules_with_icds) > 0, "No rules have ICD IDs attached"

    def test_kernel_component_has_icds(self, rules: list) -> None:
        """KERNEL component (L1) should have ICD associations."""
        kernel_rules = [r for r in rules if r.component_id == "KERNEL"]
        assert len(kernel_rules) == 1
        assert len(kernel_rules[0].icd_ids) > 0

    def test_core_component_has_icds(self, rules: list) -> None:
        """CORE component (L2) should have ICD associations."""
        core_rules = [r for r in rules if r.component_id == "CORE"]
        assert len(core_rules) == 1
        assert len(core_rules[0].icd_ids) > 0

    def test_icd_index_has_49_entries(self, icd_index: dict) -> None:
        """Real architecture.yaml has 49 ICD entries."""
        assert len(icd_index) == 49

    def test_icd_entry_has_components(self, icd_index: dict) -> None:
        """Every ICD entry has source and target components."""
        for icd_id, entry in icd_index.items():
            assert entry.source_component, f"{icd_id} missing source_component"
            assert entry.target_component, f"{icd_id} missing target_component"


class TestWrongDecoratorDetection:
    """Integration tests: detect intentionally-wrong decorators."""

    def test_correct_decorator_passes(self, rules: list, icd_index: dict) -> None:
        """Correctly decorated function: KERNEL with ICD-006 → no mismatch."""
        # ICD-006: CORE → KERNEL (boundary check request).
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-006")
            def validate_schema(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 0

    def test_wrong_decorator_kind_detected(self, rules: list, icd_index: dict) -> None:
        """Using @tenant_scoped on KERNEL (L1) → WRONG (expects kernel_boundary)."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import tenant_scoped

            @tenant_scoped(component_id="KERNEL")
            def validate_schema(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        wrong = [f for f in findings if f.kind == FindingKind.WRONG]
        assert len(wrong) == 1
        assert wrong[0].component_id == "KERNEL"
        assert wrong[0].expected_decorator == "kernel_boundary"
        assert wrong[0].actual_decorator == "tenant_scoped"

    def test_wrong_icd_ref_nonexistent(self, rules: list, icd_index: dict) -> None:
        """Referencing a nonexistent ICD produces ICD_MISMATCH."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-999")
            def validate_schema(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 1
        assert "ICD-999" in icd_mismatches[0].message
        assert "does not exist" in icd_mismatches[0].message

    def test_wrong_icd_component_mismatch(self, rules: list, icd_index: dict) -> None:
        """Decorator references ICD that doesn't involve its component."""
        # ICD-001 is UI → ALB, not KERNEL.
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-001")
            def validate_schema(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 1
        assert "KERNEL" in icd_mismatches[0].message
        assert "not a participant" in icd_mismatches[0].message

    def test_combined_wrong_kind_and_icd_mismatch(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Both WRONG (kind) and ICD_MISMATCH (ref) in one finding set."""
        # Wrong decorator kind (tenant_scoped on KERNEL) + nonexistent ICD.
        source = textwrap.dedent('''\
            from holly.arch.decorators import tenant_scoped

            @tenant_scoped(component_id="KERNEL", icd_schema="ICD-999")
            def bad_function(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        kinds = {f.kind for f in findings}
        assert FindingKind.WRONG in kinds
        assert FindingKind.ICD_MISMATCH in kinds

    def test_no_icd_schema_no_icd_check(self, rules: list, icd_index: dict) -> None:
        """Decorator without icd_schema produces no ICD_MISMATCH."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1")
            def validate_schema(payload):
                pass
        ''')
        findings = scan_full(source, "test_module", rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 0


class TestScanSourceICDStandalone:
    """Unit-style tests for scan_source_icd function."""

    def test_empty_source(self, rules: list, icd_index: dict) -> None:
        """Empty source produces no findings."""
        assert scan_source_icd("", "empty", rules, icd_index) == []

    def test_syntax_error(self, rules: list, icd_index: dict) -> None:
        """Invalid Python produces no findings (no crash)."""
        assert scan_source_icd("def (:", "bad", rules, icd_index) == []

    def test_non_holly_decorator_ignored(self, rules: list, icd_index: dict) -> None:
        """Non-Holly decorators are ignored."""
        source = textwrap.dedent('''\
            def custom_decorator(**kwargs):
                def inner(fn):
                    return fn
                return inner

            @custom_decorator(icd_schema="ICD-006", component_id="KERNEL")
            def my_func():
                pass
        ''')
        findings = scan_source_icd(source, "test", rules, icd_index)
        assert len(findings) == 0


class TestValidateICDSchemaRef:
    """Unit tests for validate_icd_schema_ref."""

    def test_no_icd_schema_returns_none(self, rules: list, icd_index: dict) -> None:
        """Missing icd_schema → no finding."""
        rules_by_comp = {r.component_id: r for r in rules}
        result = validate_icd_schema_ref(
            {"kind": "kernel_boundary", "component_id": "KERNEL"},
            rules_by_comp, icd_index,
        )
        assert result is None

    def test_empty_icd_schema_returns_none(self, rules: list, icd_index: dict) -> None:
        """Empty string icd_schema → no finding."""
        rules_by_comp = {r.component_id: r for r in rules}
        result = validate_icd_schema_ref(
            {"kind": "kernel_boundary", "component_id": "KERNEL", "icd_schema": ""},
            rules_by_comp, icd_index,
        )
        assert result is None

    def test_valid_icd_matching_component(self, rules: list, icd_index: dict) -> None:
        """Valid ICD with matching component → no finding."""
        rules_by_comp = {r.component_id: r for r in rules}
        # ICD-006: CORE → KERNEL. Use KERNEL as component_id.
        result = validate_icd_schema_ref(
            {"kind": "kernel_boundary", "component_id": "KERNEL",
             "icd_schema": "ICD-006"},
            rules_by_comp, icd_index,
        )
        assert result is None

    def test_nonexistent_icd_returns_mismatch(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Nonexistent ICD → ICD_MISMATCH."""
        rules_by_comp = {r.component_id: r for r in rules}
        result = validate_icd_schema_ref(
            {"kind": "kernel_boundary", "component_id": "KERNEL",
             "icd_schema": "ICD-FAKE"},
            rules_by_comp, icd_index,
            module_path="test", symbol_name="func",
        )
        assert result is not None
        assert result.kind == FindingKind.ICD_MISMATCH
        assert "ICD-FAKE" in result.message

    def test_wrong_component_returns_mismatch(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Component not in ICD's source/target → ICD_MISMATCH."""
        rules_by_comp = {r.component_id: r for r in rules}
        # ICD-001 is UI→ALB, not KERNEL.
        result = validate_icd_schema_ref(
            {"kind": "kernel_boundary", "component_id": "KERNEL",
             "icd_schema": "ICD-001"},
            rules_by_comp, icd_index,
            module_path="test", symbol_name="func",
        )
        assert result is not None
        assert result.kind == FindingKind.ICD_MISMATCH
        assert "not a participant" in result.message


class TestScanModuleICD:
    """Integration test for scan_module_icd with real decorators."""

    def test_module_with_correct_icd(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Module-level scan: correctly decorated function passes."""
        # ICD-006: CORE → KERNEL.
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        @kernel_boundary(
            component_id="KERNEL", gate_id="K1",
            icd_schema="ICD-006", validate=False,
        )
        def good_func(payload: dict) -> dict:
            return payload

        mod.good_func = good_func  # type: ignore[attr-defined]

        findings = scan_module_icd(mod, rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 0

    def test_module_with_wrong_icd(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Module-level scan: decorator with wrong ICD ref detected."""
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        # ICD-001 is UI→ALB, KERNEL is not a participant.
        @kernel_boundary(
            component_id="KERNEL", gate_id="K1",
            icd_schema="ICD-001", validate=False,
        )
        def bad_func(payload: dict) -> dict:
            return payload

        mod.bad_func = bad_func  # type: ignore[attr-defined]

        findings = scan_module_icd(mod, rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 1
        assert "not a participant" in icd_mismatches[0].message

    def test_module_with_nonexistent_icd(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Module-level scan: nonexistent ICD ref detected."""
        mod = types.ModuleType("test_mod")
        mod.__name__ = "test_mod"

        @kernel_boundary(
            component_id="KERNEL", gate_id="K1",
            icd_schema="ICD-GHOST", validate=False,
        )
        def ghost_func(payload: dict) -> dict:
            return payload

        mod.ghost_func = ghost_func  # type: ignore[attr-defined]

        findings = scan_module_icd(mod, rules, icd_index)
        icd_mismatches = [f for f in findings if f.kind == FindingKind.ICD_MISMATCH]
        assert len(icd_mismatches) == 1
        assert "does not exist" in icd_mismatches[0].message


class TestScanReportICDMismatch:
    """Verify ScanReport correctly accounts for ICD_MISMATCH."""

    def test_icd_mismatch_count(self, rules: list, icd_index: dict) -> None:
        """ICD_MISMATCH findings are counted and flag report as not clean."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-999")
            def bad_func(payload):
                pass
        ''')
        report = ScanReport(rules_applied=len(rules))
        report.findings.extend(scan_full(source, "test", rules, icd_index))
        assert report.icd_mismatch_count >= 1
        assert not report.is_clean

    def test_clean_report_with_valid_icd(self, rules: list, icd_index: dict) -> None:
        """Report with only OK findings is clean."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1")
            def good_func(payload):
                pass
        ''')
        report = ScanReport(rules_applied=len(rules))
        report.findings.extend(scan_full(source, "test", rules, icd_index))
        wrong = [f for f in report.findings if f.kind in (
            FindingKind.WRONG, FindingKind.ICD_MISMATCH,
        )]
        assert len(wrong) == 0


class TestEdgeCases:
    """Edge cases for ICD validation."""

    def test_decorator_no_component_id_with_icd(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Decorator with icd_schema but no component_id — ICD exists check only."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(gate_id="K1", icd_schema="ICD-006")
            def func(payload):
                pass
        ''')
        findings = scan_source_icd(source, "test", rules, icd_index)
        # ICD-006 exists, no component_id to cross-check → no mismatch.
        assert len(findings) == 0

    def test_multiple_decorators_both_checked(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Multiple Holly decorators on one function: each ICD ref checked."""
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary, eval_gated

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-999")
            @eval_gated(component_id="K8", gate_id="K8", icd_schema="ICD-888")
            def dual_gated(payload):
                pass
        ''')
        findings = scan_source_icd(source, "test", rules, icd_index)
        # Both ICD-999 and ICD-888 don't exist.
        assert len(findings) >= 2
        for f in findings:
            assert f.kind == FindingKind.ICD_MISMATCH

    @pytest.mark.parametrize("icd_id", [
        "ICD-001", "ICD-010", "ICD-025", "ICD-049",
    ])
    def test_real_icd_exists(self, icd_index: dict, icd_id: str) -> None:
        """Parametrized: verify specific ICDs exist in the index."""
        assert icd_id in icd_index, f"{icd_id} not found in ICD index"

    def test_icd_with_source_component_match(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Component matching as source_component of ICD passes."""
        # ICD-006: source=CORE. Use CORE as component_id.
        source = textwrap.dedent('''\
            from holly.arch.decorators import tenant_scoped

            @tenant_scoped(component_id="CORE", icd_schema="ICD-006")
            def core_func(payload):
                pass
        ''')
        findings = scan_source_icd(source, "test", rules, icd_index)
        assert len(findings) == 0

    def test_icd_with_target_component_match(
        self, rules: list, icd_index: dict,
    ) -> None:
        """Component matching as target_component of ICD passes."""
        # ICD-006: target=KERNEL. Use KERNEL as component_id.
        source = textwrap.dedent('''\
            from holly.arch.decorators import kernel_boundary

            @kernel_boundary(component_id="KERNEL", gate_id="K1", icd_schema="ICD-006")
            def kernel_func(payload):
                pass
        ''')
        findings = scan_source_icd(source, "test", rules, icd_index)
        assert len(findings) == 0
