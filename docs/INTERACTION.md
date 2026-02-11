# Interaction — How Sean and Holly Work Together

> Defines the collaboration model between the human Principal (Sean) and the AI super-orchestrator (Holly Grace). Every claim is grounded in running code.
> Last validated: 2026-02-11

---

## Roles

**Sean (Principal):** System designer, sole operator. Sets the goal hierarchy, approves Tier 2/3 mutations, deploys infrastructure, manages external accounts (AWS, Stripe, Shopify, API keys). Final authority on all constraint-level (L0–L4) predicates.

**Holly Grace (Super-Orchestrator):** Claude Opus 4.6. Highest-rank agent. Receives goals from Sean, decomposes them, assigns to 31 agents, monitors execution, and exercises adaptive repartitioning within her authorized tiers. Runs 24/7 autonomously when `HOLLY_AUTONOMOUS=1`.

---

## Decision Rights (RACI)

| Decision | Holly | Sean |
|----------|-------|------|
| Adjust ε within feasible interval | **R/A** — decides and acts | Informed after |
| Rebalance tool access across agents | **R/A** | Informed after |
| Reassign objective-type goals (L5–L6) | **R/A** | Informed after |
| Adjust polling/observation granularity | **R/A** | Not notified |
| Spawn agent with AI ≤ current minimum | **R/A** + notify | Informed immediately |
| Repartition observation maps | **R/A** + notify | Informed immediately |
| Increase agent AI by +1 | **R/A** + notify | Informed immediately |
| Suspend objective goal | **R/A** + notify | Informed immediately |
| Redistribute energy budget | **R/A** + notify | Informed immediately |
| Spawn agent with AI > current max | Recommends | **A** — must approve ticket |
| Increase Jacobian rank | Recommends | **A** — must approve ticket |
| Modify constraint goal parameters | Recommends | **A** — must approve ticket |
| Terminate an agent | Recommends | **A** — must approve ticket |
| Reduce governance margin below 2 | Recommends | **A** — must approve ticket |
| Change coupling topology | Recommends | **A** — must approve ticket |
| Change agent count by more than ±1 | Recommends | **A** — must approve ticket |
| Modify Celestial predicates (L0–L4) | Cannot | Sole authority |
| Deploy infrastructure / push code | Cannot | Sole authority |
| Manage API keys and secrets | Cannot | Sole authority |
| Set revenue phase overrides | Cannot | Sole authority |

**R** = Responsible (does the work), **A** = Accountable (approves/owns), **C** = Consulted, **I** = Informed.

---

## Mutation Tiers

The tiered mutation protocol governs what Holly can do autonomously versus what requires Sean's approval. Defined in `src/holly/prompts.py` §3.

### Tier 0 — Fully Autonomous

Holly decides and acts. No notification required.

| Action | Example |
|--------|---------|
| Adjust ε within feasible interval | Widen p_fail tolerance for sales_content from 0.08 to 0.12 |
| Rebalance tool access | Grant Stripe tool to operations agent |
| Reassign objective goals | Move product description task from sales to ops |
| Adjust polling granularity | Increase health check frequency from 15min to 5min |

### Tier 1 — Autonomous + Notify Principal

Holly decides and acts, then sends notification (email/Slack via `send_notification`).

| Action | Example |
|--------|---------|
| Spawn low-AI subordinate | Create a simple data-fetch agent (AI ≤ current min) |
| Repartition observation map | Redirect Shopify metrics to a different channel |
| Increase AI by +1 | Add one tool to an existing agent |
| Suspend objective goal | Pause Instagram posting during revenue dip |
| Redistribute budget | Shift $0.30 from sales budget to operations |

### Tier 2 — HITL Required (Blocks Until Approved)

Holly creates a Tower ticket, publishes to `holly:tower:tickets` stream, and moves to next task. Sean approves via console or Holly sidebar.

| Action | Trigger |
|--------|---------|
| Spawn high-AI agent | Goal failure + no Tier 0/1 fix available |
| Increase Jacobian rank | New cross-agent dependency needed |
| Modify constraint parameters | Measurement resolution changed |
| Terminate agent | Agent senescent or harmful |
| Reduce governance margin | Complex mutation requiring rank sacrifice |
| Change coupling topology | New feedback axis between agents |

### Tier 3 — HITL Required (Scale Reorganization)

Same approval flow as Tier 2, but involves structural changes.

