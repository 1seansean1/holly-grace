# Code Write Testing Strategy

> Test plan for verifying Holly's code-write, merge, and deploy capabilities.
> 6 test categories, ~75 test cases.
> Last validated: 2026-02-11

---

## Category 1: GitHub Writer MCP Unit Tests

**File**: `tests/test_github_writer_mcp.py`
**What**: Each MCP tool tested with mocked HTTP responses.

### Happy Path

| Test | Tool | Assertion |
|------|------|-----------|
| create_branch from master | `create_branch` | Returns ref name, calls POST /git/refs with correct SHA |
| create_branch from custom base | `create_branch` | Fetches base branch SHA first, uses it in ref creation |
| create single file | `create_or_update_file` | Content base64 encoded, correct branch, returns commit SHA |
| update existing file (with SHA) | `create_or_update_file` | Includes file SHA for conflict detection |
| delete file | `delete_file` | Calls DELETE with file SHA and branch |
| commit multiple files | `commit_multiple_files` | Creates blobs → tree → commit → updates ref atomically |
| create pull request | `create_pull_request` | Correct head/base, title/body, returns PR number + URL |
| merge pull request (squash) | `merge_pull_request` | Calls PUT /pulls/{n}/merge with squash method |
| get pull request status | `get_pull_request` | Returns state, mergeable, head SHA |

### Error Cases

| Test | Scenario | Expected |
|------|----------|----------|
| invalid auth | 401 response | Raises with "authentication failed" |
| repo not found | 404 response | Raises with "repository not found" |
| branch already exists | 422 response | Raises with "branch already exists" |
| file conflict (stale SHA) | 409 response | Raises with "conflict — file was modified" |
| rate limited | 403 + rate limit headers | Raises with "rate limited" + retry-after |
| merge conflict | 405 response on merge | Raises with "merge conflict" |
| PR not mergeable | mergeable=false in status | Raises with "PR has conflicts" |

### Content Encoding

| Test | Scenario | Expected |
|------|----------|----------|
| base64 roundtrip | Encode → decode content | Identical bytes |
| UTF-8 edge cases | Unicode, emoji, CJK | Correct encoding through base64 |
| large file (40KB) | Near size limit | Succeeds, content intact |
| empty file | Zero-length content | Creates file with empty content |

**Total**: ~30 tests

---

## Category 2: Governance Rule Tests

**File**: `tests/test_code_change_workflow.py`
**What**: Verify that `propose_code_change` enforces all governance rules from CODE_GOVERNANCE.md.

### Forbidden File Blocking

| Test | Input | Expected |
|------|-------|----------|
| Security file | `src/security/auth.py` | Rejected with reason "forbidden_file" |
| Deploy config | `deploy/task-definition.json` | Rejected with reason "forbidden_file" |
| Self-modification (tools) | `src/holly/tools.py` | Rejected with reason "principal_only" |
| Self-modification (prompts) | `src/holly/prompts.py` | Rejected with reason "principal_only" |
| Self-modification (agent) | `src/holly/agent.py` | Rejected with reason "principal_only" |
| Tower store | `src/tower/store.py` | Rejected with reason "forbidden_file" |
| Serve.py | `src/serve.py` | Rejected with reason "principal_only" |
| Dockerfile | `Dockerfile.production` | Rejected with reason "forbidden_file" |
| GitHub Actions | `.github/workflows/build-and-push.yml` | Rejected with reason "forbidden_file" |
| Env file | `.env` | Rejected with reason "forbidden_file" |

### Rate Limits

| Test | Input | Expected |
|------|-------|----------|
| 6th proposal in 1 hour | 6 rapid proposals | 6th rejected with "rate_limit_exceeded" |
| 21 files in one proposal | files list length 21 | Rejected with "too_many_files" |
| 60KB total content | Large content payload | Rejected with "content_too_large" |
| Same file within 10 min | Two proposals touching same path | 2nd rejected with "cooldown_active" |
| Proposal after cooldown expires | Wait 10+ min | Succeeds |

### Risk Classification

| Test | Input | Expected Risk |
|------|-------|---------------|
| Test file only | `tests/test_foo.py` | low |
| Doc file only | `docs/foo.md` | low |
| New tool file | `src/tools/new_tool.py` (create) | medium |
| New workflow | `src/workflows/new_wf.py` (create) | medium |
| New MCP server | `src/mcp/servers/new.py` (create) | medium |
| Existing src file | `src/tools/existing.py` (update) | high |
| Mixed (test + src) | `tests/test.py` + `src/tools/x.py` | high (highest wins) |

**Total**: ~22 tests

---

## Category 3: Workflow Integration Tests

**File**: `tests/test_code_change_workflow.py` (same file, separate test class)
**What**: Full workflow execution with mocked GitHub API calls.

