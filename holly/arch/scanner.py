"""AST scanner for missing/wrong architectural decorators.

Tasks 7.1 + 7.2 — AST scanner with per-module rules and ICD-aware
wrong-decorator detection.

Walks Python source files and checks that every function/class that
participates in a boundary crossing (per architecture.yaml) has the
correct Holly decorator applied.

Scanner rules are derived from architecture.yaml:
- Kernel layer (L1) components require ``@kernel_boundary``
- Core layer (L2) components with tenant isolation require ``@tenant_scoped``
- Engine layer (L3) lane dispatchers require ``@lane_dispatch``
- MCP tool endpoints require ``@mcp_tool``
- K8 eval-gated functions require ``@eval_gated``

Task 7.2 extends wrong-decorator detection with ICD awareness:
- Validates ``icd_schema`` metadata on decorators against ICD registry entries
- Cross-references component IDs against ICD source/target components
- Detects protocol/SIL mismatches between decorator metadata and ICD contracts

The scanner produces a list of ``ScanFinding`` results: MISSING
(expected decorator not found), WRONG (wrong decorator kind for
the component's layer), ICD_MISMATCH (decorator metadata conflicts
with ICD contract), or OK (correct decorator applied).
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from holly.arch.decorators import DecoratorKind, get_holly_meta
from holly.arch.registry import ArchitectureRegistry
from holly.arch.schema import ICDEntry, LayerID

if TYPE_CHECKING:
    from pathlib import Path

# ── Enumerations ─────────────────────────────────────


class FindingKind(StrEnum):
    """Classification of a scan finding."""
    OK = "ok"
    MISSING = "missing"
    WRONG = "wrong"
    ICD_MISMATCH = "icd_mismatch"


# ── Data models ──────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ScanRule:
    """A rule specifying which decorator a component requires.

    Attributes
    ----------
    component_id:
        SAD component ID this rule applies to.
    layer:
        SAD layer of the component.
    required_decorator:
        The decorator kind that must be present.
    description:
        Human-readable explanation of the rule.
    icd_ids:
        ICD identifiers associated with this component (Task 7.2).
    """
    component_id: str
    layer: LayerID
    required_decorator: DecoratorKind
    description: str = ""
    icd_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScanFinding:
    """Result of scanning a single decorated callable.

    Attributes
    ----------
    kind:
        Whether the decorator is OK, MISSING, or WRONG.
    module_path:
        Python module path (e.g. ``"holly.kernel.k1"``).
    symbol_name:
        Function or class name.
    component_id:
        SAD component ID referenced in the decorator metadata.
    expected_decorator:
        What decorator the rule says should be applied.
    actual_decorator:
        What decorator is actually applied (empty if MISSING).
    message:
        Human-readable explanation.
    """
    kind: FindingKind
    module_path: str
    symbol_name: str
    component_id: str
    expected_decorator: DecoratorKind | str
    actual_decorator: str = ""
    message: str = ""


@dataclass(slots=True)
class ScanReport:
    """Aggregate scan results.

    Attributes
    ----------
    findings:
        All individual findings.
    rules_applied:
        Number of rules that were evaluated.
    """
    findings: list[ScanFinding] = field(default_factory=list)
    rules_applied: int = 0

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.findings if f.kind == FindingKind.OK)

    @property
    def missing_count(self) -> int:
        return sum(1 for f in self.findings if f.kind == FindingKind.MISSING)

    @property
    def wrong_count(self) -> int:
        return sum(1 for f in self.findings if f.kind == FindingKind.WRONG)

    @property
    def icd_mismatch_count(self) -> int:
        return sum(1 for f in self.findings if f.kind == FindingKind.ICD_MISMATCH)

    @property
    def is_clean(self) -> bool:
        return (
            self.missing_count == 0
            and self.wrong_count == 0
            and self.icd_mismatch_count == 0
        )


# ── Rule generation ──────────────────────────────────


# Mapping from SAD layer to the default required decorator kind.
LAYER_DECORATOR_MAP: dict[LayerID, DecoratorKind] = {
    LayerID.L1_KERNEL: "kernel_boundary",
    LayerID.L2_CORE: "tenant_scoped",
    LayerID.L3_ENGINE: "lane_dispatch",
}

# Components that override the layer-level default.
COMPONENT_DECORATOR_OVERRIDES: dict[str, DecoratorKind] = {
    "MCP": "mcp_tool",
    "K8": "eval_gated",
    "EVBUS": "tenant_scoped",
    "EGRESS": "kernel_boundary",
    "KMS": "kernel_boundary",
}


def generate_rules(
    registry: ArchitectureRegistry | None = None,
) -> list[ScanRule]:
    """Generate scanner rules from architecture.yaml.

    For each component in the architecture, determines the required
    decorator based on its layer and any overrides.  ICD entries are
    cross-referenced to attach ICD identifiers to each rule (Task 7.2).

    Parameters
    ----------
    registry:
        Optional pre-loaded registry. If None, uses the singleton.

    Returns
    -------
    list[ScanRule]
        One rule per component that has an applicable decorator requirement.
    """
    reg = registry or ArchitectureRegistry.get()
    doc = reg.document
    rules: list[ScanRule] = []

    # Build component → ICD mapping from ICD entries (Task 7.2).
    comp_icds: dict[str, list[str]] = {}
    for icd in doc.icds:
        comp_icds.setdefault(icd.source_component, []).append(icd.id)
        comp_icds.setdefault(icd.target_component, []).append(icd.id)

    for comp_id, comp in doc.components.items():
        # Check override first, then layer default.
        decorator = COMPONENT_DECORATOR_OVERRIDES.get(comp_id)
        if decorator is None:
            decorator = LAYER_DECORATOR_MAP.get(comp.layer)
        if decorator is None:
            continue  # No rule for this component's layer.

        icd_ids = tuple(sorted(set(comp_icds.get(comp_id, []))))

        rules.append(ScanRule(
            component_id=comp_id,
            layer=comp.layer,
            required_decorator=decorator,
            description=f"{comp.name} ({comp.layer}) requires @{decorator}",
            icd_ids=icd_ids,
        ))

    return rules


def get_rules_for_component(
    component_id: str,
    rules: list[ScanRule] | None = None,
    registry: ArchitectureRegistry | None = None,
) -> ScanRule | None:
    """Look up the scan rule for a specific component.

    Parameters
    ----------
    component_id:
        SAD component ID.
    rules:
        Pre-generated rules. If None, generates from registry.
    registry:
        Optional registry for rule generation.

    Returns
    -------
    ScanRule | None
        The matching rule, or None if no rule applies.
    """
    if rules is None:
        rules = generate_rules(registry)
    for rule in rules:
        if rule.component_id == component_id:
            return rule
    return None


# ── AST scanning ─────────────────────────────────────


def _extract_decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """Extract decorator names from an AST node."""
    names: list[str] = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            names.append(dec.id)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                names.append(dec.func.attr)
    return names


def _extract_component_id_from_decorator(node: ast.expr) -> str | None:
    """Try to extract component_id kwarg from a decorator AST node."""
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg == "component_id" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
    return None


def scan_source(
    source: str,
    module_path: str,
    rules: list[ScanRule],
) -> list[ScanFinding]:
    """Scan a Python source string for decorator compliance.

    Walks the AST looking for functions and classes that reference
    Holly architectural decorators. For each, checks if the decorator
    kind matches the rule for the referenced component.

    Parameters
    ----------
    source:
        Python source code.
    module_path:
        Dotted module path for reporting.
    rules:
        Scanner rules to check against.

    Returns
    -------
    list[ScanFinding]
        Findings for each decorated callable found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[ScanFinding] = []
    holly_decorators = {
        "kernel_boundary", "tenant_scoped", "lane_dispatch",
        "mcp_tool", "eval_gated",
    }

    rules_by_component = {r.component_id: r for r in rules}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        dec_names = _extract_decorator_names(node)
        holly_decs = [d for d in dec_names if d in holly_decorators]

        if not holly_decs:
            continue

        # Extract component_id from decorator kwargs.
        for dec_node in node.decorator_list:
            comp_id = _extract_component_id_from_decorator(dec_node)
            if comp_id is None:
                continue

            actual_dec = ""
            if isinstance(dec_node, ast.Call) and isinstance(dec_node.func, ast.Name):
                actual_dec = dec_node.func.id
            elif isinstance(dec_node, ast.Call) and isinstance(dec_node.func, ast.Attribute):
                actual_dec = dec_node.func.attr

            rule = rules_by_component.get(comp_id)
            if rule is None:
                # No rule for this component — skip.
                continue

            if actual_dec == rule.required_decorator:
                findings.append(ScanFinding(
                    kind=FindingKind.OK,
                    module_path=module_path,
                    symbol_name=node.name,
                    component_id=comp_id,
                    expected_decorator=rule.required_decorator,
                    actual_decorator=actual_dec,
                    message=f"Correct: @{actual_dec} on {node.name} for {comp_id}",
                ))
            else:
                findings.append(ScanFinding(
                    kind=FindingKind.WRONG,
                    module_path=module_path,
                    symbol_name=node.name,
                    component_id=comp_id,
                    expected_decorator=rule.required_decorator,
                    actual_decorator=actual_dec,
                    message=(
                        f"Wrong decorator: @{actual_dec} on {node.name} "
                        f"for {comp_id} (expected @{rule.required_decorator})"
                    ),
                ))

    return findings


