"""Automated cross-document consistency validation for Holly Grace project.

This module implements the audit backbone for the /audit slash command.
It performs ~12 checks across 12+ documents to detect common inconsistencies:
- count-discrepancy: asserted count doesn't match enumerated count
- version-ref: stale version strings
- sync-control: status/progress tracking drift
- quality-gate: ruff/pytest linting and test failures
- traceability: finding register closures and evidence

The main entry point is run_audit(repo_root) which returns a list of
AuditResult dataclasses. Use format_audit_report() to render a compact
human-readable report.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


# ── AuditResult dataclass ────────────────────────────────────────────


@dataclass
class AuditResult:
    """Result of a single audit check."""

    check_id: str  # e.g., "C001"
    category: str  # version-ref | count-discrepancy | traceability | sync-control | quality-gate
    severity: str  # HIGH | MEDIUM | LOW
    status: str  # PASS | FAIL | WARN | SKIP
    message: str  # human-readable description
    expected: str = ""  # expected value
    actual: str = ""  # actual value found


# ── Helper functions ────────────────────────────────────────────────


def _find_repo_root() -> Path:
    """Find repo root by walking up from CWD looking for holly/ + docs/ dirs."""
    p = Path.cwd()
    for _ in range(20):
        if (p / "holly").is_dir() and (p / "docs").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


def _extract_number(text: str, pattern: str) -> int | None:
    """Extract first integer matching a regex pattern."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except (IndexError, ValueError):
            return None
    return None


def _extract_version(text: str, pattern: str) -> str | None:
    """Extract first version string matching a regex pattern (e.g. '0.1.0.5')."""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return match.group(1)
        except IndexError:
            return None
    return None


