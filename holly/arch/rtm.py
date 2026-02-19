"""Requirements Traceability Matrix (RTM) generator.

Task 10.2 — Build RTM generator that walks the codebase and produces
a living traceability matrix.

The RTM chain:

    Component → Decorator → ICD → Test → Status

The generator:

1. Reads the architecture registry (components, ICDs, layers).
2. Walks the source tree via AST to discover all Holly-decorated
   callables and their metadata (component_id, decorator kind,
   icd_schema references).
3. Walks the test tree to discover test functions and map them to
   components via naming conventions and decorator references.
4. Produces an ``RTM`` — a list of ``RTMEntry`` rows that can be
   serialised to CSV or inspected programmatically.

Each entry links:

- **component_id** → SAD component
- **layer** → architectural layer
- **decorator_kind** → which Holly decorator is applied
- **module_path / symbol** → implementation location
- **icd_ids** → interface contracts traversed
- **test_ids** → tests exercising this decorated callable
- **status** → COVERED, PARTIAL, UNCOVERED
"""

from __future__ import annotations

import ast
import csv
import io
import os
from dataclasses import dataclass, field

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    from strenum import StrEnum  # type: ignore[no-redef]
from typing import TYPE_CHECKING

from holly.arch.registry import ArchitectureRegistry

if TYPE_CHECKING:
    from pathlib import Path


# ═══════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════


class CoverageStatus(StrEnum):
    """Traceability status for an RTM entry."""

    COVERED = "covered"
    PARTIAL = "partial"
    UNCOVERED = "uncovered"


# ═══════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class DecoratedSymbol:
    """A decorated callable discovered in the source tree."""

    module_path: str
    symbol_name: str
    decorator_kind: str
    component_id: str
    icd_schema: str
    line: int


@dataclass(frozen=True, slots=True)
class TestReference:
    """A test function discovered in the test tree."""

    test_file: str
    test_class: str
    test_function: str
    references_component: str
    references_module: str


@dataclass(slots=True)
class RTMEntry:
    """A single row in the Requirements Traceability Matrix."""

    component_id: str
    component_name: str
    layer: str
    decorator_kind: str
    module_path: str
    symbol_name: str
    icd_ids: list[str] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)
    status: CoverageStatus = CoverageStatus.UNCOVERED

    @property
    def test_count(self) -> int:
        """Number of tests covering this entry."""
        return len(self.test_ids)


