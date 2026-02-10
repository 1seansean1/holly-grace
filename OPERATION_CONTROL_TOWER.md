# OPERATION CONTROL TOWER
### Holly Grace ATC (Air Traffic Control) human interface + durable runs + HITL clearance tickets

Date: 2026-02-10  
Repo: `c:\Users\seanp\Workspace\ecom-agents`  
Primary reference: *Informational Monism, Morphogenetic Agency, and Goal-Specification Engineering* (Allen, Feb 2026)

---

## 0) TL;DR
Stop treating agents as chat sessions. Treat them as **durable, checkpointed workflows** that run autonomously and only surface **structured "clearance requests"** into a single **Approval Inbox** ("control tower").

Core primitives:
- **Run**: LangGraph `thread_id` + Postgres checkpointer + durable event timeline.
- **Ticket**: approval record linked to a run checkpoint + interrupt id.
- **Resume**: `Command(resume=...)` applied to the run `thread_id` with optimistic concurrency on checkpoint id.
- **Exactly-once side effects**: durable effect store + 2-phase prepare/commit for risky actions.

The human interface becomes: Inbox -> Context Pack -> Approve/Edit/Reject -> Resume.

---

## 1) Current State (Repo Reality)
Holly Grace already has multiple key pieces, but they are not yet composed into the ATC model.

### What exists today
- Agents service: `src/serve.py` (FastAPI + LangServe `/agent/*`).
- Master graph: `src/graph.py` (orchestrator routes to specialists; optional sub-agent subgraph).
- Live monitoring:
  - Agents WS: `src/serve.py` exposes `/ws/events`
  - Event bridge: `console/backend/app/services/event_bridge.py` fans out to browser
  - Console WS: `console/backend/app/routers/execution.py` exposes `/ws/execution`
- Approvals:
  - DB table: `approval_queue` (created in `src/aps/store.py`)
  - API endpoints: agents `/approvals/*` in `src/serve.py`
  - Console UI: `console/frontend/src/pages/ApprovalsPage.tsx`
  - Morphogenetic cascade already creates approval records for Tier 2/3:
    - `src/morphogenetic/cascade.py`
- Some "checkpoint" plumbing exists:
  - Table `graph_checkpoints` in `src/aps/store.py`
  - Helper `src/checkpointing.py`

### Critical missing pieces (ATC blockers)
1. The master LangGraph is compiled without a checkpointer:
   - `src/serve.py` does `compiled_graph = graph.compile()` with no checkpointer.
   - Hard constraint: `Command(resume=...)` cannot be used without a checkpointer.
2. Approvals are not integrated into tool execution:
   - `src/dynamic_executor.py` executes tool calls directly.
   - `src/approval.py` exists but does not gate tool execution for most tools.
3. No durable run/timeline contract:
   - No `start_run`, `poll`, `resume_run`, `get_snapshot` API.
   - No event store table for durable timelines (WS broadcast is ephemeral).
4. Live events do not include the `thread_id`/run_id needed to filter per-run in the UI.

---

## 2) Target Architecture (ATC Pattern)
Pattern name:
**Control Tower UI + Tower Orchestrator + Agent Runners + Durable Stores**

Conceptual layout:

```
            +-------------------------------+
            |  Control Tower UI (HITL)      |
            |  - Approval Inbox             |
            |  - Context Pack               |
            |  - Run Timeline + Snapshot    |
            +---------------+---------------+
                            |
                            v
+-----------------------------------------------------+
| Agents Service: Tower Orchestrator + Runner Pool     |
| - start_run / resume_run / snapshots                 |
| - creates tickets (interrupts)                       |
| - enforces governance + concurrency                  |
+------------------+--------------------------+--------+
                   |                          |
                   v                          v
        +-------------------+       +-------------------+
        | Durable Runs (LG) |       | Tickets (HITL)     |
        | thread_id + cp    |       | approval_queue     |
        +---------+---------+       +---------+----------+
                  |                           |
                  v                           v
        +---------------------------------------------+
        | Postgres Durable Stores                      |
        | - LangGraph checkpoint tables (PostgresSaver)|
        | - tower_runs                                 |
        | - tower_run_events (append-only)             |
        | - tower_effects (exactly-once commits)       |
        | - tower_artifacts (large payload refs)       |
        +---------------------------------------------+
```