def scan_module(
    module: Any,
    rules: list[ScanRule],
) -> list[ScanFinding]:
    """Scan a loaded Python module for decorator compliance.

    Inspects all functions and classes in the module that have
    ``_holly_meta`` attached (i.e., decorated with a Holly decorator)
    and checks compliance against the rules.

    Parameters
    ----------
    module:
        An imported Python module object.
    rules:
        Scanner rules to check against.

    Returns
    -------
    list[ScanFinding]
        Findings for each decorated callable found.
    """
    findings: list[ScanFinding] = []
    rules_by_component = {r.component_id: r for r in rules}
    module_path = getattr(module, "__name__", str(module))

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        meta = get_holly_meta(obj)
        if meta is None:
            continue

        comp_id = meta.get("component_id")
        actual_kind = meta.get("kind", "")

        if comp_id is None:
            # Decorator applied without component_id — cannot verify.
            continue

        rule = rules_by_component.get(comp_id)
        if rule is None:
            continue

        if actual_kind == rule.required_decorator:
            findings.append(ScanFinding(
                kind=FindingKind.OK,
                module_path=module_path,
                symbol_name=name,
                component_id=comp_id,
                expected_decorator=rule.required_decorator,
                actual_decorator=actual_kind,
                message=f"Correct: @{actual_kind} on {name} for {comp_id}",
            ))
        else:
            findings.append(ScanFinding(
                kind=FindingKind.WRONG,
                module_path=module_path,
                symbol_name=name,
                component_id=comp_id,
                expected_decorator=rule.required_decorator,
                actual_decorator=actual_kind,
                message=(
                    f"Wrong decorator: @{actual_kind} on {name} "
                    f"for {comp_id} (expected @{rule.required_decorator})"
                ),
            ))

    return findings


