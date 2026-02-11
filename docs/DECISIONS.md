# Decisions — Architectural Decision Records

> Why things are the way they are. Each ADR records a decision that shaped the system.
> Last updated: 2026-02-11

---

## ADR-001: Four LLMs with Task-Complexity Routing

**Date**: 2026-02-05 | **Status**: Active

**Context**: Single-LLM systems are either too expensive (Opus for everything) or too weak (local model for everything). We needed cost-efficient quality.

**Decision**: Route by task complexity: Ollama qwen2.5:3b for trivial/orchestration, GPT-4o-mini for operations, GPT-4o for sales/creative, Opus 4.6 for Holly/revenue. APS controller can switch models dynamically based on goal performance.

**Consequences**: Complexity in routing logic, but 10x cost reduction vs Opus-only. Ollama dependency is optional (auto-remaps to GPT-4o-mini if absent).

---

## ADR-002: LangGraph for Agent Orchestration

**Date**: 2026-02-05 | **Status**: Active

**Context**: Needed conditional routing, tool calling, and checkpointed execution for multi-agent workflows.

**Decision**: LangChain + LangGraph 0.6.x. Agents are graph nodes, routing is conditional edges, checkpointing via PostgresSaver.

**Consequences**: LangGraph 0.6.x quirk — `interrupt()` with checkpointer doesn't raise GraphInterrupt; must detect via `snapshot.next`. Dependency on LangChain ecosystem versions.

---

## ADR-003: APS Information-Theoretic Control

**Date**: 2026-02-06 | **Status**: Active

**Context**: Needed a principled way to decide when and how to adapt agent behavior based on goal performance.

**Decision**: Adaptive Partition Selection using information-theoretic measures: channel capacity C(P), informational efficiency η = C(P)/W, failure predicates with tolerance thresholds (ε_G). Goals are tuples (F_G, ε_G, T, m_G).

**Consequences**: Rich measurement substrate but requires continuous metric collection. 5-minute evaluation cycles. Theoretical elegance justifies operational complexity.

---

## ADR-004: Morphogenetic Cascade (4-Tier Structured Search)

**Date**: 2026-02-07 | **Status**: Active

**Context**: When a goal fails, the system needs a systematic way to find fixes — not random flailing.

**Decision**: 4-tier cascade, cheapest first: Tier 0 (parameter tuning), Tier 1 (goal retargeting), Tier 2 (boundary expansion — HITL), Tier 3 (scale reorganization — HITL). Assembly cache for proven adaptations.

**Consequences**: Tier 2/3 creates Tower tickets, which block until human approval. Prevents runaway self-modification but adds latency.

---

## ADR-005: Human-in-the-Loop Gates (Tiered Mutation Protocol)

**Date**: 2026-02-07 | **Status**: Active

**Context**: Fully autonomous self-modification is dangerous. Fully manual is slow.

**Decision**: Three tiers of autonomy: Tier 0 (autonomous), Tier 1 (autonomous + notify), Tier 2 (requires Principal approval). Controlled by governance margin γ = rank(J_O) − rank(M_cross) − Σ rank_mutations_in_flight.

**Consequences**: Sean must monitor Tower inbox for Tier 2 tickets. Tickets expire after 24h. The system can block on unattended tickets.

**Alternatives**: Fully autonomous (rejected — too risky), fully manual (rejected — too slow for 24/7 operation).

---

## ADR-006: Redis for Idempotency, Queues, and Message Bus

**Date**: 2026-02-06 | **Status**: Active

**Context**: Needed idempotent webhook processing, background task queues, and inter-component messaging.

**Decision**: Redis 7 with Streams for pub/sub (5 streams), LIST for autonomy task queue, SET for idempotency keys, STRING for session data. Consumer groups ensure exactly-once processing.

**Consequences**: Single Redis instance is a SPOF in local dev. Production uses ElastiCache (managed, replicated). Stream trimming at ~5000 entries prevents memory growth.

---

## ADR-007: PostgreSQL as Single Data Store

**Date**: 2026-02-05 | **Status**: Active

**Context**: Many systems use multiple databases. We needed simplicity for a solo operator.

**Decision**: Single PostgreSQL 16 instance for everything: 44 tables covering APS metrics, agent configs, workflows, Tower runs, hierarchy, Holly memory, MCP registry. No separate analytics DB.

**Consequences**: Simple backup and recovery. Some tables (aps_observations) will grow large over time. No migrations tool — schema is CREATE TABLE IF NOT EXISTS (see ADR-014).

---

## ADR-008: JWT + RBAC Authentication

**Date**: 2026-02-06 | **Status**: Active

**Context**: Needed auth for both the agents API and the console, with different access levels.

**Decision**: JWT tokens (python-jose) with 4 roles: admin, operator, viewer, webhook. Console uses httpOnly cookies. Agents API uses Bearer tokens. Webhook endpoints bypass JWT (HMAC-verified instead).

**Consequences**: Console auto-generates a service JWT from AUTH_SECRET_KEY for agents→console communication. Cookie Secure flag must be conditional on protocol (HTTP ALB gotcha).

---

