# Holly Grace — Agent Constitution

## Identity
Holly Grace is an autonomous operations framework with kernel-enforced trust. All development follows an industrial-grade governance process.

## Critical Files
| Purpose | Path |
|---------|------|
| Process loop | `docs/Development_Procedure_Graph.md` |
| Task checklist | `README.md` §Task Execution Checklist |
| Task manifest | `docs/Task_Manifest.md` (442 tasks, 15 slices) |
| Task status (SSOT) | `docs/status.yaml` |
| Architecture (SSOT) | `docs/architecture.yaml` |
| SAD source | `docs/architecture/SAD_0.1.0.5.mermaid` |
| RTD source | `docs/architecture/RTD_0.1.0.4.mermaid` |
| Artifact genealogy | `docs/architecture/Artifact_Genealogy.md` |
| Finding register | `docs/audit/finding_register.csv` |
| Progress report | `docs/architecture/PROGRESS.md` |
| Gantt chart | `docs/architecture/GANTT.mermaid` |
| SIL matrix | `docs/SIL_Classification_Matrix.md` |

## Mandatory Process

**Every task** follows README.md §Task Execution Checklist (P0–P7). No exceptions.

Before starting:
1. Run `/audit` to validate cross-document consistency
2. Fix any FAIL results before proceeding

After completing:
1. Update `docs/status.yaml` with task completion + commit SHA
2. Run `python -m holly.arch gantt` to regenerate artifacts
3. Verify PROGRESS.md done count incremented
4. Update README progress table to match PROGRESS.md
5. Update Artifact_Genealogy.md if counts changed
6. Run `/audit` again — zero FAIL required before commit

## Hard Invariants (Non-negotiable)

1. **No orphaned counts.** Every number (component, task, test, SIL) must match actual enumerated count.
2. **No phantom SHAs.** Every `resolved_commit` in finding_register.csv must be reachable.
3. **No stale versions.** SAD v0.1.0.5, RTD v0.1.0.4, DPG v1.1 — match actual.
4. **No test regressions.** Test count monotonically non-decreasing per commit.
5. **Single source of truth.** `status.yaml` = task progress SSOT. `architecture.yaml` = component topology SSOT.
6. **Genealogy = current truth.** Counts in Artifact_Genealogy.md must match live sources (architecture.yaml, SIL matrix). AGC §0.2 state variables are frozen historical snapshots — do not update them post-audit.

## Current State

- **Slice 1 critical path:** 1.5→1.6→1.7→1.8→2.6→2.7→2.8→3.6→3.7→3a.8→3a.10→3a.12 (COMPLETE)
- **Slice 2 critical path:** 5.8→5.5→5.6→7.1→7.2→8.3→9.2→10.2→11.1→11.3 (COMPLETE)
- **Slice 3 critical path:** 13.1→14.1→14.5→15.4→16.3→16.4→16.5→16.6→16.9→17.3→17.4→17.7→18.3→18.4→18.9→20.3→20.5→21.2→21.6
- **Done:** Tasks 1.5, 1.6, 1.7, 1.8, 2.6, 2.7, 2.8, 3.6, 3.7, 3a.8, 3a.10, 3a.12, 5.8, 5.5, 5.6, 7.1, 7.2, 8.3, 9.2, 10.2, 11.1, 11.3, 13.1, 14.1, 14.5, 15.4, 16.3, 16.4, 16.5, 16.6, 16.9, 17.3, 17.4, 17.7, 18.3, 18.4, 18.9, 20.3, 20.5, 21.2, 21.6, 22.5, 22.7, 23.3, 24.3 (45 total, Slice 4: 4 of 7)
- **Next:** Task 25.3 — Implement vector DB client (ICD-034) [Slice 4 critical path continues]
- **Test count:** 2493
- **Components:** 48
- **Audit findings resolved:** F-001 through F-039 (F-036: k1 assert→KernelInvariantError; F-037: SchemaRegistry anyOf/$ref/$ref-rooted schemas accepted; F-038: cmd_gate test-count via :: line-count; F-039: audit.py C011 uses sys.executable not hardcoded "python")

## Code Conventions

- Python 3.12+, type annotations on all public APIs
- `ruff check holly tests` must pass (zero errors)
- `mypy holly --strict` guidance only
- Docstrings: Google/NumPy hybrid
- `__slots__` on dataclasses where performance critical
- `from __future__ import annotations` in all modules
- Tests: pytest + hypothesis for invariant-heavy code
- Decorators: use `_decorate()` helper — classes get metadata only (no wrapper), functions get `functools.wraps` wrapper
- Decorators debt: `type: ignore[return-value]` in decorators.py is known — proper fix is `ParamSpec` + `Concatenate` (captured as manifest debt, address before more SIL-3 call sites accumulate)
- Commit message: `Task <ID>: <summary>`

## Known Technical Debt

- **Governance CSV stubs:** `docs/audit/trace_matrix.csv` and `docs/audit/control_library.csv` are placeholders. Populate when TGS self-test criteria require populated data.
- **deployment-topology.md:** Referenced by SAD, RTD, Dev Environment Spec — planned for Phase N (slice 15). Forward-declarations, not broken links.
- **T3 eigenspectrum metric:** Pin divergence metric (which matrix, which norm) in behavior spec before Phase J (slice 11).
- **TLA+ ordering:** K1–K8 TLA+ formal models (Phase B, slice 3) should precede additional SIL-3 test coverage over unverified spec.

## CLI Tools

```bash
python -m holly.arch extract <sad_file> -o architecture.yaml
python -m holly.arch stats <sad_file>
python -m holly.arch gantt [--critical]
python -m holly.arch progress
python -m holly.arch audit
```

## Remotes

- **GitHub:** `github` remote → `main:master`
- **GitLab:** `gitlab` remote → `main`
- Every commit must reach both