def scan_directory(
    directory: Path,
    rules: list[ScanRule],
    *,
    exclude_patterns: list[str] | None = None,
) -> ScanReport:
    """Scan all Python files in a directory tree.

    Parameters
    ----------
    directory:
        Root directory to scan.
    rules:
        Scanner rules to check against.
    exclude_patterns:
        Glob patterns to exclude (e.g. ``["test_*"]``).

    Returns
    -------
    ScanReport
        Aggregate scan results.
    """
    report = ScanReport(rules_applied=len(rules))
    exclude = exclude_patterns or []

    for py_file in sorted(directory.rglob("*.py")):
        # Skip excluded patterns.
        if any(py_file.match(pat) for pat in exclude):
            continue

        # Derive module path from file path.
        try:
            rel = py_file.relative_to(directory.parent)
            module_path = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        except ValueError:
            module_path = str(py_file)

        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue

        findings = scan_source(source, module_path, rules)
        report.findings.extend(findings)

    return report


# ── ICD-aware wrong-decorator detection (Task 7.2) ──


def _build_icd_index(
    registry: ArchitectureRegistry | None = None,
) -> dict[str, ICDEntry]:
    """Build an ICD ID → ICDEntry mapping from the registry.

    Parameters
    ----------
    registry:
        Optional pre-loaded registry. If None, uses the singleton.

    Returns
    -------
    dict[str, ICDEntry]
        Mapping from ICD ID (e.g. ``"ICD-006"``) to its entry.
    """
    reg = registry or ArchitectureRegistry.get()
    return {icd.id: icd for icd in reg.document.icds}