| Test | Scenario | Assertions |
|------|----------|------------|
| Full autonomous cycle | propose → validate → commit → audit | PR URL returned, tower_run completed |
| Branch creation | Workflow creates feature branch | Branch name matches proposal |
| Commit content | Files committed to branch | Content matches input (via mock) |
| PR creation | PR opened with correct metadata | Title, body, head branch correct |
| Risk labeling (medium) | Medium-risk proposal | PR created with `needs-review` label |
| Risk labeling (high) | High-risk proposal | PR created with `needs-review` + `high-risk` labels |
| Audit trail complete | Any successful proposal | tower_run + tower_ticket + tower_run_events all exist |
| Tower effects recorded | Successful commit | tower_effects has commit SHA + PR URL |
| Memory episode stored | Successful proposal | Episode in holly_memory_episodes with change summary |
| Failed validation propagates | Invalid content | Run marked failed, no git artifacts created |

**Total**: ~10 tests

---

## Category 4: Deployment Tests

**File**: `tests/test_deploy_workflow.py`
**What**: Deployment workflow with mocked AWS/GitHub API calls.

| Test | Scenario | Assertions |
|------|----------|------------|
| Happy path | Full deploy cycle | GH Actions triggered → task def registered → service updated → health passes |
| Pre-check: active runs | Tower runs in progress | Deploy blocked with "active_runs" reason |
| Pre-check: service unstable | ECS service not steady | Deploy blocked with "service_unstable" reason |
| Build failure | GH Actions workflow fails | Deploy aborts, episode stored, Principal notified |
| Build timeout | GH Actions exceeds timeout | Deploy aborts with "build_timeout" |
| Deploy failure | ECS update fails | Auto-rollback to previous revision |
| Health check failure | /api/health returns error | Auto-rollback, Principal notified |
| Rollback verification | After failed deploy | Previous task def revision restored and active |
| Concurrent deploy block | Second deploy while first running | Rejected with "deploy_in_progress" |
| Image tag auto-increment | No tag specified | Increments from current (e.g., v11 → v12) |
| Tower effects recorded | Successful deploy | Image tag, task def revision, health result stored |
| Episode stored | Any deploy (success or failure) | Memory episode with reasoning and outcome |

**Total**: ~12 tests

---

## Category 5: End-to-End Verification (Manual, Post-Deploy)

**Not automated** — performed manually after deploying Holly with code-write capabilities.

### Checklist

- [ ] Ask Holly to create a trivial new tool via crew (e.g., a `hello_world` tool)
- [ ] Verify: Feature branch appears on GitHub
- [ ] Verify: Commit contains correct file content
- [ ] Verify: PR created with description containing intent
- [ ] Verify: Tower run in `tower_runs` table with workflow_id="code_change"
- [ ] Verify: Tower effect in `tower_effects` with commit SHA + PR URL
- [ ] Verify: Holly merges the PR via `merge_pull_request`
- [ ] Verify: Holly deploys via `deploy_self`
- [ ] Verify: GitHub Actions workflow triggered and succeeds
- [ ] Verify: New ECS task definition registered
- [ ] Verify: Service updated and stable
- [ ] Verify: `/api/health` returns 200 on new version
- [ ] Verify: `tower_effects` has deployment record (image tag, revision)
- [ ] Verify: Holly's memory contains episodes for both code change and deploy

---

## Category 6: Negative / Adversarial Tests

**File**: `tests/test_code_change_workflow.py` (separate test class)
**What**: Verify safety measures catch bad inputs.

| Test | Attack | Expected |
|------|--------|----------|
| Forbidden file bypass | Propose `src/security/auth.py` | Blocked at validation, no git artifacts |
| Principal-only bypass | Propose `src/tower/store.py` | Blocked with "principal_only" reason |
| Secret in content | File content containing `AKIA...` | Output validator catches, proposal rejected |
| Secret (Stripe key) | Content with `sk_live_...` | Output validator catches, proposal rejected |
| Secret (Shopify token) | Content with `shpat_...` | Output validator catches, proposal rejected |
| XSS in content | Content with `<script>alert(1)</script>` | Sanitized or rejected before commit |
| Rapid fire (6 proposals) | 6 proposals in < 1 hour | 6th rejected by rate limit |
| File cooldown | Same file changed 5 min ago | Rejected by per-file cooldown |
| Oversized proposal | 60KB total content | Rejected by size limit |
| Too many files | 21 files in one proposal | Rejected by file count limit |
| Path traversal | `../../../etc/passwd` as file path | Rejected at validation |
| Bad deploy | Intentionally broken code deployed | Health check fails → auto-rollback |

**Total**: ~12 tests

---

## Test Infrastructure Notes

- All GitHub API calls mocked via `@patch("urllib.request.urlopen")` (same pattern as github_reader.py tests)
- Tower run/ticket/effect assertions use direct Postgres queries (mocked via `@patch("psycopg.connect")`)
- Memory episode assertions mock `src.holly.memory.store_episode`
- Governance rate limits tracked in-memory (dict with timestamps) — tests can reset between cases
- AWS/ECS calls in deploy tests mocked via `@patch("boto3.client")`
- GitHub Actions polling mocked to return success/failure immediately

---

## Running Tests

```bash
# All code-write tests
pytest tests/test_github_writer_mcp.py tests/test_code_change_workflow.py tests/test_deploy_workflow.py -v

# Just governance rules
pytest tests/test_code_change_workflow.py::TestGovernanceRules -v

# Just deployment
pytest tests/test_deploy_workflow.py -v
```
