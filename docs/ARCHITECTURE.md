# Architecture

> Single source of truth for the as-built Holly Grace system.
> Last validated: 2026-02-11

---

## System Overview

Holly Grace is an autonomous e-commerce agent system that manages a print-on-demand Shopify store (Liberty Forge). It consists of 31 AI agents orchestrated by a super-orchestrator (Holly Grace, Claude Opus 4.6), backed by a goal hierarchy with formal verification, durable workflow execution via the Operation Control Tower, and a React console for human oversight. The system runs 24/7 with autonomous scheduling, human-in-the-loop approval gates, and revenue-aware cost control.

### Stack

| Layer | Technology |
|-------|------------|
| LLMs | Ollama qwen2.5:3b (orchestrator), GPT-4o (sales), GPT-4o-mini (ops), Claude Opus 4.6 (Holly/revenue) |
| Framework | LangChain + LangGraph 0.6.x |
| API | FastAPI (agents :8050, console :8060) |
| Database | PostgreSQL 16 (44 tables) |
| Cache/Bus | Redis 7 (5 streams, idempotency, session, queue) |
| Vector Store | ChromaDB (all-MiniLM-L6-v2 embeddings) |
| Scheduler | APScheduler (19 jobs) |
| Console | React 18 + Vite + Tailwind (19 pages) |
| Deployment | AWS ECS Fargate (us-east-2), ALB, ECR, ElastiCache, RDS |
| Local Dev | Docker Compose (5 services) |

### Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│  AWS ECS Fargate (us-east-2)                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │  holly-grace container (Dockerfile.production)     │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │ nginx:80 │  │ agents:8050  │  │ console:8060 │ │ │
│  │  │ (proxy)  │  │ (FastAPI)    │  │ (FastAPI)    │ │ │
│  │  └──────────┘  └──────────────┘  └──────────────┘ │ │
│  │  managed by supervisord                           │ │
│  └────────────────────────────────────────────────────┘ │
│                          │                              │
│  ┌──────────────┐  ┌─────┴──────┐  ┌────────────────┐  │
│  │ RDS Postgres │  │ ElastiCache│  │ CloudWatch     │  │
│  │ :5432        │  │ Redis:6379 │  │ Logs           │  │
│  └──────────────┘  └────────────┘  └────────────────┘  │
│                                                         │
│  ALB: holly-grace-alb-*.us-east-2.elb.amazonaws.com    │
│  ECR: 327416545926.dkr.ecr.us-east-2.amazonaws.com    │
└─────────────────────────────────────────────────────────┘
```

---

## Component Map

### `src/` — Agent Backend (21 packages)

| Package | Purpose | Key Files |
|---------|---------|-----------|
| `agents/` | Agent node definitions (LangGraph) | `nodes.py`, `tools.py` |
| `app_factory/` | Mobile app generation pipeline | `models.py` |
| `aps/` | Adaptive Partition Selection (info-theoretic control) | `controller.py`, `store.py`, `theta.py`, `revenue_epsilon.py`, `financial_health.py` |
| `channels/` | Multi-channel notifications (Slack, email) | `dock.py`, `sanitizer.py`, `bridge.py` |
| `evaluation/` | Golden-task eval suite | `golden_suite.py` |
| `guardrails/` | Input/output validation | `input_validator.py`, `output_validator.py` |
| `hierarchy/` | 7-level goal hierarchy with eigenspectrum | `models.py`, `store.py`, `engine.py`, `seed.py`, `observer.py` |
| `holly/` | Holly Grace super-orchestrator | `agent.py`, `tools.py`, `prompts.py`, `autonomy.py`, `consumer.py`, `session.py`, `memory.py` |
| `holly/crew/` | 15 Construction Crew agents | `registry.py`, individual agent files |
| `llm/` | LLM routing and fallback | `config.py`, `router.py`, `fallback.py` |
| `mcp/` | MCP server registry | `store.py`, `routes.py`, `servers/github_reader.py` |
| `memory/` | Hybrid memory (short + long term) | `hybrid.py` |
| `morphogenetic/` | Developmental biology-inspired goal system | `goals.py`, `instruments.py`, `assembly.py`, `scheduler_jobs.py` |
| `plugins/` | Plugin system (manifest-driven) | `registry.py`, `hooks.py` |
| `resilience/` | Health checks, circuit breakers | `health.py`, `circuit_breaker.py` |
| `scheduler/` | APScheduler autonomous jobs | `autonomous.py` |
| `security/` | JWT auth, RBAC, middleware | `auth.py`, `middleware.py` |
| `sessions/` | Customer session management | `manager.py` |
| `tools/` | LangChain tools (Shopify, Stripe, Solana, etc.) | `shopify.py`, `stripe_tool.py`, `solana_tool.py`, `hierarchy_tool.py`, `browser.py`, `document.py`, `email_inbox.py` |
| `tower/` | Control Tower — durable runs | `store.py`, `runner.py`, `worker.py`, `checkpointer.py` |
| `webhooks/` | Inbound webhook handlers | `handlers.py` |
| `workflows/` | Standalone workflow pipelines | `signal_generator.py`, `revenue_engine.py` |

Root-level files: `serve.py` (main app), `graph.py` (LangGraph build), `bus.py` (Redis Streams), `events.py` (broadcaster), `agent_registry.py`, `tool_registry.py`, `workflow_registry.py`, `workflow_compiler.py`.

### `console/backend/` — Console API (22 routers)

| Router | Prefix | Purpose |
|--------|--------|---------|
| `auth.py` | `/api/auth` | Login, logout, /me (JWT cookie) |
| `health.py` | `/api/health` | Proxy to agents + circuit breakers |
| `agents.py` | `/api/agents` | Proxy agent CRUD |
| `tools.py` | `/api/tools` | Proxy tool registry |
| `workflows.py` | `/api/workflows` | Proxy workflow CRUD |
| `tower.py` | `/api/tower` | Proxy tower runs, tickets, effects |
| `hierarchy.py` | `/api/hierarchy` | Proxy gate, predicates, blocks, modules |
| `holly.py` | `/api/holly` | Proxy Holly message, session, greeting |
| `autonomy.py` | `/api/autonomy` | Proxy autonomy status, queue, audit |
| `approvals.py` | `/api/approvals` | Proxy approval queue |
| `morphogenetic.py` | `/api/morph` | Proxy snapshot, trajectory, goals, cascade |
| `evaluations.py` | `/api/eval` | Proxy eval runs + results |
| `scheduler.py` | `/api/scheduler` | Proxy scheduler jobs + DLQ |
| `execution.py` | `/api/execution` | Proxy checkpoints |
| `graph.py` | `/api/graph` | Proxy graph definition + metadata |
| `system.py` | `/api/system` | Proxy system export/import/images |
| `mcp.py` | `/api/mcp` | Proxy MCP servers + tools |
| `traces.py` | `/api/traces` | LangSmith trace proxy |
| `costs.py` | `/api/costs` | LangSmith cost aggregation |
| `chat.py` | `/api/chat` | Direct LLM chat (non-Holly) |
| `app_factory.py` | `/api/app-factory` | Proxy App Factory projects |
| `logs.py` | — | (included in routers dir) |

### `console/frontend/` — React Console (19 pages)

| Page | Route | Purpose |
|------|-------|---------|
| `TowerPage` | `/` (index), `/tower` | Control Tower — inbox, runs, tickets |
| `WorkflowPage` | `/canvas` | Visual workflow editor + live execution |
| `WorkflowsPage` | `/workflows` | Workflow list + CRUD |
| `AgentsPage` | `/agents` | Agent config editor |
| `HierarchyPage` | `/hierarchy` | Gate banner, predicate table, eigenspectrum chart |
| `ApprovalsPage` | `/approvals` | Approval queue management |
| `EvalPage` | `/eval` | Golden-task evaluation results |
| `MorphPage` | `/morph` | Morphogenetic snapshot + trajectory |
| `AutonomyPage` | `/autonomy` | Holly autonomy loop status + audit |
| `LogsPage` | `/logs` | Real-time log viewer |
| `TracesPage` | `/traces` | LangSmith trace browser |
| `CostsPage` | `/costs` | LLM cost dashboard |
| `ToolsPage` | `/tools` | Tool registry browser |
| `McpPage` | `/mcp` | MCP server management |
| `HealthPage` | `/health` | System health + circuit breakers |
| `SystemPage` | `/system` | System export/import |
| `ChatPage` | `/chat` | Direct LLM chat interface |
| `LoginPage` | `/login` | Authentication |
| `HollyPage` | — | Legacy (Holly is now persistent sidebar) |

**Persistent components**: `HollySidebar.tsx` (right panel, collapsible, via `HollyContext.tsx`), `Sidebar.tsx` (left nav), `Shell.tsx` (layout wrapper).

---

## Infrastructure

### Docker Compose (Local Dev) — 5 Services

| Service | Image | Port (host:container) | Purpose |
|---------|-------|-----------------------|---------|
| `postgres` | postgres:16-alpine | 5434:5432 | Primary database |
| `redis` | redis:7-alpine | 6381:6379 | Cache, bus, queues |
| `chromadb` | chromadb/chroma:latest | 8100:8000 | Vector store |
| `ollama` | ollama/ollama:latest | 11435:11434 | Local LLM (GPU) |
| `android-builder` | custom | — | App Factory builds |

### AWS Production

| Resource | Detail |
|----------|--------|
| Region | us-east-2 |
| ECS Cluster | holly-grace-cluster |
| ECS Service | holly-grace (Fargate, 1 task) |
| Task Definition | holly-grace-holly-grace (1 vCPU, 2GB RAM) |
| ECR | 327416545926.dkr.ecr.us-east-2.amazonaws.com/holly-grace/holly-grace |
| ALB | holly-grace-alb-708960690.us-east-2.elb.amazonaws.com |
| RDS | PostgreSQL (via DATABASE_URL secret) |
| ElastiCache | Redis (holly-grace-redis.1bufji.0001.use2.cache.amazonaws.com:6379) |
| Secrets | AWS Secrets Manager: holly-grace/production/secrets-TVmKFm |
| Logs | CloudWatch: /ecs/holly-grace/holly-grace |

---

## Data Architecture

### PostgreSQL — 44 Tables

**APS (Adaptive Partition Selection)** — 14 tables:
`aps_observations`, `aps_metrics`, `aps_theta_switches`, `aps_theta_cache`, `agent_configs`, `agent_config_versions`, `tool_registry`, `workflow_definitions`, `workflow_versions`, `agent_efficacy`, `execution_budgets`, `eval_results`, `graph_checkpoints`, `dead_letter_queue`

**Morphogenetic** — 6 tables:
`morphogenetic_goals`, `assembly_cache`, `developmental_snapshots`, `cascade_events`, `cascade_config`, `approval_queue`

**System** — 3 tables:
`system_images`, `app_factory_projects`

**Goal Hierarchy** — 10 tables:
`hierarchy_predicates`, `hierarchy_blocks`, `hierarchy_coupling_axes`, `hierarchy_agents`, `hierarchy_orchestrators`, `terrestrial_modules`, `hierarchy_eigenvalues`, `hierarchy_feasibility_log`, `hierarchy_gate_status`, `hierarchy_observations`

**Tower (Control Tower)** — 6 tables:
`tower_runs`, `tower_run_events`, `tower_tickets`, `tower_effects`, `bus_dead_letters`, `holly_sessions`

**Holly** — 3 tables:
`holly_notifications`, `holly_autonomy_audit`, `holly_memory_episodes`, `holly_memory_facts`

**MCP** — 2 tables:
`mcp_servers`, `mcp_tools`

### Redis — 5 Streams + Keys

| Stream | Purpose |
|--------|---------|
| `holly:tower:events` | Workflow run lifecycle (queued, running, completed, failed) |
| `holly:tower:tickets` | Approval requests (created, decided) |
| `holly:human:inbound` | Messages from human to Holly |
| `holly:human:outbound` | Messages from Holly to human |
| `holly:system:health` | System health events |

Consumer group: `holly-grace`. Additional Redis keys: idempotency locks, autonomy task queue (`holly:autonomy:tasks`), session data.

### External Integrations

| Service | Purpose | Auth |
|---------|---------|------|
| Shopify | Store management, products, orders | Access token |
| Stripe | Payments, revenue tracking | Secret key |
| Printful | Print-on-demand fulfillment | API key |
| OpenAI | GPT-4o, GPT-4o-mini | API key |
| Anthropic | Claude Opus 4.6 (Holly) | API key |
| Ollama | qwen2.5:3b (local) | None (localhost) |
| LangSmith | Tracing and evaluation | API key |
| CoinGecko | SOL price for mining analysis | Free API |
| Solana RPC | Validator health, block production | Public endpoint |
| IMAP | Inbound email listener (Sage) | Gmail credentials |

---

## Agent Architecture

### 31 Agents (16 Workflow + 15 Crew)

**Workflow Agents** (execute in LangGraph):

| Agent ID | Model | Role |
|----------|-------|------|
| `orchestrator` | qwen2.5:3b / GPT-4o-mini | Route tasks to specialists |
| `sales_content` | GPT-4o | Marketing, social, campaigns |
| `operations` | GPT-4o-mini | Orders, fulfillment, inventory |
| `revenue` | Opus 4.6 | Revenue analysis, Stripe, Solana |
| `af_architect` | GPT-4o | App Factory design |
| `af_frontend` | GPT-4o | App Factory UI |
| `af_backend` | GPT-4o-mini | App Factory backend |
| `af_qa` | GPT-4o-mini | App Factory testing |
| + 8 more sub-agents | various | Specialized sub-tasks |

**Construction Crew** (dispatched by Holly via `dispatch_crew`):

| Agent ID | Role | Enneagram |
|----------|------|-----------|
| `crew_architect` | System design | Investigator (5) |
| `crew_tool_smith` | Tool building | Loyalist (6) |
| `crew_mcp_creator` | MCP server creation | Reformer (1) |
| `crew_test_engineer` | Testing | Loyalist (6) |
| `crew_wiring_tech` | Integration wiring | Achiever (3) |
| `crew_program_manager` | Project management | Achiever (3) |
| `crew_finance_officer` | Financial analysis | Investigator (5) |
| `crew_lead_researcher` | Deep Research Protocol | Investigator (5) |
| `crew_critic` | Critical analysis | Challenger (8) |
| `crew_wise_old_man` | Strategic wisdom | Peacemaker (9) |
| `crew_epsilon_tuner` | APS/epsilon calibration | Reformer (1) |
| `crew_strategic_advisor` | Strategic planning | Enthusiast (7) |
| `crew_system_engineer` | Infrastructure | Loyalist (6) |
| `crew_cyber_security` | Security analysis | Challenger (8) |
| `crew_product_manager` | Product direction | Helper (2) |

### Holly Grace — Super-Orchestrator

- **Model**: Claude Opus 4.6 (Anthropic function calling)
- **Tools**: 17 (11 core + 6 introspection) — see INTERACTION.md for full list
- **Max tool rounds**: 5 per message
- **Session persistence**: `holly_sessions` table
- **Communication**: WebSocket streaming (`/ws/holly`), REST (`/holly/message`)
- **Background processes**: Autonomy loop (daemon thread), Bus consumer (daemon thread)
- **Self-modification governance**: MCP GitHub reader for code introspection, crew dispatch for implementation

### LangGraph Flow

```
Human Message → Orchestrator → [sales_content | operations | revenue] → END
                     │                                                    ▲
                     └─────── (conditional routing by task type) ─────────┘