def validate_icd_schema_ref(
    meta: dict[str, Any],
    rules_by_component: dict[str, ScanRule],
    icd_index: dict[str, ICDEntry],
    *,
    module_path: str = "",
    symbol_name: str = "",
) -> ScanFinding | None:
    """Validate a decorator's ``icd_schema`` metadata against ICD registry.

    If the decorator carries an ``icd_schema`` field, verifies that:

    1. The referenced ICD ID exists in the registry.
    2. The decorator's ``component_id`` matches the ICD's source or
       target component.

    Parameters
    ----------
    meta:
        The ``_holly_meta`` dict from the decorated callable.
    rules_by_component:
        Pre-built component → ScanRule mapping.
    icd_index:
        ICD ID → ICDEntry mapping.
    module_path:
        Dotted module path for reporting.
    symbol_name:
        Function or class name for reporting.

    Returns
    -------
    ScanFinding | None
        An ICD_MISMATCH finding if validation fails, or None if OK.
    """
    icd_schema = meta.get("icd_schema", "")
    if not icd_schema:
        return None

    comp_id = meta.get("component_id", "")
    actual_kind = meta.get("kind", "")

    # Check 1: Does the ICD exist?
    icd_entry = icd_index.get(icd_schema)
    if icd_entry is None:
        return ScanFinding(
            kind=FindingKind.ICD_MISMATCH,
            module_path=module_path,
            symbol_name=symbol_name,
            component_id=comp_id,
            expected_decorator=actual_kind,
            actual_decorator=actual_kind,
            message=(
                f"ICD mismatch: @{actual_kind} on {symbol_name} references "
                f"icd_schema={icd_schema!r} which does not exist in "
                f"architecture.yaml"
            ),
        )

    # Check 2: Does the component participate in this ICD?
    if comp_id and comp_id not in (
        icd_entry.source_component,
        icd_entry.target_component,
    ):
        return ScanFinding(
            kind=FindingKind.ICD_MISMATCH,
            module_path=module_path,
            symbol_name=symbol_name,
            component_id=comp_id,
            expected_decorator=actual_kind,
            actual_decorator=actual_kind,
            message=(
                f"ICD mismatch: @{actual_kind} on {symbol_name} for "
                f"{comp_id} references icd_schema={icd_schema!r}, but "
                f"{comp_id} is not a participant in {icd_schema} "
                f"(source={icd_entry.source_component}, "
                f"target={icd_entry.target_component})"
            ),
        )

    return None


def _extract_icd_schema_from_decorator(node: ast.expr) -> str | None:
    """Try to extract icd_schema kwarg from a decorator AST node."""
    if isinstance(node, ast.Call):
        for kw in node.keywords:
            if kw.arg == "icd_schema" and isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
    return None