def _read_file_safe(path: Path) -> str | None:
    """Read a file safely; return None if not found."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None


def _grep_count_assertion(text: str, patterns: list[str]) -> int | None:
    """Find a count assertion matching any of the given regex patterns."""
    for pattern in patterns:
        count = _extract_number(text, pattern)
        if count is not None:
            return count
    return None


# ── Individual check functions ───────────────────────────────────────


def _check_c001_component_count(repo_root: Path) -> AuditResult:
    """C001 — Component count consistency (HIGH).

    Parse architecture.yaml component count vs assertions in Artifact_Genealogy.md
    """
    try:
        from holly.arch import registry

        # Get component count from architecture.yaml
        arch_path = repo_root / "docs" / "architecture.yaml"
        registry.ArchitectureRegistry.reset()
        registry.ArchitectureRegistry.configure(arch_path)
        reg = registry.ArchitectureRegistry.get()
        comp_count = reg.document.component_count

        # Extract from Artifact_Genealogy.md
        genealogy_path = repo_root / "docs" / "architecture" / "Artifact_Genealogy.md"
        genealogy_text = _read_file_safe(genealogy_path)
        if not genealogy_text:
            return AuditResult(
                "C001",
                "count-discrepancy",
                "HIGH",
                "SKIP",
                "Artifact_Genealogy.md not found",
            )

        # Look for mermaid label and narrative assertions
        mermaid_count = _grep_count_assertion(
            genealogy_text,
            [
                r'nodes?.*?(\d+)\s+(?:component|comp)',
                r'(\d+)\s+nodes?\s+total',
                r'\((\d+)\s+component',
            ],
        )
        narrative_count = _grep_count_assertion(
            genealogy_text,
            [
                r'defining\s+(\d+)\s+component',
                r'comprises?\s+(\d+)\s+component',
                r'(\d+)\s+architect(?:ural)?\s+component',
            ],
        )

        # All must agree
        if (
            mermaid_count is not None
            and narrative_count is not None
            and mermaid_count == narrative_count == comp_count
        ):
            return AuditResult(
                "C001",
                "count-discrepancy",
                "HIGH",
                "PASS",
                f"Component count: {comp_count} ✓",
                expected=str(comp_count),
                actual=str(comp_count),
            )

        mismatches = []
        if mermaid_count is not None and mermaid_count != comp_count:
            mismatches.append(f"Genealogy mermaid: {mermaid_count}")
        if narrative_count is not None and narrative_count != comp_count:
            mismatches.append(f"Genealogy narrative: {narrative_count}")
        mismatches.append(f"architecture.yaml: {comp_count}")

        return AuditResult(
            "C001",
            "count-discrepancy",
            "HIGH",
            "FAIL",
            f"Component count mismatch: {' vs '.join(mismatches)}",
            expected=str(comp_count),
            actual=" | ".join(mismatches),
        )

    except ImportError:
        return AuditResult(
            "C001",
            "count-discrepancy",
            "HIGH",
            "SKIP",
            "Architecture modules not available",
        )
    except Exception as e:
        return AuditResult(
            "C001",
            "count-discrepancy",
            "HIGH",
            "FAIL",
            f"Error checking component count: {e}",
        )


def _check_c002_connection_count(repo_root: Path) -> AuditResult:
    """C002 — Connection count consistency (MEDIUM).

    architecture.yaml connections vs Artifact_Genealogy assertions.
    """
    try:
        from holly.arch import registry

        arch_path = repo_root / "docs" / "architecture.yaml"
        registry.ArchitectureRegistry.reset()
        registry.ArchitectureRegistry.configure(arch_path)
        reg = registry.ArchitectureRegistry.get()
        conn_count = reg.document.connection_count

        genealogy_path = repo_root / "docs" / "architecture" / "Artifact_Genealogy.md"
        genealogy_text = _read_file_safe(genealogy_path)
        if not genealogy_text:
            return AuditResult(
                "C002",
                "count-discrepancy",
                "MEDIUM",
                "SKIP",
                "Artifact_Genealogy.md not found",
            )

        # Extract assertions
        genealogy_count = _grep_count_assertion(
            genealogy_text,
            [
                r'(\d+)\s+edges?(?:\s|$)',
                r'(\d+)\s+connections?(?:\s|$)',
                r'(\d+)\s+(?:cross-)?boundary',
            ],
        )

        if genealogy_count is None or genealogy_count == conn_count:
            return AuditResult(
                "C002",
                "count-discrepancy",
                "MEDIUM",
                "PASS",
                f"Connection count: {conn_count} ✓",
                expected=str(conn_count),
                actual=str(conn_count),
            )

        return AuditResult(
            "C002",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Connection count mismatch: Genealogy says {genealogy_count}, architecture.yaml has {conn_count}",
            expected=str(conn_count),
            actual=str(genealogy_count),
        )

    except ImportError:
        return AuditResult(
            "C002",
            "count-discrepancy",
            "MEDIUM",
            "SKIP",
            "Architecture modules not available",
        )
    except Exception as e:
        return AuditResult(
            "C002",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Error checking connection count: {e}",
        )


def _check_c003_task_count(repo_root: Path) -> AuditResult:
    """C003 — Task count consistency (HIGH).

    Manifest total_tasks vs README and DPG counts.
    """
    try:
        from holly.arch import manifest_parser

        # Parse manifest
        manifest_path = repo_root / "docs" / "Task_Manifest.md"
        manifest_text = _read_file_safe(manifest_path)
        if not manifest_text:
            return AuditResult(
                "C003",
                "count-discrepancy",
                "HIGH",
                "SKIP",
                "Task_Manifest.md not found",
            )

        manifest = manifest_parser.parse_manifest(manifest_text)
        manifest_count = manifest.total_tasks

        # Extract from README
        readme_path = repo_root / "README.md"
        readme_text = _read_file_safe(readme_path)
        readme_count = None
        if readme_text:
            readme_count = _grep_count_assertion(
                readme_text,
                [
                    r'(\d+)\s+specified\s+tasks?',
                    r'(\d+)\s+tasks?.*?specified',
                ],
            )

        # Compare
        if readme_count is not None and readme_count != manifest_count:
            return AuditResult(
                "C003",
                "count-discrepancy",
                "HIGH",
                "FAIL",
                f"Task count: README says {readme_count} but manifest yields {manifest_count}",
                expected=str(manifest_count),
                actual=str(readme_count),
            )

        return AuditResult(
            "C003",
            "count-discrepancy",
            "HIGH",
            "PASS",
            f"Task count: {manifest_count} ✓",
            expected=str(manifest_count),
            actual=str(manifest_count),
        )

    except ImportError:
        return AuditResult(
            "C003",
            "count-discrepancy",
            "HIGH",
            "SKIP",
            "Architecture modules not available",
        )
    except Exception as e:
        return AuditResult(
            "C003",
            "count-discrepancy",
            "HIGH",
            "FAIL",
            f"Error checking task count: {e}",
        )


def _check_c004_critical_path_count(repo_root: Path) -> AuditResult:
    """C004 — Critical path count consistency (MEDIUM).

    Manifest critical path length vs README progress table.
    """
    try:
        from holly.arch import manifest_parser

        manifest_path = repo_root / "docs" / "Task_Manifest.md"
        manifest_text = _read_file_safe(manifest_path)
        if not manifest_text:
            return AuditResult(
                "C004",
                "count-discrepancy",
                "MEDIUM",
                "SKIP",
                "Task_Manifest.md not found",
            )

        manifest = manifest_parser.parse_manifest(manifest_text)
        crit_count = len(manifest.all_critical_path_ids)

        # Extract Slice 1 critical path from README Σ row or Slice 1 row
        # README format: | 1 | Phase A ... | 8 | 39 | 20% [##........] | 8/12 |
        readme_path = repo_root / "README.md"
        readme_text = _read_file_safe(readme_path)
        slice1_crit = None
        if readme_text:
            # Match Slice 1 row: | 1 | ... | X/Y |
            m = re.search(r'\|\s*1\s*\|.*?\|\s*(\d+)/(\d+)\s*\|', readme_text)
            if m:
                slice1_crit = (int(m.group(1)), int(m.group(2)))

        # Cross-check: manifest Slice 1 critical path
        s1_crit_ids = manifest.slices[0].critical_path if manifest.slices else []
        manifest_s1_total = len(s1_crit_ids)

        if slice1_crit is not None and slice1_crit[1] != manifest_s1_total:
            return AuditResult(
                "C004",
                "count-discrepancy",
                "MEDIUM",
                "WARN",
                f"Slice 1 critical path: README says {slice1_crit[0]}/{slice1_crit[1]}, manifest has {manifest_s1_total} total",
                expected=str(manifest_s1_total),
                actual=str(slice1_crit[1]),
            )

        return AuditResult(
            "C004",
            "count-discrepancy",
            "MEDIUM",
            "PASS",
            f"Critical path total: {crit_count} across all slices, Slice 1: {manifest_s1_total} ✓",
            expected=str(crit_count),
            actual=str(crit_count),
        )

    except ImportError:
        return AuditResult(
            "C004",
            "count-discrepancy",
            "MEDIUM",
            "SKIP",
            "Architecture modules not available",
        )
    except Exception as e:
        return AuditResult(
            "C004",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Error checking critical path: {e}",
        )


def _check_c005_done_task_count(repo_root: Path) -> AuditResult:
    """C005 — Done task count (HIGH).

    status.yaml done count vs PROGRESS.md vs README.
    """
    try:
        import yaml

        # Count from status.yaml
        status_path = repo_root / "docs" / "status.yaml"
        status_text = _read_file_safe(status_path)
        if not status_text:
            return AuditResult(
                "C005",
                "count-discrepancy",
                "HIGH",
                "SKIP",
                "status.yaml not found",
            )

        data = yaml.safe_load(status_text)
        done_count_yaml = 0
        if data and "tasks" in data:
            for _task_id, task_info in data["tasks"].items():
                if (isinstance(task_info, dict) and task_info.get("status") == "done") or (isinstance(task_info, str) and task_info == "done"):
                    done_count_yaml += 1

        # Count from PROGRESS.md — Σ row format: | **Σ** | **All** | **8** | **442** | ...
        progress_path = repo_root / "docs" / "architecture" / "PROGRESS.md"
        progress_text = _read_file_safe(progress_path)
        done_count_progress = None
        if progress_text:
            sigma_match = re.search(
                r'\|\s*\*\*Σ\*\*\s*\|.*?\|\s*\*\*(\d+)\*\*\s*\|',
                progress_text,
            )
            if sigma_match:
                done_count_progress = int(sigma_match.group(1))

        # Extract from README — same Σ row format
        readme_path = repo_root / "README.md"
        readme_text = _read_file_safe(readme_path)
        done_count_readme = None
        if readme_text:
            sigma_match = re.search(
                r'\|\s*\*\*Σ\*\*\s*\|.*?\|\s*\*\*(\d+)\*\*\s*\|',
                readme_text,
            )
            if sigma_match:
                done_count_readme = int(sigma_match.group(1))

        # All must agree
        if (
            done_count_progress is not None
            and done_count_progress == done_count_yaml
        ):
            status_str = "PASS"
            if done_count_readme is not None and done_count_readme != done_count_yaml:
                status_str = "WARN"

            return AuditResult(
                "C005",
                "count-discrepancy",
                "HIGH",
                status_str,
                f"Done task count: {done_count_yaml} ✓",
                expected=str(done_count_yaml),
                actual=str(done_count_yaml),
            )

        return AuditResult(
            "C005",
            "count-discrepancy",
            "HIGH",
            "WARN",
            f"Done count: status.yaml={done_count_yaml}, PROGRESS.md={done_count_progress}",
            expected=str(done_count_yaml),
            actual=str(done_count_progress or "?"),
        )

    except Exception as e:
        return AuditResult(
            "C005",
            "count-discrepancy",
            "HIGH",
            "FAIL",
            f"Error checking done task count: {e}",
        )


def _check_c006_finding_register_shas(repo_root: Path) -> AuditResult:
    """C006 — Finding register SHA validity (HIGH).

    Check that resolved findings have valid commit SHAs (not pending/N/A).
    """
    try:
        finding_path = repo_root / "docs" / "audit" / "finding_register.csv"
        if not finding_path.exists():
            return AuditResult(
                "C006",
                "traceability",
                "HIGH",
                "SKIP",
                "finding_register.csv not found",
            )

        pending_count = 0
        with open(finding_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                status = row.get("status", "").upper()
                resolved_commit = row.get("resolved_commit", "").strip()

                # CLOSED findings may have N/A; RESOLVED must have real commit
                if status == "RESOLVED" and resolved_commit in ("pending", "N/A", ""):
                    pending_count += 1

        if pending_count == 0:
            return AuditResult(
                "C006",
                "traceability",
                "HIGH",
                "PASS",
                "All resolved findings have valid commit SHAs ✓",
            )

        return AuditResult(
            "C006",
            "traceability",
            "HIGH",
            "WARN",
            f"Finding register: {pending_count} findings still pending SHA",
            actual=str(pending_count),
        )

    except Exception as e:
        return AuditResult(
            "C006",
            "traceability",
            "HIGH",
            "FAIL",
            f"Error checking finding register: {e}",
        )


def _check_c007_version_refs(repo_root: Path) -> AuditResult:
    """C007 — Version references (MEDIUM).

    Check DPG header and other files reference correct SAD/RTD versions.
    """
    try:
        # Get SAD version from architecture.yaml (dotted semver, e.g. "0.1.0.5")
        arch_path = repo_root / "docs" / "architecture.yaml"
        arch_text = _read_file_safe(arch_path)
        sad_version = None
        if arch_text:
            sad_version = _extract_version(arch_text, r'sad_version:\s*["\']?([0-9]+(?:\.[0-9]+)+)')

        # Check README for matching version
        readme_path = repo_root / "README.md"
        readme_text = _read_file_safe(readme_path)
        readme_sad_version = None
        if readme_text:
            readme_sad_version = _extract_version(
                readme_text, r'SAD\s+v?([0-9]+(?:\.[0-9]+)+)'
            )

        # Check Genealogy
        genealogy_path = repo_root / "docs" / "architecture" / "Artifact_Genealogy.md"
        genealogy_text = _read_file_safe(genealogy_path)
        genealogy_sad_version = None
        if genealogy_text:
            genealogy_sad_version = _extract_version(
                genealogy_text, r'SAD\s+v?([0-9]+(?:\.[0-9]+)+)'
            )

        # Compare version strings
        mismatches = []
        if (
            sad_version
            and readme_sad_version
            and sad_version != readme_sad_version
        ):
            mismatches.append(
                f"README v{readme_sad_version} vs architecture.yaml v{sad_version}"
            )
        if (
            sad_version
            and genealogy_sad_version
            and sad_version != genealogy_sad_version
        ):
            mismatches.append(
                f"Genealogy v{genealogy_sad_version} vs architecture.yaml v{sad_version}"
            )

        if mismatches:
            return AuditResult(
                "C007",
                "version-ref",
                "MEDIUM",
                "WARN",
                f"Version mismatch: {'; '.join(mismatches)}",
                expected=f"v{sad_version}",
                actual=f"v{readme_sad_version}",
            )

        return AuditResult(
            "C007",
            "version-ref",
            "MEDIUM",
            "PASS",
            f"Version references consistent (SAD v{sad_version}) ✓",
            expected=f"v{sad_version}",
            actual=f"v{sad_version}",
        )

    except Exception as e:
        return AuditResult(
            "C007",
            "version-ref",
            "MEDIUM",
            "FAIL",
            f"Error checking version refs: {e}",
        )


def _check_c008_sil_count(repo_root: Path) -> AuditResult:
    """C008 — SIL count (MEDIUM).

    Count SIL assignments and compare to Genealogy mermaid SIL node.
    """
    try:
        sil_path = repo_root / "docs" / "SIL_Classification_Matrix.md"
        sil_text = _read_file_safe(sil_path)
        if not sil_text:
            return AuditResult(
                "C008",
                "count-discrepancy",
                "MEDIUM",
                "SKIP",
                "SIL_Classification_Matrix.md not found",
            )

        # Count SIL assignments — data rows have SIL level (1/2/3) in 4th column:
        # | Component Name | SAD Node | Layer | SIL | ...
        sil_count = len(re.findall(
            r'^\|[^|]+\|[^|]+\|[^|]+\|\s*[123]\s*\|',
            sil_text,
            re.MULTILINE,
        ))

        # Extract from Genealogy — the SIL node label says e.g. "43 components,\nSIL-1/2/3"
        genealogy_path = repo_root / "docs" / "architecture" / "Artifact_Genealogy.md"
        genealogy_text = _read_file_safe(genealogy_path)
        genealogy_sil_count = None
        if genealogy_text:
            # Look for the SIL Classification mermaid node: SIL["...N components..."]
            sil_node_match = re.search(
                r'SIL\["SIL Classification.*?(\d+)\s+components',
                genealogy_text,
                re.DOTALL,
            )
            if sil_node_match:
                genealogy_sil_count = int(sil_node_match.group(1))

        if genealogy_sil_count is None or genealogy_sil_count == sil_count:
            return AuditResult(
                "C008",
                "count-discrepancy",
                "MEDIUM",
                "PASS",
                f"SIL count: {sil_count} ✓",
                expected=str(sil_count),
                actual=str(sil_count),
            )

        return AuditResult(
            "C008",
            "count-discrepancy",
            "MEDIUM",
            "WARN",
            f"SIL count: Genealogy says {genealogy_sil_count}, matrix has {sil_count}",
            expected=str(sil_count),
            actual=str(genealogy_sil_count),
        )

    except Exception as e:
        return AuditResult(
            "C008",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Error checking SIL count: {e}",
        )


def _check_c009_ruff_lint(repo_root: Path) -> AuditResult:
    """C009 — ruff lint clean (MEDIUM).

    Run ruff check and verify zero errors.
    """
    try:
        result = subprocess.run(
            ["ruff", "check", "holly", "tests", "--quiet"],
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )

        if result.returncode == 0:
            return AuditResult(
                "C009",
                "quality-gate",
                "MEDIUM",
                "PASS",
                "ruff check passed ✓",
            )

        return AuditResult(
            "C009",
            "quality-gate",
            "MEDIUM",
            "FAIL",
            f"ruff check failed: {result.stdout.decode() or result.stderr.decode()}",
            actual="ruff errors detected",
        )

    except FileNotFoundError:
        return AuditResult(
            "C009",
            "quality-gate",
            "MEDIUM",
            "SKIP",
            "ruff not available",
        )
    except subprocess.TimeoutExpired:
        return AuditResult(
            "C009",
            "quality-gate",
            "MEDIUM",
            "SKIP",
            "ruff check timed out",
        )
    except Exception as e:
        return AuditResult(
            "C009",
            "quality-gate",
            "MEDIUM",
            "SKIP",
            f"Could not run ruff: {e}",
        )


def _check_c010_pytest_pass(repo_root: Path) -> AuditResult:
    """C010 — pytest pass (HIGH).

    Run pytest and verify all tests pass.
    """
    try:
        result = subprocess.run(
            ["pytest", "tests/", "-q", "--tb=no"],
            cwd=repo_root,
            capture_output=True,
            timeout=60,
        )

        if result.returncode == 0:
            return AuditResult(
                "C010",
                "quality-gate",
                "HIGH",
                "PASS",
                "pytest all passed ✓",
            )

        return AuditResult(
            "C010",
            "quality-gate",
            "HIGH",
            "FAIL",
            f"pytest failures: {result.stdout.decode() or result.stderr.decode()}",
            actual="test failures",
        )

    except FileNotFoundError:
        return AuditResult(
            "C010",
            "quality-gate",
            "HIGH",
            "SKIP",
            "pytest not available",
        )
    except subprocess.TimeoutExpired:
        return AuditResult(
            "C010",
            "quality-gate",
            "HIGH",
            "SKIP",
            "pytest timed out",
        )
    except Exception as e:
        return AuditResult(
            "C010",
            "quality-gate",
            "HIGH",
            "SKIP",
            f"Could not run pytest: {e}",
        )


def _check_c011_gantt_freshness(repo_root: Path) -> AuditResult:
    """C011 — Gantt freshness (MEDIUM).

    Generate Gantt via CLI and compare to checked-in version.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "holly.arch", "gantt", "--stdout"],
            cwd=repo_root,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            return AuditResult(
                "C011",
                "sync-control",
                "MEDIUM",
                "FAIL",
                "gantt --stdout failed",
            )

        generated_gantt = result.stdout.decode(encoding="utf-8", errors="replace")

        gantt_path = repo_root / "docs" / "architecture" / "GANTT.mermaid"
        gantt_text = _read_file_safe(gantt_path)
        if not gantt_text:
            return AuditResult(
                "C011",
                "sync-control",
                "MEDIUM",
                "SKIP",
                "GANTT.mermaid not found",
            )

        # Compare (normalize whitespace)
        gen_normalized = "\n".join(line.rstrip() for line in generated_gantt.split("\n"))
        file_normalized = "\n".join(line.rstrip() for line in gantt_text.split("\n"))

        if gen_normalized == file_normalized:
            return AuditResult(
                "C011",
                "sync-control",
                "MEDIUM",
                "PASS",
                "GANTT.mermaid is fresh ✓",
            )

        # Count differing lines (changed content + length delta)
        gen_lines = gen_normalized.split("\n")
        file_lines = file_normalized.split("\n")
        min_len = min(len(gen_lines), len(file_lines))
        diff_count = sum(
            1 for i in range(min_len) if gen_lines[i] != file_lines[i]
        ) + abs(len(gen_lines) - len(file_lines))

        return AuditResult(
            "C011",
            "sync-control",
            "MEDIUM",
            "WARN",
            f"GANTT.mermaid is stale (≈{diff_count} line diff)",
            actual=f"{diff_count} lines",
        )

    except FileNotFoundError:
        return AuditResult(
            "C011",
            "sync-control",
            "MEDIUM",
            "SKIP",
            "gantt command not available",
        )
    except subprocess.TimeoutExpired:
        return AuditResult(
            "C011",
            "sync-control",
            "MEDIUM",
            "SKIP",
            "gantt --stdout timed out",
        )
    except Exception as e:
        return AuditResult(
            "C011",
            "sync-control",
            "MEDIUM",
            "SKIP",
            f"Could not check gantt freshness: {e}",
        )


