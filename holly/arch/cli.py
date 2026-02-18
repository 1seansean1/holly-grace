"""CLI for architecture extraction and development tracking.

Usage:
    python -m holly.arch extract docs/architecture/SAD_0.1.0.5.mermaid -o architecture.yaml
    python -m holly.arch stats docs/architecture/SAD_0.1.0.5.mermaid
    python -m holly.arch gantt                  # generate Gantt + progress report
    python -m holly.arch gantt --critical       # critical-path only
    python -m holly.arch progress               # print progress summary to stdout
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from holly.arch.extract import extract_from_file, to_yaml, write_architecture_yaml
from holly.arch.sad_parser import parse_sad_file


def cmd_extract(args: argparse.Namespace) -> None:
    """Extract architecture.yaml from a SAD mermaid file."""
    sad_path = Path(args.sad_file)
    if not sad_path.exists():
        print(f"ERROR: SAD file not found: {sad_path}", file=sys.stderr)
        sys.exit(1)

    doc = extract_from_file(sad_path)

    if args.output:
        output_path = Path(args.output)
        write_architecture_yaml(doc, output_path)
        print(f"Wrote {output_path} ({doc.component_count} components, "
              f"{doc.connection_count} connections, "
              f"{doc.boundary_crossing_count} boundary crossings)")
    else:
        print(to_yaml(doc))


def cmd_stats(args: argparse.Namespace) -> None:
    """Print statistics about a SAD mermaid file."""
    sad_path = Path(args.sad_file)
    if not sad_path.exists():
        print(f"ERROR: SAD file not found: {sad_path}", file=sys.stderr)
        sys.exit(1)

    ast = parse_sad_file(sad_path)
    doc = extract_from_file(sad_path)

    print(f"SAD: {sad_path.name}")
    print(f"  Version:      {doc.metadata.sad_version}")
    print(f"  Chart:        {ast.chart_type} {ast.chart_direction}")
    print(f"  Subgraphs:    {ast.subgraph_count}")
    print(f"  Nodes:        {ast.node_count}")
    print(f"  Edges:        {ast.edge_count}")
    print(f"  Components:   {doc.component_count}")
    print(f"  Connections:  {doc.connection_count}")
    print(f"  Boundary X:   {doc.boundary_crossing_count}")
    print(f"  K-invariants: {len(doc.kernel_invariants)}")
    print()
    print("Layer distribution:")
    from holly.arch.schema import LayerID
    for layer in LayerID:
        comps = doc.components_in_layer(layer)
        if comps:
            names = ", ".join(c.id for c in comps)
            print(f"  {layer.value:12s}  ({len(comps):2d})  {names}")


def _find_repo_root() -> Path:
    """Walk up from cwd to find repo root (contains docs/ and holly/)."""
    p = Path.cwd()
    for _ in range(10):
        if (p / "docs").is_dir() and (p / "holly").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd()


def cmd_gantt(args: argparse.Namespace) -> None:
    """Generate Gantt charts and progress report from manifest + status.yaml."""
    from holly.arch.tracker import (
        build_registry,
        generate_gantt,
        generate_gantt_critical_only,
        generate_progress_report,
    )

    root = _find_repo_root()
    manifest_path = Path(args.manifest) if args.manifest else root / "docs" / "Task_Manifest.md"
    status_path = Path(args.status) if args.status else root / "docs" / "status.yaml"
    output_dir = Path(args.output_dir) if args.output_dir else root / "docs" / "architecture"

    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    if args.critical:
        registry = build_registry(manifest_path, status_path)
        out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        out.write(generate_gantt_critical_only(registry))
        out.write("\n")
        out.flush()
        out.detach()  # prevent closing underlying stdout
    elif args.stdout:
        registry = build_registry(manifest_path, status_path)
        out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        out.write(generate_gantt(registry))
        out.write("\n")
        out.flush()
        out.detach()  # prevent closing underlying stdout
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = generate_progress_report(manifest_path, status_path, output_dir)
        for name, path in outputs.items():
            print(f"  {name}: {path}")
        print(f"\nGenerated {len(outputs)} artifacts.")


def cmd_progress(args: argparse.Namespace) -> None:
    """Print progress summary to stdout."""
    from holly.arch.tracker import build_registry

    root = _find_repo_root()
    manifest_path = Path(args.manifest) if args.manifest else root / "docs" / "Task_Manifest.md"
    status_path = Path(args.status) if args.status else root / "docs" / "status.yaml"

    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    registry = build_registry(manifest_path, status_path)
    for line in registry.summary_lines:
        print(line)


def cmd_audit(args: argparse.Namespace) -> None:
    """Run cross-document consistency audit."""
    from holly.arch.audit import format_audit_report, run_audit

    root = _find_repo_root()
    results = run_audit(root)
    print(format_audit_report(results))

    fail_count = sum(1 for r in results if r.status == "FAIL")
    if fail_count > 0:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="holly-arch",
        description="Holly architecture extraction and tracking tooling",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # extract
    p_extract = sub.add_parser("extract", help="Extract architecture.yaml from SAD")
    p_extract.add_argument("sad_file", help="Path to SAD mermaid file")
    p_extract.add_argument("-o", "--output", help="Output YAML path (stdout if omitted)")
    p_extract.set_defaults(func=cmd_extract)

    # stats
    p_stats = sub.add_parser("stats", help="Print SAD statistics")
    p_stats.add_argument("sad_file", help="Path to SAD mermaid file")
    p_stats.set_defaults(func=cmd_stats)

    # gantt
    p_gantt = sub.add_parser("gantt", help="Generate Gantt chart from manifest + status")
    p_gantt.add_argument("-m", "--manifest", help="Path to Task_Manifest.md")
    p_gantt.add_argument("-s", "--status", help="Path to status.yaml")
    p_gantt.add_argument("-o", "--output-dir", help="Output directory for artifacts")
    p_gantt.add_argument("--critical", action="store_true", help="Critical-path tasks only")
    p_gantt.add_argument("--stdout", action="store_true", help="Print to stdout instead of files")
    p_gantt.set_defaults(func=cmd_gantt)

    # progress
    p_progress = sub.add_parser("progress", help="Print progress summary")
    p_progress.add_argument("-m", "--manifest", help="Path to Task_Manifest.md")
    p_progress.add_argument("-s", "--status", help="Path to status.yaml")
    p_progress.set_defaults(func=cmd_progress)

    # audit
    p_audit = sub.add_parser("audit", help="Run cross-document consistency audit")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