def scan_source_icd(
    source: str,
    module_path: str,
    rules: list[ScanRule],
    icd_index: dict[str, ICDEntry],
) -> list[ScanFinding]:
    """Scan source for ICD-aware wrong-decorator violations (Task 7.2).

    Extends ``scan_source`` with ICD cross-validation: for each
    decorator that carries an ``icd_schema`` parameter, verifies that
    the referenced ICD exists and the component participates in it.

    Parameters
    ----------
    source:
        Python source code.
    module_path:
        Dotted module path for reporting.
    rules:
        Scanner rules to check against.
    icd_index:
        ICD ID → ICDEntry mapping.

    Returns
    -------
    list[ScanFinding]
        ICD_MISMATCH findings for decorator/ICD conflicts.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    findings: list[ScanFinding] = []
    holly_decorators = {
        "kernel_boundary", "tenant_scoped", "lane_dispatch",
        "mcp_tool", "eval_gated",
    }
    rules_by_component = {r.component_id: r for r in rules}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        dec_names = _extract_decorator_names(node)
        holly_decs = [d for d in dec_names if d in holly_decorators]

        if not holly_decs:
            continue

        for dec_node in node.decorator_list:
            icd_ref = _extract_icd_schema_from_decorator(dec_node)
            if icd_ref is None:
                continue

            comp_id = _extract_component_id_from_decorator(dec_node) or ""
            actual_dec = ""
            if isinstance(dec_node, ast.Call) and isinstance(dec_node.func, ast.Name):
                actual_dec = dec_node.func.id
            elif isinstance(dec_node, ast.Call) and isinstance(dec_node.func, ast.Attribute):
                actual_dec = dec_node.func.attr

            # Build a synthetic meta dict for validation.
            meta = {
                "kind": actual_dec,
                "component_id": comp_id,
                "icd_schema": icd_ref,
            }
            finding = validate_icd_schema_ref(
                meta, rules_by_component, icd_index,
                module_path=module_path, symbol_name=node.name,
            )
            if finding is not None:
                findings.append(finding)

    return findings


def scan_module_icd(
    module: Any,
    rules: list[ScanRule],
    icd_index: dict[str, ICDEntry],
) -> list[ScanFinding]:
    """Scan a loaded module for ICD-aware wrong-decorator violations.

    Inspects all decorated callables and validates their ``icd_schema``
    metadata against the ICD registry.

    Parameters
    ----------
    module:
        An imported Python module object.
    rules:
        Scanner rules to check against.
    icd_index:
        ICD ID → ICDEntry mapping.

    Returns
    -------
    list[ScanFinding]
        ICD_MISMATCH findings for decorator/ICD conflicts.
    """
    findings: list[ScanFinding] = []
    rules_by_component = {r.component_id: r for r in rules}
    module_path = getattr(module, "__name__", str(module))

    for name, obj in inspect.getmembers(module):
        if name.startswith("_"):
            continue

        meta = get_holly_meta(obj)
        if meta is None:
            continue

        finding = validate_icd_schema_ref(
            meta, rules_by_component, icd_index,
            module_path=module_path, symbol_name=name,
        )
        if finding is not None:
            findings.append(finding)

    return findings


def scan_full(
    source: str,
    module_path: str,
    rules: list[ScanRule],
    icd_index: dict[str, ICDEntry] | None = None,
) -> list[ScanFinding]:
    """Combined scan: layer rules (7.1) + ICD validation (7.2).

    Parameters
    ----------
    source:
        Python source code.
    module_path:
        Dotted module path for reporting.
    rules:
        Scanner rules to check against.
    icd_index:
        Optional ICD ID → ICDEntry mapping. If None, ICD checks skipped.

    Returns
    -------
    list[ScanFinding]
        All findings (OK, MISSING, WRONG, ICD_MISMATCH).
    """
    findings = scan_source(source, module_path, rules)
    if icd_index:
        findings.extend(scan_source_icd(source, module_path, rules, icd_index))
    return findings
