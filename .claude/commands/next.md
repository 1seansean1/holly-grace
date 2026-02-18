# /next — Execute the next critical-path task

You are executing a single task from the Holly Grace development pipeline. Follow the Task Execution Checklist (README.md §Task Execution Checklist) exactly. No shortcuts.

## Phase 1: Pre-flight (P0–P2)

1. **Run audit.** Execute `python -m holly.arch audit` from the repo root. If any check shows FAIL, stop and fix those first. Do not proceed to a new task with existing failures.

2. **Sync state.** Read `docs/status.yaml` and identify all tasks marked `done`. Read `docs/architecture/PROGRESS.md` and confirm the done counts match. Read the README progress table (Σ row) and confirm it matches too. If any disagree, fix the discrepancy before proceeding.

3. **Identify next task.** Parse `docs/Task_Manifest.md` and find the critical path for Slice 1: `1.5→1.6→1.7→1.8→2.6→2.7→2.8→3.6→3.7→3a.8→3a.10→3a.12`. The next task is the first one in this sequence whose status in `docs/status.yaml` is NOT `done`. Report which task you will execute.

4. **Read task spec.** In `docs/Task_Manifest.md`, find the task entry. Note its MP step, input artifacts, output artifacts, verification method, and acceptance criteria. Read any referenced specification documents (ICD, Behavior Specs, Goal Hierarchy) that the task traces to.

5. **Spec pre-check (P2).** Verify the acceptance criteria are concrete and testable. If vague, sharpen them against the γ-phase specs before proceeding.

6. **Report plan.** Tell the user: "Next task: `<ID>` — `<name>`. Dependencies satisfied. Acceptance criteria: `<list>`. Proceeding with implementation."

## Phase 2: Implementation (P3–P5)

7. **Implement (P3A).** Write production code in the module specified by the RTD (`docs/architecture/RTD_0.1.0.4.mermaid`). Follow existing code patterns: type annotations, docstrings, `__slots__`, ruff compliance, `from __future__ import annotations`.

8. **Test authoring (P3C).** Write tests exercising the acceptance criteria. At minimum: one positive test per criterion, one negative test (invalid input / failure path). Use property-based tests (hypothesis) for invariant-heavy code. Place in `tests/unit/` or `tests/integration/` as appropriate.

9. **Verification (P4).** Run:
   - `ruff check holly tests` — must be zero errors
   - `pytest tests/ -q` — must be all pass, zero regressions
   If either fails, fix before proceeding.

10. **Regression gate (P5).** Confirm the pre-existing test count still passes. Report: "Tests: X passed (was Y before this task, +Z new)."

## Phase 3: Documentation sync (P6–P7)

This phase is where most process violations occur. Execute every step.

11. **Update status.yaml (P6.1a).** Mark the task `done` with today's date and a note including test count contribution. Format:
    ```yaml
    <task_id>:
      status: done
      date: "<YYYY-MM-DD>"
      note: "<summary> (<N> tests)"
    ```

12. **Regenerate tracking artifacts.** Run `python -m holly.arch gantt`. This regenerates `GANTT.mermaid`, `GANTT_critical.mermaid`, and `PROGRESS.md`.

13. **Diff PROGRESS.md.** Confirm the done count incremented. If unchanged, something is wrong — halt and investigate.

14. **Update README progress table.** Update the Slice 1 row and Σ row to match PROGRESS.md totals.

15. **Update Artifact Genealogy.** If implementation added new modules, components, or tests, update the counts in `docs/architecture/Artifact_Genealogy.md`: mermaid node labels, narrative paragraphs, inventory table, and chronology section.

16. **Final audit.** Run `python -m holly.arch audit` again. Zero FAIL results required.

17. **Commit (P7).** Stage only files touched by this task. Commit message: `Task <ID>: <summary>`. Push to both remotes: `git push github main:master && git push gitlab main`.

18. **Report completion.** Tell the user: "Task `<ID>` complete. Tests: X total (+Y new). Audit: clean. Committed: `<sha>`. Next critical-path task: `<next_id>`."
