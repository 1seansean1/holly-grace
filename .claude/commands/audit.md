# /audit — Cross-document consistency check

Run the automated audit script and report results. Fix any failures found.

## Steps

1. **Run the audit.** Execute from repo root:
   ```
   python -m holly.arch audit
   ```

2. **Report results.** Show the full audit report output to the user. Highlight any FAIL or WARN results.

3. **If all PASS:** Report "Audit clean — all checks passed." and stop.

4. **If any FAIL:** For each failed check:
   - Explain what the check validates
   - Show the expected vs actual values
   - Identify which file(s) need correction
   - Apply the fix
   - Re-run the audit to confirm the fix resolved it

5. **If any WARN:** Report warnings to the user. Warnings are advisory — they don't block work but should be addressed when convenient. Common warnings:
   - Finding register entries with `pending` SHAs (need backfill after next commit)
   - Gantt chart slightly stale (regenerate with `python -m holly.arch gantt`)

6. **After fixing:** If fixes were applied, re-run the full audit to confirm zero FAIL. Report final status.

## What the audit checks

| Check | Severity | What it validates |
|-------|----------|-------------------|
| C001 | HIGH | Component count matches across architecture.yaml and Artifact_Genealogy.md |
| C002 | MEDIUM | Connection count consistency |
| C003 | HIGH | Task count (manifest vs README) |
| C004 | MEDIUM | Critical path count (manifest vs README) |
| C005 | HIGH | Done task count (status.yaml vs PROGRESS.md vs README) |
| C006 | HIGH | Finding register SHAs are real (no "pending") |
| C007 | MEDIUM | Version references (SAD/RTD versions across documents) |
| C008 | MEDIUM | SIL count (classification matrix vs Genealogy) |
| C009 | MEDIUM | ruff lint clean |
| C010 | HIGH | pytest all pass |
| C011 | MEDIUM | Gantt chart freshness |
| C012 | MEDIUM | Genealogy SAD component count matches architecture.yaml |

## Important

- Run this at the START and END of every task (per the Task Execution Checklist)
- Never commit with a FAIL result unless you have a documented reason
- If a check shows SKIP, it means a dependency is unavailable (e.g., ruff not installed) — this is acceptable in constrained environments but should be resolved