---

## 3) Required External Contract (API)
Expose an explicit "workflow service" lifecycle API on the agents service.

### Run lifecycle
- `POST /tower/runs/start`
  - Starts an async durable run.
  - Returns `{run_id}` where `run_id == thread_id`.
- `GET /tower/runs/{run_id}`
  - Status, metadata, last checkpoint id, last ticket id.
- `GET /tower/runs/{run_id}/events?after_id=&limit=`
  - Durable timeline.
- `GET /tower/runs/{run_id}/snapshot`
  - Current LangGraph `StateSnapshot` view (values/next/tasks/interrupts).
- `POST /tower/runs/{run_id}/resume`
  - Resume with decision payload, optimistic concurrency on checkpoint id.

### Inbox and tickets
- `GET /tower/inbox?status=pending&system_id=&risk_level=&limit=`
  - Primary ATC query.
- `GET /tower/tickets/{ticket_id}`
  - Ticket detail + context pack + run linkage.
- `POST /tower/tickets/{ticket_id}/decide`
  - Approve/reject/approve-with-edits.
  - If linked to a run: resumes the run.

### Optimistic concurrency
Every ticket decision that resumes a run must include:
- `expected_checkpoint_id`

If the run advanced since the ticket was issued:
- return 409 and require a fresh ticket.

---

## 4) Persistence Model (Postgres)

### 4.1 New tables
Add the following tables (schema is decision-complete; implement via `CREATE TABLE IF NOT EXISTS ...`).

#### `tower_runs`
- `run_id TEXT PRIMARY KEY` (LangGraph thread id)
- `workflow_id TEXT NOT NULL` (default: `default`)
- `system_id TEXT NOT NULL DEFAULT 'primary'` (UI lane/grouping)
- `mission_id TEXT NULL` (optional grouping across spawned runs)
- `parent_run_id TEXT NULL` (hierarchy)
- `status TEXT NOT NULL` (`queued|running|waiting_approval|completed|failed|canceled`)
- `priority INT NOT NULL DEFAULT 5`
- `policy JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_by TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `started_at TIMESTAMPTZ NULL`
- `finished_at TIMESTAMPTZ NULL`
- `last_checkpoint_id TEXT NULL`
- `last_ticket_id BIGINT NULL`
- `last_error TEXT NULL`

Indexes:
- `(status, priority, updated_at DESC)`
- `(system_id, updated_at DESC)`
- `(parent_run_id)`
- `(mission_id)`

#### `tower_run_events` (append-only timeline)
- `id BIGSERIAL PRIMARY KEY`
- `run_id TEXT NOT NULL`
- `event_type TEXT NOT NULL`
- `payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Indexes:
- `(run_id, id)`

#### `tower_effects` (durable exactly-once)
- `effect_id TEXT PRIMARY KEY`
- `run_id TEXT NOT NULL`
- `tool_name TEXT NOT NULL`
- `params_hash TEXT NOT NULL`
- `status TEXT NOT NULL` (`prepared|committed|aborted`)
- `prepared_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `result_payload JSONB NOT NULL DEFAULT '{}'::jsonb`
- `ticket_id BIGINT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `committed_at TIMESTAMPTZ NULL`

Indexes:
- `(run_id, tool_name, created_at DESC)`

