# Holly 3.0 Development Roadmap v0.1

Holly is an AI assistant that can do real work on its own. Instead of needing a person to guide every single step, Holly takes a high-level goal — like "investigate why our website is slow" or "set up a new project environment" — and figures out the steps, runs them, and checks the results. When something important comes up that needs a human decision, Holly stops and asks before continuing. Think of it like having a very capable coworker who can handle complex, multi-step tasks across different tools and systems, but always checks in with you before doing anything risky or irreversible.

Holly exists because today's AI tools are either too simple (just answering questions) or too dangerous (taking actions without enough guardrails). Holly is built from the ground up with safety, auditability, and multi-user support baked in — not bolted on after the fact. Every action Holly takes is logged, every external call is filtered and monitored, and every piece of sensitive data is automatically scrubbed before it hits a log file. As a user, you interact with Holly through a chat interface or a web console. You tell her what you need in plain English, she breaks it down into a plan, and you watch the work happen in real time. You can pause, redirect, or approve at any point. She's your teammate, not a black box.

---

| # | Step | Description |
|---|---|---|
| | **Phase A — Architecture Enforcement** | |
| 1 | Extract | Published SAD → `architecture.yaml` |
| 2 | Registry | Python singleton loads YAML, exposes lookups |
| 3 | Decorators | `@kernel_boundary`, `@tenant_scoped`, etc. — stamp arch metadata |
| 4 | Scaffold | Generate package skeleton from repo tree |
| 5 | ICD | Contract specs per boundary crossing |
| 6 | Validate | YAML ↔ SAD drift detection |
| 7 | Scan | AST-walk for missing/wrong decorators |
| 8 | Test | Generate pytest arch contract fixtures |
| 9 | CI Gate | All three modes block merge on failure |
| | **Phase B — Kernel (L1)** | |
| 10 | KernelContext | Async context manager, boundary wrapping |
| 11 | K1–K4 | Schema validation, permissions, bounds, trace injection |
| 12 | K5–K6 | Idempotency key gen (RFC 8785), audit WAL |
| 13 | K7–K8 | HITL gates, eval gates |
| 14 | Exceptions | KernelViolation, BoundsExceeded, HITLRequired |
| 15 | Kernel tests | Unit + integration for every invariant |
| | **Phase C — Storage Layer** | |
| 16 | Postgres | Async pool, models, RLS policies, migrations |
| 17 | Partitioning | Time-based partitions, auto-create, archival to S3 |
| 18 | Redis | Pool, pub/sub, queues, cache, HA config |
| 19 | ChromaDB | Client, tenant-isolated collections, embedding pipeline |
| 20 | Storage tests | Connection, RLS enforcement, partition lifecycle |
| | **Phase D — Safety & Infra** | |
| 21 | Redaction | Canonical library — single source of truth |
| 22 | Guardrails | Input sanitization, output redaction, injection detection |
| 23 | Governance | Forbidden paths, code review analysis |
| 24 | Secret scanner | Detect + redact in traces |
| 25 | Egress | L7 allowlist/redact/rate-limit, L3 NAT routing |
| 26 | Secrets | KMS/Vault client, key rotation, credential store |
| | **Phase E — Core (L2)** | |
| 27 | Conversation | Bidirectional WS chat interface |
| 28 | Intent | Classifier: direct_solve / team_spawn / clarify |
| 29 | Goals | Decomposer, 7-level hierarchy, lexicographic gating |
| 30 | APS | Controller, T0–T3 tiers, Assembly Index |
| 31 | Topology | Team spawn/steer/dissolve, contracts, eigenspectrum |
| 32 | Memory | 3-tier: short (Redis), medium (PG), long (Chroma) |
| 33 | Core tests | Intent → goal → APS → topology integration |
| | **Phase F — Engine (L3)** | |
| 34 | Lanes | Manager, policy, main/cron/subagent dispatchers |
| 35 | MCP | Registry, per-agent permissions, introspection |
| 36 | MCP builtins | code (gRPC→sandbox), web, filesystem, database |
| 37 | Workflow | Durable engine, checkpoint, retry, DAG compiler |
| 38 | Engine tests | Goal → lane → workflow → tool → result e2e |
| | **Phase G — Sandbox** | |
| 39 | Sandbox image | Minimal container, no network, no holly deps |
| 40 | gRPC service | ExecutionRequest/Result proto, server, executor |
| 41 | Isolation | Namespaces (PID/NET/MNT), seccomp, resource limits |
| 42 | gVisor/Firecracker | Production runtime configs |
| 43 | Sandbox tests | Network escape, filesystem escape, resource limits |
| | **Phase H — API & Auth** | |
| 44 | Server | Starlette app factory, middleware stack |
| 45 | JWT middleware | JWKS verification, claims extraction, revocation cache |
| 46 | Auth | RBAC enforcement from JWT claims |
| 47 | Routes | chat, goals, agents, topology, execution, audit, config, health |
| 48 | WebSockets | Manager, 9 channels, tenant-scoped authz, re-auth |
| 49 | API tests | Auth, routing, WS channel delivery |
| | **Phase I — Observability** | |
| 50 | Event bus | Unified ingest, sampling, backpressure, tenant-scoped fanout |
| 51 | Logger | Structured JSON, correlation-aware, redact-before-persist |
| 52 | Trace store | Decision tree persistence, redact payloads |
| 53 | Metrics | Prometheus collectors |
| 54 | Exporters | PG (partitioned), Redis (real-time streams) |
| | **Phase J — Agents** | |
| 55 | BaseAgent | Lifecycle, message protocol, kernel binding |
| 56 | Agent registry | Type catalog, capability declarations |
| 57 | Prompts | Holly, researcher, builder, reviewer, planner |
| 58 | Constitution | Celestial L0–L4 (immutable), Terrestrial L5–L6 (optimization) |
| | **Phase K — Config** | |
| 59 | Settings | Pydantic env-driven config |
| 60 | Hot reload | Runtime updates without restart |
| 61 | Audit + rollback | Change logging, HITL on dangerous keys, version revert |
| | **Phase L — Console (L5)** | |
| 62 | Shell | React + Vite + Tailwind + Zustand scaffold |
| 63 | Chat | Panel, message bubbles, input bar |
| 64 | Topology | Live agent graph, contract cards |
| 65 | Goals | Tree explorer, celestial badges |
| 66 | Execution | Lane monitor, task timeline |
| 67 | Audit | Log viewer, trace tree, metrics dashboard |
| | **Phase M — Deploy & Ops** | |
| 68 | Docker | Compose (dev), production Dockerfile |
| 69 | AWS | VPC/CFn, ALB/WAF, ECS Fargate task defs |
| 70 | Authentik | OIDC flows, RBAC policies |
| 71 | Scripts | seed_db, migrate, dev, partition maintenance |
| 72 | Runbook | Operational procedures, DR/restore |
| 73 | Docs | Glossary, sandbox security, egress model, deployment topology |