@dataclass(slots=True)
class RTM:
    """The full Requirements Traceability Matrix."""

    entries: list[RTMEntry] = field(default_factory=list)
    component_count: int = 0
    decorated_count: int = 0
    test_count: int = 0

    @property
    def covered_count(self) -> int:
        """Entries with at least one test."""
        return sum(1 for e in self.entries if e.status == CoverageStatus.COVERED)

    @property
    def partial_count(self) -> int:
        """Entries with tests but missing ICD coverage."""
        return sum(1 for e in self.entries if e.status == CoverageStatus.PARTIAL)

    @property
    def uncovered_count(self) -> int:
        """Entries with zero tests."""
        return sum(1 for e in self.entries if e.status == CoverageStatus.UNCOVERED)

    @property
    def coverage_ratio(self) -> float:
        """Fraction of entries that are COVERED."""
        total = len(self.entries)
        return self.covered_count / total if total > 0 else 0.0

    def to_csv(self) -> str:
        """Serialise the RTM to CSV."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "component_id",
            "component_name",
            "layer",
            "decorator_kind",
            "module_path",
            "symbol_name",
            "icd_ids",
            "test_ids",
            "test_count",
            "status",
        ])
        for entry in self.entries:
            writer.writerow([
                entry.component_id,
                entry.component_name,
                entry.layer,
                entry.decorator_kind,
                entry.module_path,
                entry.symbol_name,
                ";".join(entry.icd_ids),
                ";".join(entry.test_ids),
                entry.test_count,
                entry.status,
            ])
        return buf.getvalue()


# ═══════════════════════════════════════════════════════════
# AST walkers
# ═══════════════════════════════════════════════════════════

# Holly decorator names we search for in the AST.
_HOLLY_DECORATORS: set[str] = {
    "kernel_boundary",
    "tenant_scoped",
    "lane_dispatch",
    "mcp_tool",
    "eval_gated",
}


def _extract_keyword_str(
    keywords: list[ast.keyword],
    key: str,
) -> str:
    """Extract a string keyword argument from decorator kwargs."""
    for kw in keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return ""


def discover_decorated_symbols(
    root: Path,
    *,
    package: str = "holly",
) -> list[DecoratedSymbol]:
    """Walk the source tree and find all Holly-decorated callables.

    Parses each ``.py`` file's AST, finds functions and classes with
    decorators matching the Holly set, and extracts metadata from
    keyword arguments.

    Parameters
    ----------
    root:
        Repository root directory.
    package:
        Top-level package name.

    Returns
    -------
    list[DecoratedSymbol]:
        All decorated callables found.
    """
    src_root = root / package.replace(".", os.sep)
    if not src_root.exists():
        return []

    symbols: list[DecoratedSymbol] = []

    for py_file in sorted(src_root.rglob("*.py")):
        rel = py_file.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        module_path = ".".join(parts)

        source = py_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue

            for dec in node.decorator_list:
                dec_name = ""
                keywords: list[ast.keyword] = []

                if isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Name):
                        dec_name = dec.func.id
                    elif isinstance(dec.func, ast.Attribute):
                        dec_name = dec.func.attr
                    keywords = dec.keywords
                elif isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr

                if dec_name not in _HOLLY_DECORATORS:
                    continue

                component_id = _extract_keyword_str(keywords, "component_id")
                icd_schema = _extract_keyword_str(keywords, "icd_schema")

                symbols.append(DecoratedSymbol(
                    module_path=module_path,
                    symbol_name=node.name,
                    decorator_kind=dec_name,
                    component_id=component_id,
                    icd_schema=icd_schema,
                    line=node.lineno,
                ))

    return symbols


def discover_tests(
    root: Path,
    *,
    test_dir: str = "tests",
) -> list[TestReference]:
    """Walk the test tree and discover test functions.

    Extracts test function names and attempts to infer which
    component/module they exercise based on:

    1. Import statements referencing ``holly.*`` modules.
    2. Test class/function names containing component references.

    Parameters
    ----------
    root:
        Repository root.
    test_dir:
        Relative path to the test directory.

    Returns
    -------
    list[TestReference]:
        All test functions found.
    """
    test_root = root / test_dir
    if not test_root.exists():
        return []

    tests: list[TestReference] = []

    for py_file in sorted(test_root.rglob("test_*.py")):
        rel_path = str(py_file.relative_to(root))
        source = py_file.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        # Collect holly module imports for reference mapping.
        holly_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("holly."):
                        holly_imports.add(alias.name)
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("holly.")
            ):
                holly_imports.add(node.module)

        # Extract the primary holly module reference (most specific).
        primary_module = ""
        for imp in sorted(holly_imports, key=len, reverse=True):
            if not imp.startswith("holly.arch"):
                primary_module = imp
                break
        if not primary_module and holly_imports:
            primary_module = sorted(holly_imports, key=len, reverse=True)[0]

        # Infer component from file name or imports.
        component_ref = _infer_component_from_filename(py_file.stem)

        # Walk AST to find test functions.
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                for item in node.body:
                    if (
                        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name.startswith("test_")
                    ):
                        tests.append(TestReference(
                                test_file=rel_path,
                                test_class=class_name,
                                test_function=item.name,
                                references_component=component_ref,
                                references_module=primary_module,
                            ))
            elif (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                and node.col_offset == 0
            ):
                tests.append(TestReference(
                            test_file=rel_path,
                            test_class="",
                            test_function=node.name,
                            references_component=component_ref,
                            references_module=primary_module,
                        ))

    return tests


# Component name extraction from test file names.
_TEST_FILE_COMPONENT_MAP: dict[str, str] = {
    "test_k1": "K1",
    "test_k8": "K8",
    "test_k8_eval_gate": "K8",
    "test_decorators": "KERNEL",
    "test_scanner": "KERNEL",
    "test_scanner_icd": "KERNEL",
    "test_pipeline_k1": "K1",
    "test_contract_fixtures": "KERNEL",
    "test_fitness": "KERNEL",
    "test_icd_models": "KERNEL",
    "test_icd_registry": "KERNEL",
    "test_sad_extract": "KERNEL",
    "test_schema_registry": "KERNEL",
    "test_gantt": "KERNEL",
    "test_manifest_parser": "KERNEL",
    "test_progress": "KERNEL",
    "test_registry": "KERNEL",
    "test_sil_parser": "KERNEL",
    "test_spiral_gate": "KERNEL",
}


def _infer_component_from_filename(stem: str) -> str:
    """Infer component reference from test file name stem."""
    return _TEST_FILE_COMPONENT_MAP.get(stem, "")


# ═══════════════════════════════════════════════════════════
# RTM generation
# ═══════════════════════════════════════════════════════════


def generate_rtm(
    root: Path,
    *,
    package: str = "holly",
    test_dir: str = "tests",
) -> RTM:
    """Generate the Requirements Traceability Matrix.

    Walks the codebase to discover decorated symbols and tests,
    then correlates them to produce RTM entries.

    Parameters
    ----------
    root:
        Repository root directory.
    package:
        Top-level package name.
    test_dir:
        Relative path to test directory.

    Returns
    -------
    RTM:
        The generated traceability matrix.
    """
    # 1. Load architecture registry.
    reg = ArchitectureRegistry.get()
    doc = reg.document
    components = doc.components
    icds = doc.icds

    # Build component → ICD mapping.
    component_icd_map: dict[str, list[str]] = {}
    for icd in icds:
        for comp_id in (icd.source_component, icd.target_component):
            component_icd_map.setdefault(comp_id, []).append(icd.id)

    # 2. Discover decorated symbols.
    symbols = discover_decorated_symbols(root, package=package)

    # 3. Discover tests.
    tests = discover_tests(root, test_dir=test_dir)

    # Build module → test mapping.
    module_test_map: dict[str, list[str]] = {}
    component_test_map: dict[str, list[str]] = {}
    for t in tests:
        test_id = (
            f"{t.test_file}::{t.test_class}::{t.test_function}"
            if t.test_class
            else f"{t.test_file}::{t.test_function}"
        )
        if t.references_module:
            module_test_map.setdefault(t.references_module, []).append(test_id)
        if t.references_component:
            component_test_map.setdefault(t.references_component, []).append(test_id)

    # 4. Build RTM entries.
    entries: list[RTMEntry] = []

    for sym in symbols:
        comp = components.get(sym.component_id)
        comp_name = comp.name if comp else sym.component_id
        layer = comp.layer if comp else ""

        # Resolve ICDs: from decorator metadata + component mapping.
        icd_ids: list[str] = []
        if sym.icd_schema:
            icd_ids.append(sym.icd_schema)
        for icd_id in component_icd_map.get(sym.component_id, []):
            if icd_id not in icd_ids:
                icd_ids.append(icd_id)

        # Find matching tests.
        test_ids: list[str] = []
        # Tests referencing this module.
        for tid in module_test_map.get(sym.module_path, []):
            if tid not in test_ids:
                test_ids.append(tid)
        # Tests referencing this component.
        for tid in component_test_map.get(sym.component_id, []):
            if tid not in test_ids:
                test_ids.append(tid)
        # Tests referencing parent module.
        parent_module = ".".join(sym.module_path.split(".")[:-1])
        for tid in module_test_map.get(parent_module, []):
            if tid not in test_ids:
                test_ids.append(tid)

        # Determine status.
        if test_ids and icd_ids:
            status = CoverageStatus.COVERED
        elif test_ids:
            status = CoverageStatus.PARTIAL
        else:
            status = CoverageStatus.UNCOVERED

        entries.append(RTMEntry(
            component_id=sym.component_id,
            component_name=comp_name,
            layer=str(layer),
            decorator_kind=sym.decorator_kind,
            module_path=sym.module_path,
            symbol_name=sym.symbol_name,
            icd_ids=icd_ids,
            test_ids=test_ids,
            status=status,
        ))

    rtm = RTM(
        entries=entries,
        component_count=len(components),
        decorated_count=len(symbols),
        test_count=len(tests),
    )

    return rtm


def generate_rtm_report(rtm: RTM) -> str:
    """Generate a human-readable RTM summary report.

    Parameters
    ----------
    rtm:
        The generated RTM.

    Returns
    -------
    str:
        Multi-line summary report.
    """
    lines = [
        "Requirements Traceability Matrix — Summary",
        "═" * 50,
        f"Components in architecture: {rtm.component_count}",
        f"Decorated symbols found:    {rtm.decorated_count}",
        f"Test functions found:        {rtm.test_count}",
        f"RTM entries:                 {len(rtm.entries)}",
        "",
        "Coverage:",
        f"  COVERED:   {rtm.covered_count}",
        f"  PARTIAL:   {rtm.partial_count}",
        f"  UNCOVERED: {rtm.uncovered_count}",
        f"  Ratio:     {rtm.coverage_ratio:.1%}",
    ]

    # Uncovered entries.
    uncovered = [e for e in rtm.entries if e.status == CoverageStatus.UNCOVERED]
    if uncovered:
        lines.append("")
        lines.append("Uncovered entries:")
        for e in uncovered:
            lines.append(
                f"  {e.component_id}.{e.symbol_name} "
                f"({e.decorator_kind}) in {e.module_path}"
            )

    return "\n".join(lines)