#### `tower_artifacts` (optional but planned)
- `artifact_id BIGSERIAL PRIMARY KEY`
- `run_id TEXT NOT NULL`
- `name TEXT NOT NULL`
- `content_type TEXT NOT NULL`
- `storage_type TEXT NOT NULL` (`inline_json|inline_text|file_path`)
- `inline_json JSONB NULL`
- `inline_text TEXT NULL`
- `file_path TEXT NULL`
- `size_bytes INT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Indexes:
- `(run_id, created_at DESC)`

### 4.2 Extend existing `approval_queue` as the unified ticket inbox
Extend `approval_queue` with the following columns:
- `thread_id TEXT NULL`
- `checkpoint_id TEXT NULL`
- `interrupt_id TEXT NULL`
- `context_pack JSONB NULL`
- `decision_payload JSONB NULL`

Indexes:
- `idx_approval_thread` on `(thread_id)` when `thread_id IS NOT NULL`.

Rationale:
- Existing approvals remain valid.
- Tower UI consumes the same underlying queue, but with richer run linkage.

---

## 5) Durable Execution Requirements (LangGraph)

### 5.1 Checkpointer choice
Use `langgraph.checkpoint.postgres.PostgresSaver` (already present in `.venv`).

Startup:
- Call `PostgresSaver.setup()` once on startup (skip when `TESTING=1`).

### 5.2 Invocation requirements
Every durable run must:
- Compile the graph with a checkpointer: `graph.compile(checkpointer=...)`
- Invoke/resume with a stable thread id:

```python
app.invoke(input_state, {"configurable": {"thread_id": run_id}, ...})
```

Interrupt/resume:
- pause: `interrupt(payload)` inside node code
- resume: `invoke(Command(resume=decision_payload), config={"configurable":{"thread_id":run_id}})`

---

## 6) Ticket Design (Interrupts) + Context Packs

### 6.1 Ticket payload schema (interrupt payload)
Minimal required fields:
- `ticket_type`: `tool_call|morphogenetic|publish|spend|write_db|external_comm|config_change`
- `run_id` (thread id)
- `checkpoint_id`
- `interrupt_id`
- `proposed_action` (typed object)
- `risk`: `low|medium|high`
- `policy_triggers`: list of strings
- `allowed_edits`: JSON pointer-like paths or explicit field list
- `evidence_refs`: list of `{event_id|artifact_id|trace_id}`
- `expires_at`

### 6.2 Context Pack (UI contract)
Stored as JSON in `approval_queue.context_pack`:
- `tldr`
- `why_stopped`
- `proposed_action_preview`
- `impact`
- `risk_flags`
- `evidence` (top 3)
- `options` (approve / approve-with-edits schema / reject reasons)
- `breadcrumb` (next nodes/tasks, checkpoint id, run metadata)

Generation:
- deterministic template
- small/cheap model with hard token cap
- output sanitized (reuse output guardrails)

---

## 7) Exactly-Once Side Effects (Replay Safety)
Problem:
- LangGraph can replay code around interrupts on resume. Risky side effects must not duplicate.

Solution:
- Use `tower_effects` as the durable idempotency source of truth.

Algorithm for a risky tool call:
1. Compute `effect_id = sha256({run_id, tool_name, canonical_params, stage})`
2. Prepare (no side effect):
   - insert `tower_effects(status='prepared', prepared_payload=...)`
   - create ticket referencing `effect_id`
   - `interrupt({...})`
3. On resume:
   - if rejected: mark `tower_effects.status='aborted'`
   - if approved:
     - if already committed: return stored result
     - else execute tool, store result, mark committed

Existing Redis tool idempotency stays useful, but it is not sufficient for durable correctness.

---

## 8) Implementation Plan (Concrete Steps + File Touches)

### Phase A - Persistence + Tower core (agents service)
1. DB schema changes:
- Update `src/aps/store.py` init SQL to create `tower_*` tables and extend `approval_queue`.
- Add indexes.

2. New Tower modules (add `src/tower/`):
- `src/tower/store.py`
  - CRUD for runs/events/effects/tickets using psycopg.
- `src/tower/checkpointer.py`
  - `setup_checkpointer()` calls `PostgresSaver.setup()` once.
  - `get_checkpointer()` yields a saver instance (context manager).
- `src/tower/runner.py`
  - ThreadPool-based worker pool.
  - `start_run`, `resume_run`, `get_snapshot`, `get_events`.
- `src/tower/context_pack.py`
  - Context pack generator using strict templates.
- `src/tower/event_sink.py`
  - Appends durable events to `tower_run_events`.

3. Lifespan wiring:
- In `src/serve.py` lifespan startup (non-TESTING):
  - init APS tables (already done)
  - init Tower tables
  - setup checkpointer

### Phase B - Durable workflow compilation
Implement a uniform workflow compilation for runs:
- `default`: `build_graph(router).compile(checkpointer=...)`
- non-default: use `src/workflow_registry.py` + `src/workflow_compiler.py` and compile with checkpointer.

### Phase C - Integrate approvals into tool execution (critical)
Modify `src/dynamic_executor.py` tool-call loop:
- For each tool call:
  - classify risk via `src/approval.py` `ApprovalGate.classify_risk`
  - if low: execute normally (still idempotent)
  - if medium/high:
    - create `tower_effects` prepared row
    - create ticket in `approval_queue` with `thread_id`, `checkpoint_id`, `interrupt_id`
    - `interrupt()` with the ticket payload
  - on resume: commit or abort effect based on decision payload

### Phase D - Agents-service Tower API
Add endpoints to `src/serve.py`:
- `/tower/runs/start`
- `/tower/runs/{run_id}`
- `/tower/runs/{run_id}/events`
- `/tower/runs/{run_id}/snapshot`
- `/tower/runs/{run_id}/resume`
- `/tower/inbox`
- `/tower/tickets/{ticket_id}`
- `/tower/tickets/{ticket_id}/decide`

Auth:
- Add these to `src/security/auth.py` `OPERATOR_PATHS` templates.

### Phase E - Console backend proxy
Add:
- `console/backend/app/routers/tower.py` proxying to agents `/tower/*`
Register in:
- `console/backend/app/main.py`

### Phase F - Control Tower UI (Inbox-first)
1. Add `console/frontend/src/pages/TowerPage.tsx` (ATC layout)
- Left: inbox list
- Center: context pack
- Right: run timeline + snapshot

2. Make Tower the default landing
- `console/frontend/src/App.tsx` index route becomes Tower.
- Add `/tower` route.
- Add sidebar item in `console/frontend/src/components/layout/Sidebar.tsx`.

3. Live event filtering by run
- Update agents WS event payloads to include `thread_id` from callback metadata.
- Update `console/frontend/src/hooks/useExecutionStream.ts` to preserve `thread_id`.

### Phase G - Scheduler integration (make autonomous runs resumable)
Update `src/scheduler/autonomous.py`:
- Instead of `compiled_graph.invoke(state)` directly, schedule Tower `start_run(...)`:
  - Every scheduled task has a `run_id` and can interrupt/resume later.

### Phase H - Morphogenetic tickets unified into Tower inbox
Update `src/morphogenetic/cascade.py` Tier2/Tier3 approval creation:
- Ensure it writes:
  - `context_pack` (minimal at first; full generator later)
  - parameters include `system_id='governance'` so UI can lane/group

---

## 9) Test Plan
Backend (pytest):
1. Durable interrupt/resume (unit)
- Use `MemorySaver` to verify `interrupt()` and resume behavior.
2. Optimistic concurrency
- Resume with wrong `expected_checkpoint_id` returns 409.
3. Effect idempotency
- Prepare/commit effect twice returns the same committed result without re-executing.
4. Event store cursoring
- `/events?after_id=` returns deterministic ordering and correct pagination.

UI:
- Smoke: inbox loads, ticket selection shows context pack, approve/reject changes status.

---

## 10) Definition of Done
1. A run can be started asynchronously, interrupts into an inbox ticket, and resumes to completion after approval.
2. Works after process restart (durability via Postgres checkpointer).
3. Tower UI is inbox-first and can triage without reading raw logs.
4. Side effects are exactly-once across resume/replay.

---

## 11) Preflight Notes (Environment)
### Database URL mismatch to fix early
Docker compose uses:
- `postgresql://holly:holly_dev_password@localhost:5434/holly_grace`

Repo `.env` and `.env.example` currently show:
- `postgresql://ecom:ecom_dev_password@localhost:5434/ecom_agents`

Fix plan:
- Standardize on the compose credentials for local dev.
- Ensure Tower + APS + checkpointer all point to the same `DATABASE_URL`.

---

