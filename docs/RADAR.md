# Radar — What to Work on Next

> Improvement radar organized by urgency and category. Updated via biweekly sweeps.
> Last sweep: 2026-02-11 (initial)

---

## How This Works

### Four Quadrants

| Quadrant | Question |
|----------|----------|
| **Reliability & Safety** | What could break, lose data, or cause harm? |
| **Correctness & Quality** | What is wrong, stale, or misleading? |
| **Efficiency & Cost** | What is wasteful, slow, or expensive? |
| **Capability & Reach** | What can't the system do that it should? |

### Three Rings

| Ring | Meaning | Action |
|------|---------|--------|
| **INNER** | Active risk or high-leverage fix | Act now |
| **MIDDLE** | Known gap or approaching limit | Plan soon |
| **OUTER** | Theoretical risk or future need | Watch |

---

## Current Radar (Sweep #1 — 2026-02-11)

### INNER — Act Now

| ID | Quadrant | Item | Evidence |
|----|----------|------|----------|
| I-1 | Reliability | **Secrets in git history** | API keys were committed in early development (.env checked in). Keys rotated, but old values persist in git history. |
| I-2 | Correctness | **docs/SYSTEM.md is 2,256 lines and stale** | Last accurate ~Feb 8. Missing Holly, Tower, hierarchy, bus, crew, autonomy, MCP, solana tools. Now superseded by ARCHITECTURE.md. Scheduled for deletion. |
| I-3 | Correctness | **Holly's prompt says 18 tools, actual count is 25** | `src/holly/prompts.py` §0 says "18 function-calling tools." Actual tools in `src/holly/tools.py`: 25. Drift from code additions. |
| I-4 | Reliability | **No CI/CD pipeline** | Manual 7-step deploy process. Cookie Secure flag bug was only caught in production (ADR-013). |
| I-5 | Reliability | **No database backups configured** | RDS likely has automated snapshots (AWS default), but no explicit backup strategy documented or verified. |

### MIDDLE — Plan Soon

| ID | Quadrant | Item | Evidence |
|----|----------|------|----------|
| M-1 | Efficiency | **Opus 4.6 cost for Holly** | Every Holly message costs ~$0.10-0.50 in Opus tokens. Autonomous monitoring sweeps every 5 min compound this. Revenue must grow to sustain. |
| M-2 | Reliability | **Single-container architecture** | Agents, console, nginx all in one container. If agents crash, console goes down too. No independent scaling. |
| M-3 | Correctness | **44 tables with no migration tool** | CREATE TABLE IF NOT EXISTS only. No column drops or renames possible without manual SQL. Orphaned columns accumulate (ADR-014). |
| M-4 | Capability | **No automated testing on deploy** | Tests exist (1100+) but aren't run automatically before or after deployment. |
| M-5 | Efficiency | **aps_observations table growth** | Every APS evaluation (5-min cycle) writes observations. ~288/day per channel. No archival strategy. |
| M-6 | Reliability | **No staging environment** | All deploys go directly to production (ADR-016). Only rollback is previous task definition revision. |
| M-7 | Capability | **Holly cannot write code** | MCP GitHub reader is read-only. Holly can propose improvements via crew agents but implementation requires Sean's manual code deployment. |
| M-8 | Correctness | **holly-human-dynamics docs are 60% aspirational** | 17 files created in one session. Many describe capabilities that don't exist or contradict reality. Scheduled for deletion with this doc set. |

### OUTER — Watch

| ID | Quadrant | Item | Evidence |
|----|----------|------|----------|
| O-1 | Reliability | **Redis single point of failure** | If Redis dies: no bus events, no autonomy queue, no idempotency checks. Production uses ElastiCache (managed) but local dev uses single container. |
| O-2 | Efficiency | **Ollama GPU memory (4GB VRAM)** | RTX 2050 with 4GB VRAM limits local model size. qwen2.5:3b fits but larger models won't. Production doesn't use Ollama (remaps to GPT-4o-mini). |
| O-3 | Capability | **No multi-tenant support** | Single Shopify store, single operator. If Liberty Forge adds a second store, major refactoring needed. |
| O-4 | Reliability | **Tower ticket 24h expiry** | If Sean doesn't check tickets for 24h, Tier 2 mutations expire. The cascade may re-trigger the same ticket indefinitely. |
| O-5 | Capability | **No webhook write access** | Inbound webhooks (Shopify, Stripe) work. Outbound webhook subscriptions require manual setup. |
| O-6 | Efficiency | **ChromaDB embedding model fixed** | all-MiniLM-L6-v2 auto-downloaded on first use. No way to switch embedding models without re-indexing. |

---

## Sweep Process

Run every 2 weeks or after any incident.

### 1. Validate counts against ARCHITECTURE.md
```bash
# Tables
grep -c "CREATE TABLE" src/**/*.py
# Expected: 44 (check against ARCHITECTURE.md Data Architecture section)

# Agents
curl http://localhost:8050/agents | python -c "import sys,json; print(json.load(sys.stdin)['agents'].__len__())"
# Expected: 31 (16 workflow + 15 crew)

# Endpoints (rough count from serve.py)
grep -c "@app\.\(get\|post\|put\|delete\|websocket\)" src/serve.py
# Expected: ~105

# Scheduled jobs
curl http://localhost:8050/scheduler/jobs | python -c "import sys,json; print(json.load(sys.stdin)['count'])"
# Expected: 18
```

### 2. Review incidents since last sweep
- Check DLQ: `GET /scheduler/dlq` — any unresolved entries?
- Check Tower failures: `GET /tower/runs?status=failed` — any new patterns?
- Check autonomy audit: `GET /holly/autonomy/audit?limit=50` — failure rate?
- Check CloudWatch for ERROR level logs

### 3. Detect drift between docs and reality
- Compare ARCHITECTURE.md table counts with actual database
- Compare INTERACTION.md tool count with `src/holly/tools.py`
- Verify all scheduled jobs in autonomous.py match ARCHITECTURE.md table

### 4. Check LLM cost and error rates
- LangSmith dashboard: total cost since last sweep
- Anthropic console: Holly's token usage
- OpenAI dashboard: GPT-4o/mini usage
- Look for cost anomalies (>2x baseline)

### 5. Move items between rings
- OUTER → MIDDLE: when theoretical risk becomes a near-miss
- MIDDLE → INNER: when gap starts causing problems
- INNER → resolved: when fix is deployed and verified
- Add new items discovered during sweep

---

## Resolved Items

| Date | ID | Item | Resolution |
|------|----|------|------------|
| 2026-02-11 | — | Cookie Secure flag blocking login | Conditional flag based on X-Forwarded-Proto (v10 deploy) |
| 2026-02-11 | — | Console not deployed | Combined Dockerfile.production with nginx proxy |
| 2026-02-11 | — | Rogue ALB listener rules | Deleted stale rules, verified single listener |
| 2026-02-11 | I-2 | Stale docs | Replaced with 5 living docs (this sweep) |
| 2026-02-11 | M-8 | Aspirational holly-human-dynamics | Deleted, content folded into INTERACTION.md |
