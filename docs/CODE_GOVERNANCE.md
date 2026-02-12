# Code Governance — Holly's Code-Write Safety Model

> Defines how Holly is allowed to modify code, merge PRs, and deploy.
> Every rule here is enforced in code unless marked as "prompt-level norm."
> Last validated: 2026-02-11

---

## 1. Scope of Authority

### What Holly MAY Modify

- Tool implementations (`src/tools/`)
- Workflow definitions (`src/workflows/`)
- Agent configurations (`src/holly/crew/`)
- MCP server code (`src/mcp/servers/`)
- Test files (`tests/`)
- Documentation (`docs/`)
- Scheduler job definitions
- Configuration files (non-secret)

### What Holly MUST NOT Modify (Hard-Blocked in Code)

| Path / Pattern | Reason |
|----------------|--------|
| `src/security/` | Auth middleware, JWT signing, RBAC roles |
| `src/tower/` | Approval system, ticket store, checkpointer |
| `deploy/` | Task definitions, infrastructure configs |
| `.env`, `*.env*` | Environment secrets |
| `src/holly/tools.py` | Her own tool definitions (self-modification) |
| `src/holly/agent.py` | Her own agent configuration |
| `src/holly/prompts.py` | Her own system prompt |
| `src/serve.py` | API surface and lifespan |
| `Dockerfile*` | Container build definitions |
| `.github/workflows/` | CI/CD pipeline definitions |

Attempts to modify these files are **rejected at validation** by `propose_code_change`. No git artifacts are created. The run is marked failed with a clear reason.

### Principal-Only Files

Changes to the files in the "MUST NOT" list above require Sean to make them manually. Holly may propose changes via chat (describe what she wants changed and why) but cannot execute them herself.

---

## 2. Approval Flow

Every code change follows this flow:

```
Holly decides to change code
    │
    ▼
propose_code_change()          ← Single entry point (funnel)
    │
    ├─ Validate governance rules (forbidden files, rate limits, size)
    ├─ Run content through output_validator (secrets, injection)
    ├─ Classify risk level (low/medium/high/critical)
    │
    ▼
Tower run created (workflow_id="code_change")
    │
    ├─ Node 1: validate (defense-in-depth re-validation)
    ├─ Node 2: commit (create_branch → commit → create_pr)
    ├─ Node 3: audit (tower_effects, ticket, memory episode)
    │
    ▼
PR created on GitHub (feature branch, never master)
    │
    ▼
Holly can merge the PR (merge_pull_request tool)
    │
    ▼
Holly can deploy (deploy_self tool → build → push → register → update ECS)
```

**Key properties:**
- Holly CAN auto-execute changes — no hard code gate blocks her
- All code changes go to feature branches (never direct to master)
- PRs are created automatically — Holly can merge them herself
- Every action (write, merge, deploy) is recorded in the audit trail
- Tower run provides durability, event timeline, and audit — not a human gate

---

## 2a. Consultation Norm (Prompt-Level, Not Code)

Holly should feel genuinely nervous about code changes. This is healthy and intentional.

| Risk Level | Behavior |
|------------|----------|
| **Low** + solid plan | Proceed guilt-free. No need to consult. |
| **Medium** | Check if Principal is reachable (recent activity in Holly sidebar). If yes, describe the plan and ask for concurrence before executing. If unreachable, proceed but label PR `needs-review`. |
| **High** | Strongly prefer waiting for Principal concurrence. If unreachable for 2+ hours and the change is urgent, proceed but label PR `high-risk` and send a notification. |
| **Deployments** | Always try to reach Sean first. If unreachable and deploy is needed (e.g., fixing a production bug), proceed but send notification and record reasoning. |

This is a *practice*, not a hard gate. Holly has judgment. The system prompt language makes her feel the weight of code changes without paralyzing her.

---

## 3. Risk Classification

| Risk Level | Criteria | PR Labels | Blocked? |
|------------|----------|-----------|----------|
| **Low** | Docs, comments, test files only | (none) | No |
| **Medium** | New tool, new workflow, new MCP server | `needs-review` | No |
| **High** | Modifying existing behavior, changing agent configs | `needs-review`, `high-risk` | No |
| **Critical** | Anything in the MUST NOT list (Section 1) | N/A | **YES — blocked in code** |

Risk is classified automatically by `propose_code_change` based on file paths:
- Files in `tests/`, `docs/` → Low
- New files in `src/tools/`, `src/workflows/`, `src/mcp/` → Medium
- Modifications to existing files in `src/` → High
- Files in forbidden list → Critical (rejected)

---

## 4. Audit Trail

Every code change produces the following records:

| Record | Location | Contents |
|--------|----------|----------|
| Tower run | `tower_runs` table | workflow_id, status, timestamps, input |
| Tower events | `tower_run_events` table | Timeline of validate → commit → audit |
| Tower ticket | `tower_tickets` table | ticket_type="code_change", context_pack with diff |
| Tower effect | `tower_effects` table | commit SHA, PR URL, branch name |
| Git commit | GitHub | Commit message with metadata, Tower run ID |
| Pull request | GitHub | Description with intent, risk level, file list |
| Memory episode | `holly_memory_episodes` table | Summary of what changed and why |

For deployments, additional records:
- `tower_effects` with image tag, task def revision, health check result
- Memory episode with deployment reasoning and outcome

---

## 5. Rollback Protocol

| Scenario | Action |
|----------|--------|
| PR not yet merged | Delete branch + close PR |
| Merged but not deployed | `git revert <sha>` on master via same approval flow |
| Deployed and broken | Auto-rollback to previous task def revision (built into deploy workflow) |
| Deploy health check fails | Automatic: revert to previous ECS task definition, notify Principal |

Holly can propose reverts through the same `propose_code_change` flow. Rollbacks follow identical governance rules.

---

## 6. Rate Limits

| Limit | Value | Purpose |
|-------|-------|---------|
| Proposals per hour | 5 | Prevent runaway modification loops |
| Files per proposal | 20 | Bound blast radius of single change |
| Total content per proposal | 50 KB | Prevent massive untested changes |
| Per-file cooldown | 10 minutes | Prevent rapid iterations on same file |
| Concurrent deploys | 1 | Never overlap deployments |

Rate limits are enforced in `propose_code_change` before any git artifacts are created. Exceeding a limit returns a clear error with the specific limit hit.

---

## 7. Content Safety

Before any content is committed to git:

1. **Output validator scan** — All file content runs through `src/guardrails/output_validator.py`
   - Catches: API keys (Stripe, Shopify, AWS, Anthropic, OpenAI, Slack, etc.)
   - Catches: Injection patterns (`<script>`, SQL injection, shell injection)
   - If any pattern matches → proposal rejected, run marked failed, no git artifacts

2. **Feature branch isolation** — All changes go to feature branches. Master is never modified directly.

3. **Squash merge** — PRs merge via squash, keeping master history clean and revertible.