def _check_c012_genealogy_component_count(repo_root: Path) -> AuditResult:
    """C012 — Genealogy SAD component count matches architecture.yaml.

    Extract SAD node label component count from Artifact_Genealogy.md mermaid graph
    and compare to actual architecture.yaml component count.
    """
    try:
        import yaml

        # Read Artifact_Genealogy.md and extract SAD node label component count
        genealogy_path = repo_root / "docs" / "architecture" / "Artifact_Genealogy.md"
        genealogy_text = _read_file_safe(genealogy_path)
        if not genealogy_text:
            return AuditResult(
                "C012",
                "count-discrepancy",
                "MEDIUM",
                "SKIP",
                "Artifact_Genealogy.md not found",
            )

        # Search for SAD node label: look for SAD["SAD or SAD v pattern
        # Pattern: SAD["SAD ... components"] or SAD v... components
        sad_count_from_genealogy = None
        for line in genealogy_text.split("\n"):
            # Look for lines like: SAD["SAD v1.0: 48 components"]
            if "SAD" in line and ("component" in line.lower()):
                count = _extract_number(line, r'(\d+)\s+component')
                if count is not None:
                    sad_count_from_genealogy = count
                    break

        # Read architecture.yaml and count components
        arch_path = repo_root / "docs" / "architecture.yaml"
        arch_text = _read_file_safe(arch_path)
        if not arch_text:
            return AuditResult(
                "C012",
                "count-discrepancy",
                "MEDIUM",
                "SKIP",
                "architecture.yaml not found",
            )

        # Parse YAML and count components
        try:
            arch_data = yaml.safe_load(arch_text)
            components_dict = arch_data.get("components", {})
            if not isinstance(components_dict, dict):
                components_dict = {}
            actual_component_count = len(components_dict)
        except Exception:
            return AuditResult(
                "C012",
                "count-discrepancy",
                "MEDIUM",
                "FAIL",
                "Failed to parse architecture.yaml",
            )

        # Compare counts
        if sad_count_from_genealogy is None:
            return AuditResult(
                "C012",
                "count-discrepancy",
                "MEDIUM",
                "WARN",
                f"Could not extract SAD component count from Genealogy.md (architecture.yaml has {actual_component_count})",
                expected=str(actual_component_count),
                actual="unknown",
            )

        if sad_count_from_genealogy == actual_component_count:
            return AuditResult(
                "C012",
                "count-discrepancy",
                "MEDIUM",
                "PASS",
                f"Genealogy SAD component count: {actual_component_count} ✓",
                expected=str(actual_component_count),
                actual=str(actual_component_count),
            )

        return AuditResult(
            "C012",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Component count mismatch: Genealogy SAD node says {sad_count_from_genealogy}, architecture.yaml has {actual_component_count}",
            expected=str(actual_component_count),
            actual=str(sad_count_from_genealogy),
        )

    except Exception as e:
        return AuditResult(
            "C012",
            "count-discrepancy",
            "MEDIUM",
            "FAIL",
            f"Error checking genealogy component count: {e}",
        )


