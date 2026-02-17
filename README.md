# Holly Grace

**Autonomous operations with kernel-enforced trust.**

Holly Grace is a multi-tenant autonomous operations platform that receives declarative intent via natural language, decomposes it into a 7-level goal hierarchy, and orchestrates agent teams to execute durable workflows against external systems. Every boundary crossing is wrapped by kernel-enforced invariants — schema validation, permission gating, bounds checking, trace injection, idempotency, and human-in-the-loop gates. The architecture is a three-layer stack: **Kernel (L1)** enforces invariants in-process, **Core (L2)** handles intent classification, goal decomposition, topology management, and tiered memory, and **Engine (L3)** runs durable workflows with effectively-once semantics across concurrent lanes, an MCP tool registry with per-agent permission masks, and sandboxed code execution over gRPC. All storage, observability, and egress are tenant-isolated by default. Auth is JWKS-based via Authentik OIDC with short-lived tokens and Redis-backed revocation. Every action is auditable, every external call is filtered, and all sensitive data is canonically redacted before it reaches a log.

## Theoretical Foundation

Holly Grace is the reference implementation of the framework developed in:

> **Allen, S. P. (2026).** *Informational Monism, Morphogenetic Agency, and Goal-Specification Engineering: A Unified Framework.* v2.0, 289 pp.

The monograph constructs a unified mathematical framework in twelve parts: channel-theoretic microdynamics and induced macro-channels (Parts I–II), a formal agency model built on digital branching, feedback Jacobians, agency rank, and cognitive light cones (Part III), goal predicate sets with codimension-based specification hierarchies (Part IV), multi-agent feasibility via steering operators, assignment matrices, and infeasibility residuals (Part V), adaptive governance through epsilon-band compliance and repartitioning (Part VI), a feasibility–governance equivalence theorem (Part VII), steering power analysis with coupling scaling laws and governance margin bounds (Part VIII), and logical foundations grounding the entire apparatus in constructive and classical pluralism (Part IX). Parts X–XII map the theory directly onto agent configuration architecture — APS tier selection, failure predicates, constitutional hierarchies, runtime alignment envelopes, prompt-injection defense boundaries, tool permission masks, and tiered memory subsystems with K-scope crystallisation — providing the formal specification from which Holly's kernel invariants, goal decomposer, topology manager, and eval gates are derived.

## Design Methodology

Holly's development methodology is synthesized from ISO systems-engineering standards (42010 architecture descriptions, 25010 quality models, 15288/12207 lifecycle processes), safety-critical practices (SIL-based rigor mapping, FMEA/FTA, formal verification on high-risk paths), and the operational philosophies of SpaceX (responsible-engineer ownership, rapid build-test-build iteration, stratified requirements with HITL in CI), OpenAI (eval-driven development where evaluations are the source of truth, staged rollouts, feature flags for AI behavior), and Anthropic (constitutional AI as executable specification, five-layer defense-in-depth safety, security boundary patterns). The core principle is a traceable chain — stakeholder concern → requirement → architecture decision → decorated code → automated test → deployment proof — enforced by architecture fitness functions that run as CI gates, ensuring the SAD and codebase never drift apart.

The build process follows an architecture-as-code discipline: the SAD is machine-parsed into `architecture.yaml`, which drives a decorator registry (`@kernel_boundary`, `@tenant_scoped`, etc.) that stamps every module with its architectural contract. AST scanners and ArchUnit-style validators block merges when decorators are missing or boundary crossings violate the ICD. Agent orchestration borrows from durable-execution frameworks (Temporal.io patterns) with kernel-level invariant enforcement at every boundary — schema validation, permission checks, bounds enforcement, trace injection, idempotency, and HITL gates — because multi-agent systems exhibit 41–87% failure rates without structural safeguards. Eval-driven development (EDDOps) governs the agent layer: property-based tests and adversarial eval suites gate every agent prompt and constitution change, treating behavioral specifications as first-class, version-controlled artifacts with the same rigor as code.

## Orchestration Model

The APS Controller (Adaptive Partition Selection) classifies every decomposed goal into one of four tiers: **T0 Reflexive** (single-agent, no coordination), **T1 Deliberative** (single-agent, multi-step reasoning), **T2 Collaborative** (multi-agent team with fixed contracts), and **T3 Morphogenetic** (dynamic team that restructures itself mid-execution). T0/T1 goals execute directly on the Main Lane. T2/T3 goals trigger the Team Topology Manager, which spawns agent teams onto the Subagent Lane with three binding constraints: inter-agent contracts (schema-enforced call boundaries), per-agent MCP tool permissions, and resource budgets (compute, token, and time limits). T3 topologies can reshape during execution — adding or removing agents, reassigning permissions, re-scoping budgets — via the Topology Manager's steer operation, without tearing down the team.