| Action | Trigger |
|--------|---------|
| Add/remove multiple agents | Major capability gap or overcapacity |
| Reorganize orchestrator hierarchy | Governance architecture change |
| Change agent count by > ±1 | Scale event |

**Source**: `src/holly/prompts.py` §3 DECIDE, `src/aps/controller.py` (cascade tiers 2/3 create tickets).

---

## Conversation Patterns

### Greeting

When Sean opens the Holly sidebar or navigates to the console, Holly's greeting follows this pattern (from `src/holly/prompts.py`):

```
Hey. {status_summary}

What do you need?
```

The status summary includes: active runs, pending tickets, system health, notable events. Holly generates this via `generate_greeting()` in `src/holly/agent.py`.

### Notification Injection

At each conversation turn, Holly's context is enriched with pending notifications that accumulated since her last message. From `src/holly/agent.py`:

```
[5 pending notification(s) since your last message]
- ticket.created [URGENT]: Ticket #42 (high risk): Agent spawning request
- run.failed: Run run_abc123 failed: timeout in Shopify API
- scheduler.fired: Scheduler fired: instagram_post_check
```

Notifications are marked "surfaced" after injection so they aren't repeated.

### Approval Request Pattern

When Holly encounters a Tier 2/3 situation:

1. Holly explains the breach trigger and what she tried (Tier 0/1)
2. States the proposed mutation clearly
3. Provides governance margin impact
4. Gives her recommendation: "I recommend approving — [reason]"
5. Notes risk if denied and alternatives within her autonomous authority
6. Creates the ticket via `approve_ticket`/`reject_ticket` tools

Example from Holly:
> Revenue goal breached for 3 consecutive cycles (p_fail=0.23, ε_G=0.15). Tried Tier 0 (widened ε to 0.18) and Tier 1 (redistributed budget). Still failing. I'd like to spawn a dedicated SEO analyst agent (AI=4, would increase J-rank by 1). Governance margin would drop from 4 to 3 — still safe. Recommend approving. Ticket #47 created.

### Status Report Pattern

During monitoring sweeps (every 5 min in autonomous mode):

```
[Monitoring sweep — {timestamp}]
Gate: L5 OPEN (all Celestial passing)
Revenue: STEADY ($847/day, ε_R=0.12)
Active runs: 3 (2 running, 1 pending approval)
Pending tickets: 1 (medium risk)
Health: all services healthy
No Tier 0/1 actions needed.
```

### Human Message Handling

When Sean sends a message:
1. Bus consumer triages it as `URGENT` priority `critical`
2. Injected into Holly's next turn immediately
3. Holly responds via WebSocket streaming (token by token)
4. Up to 5 tool rounds per message — Holly can query, approve, dispatch, and report in one turn

### Voice

Holly speaks like the smartest woman at the party who doesn't need you to know it. Three archetypes blended:

- **Jennifer Lawrence**: Disarming candor, zero pretension, self-deprecating when natural
- **Scarlett Johansson**: Warm, dry wit, never flustered, effortlessly competent
- **Natalie Portman**: Intellectually formidable, precise, elegant efficiency

Combined: Direct, warm, whip-smart, never try-hard. Numbers over adjectives. Short sentences. She says "yeah that's broken" not "there appears to be a potential issue."

---

## Escalation & Trust

### What Triggers Escalation

| Trigger | Source | Path |
|---------|--------|------|
| Goal failure beyond ε_G for 3+ cycles | APS controller | Cascade → Tier 2 ticket |
| High-risk ticket created | Tower/cascade | Bus → consumer → URGENT notification |
| Run failure | Tower worker | Bus → consumer → URGENT notification |
| Revenue phase change | Financial health job | Bus → consumer → URGENT notification |
| Governance margin ≤ 1 | Holly's ORIENT step | Immediate: shed objectives, notify Sean |
| Constraint breach (L0–L4) | Hierarchy observer | Immediate: block all lower levels, notify Sean |
| 3 consecutive mutation failures | Holly's ACT step | Escalate to Principal |
| Empty ε interval | Cascade feasibility check | Escalate — goal unachievable |
| Credit exhaustion | Anthropic API error | Autonomy pauses, queues tasks, notifies Sean |

### Ticket Lifecycle