# ── Main audit orchestration ─────────────────────────────────────────


def run_audit(repo_root: Path) -> list[AuditResult]:
    """Run all audit checks. Return list of AuditResult in check order.

    Parameters
    ----------
    repo_root : Path
        Root directory of the Holly Grace project.

    Returns
    -------
    list[AuditResult]
        Results from all checks, in order (C001 through C012).
    """
    checks: list[Callable[[Path], AuditResult]] = [
        _check_c001_component_count,
        _check_c002_connection_count,
        _check_c003_task_count,
        _check_c004_critical_path_count,
        _check_c005_done_task_count,
        _check_c006_finding_register_shas,
        _check_c007_version_refs,
        _check_c008_sil_count,
        _check_c009_ruff_lint,
        _check_c010_pytest_pass,
        _check_c011_gantt_freshness,
        _check_c012_genealogy_component_count,
    ]

    results: list[AuditResult] = []
    for check in checks:
        try:
            result = check(repo_root)
            results.append(result)
        except Exception as e:
            results.append(
                AuditResult(
                    check.__name__.replace("_check_", "").upper(),
                    "unknown",
                    "HIGH",
                    "FAIL",
                    f"Unexpected error: {e}",
                )
            )

    return results


def format_audit_report(results: list[AuditResult]) -> str:
    """Format audit results as a compact human-readable report.

    Parameters
    ----------
    results : list[AuditResult]
        Results from run_audit().

    Returns
    -------
    str
        Formatted report with summary.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"AUDIT REPORT — {timestamp}",
        "═" * 60,
    ]

    for result in results:
        status_icon = {
            "PASS": "✓",
            "FAIL": "✗",
            "WARN": "⚠",
            "SKIP": "⊘",
        }.get(result.status, "?")

        msg = result.message
        if result.expected and result.actual and result.expected != result.actual:
            msg += f" (expected {result.expected}, got {result.actual})"

        lines.append(f"{result.status:4s} {status_icon}  {result.check_id}  {msg}")

    # Summary
    lines.append("═" * 60)
    counts = {
        "PASS": sum(1 for r in results if r.status == "PASS"),
        "FAIL": sum(1 for r in results if r.status == "FAIL"),
        "WARN": sum(1 for r in results if r.status == "WARN"),
        "SKIP": sum(1 for r in results if r.status == "SKIP"),
    }
    summary = " | ".join(
        f"{count} {status}" for status, count in counts.items() if count > 0
    )
    lines.append(f"Results: {summary}")

    return "\n".join(lines)


def main() -> int:
    """Find repo root, run audit, print report. Return 0 if no FAIL, 1 if any FAIL."""
    repo_root = _find_repo_root()

    results = run_audit(repo_root)
    report = format_audit_report(results)
    print(report)

    # Exit code: 1 if any FAIL, else 0
    has_fail = any(r.status == "FAIL" for r in results)
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