```

Tower worker compiles graphs with PostgresSaver checkpointer. Interrupt at any node creates a ticket; resume uses `Command(resume=value)` with optimistic concurrency.

---

## Goal Hierarchy

7 levels (L0–L6), 37 predicates, 10 blocks (A–J), ~80 coupling axes, 19 eigenvalues.

| Level | Name | Predicates | Nature |
|-------|------|------------|--------|
| L0 | Transcendent Orientation | f1–f4 | Celestial (immutable) |
| L1 | Conscience | f5–f8 | Celestial |
| L2 | Nonmaleficence | f9–f11 | Celestial |
| L3 | Legal Rights | f12–f16 | Celestial |
| L4 | Self-Preservation | f17–f21 | Celestial |
| L5 | Terrestrial (Profit) | f22–f28 | Celestial + Terrestrial |
| L6 | Personality | f29–f37 | Celestial |

**Gate Rule**: `GATE(L) = open` iff all predicates at levels 0..(L-1) pass. If L2 fails, L3–L6 are blocked regardless.

**Feasibility**: Statement 55 verification via `numpy.linalg.eigh()` eigenspectrum analysis. Checks rank coverage, coupling coverage, and epsilon damage tolerance.

**Observer**: Automated feed every 15 min — L0=axiom (always 1.0), L1=guardrails, L2=approvals, L4=health checks, L5=Stripe revenue.

---

## API Surface

### Agent Server (serve.py) — ~105 endpoints

| Category | Method | Path | Count |
|----------|--------|------|-------|
| Root/Health | GET | `/`, `/health`, `/circuit-breakers` | 3 |
| Scheduler | GET/POST | `/scheduler/jobs`, `/scheduler/dlq`, `/scheduler/trigger/{id}`, `/scheduler/dlq/{id}/retry` | 4 |
| Graph | GET | `/graph/definition`, `/graph/metadata` | 2 |
| APS | GET/POST | `/aps/metrics`, `/aps/metrics/{id}`, `/aps/partitions`, `/aps/switch/{ch}/{th}`, `/aps/chain-capacity`, `/aps/evaluate`, `/aps/trace/{id}`, `/aps/cache` | 8 |
| Agents | GET/POST/PUT/DELETE | `/agents`, `/agents/{id}`, `/agents/{id}/efficacy`, `/agents/efficacy/compute`, `/agents/{id}/versions`, `/agents/{id}/versions/{v}`, `/agents/{id}/rollback`, `/agents/{id}/default` | 10 |
| Tools | GET | `/tools` | 1 |
| Workflows | GET/POST/PUT/DELETE | `/workflows`, `/workflows/{id}`, `/workflows/{id}/activate`, `/workflows/{id}/compile`, `/workflows/{id}/versions`, `/workflows/{id}/versions/{v}`, `/workflows/{id}/rollback` | 9 |
| Approvals | GET/POST | `/approvals`, `/approvals/stats`, `/approvals/{id}`, `/approvals/{id}/approve`, `/approvals/{id}/reject` | 5 |
| Eval | POST/GET | `/eval/run`, `/eval/results`, `/eval/results/{id}` | 3 |
| Morphogenetic | GET/POST/PUT/DELETE | `/morphogenetic/snapshot`, `/morphogenetic/trajectory`, `/morphogenetic/goals`, `/morphogenetic/goals/{id}`, `/morphogenetic/goals/reset`, `/morphogenetic/assembly`, `/morphogenetic/cascade`, `/morphogenetic/evaluate`, `/morphogenetic/cascade/config`, `/morphogenetic/cascade/config` (PUT), `/morphogenetic/cascade/config/reset` | 11 |
| System | GET/POST | `/system/export`, `/system/import`, `/system/import/preview`, `/system/images`, `/system/images/{id}` | 5 |
| Checkpoints | GET | `/executions/{id}/checkpoints` | 1 |
| Tower | GET/POST | `/tower/runs/start`, `/tower/runs`, `/tower/runs/{id}`, `/tower/runs/{id}/events`, `/tower/runs/{id}/snapshot`, `/tower/runs/{id}/resume`, `/tower/inbox`, `/tower/tickets/{id}`, `/tower/tickets/{id}/decide`, `/tower/effects/{id}` | 10 |
| Hierarchy | GET/POST/DELETE | `/hierarchy/gate`, `/hierarchy/gate/{level}`, `/hierarchy/predicates`, `/hierarchy/predicates/{idx}`, `/hierarchy/predicates/{idx}/observe`, `/hierarchy/blocks`, `/hierarchy/eigenspectrum`, `/hierarchy/feasibility`, `/hierarchy/agents`, `/hierarchy/orchestrators`, `/hierarchy/modules`, `/hierarchy/modules/{id}`, `/hierarchy/modules` (POST), `/hierarchy/modules/{id}` (DELETE), `/hierarchy/coupling`, `/hierarchy/coupling/upward-budget`, `/hierarchy/recompute` | 17 |
| Holly | GET/POST/WS | `/holly/message`, `/holly/session`, `/holly/clear`, `/holly/greeting`, `/holly/notifications`, `/holly/autonomy/status`, `/holly/autonomy/pause`, `/holly/autonomy/resume`, `/holly/autonomy/queue`, `/holly/autonomy/queue/{id}` (DELETE), `/holly/autonomy/queue` (DELETE), `/holly/autonomy/audit` | 12 |
| Agent Invoke | POST | `/agent/invoke`, `/agent/direct/*` (LangServe) | 2 |
| App Factory | GET/POST/DELETE | `/app-factory/projects`, `/app-factory/projects/{id}` | 4 |
| WebSocket | WS | `/ws/events`, `/ws/holly` | 2 |
| MCP | — | (via mcp_router) | ~6 |
| Webhooks | POST | (via register_webhook_routes) | ~3 |

### Console Backend — Proxy layer (~22 router files, proxying to agents)

All console routes are prefixed `/api/` and proxy to the agents server at `:8050` using `httpx.AsyncClient`. Authentication via httpOnly JWT cookie (see INTERACTION.md).

---

## Scheduled Jobs — 19 Jobs + 1 Listener

| ID | Schedule | Function | Gating |
|----|----------|----------|--------|
| `order_check` | Every 30 min | Direct invoke: check orders | None |
| `instagram_post_9` | Daily 9:00 | Tower run: create Instagram post | Revenue epsilon |
| `instagram_post_15` | Daily 15:00 | Tower run: create Instagram post | Revenue epsilon |
| `weekly_campaign` | Monday 9:00 | Tower run: weekly marketing campaign | Revenue epsilon |
| `daily_revenue` | Daily 8:00 | Direct invoke: revenue report | None |
| `health_check` | Every 15 min | Health check sweep | None |
| `aps_evaluation` | Every 5 min | APS controller evaluation | None |
| `efficacy_aggregation` | Every 30 min | Agent efficacy computation | None |
| `financial_health` | Every 30 min | Stripe revenue → financial health cache | None |
| `morphogenetic_evaluation` | Every 15 min | Morphogenetic snapshot + cascade | None |
| `hierarchy_observation` | Every 15 min | Feed L0–L6 predicates from system state | None |
| `solana_mining_check` | Every 6 hours | Tower run: Solana profitability check | Hierarchy L5 gate |
| `signal_generator` | Every 2 hours | Product description A/B testing | None |
| `revenue_engine` | Daily 6:00 | SEO + content marketing pipeline | None |
| `sage_morning_greeting` | Daily 7:00 | Morning email/SMS greeting to Sean | None |
| `dlq_retry` | Every 5 min | Retry dead letter queue entries | None |
| `approval_expiry` | Every 5 min | Expire stale approval requests | None |
| `tower_ticket_expiry` | Every 5 min | Expire stale Tower tickets | None |
| **Inbox listener** | Persistent IMAP IDLE | Inbound email/SMS → Tower run | None |