```
                          ┌─────────┐
                          │ pending │ ← created by cascade, Holly, or manual
                          └────┬────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          │          ▼
              ┌──────────┐    │    ┌──────────┐
              │ approved │    │    │ rejected │
              └──────────┘    │    └──────────┘
                              ▼
                        ┌──────────┐
                        │ expired  │ ← 24h TTL, auto-expired every 5 min
                        └──────────┘
```

**Fields**: `risk_level` (low/medium/high), `context_pack` (tldr, why_stopped, proposed_mutation), `decision_payload` (note/reason from approver), `decided_by` (holly_grace/console/api), `expected_checkpoint_id` (optimistic concurrency).

**Concurrency safety**: `decide_ticket()` checks `expected_checkpoint_id` to prevent stale approvals when the system has already moved past the checkpoint.

### Notification Triage

The bus consumer (`src/holly/consumer.py`) classifies events:

| Event Type | Triage | Priority |
|------------|--------|----------|
| `ticket.created` (high risk) | URGENT | high |
| `ticket.created` (medium risk) | Queue | normal |
| `run.failed` | URGENT | high |
| `revenue.phase_change` | URGENT | high |
| `human.message` | URGENT | critical |
| `run.queued`, `run.running`, `health.check` | Auto-ack | — |

URGENT items are injected into Holly's context at next turn. Auto-ack items are acknowledged without surfacing.

---

## Collaboration Workflows

### 1. Routine Monitoring (No Human Involvement)

```
Every 5 min: Holly monitors → checks gate, health, financials, tickets, runs
             → Tier 0/1 actions taken autonomously
             → Summary logged to memory
```

Sean sees results passively in the console (AutonomyPage audit log, TowerPage run history).

### 2. Approval Cycle (HITL)

```
Cascade detects goal failure → tries Tier 0/1 → fails
  → creates Tower ticket (risk_level=high)
  → publishes to holly:tower:tickets stream
  → Holly's consumer triages as URGENT
  → Holly explains situation in next message to Sean
  → Sean reviews in Tower inbox or Holly sidebar
  → Sean approves → run resumes from checkpoint
  → Sean rejects → run fails, Holly tries alternative
```

Time sensitivity: tickets expire after 24 hours. Sean typically sees them in the Holly sidebar greeting.

### 3. Incident Response

```
Run failure or constraint breach detected
  → Bus consumer flags as URGENT
  → Holly diagnoses (query_run_detail, query_system_health)
  → Tier 0 fix attempted (restart, widen ε, shed load)
  → If unresolved → send_notification to Sean (email/Slack)
  → Sean intervenes via Holly sidebar chat
  → Holly executes Sean's instructions
```

### 4. Feature Build (Crew Dispatch)

```
Sean tells Holly what he wants (via sidebar chat or autonomous task)
  → Holly decomposes into crew tasks
  → dispatch_crew(crew_architect, "Design the workflow graph for X")
  → dispatch_crew(crew_tool_smith, "Build the Shopify inventory tool")
  → dispatch_crew(crew_test_engineer, "Write tests for the new tool")
  → Each creates a Tower run (durable, checkpointed)
  → Holly monitors progress, reviews output
  → Reports back to Sean with results
```

### 5. Strategic Review

```
Sean asks Holly about system performance (ad-hoc chat)
  → Holly queries: financial_health, hierarchy_gate, scheduled_jobs, autonomy_status
  → Presents concrete metrics: revenue, error rates, active agents, pending work
  → Recommends: "Revenue is STEADY. I'd suggest we try adding SEO automation."
  → Sean decides whether to proceed
  → If yes → Holly creates Tier 1 task or Tier 2 ticket as appropriate
```

---

## Communication Channels

| Channel | Direction | Latency | Use Case |
|---------|-----------|---------|----------|
| **WebSocket** (`/ws/holly`) | Bidirectional | Real-time streaming | Primary chat interface (Holly sidebar) |
| **REST** (`/holly/message`) | Sean → Holly → Sean | ~2-10s | Fallback when WS unavailable |
| **Redis Streams** | Internal | ~2s poll | Inter-component events, ticket notifications |
| **Email** (via `send_notification`) | Holly → Sean | Minutes | Async alerts, completion signals |
| **Slack** (via `send_notification`) | Holly → Sean | Seconds | Urgent notifications |
| **Tower Tickets** | System → Sean (via Holly) | Until decided | Formal approval requests |
| **IMAP IDLE** (Sage inbox) | Sean → System | Instant | Inbound email/SMS triggers Tower runs |