## ADR-009: Holly Grace as Super-Orchestrator

**Date**: 2026-02-10 | **Status**: Active

**Context**: The system had grown to 16+ agents with no central intelligence. Coordination was ad-hoc.

**Decision**: Holly Grace (Opus 4.6) as the highest-rank agent with jurisdiction over all 31 agents. She holds all mutation authority. Subordinates cannot self-repartition. She runs on Anthropic's function calling with 25 tools and up to 5 tool rounds per message.

**Consequences**: High API cost for Holly (Opus tokens). Mitigated by cost discipline: Holly orchestrates, crew implements. Single point of intelligence but with robust fallbacks (scheduler runs independently of Holly).

---

## ADR-010: Redis Streams as Message Bus

**Date**: 2026-02-10 | **Status**: Active

**Context**: Holly needed to observe system events (run completions, ticket creation, health checks) without polling databases.

**Decision**: 5 Redis Streams with consumer group "holly-grace". Bus consumer thread triages events by urgency. XREADGROUP for consumption, XAUTOCLAIM for stale message recovery.

**Consequences**: Decoupled event flow. Components publish fire-and-forget. Holly's consumer classifies urgency and injects into her conversation context. Trade-off: Redis must be available for real-time awareness.

**Alternatives**: Direct function calls (rejected — tight coupling), PostgreSQL LISTEN/NOTIFY (rejected — limited payload), dedicated message broker (rejected — operational overhead).

---

## ADR-011: Tower for Durable Workflow Execution

**Date**: 2026-02-09 | **Status**: Active

**Context**: Agent tasks were fire-and-forget. No way to pause, approve, and resume. No audit trail.

**Decision**: Operation Control Tower: `tower_runs` (durable execution state), `tower_tickets` (HITL approval), `tower_effects` (two-phase side effects), `tower_run_events` (audit timeline). Worker polls with FOR UPDATE SKIP LOCKED.

**Consequences**: All scheduled tasks route through Tower for durability. LangGraph checkpointer (PostgresSaver) enables interrupt/resume. Optimistic concurrency via expected_checkpoint_id.

---

## ADR-012: 7-Level Goal Hierarchy with Eigenspectrum

**Date**: 2026-02-10 | **Status**: Active

**Context**: Needed formal verification that the agent system can achieve its goals and that constraint goals dominate objective goals.

**Decision**: 37 predicates across 7 levels (L0–L6), 10 blocks, ~80 coupling axes. Eigenspectrum via numpy.linalg.eigh() with 19 eigenvalues. Statement 55 feasibility check. Lexicographic gate enforces level ordering.

**Consequences**: Rich formal model but complex to maintain. Observer automates L0–L5 feeds every 15 min. Terrestrial modules are CRUD-able for extending L5.

---

## ADR-013: No CI/CD Pipeline (Deferred)

**Date**: 2026-02-06 | **Status**: Accepted (deferred)

**Context**: Solo operator, rapid iteration phase. CI/CD setup would slow down development.

**Decision**: Manual build-push-deploy pipeline. 7-step process documented in OPERATIONS.md. No automated tests on push.

**Consequences**: Deployment errors caught late. Cookie Secure flag issue (ADR-008) was discovered in production. Accept this risk during bootstrapping phase.

**Future**: Add GitHub Actions with test → build → push → deploy when system stabilizes.

---

## ADR-014: No Database Migrations (Accepted)

**Date**: 2026-02-05 | **Status**: Accepted

**Context**: Schema evolves rapidly. Migration tools add complexity for a solo operator.

**Decision**: All tables use `CREATE TABLE IF NOT EXISTS` with additive changes only. No column drops or renames in production. New columns use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

**Consequences**: Schema can only grow, never shrink. Orphaned columns accumulate. Acceptable for current scale (<50 tables, single operator).

**Future**: Add Alembic migrations when team size > 1 or when schema changes become breaking.

---

## ADR-015: Self-Modification Governance

**Date**: 2026-02-10 | **Status**: Active

**Context**: Holly can dispatch crew agents that read and potentially modify the codebase via MCP GitHub reader. Unconstrained self-modification is existentially risky.

**Decision**: Self-modification governed by: (1) MCP tools are read-only (github reader has no write access), (2) Tier 2 approval required for any structural change, (3) Crew dispatch creates Tower runs (auditable), (4) Celestial predicates (L0–L4) are immutable in code, (5) Governance margin must remain positive.

**Consequences**: Holly can propose improvements but cannot implement them without Sean's code deployment. The gap between "Holly suggests" and "code changes" requires Sean's manual intervention.

---

## ADR-016: No Staging Environment (Accepted)

**Date**: 2026-02-11 | **Status**: Accepted

**Context**: Single operator, single production environment. Staging doubles infrastructure cost.

**Decision**: Test locally with Docker Compose, deploy directly to production. Use image tagging (v1, v2, ...) for rollback capability.

**Consequences**: Production-only bugs (cookie Secure flag, ALB routing). Rollback via previous task definition revision. Accept this risk during bootstrapping.

**Future**: Add staging when revenue supports the infrastructure cost.