Goals follow a 7-level hierarchy split into two regimes. **Celestial (L0–L4)** goals are immutable safety constraints — permission boundaries, constitutional rules, invariant enforcement — that no lower-level goal can override. **Terrestrial (L5–L6)** goals are the user's actual intent, decomposed into executable subgoals. Lexicographic gating enforces strict priority: a Terrestrial goal can never satisfy itself by violating a Celestial constraint. Failure detection operates at three levels: kernel eval gates (K8) halt execution when a goal's output fails a behavioral check, the workflow engine's compensating actions fire on task-graph node failure, and the Topology Manager's eigenspectrum monitors team communication patterns against contracted topology — triggering steer or dissolve when divergence exceeds threshold.

## Execution Model

Phases follow a **spiral** cadence, not waterfall. Phase A steps 1–3 execute first, then a thin Kernel slice (B.15–B.16) validates the enforcement loop end-to-end before backfilling the rest of A and B. Each phase ends with an explicit quality gate; no phase starts until its predecessor's gate passes. Critical-path components (Kernel L1, Sandbox L7, Egress) carry **SIL-3 rigor** (formal specs, property-based tests, independent verification). Standard-path components (Console L5, Config) carry **SIL-1 rigor** (unit tests, code review).

---

| # | Step | Description |
|---|---|---|
| | **Phase A — Architecture Enforcement** | |
| 1 | Extract | Published SAD → `architecture.yaml` |
| 2 | Registry | Python singleton loads YAML, exposes lookups |
| 3 | Decorators | `@kernel_boundary`, `@tenant_scoped`, etc. — stamp arch metadata |
| 3a | Spiral gate | Build thin Kernel slice (B.15–B.16), validate enforcement loop e2e |
| 4 | Scaffold | Generate package skeleton from repo tree |
| 5 | ICD | Contract specs per boundary crossing |
| 5a | ATAM | Architecture quality-attribute evaluation against stakeholder scenarios |
| 6 | Validate | YAML ↔ SAD drift detection |
| 7 | Scan | AST-walk for missing/wrong decorators |
| 8 | Test | Arch contract fixtures + property-based boundary fuzzing (Hypothesis) |
| 9 | Fitness fns | Continuous fitness functions — run on every commit, not just merge |
| 10 | RTM gen | Auto-generate living Requirements Traceability Matrix from decorators |
| 11 | CI gate | Block merge on drift, decorator, fitness, or RTM failure; staged canary |
| | **Phase B — Failure Analysis & Kernel (L1)** | |
| 12 | SIL mapping | Assign criticality tiers to every component (SIL-1 → SIL-3) |
| 13 | FMEA | Failure-mode analysis: kernel invariants, sandbox escape, egress bypass, goal injection |
| 14 | Formal specs | TLA+ specs for kernel invariant state machine + sandbox isolation |
| 15 | KernelContext | Async context manager, boundary wrapping |
| 16 | K1–K4 | Schema validation, permissions, bounds, trace injection |
| 17 | K5–K6 | Idempotency key gen (RFC 8785), audit WAL |
| 18 | K7–K8 | HITL gates, eval gates |
| 19 | Exceptions | KernelViolation, BoundsExceeded, HITLRequired |
| 20 | Dissimilar verify | Independent verification channel for kernel safety checks |
| 21 | Kernel tests | Formal verification + property-based + unit + integration (SIL-3) |
| | **Phase C — Storage Layer** | |
| 22 | Postgres | Async pool, models, RLS policies, migrations |
| 23 | Partitioning | Time-based partitions, auto-create, archival to S3 |
| 24 | Redis | Pool, pub/sub, queues, cache, HA config |
| 25 | ChromaDB | Client, tenant-isolated collections, embedding pipeline |
| 26 | Storage tests | Connection, RLS enforcement, partition lifecycle (SIL-2) |
| | **Phase D — Safety & Infra** | |
| 27 | Redaction | Canonical library — single source of truth |
| 28 | Guardrails | Input sanitization, output redaction, injection detection |
| 29 | Governance | Forbidden paths, code review analysis |
| 30 | Secret scanner | Detect + redact in traces |
| 31 | Egress | L7 allowlist/redact/rate-limit, L3 NAT routing |
| 32 | Secrets | KMS/Vault client, key rotation, credential store |
| 33 | Safety case | Structured safety argument (claims → evidence → context) for D.27–D.32 |
| | **Phase E — Core (L2)** | |
| 34 | Conversation | Bidirectional WS chat interface |
| 35 | Intent | Classifier: direct_solve / team_spawn / clarify |
| 36 | Goals | Decomposer, 7-level hierarchy, lexicographic gating |
| 37 | APS | Controller, T0–T3 tiers, Assembly Index |
| 38 | Topology | Team spawn/steer/dissolve, contracts, eigenspectrum |
| 39 | Memory | 3-tier: short (Redis), medium (PG), long (Chroma) |
| 40 | Core tests | Intent → goal → APS → topology integration (SIL-2) |
| | **Phase F — Engine (L3)** | |
| 41 | Lanes | Manager, policy, main/cron/subagent dispatchers |
| 42 | MCP | Registry, per-agent permissions, introspection |
| 43 | MCP builtins | code (gRPC→sandbox), web, filesystem, database |
| 44 | Workflow | Durable engine, saga patterns, compensation logic, dead-letter, DAG compiler |
| 45 | Engine tests | Goal → lane → workflow → tool → result e2e (SIL-2) |
| | **Phase G — Sandbox** | |
| 46 | Sandbox image | Minimal container, no network, no holly deps |
| 47 | gRPC service | ExecutionRequest/Result proto, server, executor |
| 48 | Isolation | Namespaces (PID/NET/MNT), seccomp, resource limits |
| 49 | gVisor/Firecracker | Production runtime configs |
| 50 | Sandbox tests | Network escape, filesystem escape, resource limits (SIL-3) |
| | **Phase H — API & Auth** | |
| 51 | Server | Starlette app factory, middleware stack |
| 52 | JWT middleware | JWKS verification, claims extraction, revocation cache |
| 53 | Auth | RBAC enforcement from JWT claims |
| 54 | Routes | chat, goals, agents, topology, execution, audit, config, health |
| 55 | WebSockets | Manager, 9 channels, tenant-scoped authz, re-auth |
| 56 | API tests | Auth, routing, WS channel delivery (SIL-2) |
| | **Phase I — Observability** | |
| 57 | Event bus | Unified ingest, sampling, backpressure, tenant-scoped fanout |
| 58 | Logger | Structured JSON, correlation-aware, redact-before-persist |
| 59 | Trace store | Decision tree persistence, redact payloads |
| 60 | Metrics | Prometheus collectors |
| 61 | Exporters | PG (partitioned), Redis (real-time streams) |
| | **Phase J — Agents** | |
| 62 | BaseAgent | Lifecycle, message protocol, kernel binding |
| 63 | Agent registry | Type catalog, capability declarations |
| 64 | Prompts | Holly, researcher, builder, reviewer, planner |
| 65 | Constitution | Celestial L0–L4 (immutable), Terrestrial L5–L6 — as executable specs |
| | **Phase K — Eval Infrastructure (EDDOps)** | |
| 66 | Eval framework | Harness, dataset loaders, metric collectors, regression tracker |
| 67 | Behavioral suites | Per-agent property-based + adversarial eval suites |
| 68 | Constitution gate | Automated behavioral regression on every constitution/prompt change |
| 69 | Eval CI | Eval pipeline as CI stage — blocks agent merges on regression |
| | **Phase L — Config** | |
| 70 | Settings | Pydantic env-driven config |
| 71 | Hot reload | Runtime updates without restart |
| 72 | Audit + rollback | Change logging, HITL on dangerous keys, version revert |
| | **Phase M — Console (L5)** | |
| 73 | Shell | React + Vite + Tailwind + Zustand scaffold |
| 74 | Chat | Panel, message bubbles, input bar |
| 75 | Topology | Live agent graph, contract cards |
| 76 | Goals | Tree explorer, celestial badges |
| 77 | Execution | Lane monitor, task timeline |
| 78 | Audit | Log viewer, trace tree, metrics dashboard |
| | **Phase N — Deploy & Ops** | |
| 79 | Docker | Compose (dev), production Dockerfile |
| 80 | AWS | VPC/CFn, ALB/WAF, ECS Fargate task defs |
| 81 | Authentik | OIDC flows, RBAC policies |
| 82 | Staged rollout | Feature flags, canary deploys, progressive delivery gates |
| 83 | Scripts | seed_db, migrate, dev, partition maintenance |
| 84 | Safety case | Full system safety argument (claims → evidence → context) for release |
| 85 | Runbook | Operational procedures, DR/restore |
| 86 | Docs | Glossary, sandbox security, egress model, deployment topology |

> Previous codebase (ecom-agents / Holly v2) archived on `archive/v2` branch.