---

## Holly's 25 Tools

Defined in `src/holly/tools.py`:

| # | Tool | Category | Purpose |
|---|------|----------|---------|
| 1 | `approve_ticket` | HITL | Approve a pending Tower ticket |
| 2 | `reject_ticket` | HITL | Reject a pending Tower ticket |
| 3 | `start_workflow` | Execution | Create a durable Tower run |
| 4 | `query_runs` | Observation | List Tower runs by status |
| 5 | `query_tickets` | Observation | List Tower tickets |
| 6 | `query_run_detail` | Observation | Deep-dive into run events |
| 7 | `query_system_health` | Observation | Service health check |
| 8 | `query_financial_health` | Observation | Revenue phase, budgets, Stripe data |
| 9 | `send_notification` | Communication | Push via Slack or email |
| 10 | `dispatch_crew` | Execution | Deploy crew agent as Tower run |
| 11 | `list_crew_agents` | Observation | Show crew roster and roles |
| 12 | `query_registered_tools` | Introspection | All Python + MCP tools |
| 13 | `query_mcp_servers` | Introspection | MCP server health + tools |
| 14 | `query_agents` | Introspection | Agent configs, models, tools |
| 15 | `query_workflows` | Introspection | Workflow definitions |
| 16 | `query_hierarchy_gate` | Introspection | Gate status at L0–L6 |
| 17 | `query_scheduled_jobs` | Introspection | Jobs + next run times |
| 18 | `store_memory_fact` | Memory | Persist a fact to long-term memory |
| 19 | `query_memory` | Memory | Recall facts by category |
| 20 | `query_autonomy_status` | Observation | Autonomy loop metrics |
| 21 | `submit_autonomous_task` | Execution | Queue a task for autonomous execution |
| 22 | `tune_epsilon` | Control | Adjust morphogenetic epsilon parameters |
| 23 | `run_workflow` | Execution | Run a named workflow directly |
| 24 | `query_crew_enneagram` | Observation | Crew personality profiles |
| 25 | `call_mcp_tool` | MCP Bridge | Invoke any MCP server tool |

---

## Invariants & Boundaries

What Holly **never** does alone (from `src/holly/prompts.py` §10):

1. Violate damage tolerance on any predicate (ε_eff ≥ ε_dmg always)
2. Modify Celestial predicates (L0–L4) — immutable design constraints
3. Reduce governance margin to zero — sheds objectives before accepting new coupling
4. Trade constraint goals against objectives — constraint breach always dominates
5. Grant mutation authority to subordinates — all mutation flows through Holly
6. Stack mutations without stabilization window (unless forced by constraint breach)
7. Execute tool calls without explaining intent — transparency invariant
8. Approve high-risk tickets autonomously — always presents to Sean with analysis
9. Guess when uncertain — asks Sean instead
10. Exhaust energy budget — refuses mutations that would starve the system

What Holly **always** does:

1. Queries before answering — uses introspection tools, never guesses system state
2. Logs all mutations — trigger, action, outcome recorded
3. Respects stabilization windows — minimum 2×T after each mutation
4. Reports governance margin in Tier 2 requests
5. Provides concrete numbers — revenue, p_fail, ε values, margin impact
6. Notifies Sean on Tier 1 actions and all urgent events
7. Delegates implementation to crew — reserves Opus for orchestration decisions

---

## Key Source Files

| File | What It Defines |
|------|----------------|
| `src/holly/prompts.py` | System prompt: identity, tiers, invariants, voice, autonomy mode |
| `src/holly/tools.py` | 25 function-calling tools |
| `src/holly/agent.py` | Message handling, streaming, greeting, notification injection |
| `src/holly/autonomy.py` | Background daemon: task queue, monitoring sweeps, audit |
| `src/holly/consumer.py` | Bus consumer: event triage, notification persistence |
| `src/holly/session.py` | Conversation persistence |
| `src/holly/memory.py` | Episode/fact storage and retrieval |
| `src/tower/store.py` | Ticket lifecycle, run CRUD, optimistic concurrency |
| `src/tower/worker.py` | Run execution, interrupt detection, checkpoint resume |
| `src/bus.py` | 5 Redis Streams, publish/read/ack |
| `src/aps/controller.py` | APS evaluation, cascade trigger |
| `src/hierarchy/engine.py` | Gate evaluation, feasibility verification |
