# Holly Grace

**Autonomous operations with kernel-enforced trust.**

Holly Grace is the reference implementation of the theoretical framework developed in:

> **Allen, S. P. (2026).** *Informational Monism, Morphogenetic Agency, and Goal-Specification Engineering: A Unified Framework.* v2.0, 289 pp.

## From Informational Monism to Autonomous Operations

The framework begins from a single ontological commitment: every system — computational, biological, organizational — is a network of information channels, and the dynamics that matter are the dynamics of those channels. Channel theory supplies the microdynamics: tokens flow through typed conduits whose capacity, noise, and coupling are measurable quantities. When channels compose, they induce macro-channels with emergent bandwidth and loss characteristics that are not simple sums of their parts. Admissibility conditions distinguish passive transport — information flowing through a structure — from active regeneration, where a subsystem reconstructs and redirects its own channels. That distinction is the formal boundary between mechanism and agency.

Agency is defined by three properties: digital branching (the capacity to select among discrete successor states), a feedback Jacobian (sensitivity of future channel structure to current output), and agency rank (the dimensionality of the state space an agent can steer). Together these yield a cognitive light cone — the region of the system's future that a given agent can causally influence within its resource and time budget. A single agent with high rank and a wide light cone can solve problems unilaterally. An agent with narrow rank must compose with others, and the terms of that composition are not negotiable — they are set by the mathematics of multi-agent feasibility.

Goal structure follows directly. A goal is a predicate set over the system's state space: a region the system must reach or remain within. Goals have codimension — the number of independent constraints they impose — and they compose into hierarchies where higher-level goals lexicographically dominate lower ones. Holly formalizes this as two regimes: **Celestial goals (L0–L4)** are immutable safety constraints — permission boundaries, constitutional rules, invariant enforcement — that no lower-level goal can override. **Terrestrial goals (L5–L6)** are the user's actual intent, decomposed into executable subgoals. Lexicographic gating means a Terrestrial goal can never satisfy itself by violating a Celestial constraint.

Multi-agent feasibility determines whether a given assignment of goals to agents is satisfiable. Steering operators map agent outputs to goal-state transitions; assignment matrices bind agents to subgoals; the infeasibility residual measures the gap between what a team can collectively steer and what the goal hierarchy demands. When the residual is nonzero, the topology must change — agents added, removed, or re-scoped — and adaptive governance defines how that change happens safely. Epsilon-band compliance gives each agent a tolerance envelope; repartitioning restructures team boundaries when compliance degrades; and the feasibility–governance equivalence theorem guarantees that if governance constraints are satisfied, the system remains within the feasible operating region. Steering power analysis quantifies the coupling scaling laws and governance margins that bound how much morphogenetic flexibility a topology can sustain before coherence breaks down.

## Architecture

Holly instantiates this theory as a three-layer stack. **Kernel (L1)** is an in-process library that wraps every boundary crossing with invariant enforcement: schema validation, permission gating, bounds checking, trace injection, idempotency, HITL gates, and eval gates. **Core (L2)** receives declarative intent via natural language, classifies it (direct solve, team spawn, or clarify), decomposes it into the 7-level goal hierarchy, and routes it through the APS Controller. APS classifies each goal into one of four tiers — **T0 Reflexive** (single-agent, no coordination), **T1 Deliberative** (single-agent, multi-step reasoning), **T2 Collaborative** (multi-agent team with fixed contracts), **T3 Morphogenetic** (dynamic team that restructures mid-execution) — and dispatches accordingly. The Team Topology Manager spawns agent teams with three binding constraints: inter-agent contracts, per-agent MCP tool permissions, and resource budgets. T3 topologies reshape via steer operations; the eigenspectrum monitors communication patterns against contracted topology and triggers steer or dissolve when divergence exceeds threshold. **Engine (L3)** runs durable workflows with effectively-once semantics across concurrent lanes, an MCP tool registry with per-agent permission masks, and sandboxed code execution over gRPC. Failure detection operates at three levels: K8 eval gates halt on behavioral check failure, the workflow engine fires compensating actions on task-graph node failure, and eigenspectrum divergence triggers topological restructuring. All storage, observability, and egress are tenant-isolated by default. Auth is JWKS-based via Authentik OIDC with short-lived tokens and Redis-backed revocation.

## Artifact Genealogy

Every artifact in this codebase traces back through a five-phase derivation chain: **α Research & Theory** (literature review + monograph) → **β Architecture** (custom SAD tool + SAD/RTD) → **γ Specifications** (ICD, Behavior Specs, Goal Hierarchy, SIL Matrix) → **δ Process & Governance** (Design Methodology, Task Manifest, Test Governance, Development Procedure) → **ε Execution** (code, tests, evidence, audit artifacts). The complete derivation graph — every node, every edge — is in [`docs/architecture/Artifact_Genealogy.md`](docs/architecture/Artifact_Genealogy.md). No artifact exists without provenance.

## Development Procedure

All development follows a single executable graph defined in [`docs/Development_Procedure_Graph.md`](docs/Development_Procedure_Graph.md). The graph is iterative — it loops per task batch within a slice and per slice across the 15-slice spiral. No development work occurs outside this graph.

```
P0 Context Sync → P1 Task Derivation (+Test Governance) → P2 Spec Pre-Check
    → [P3A Implementation ‖ P3B Formal Verification ‖ P3C Test Authoring]
    → P4 Verification → P5 Regression Gate → P6 Doc Sync → P7 Commit
    → P8 Spiral Gate Check → P9 Phase Gate Ceremony → loop or P11 Release
```

**P0** pulls both repos, parses the Task Manifest, diffs architecture against SAD/RTD, and emits a context digest. **P1** selects the next task batch by topological sort with SIL-priority ordering and runs the Test Governance Derivation (§3 of the [`Test_Governance_Spec.md`](docs/Test_Governance_Spec.md)) — building a control applicability matrix, deriving test requirements per control, and assembling trace chain stubs *before any code is written*. **P2** pre-checks every task against the ICD, Behavior Specs, Goal Hierarchy, and Monograph Glossary; spec gaps halt the cycle. **P3A/B/C** run in parallel: implementation, TLA+ authoring (SIL-3), and test authoring governed by the per-task test artifact checklist. **P4** executes the full verification pipeline including a test governance compliance check (falsification ratio, trace chain completeness, control coverage). **P5** runs the full test suite for regression with SIL boundary and ICD schema validation. **P8** evaluates maturity-appropriate gates: Security + Test (slices 1–5), plus Traceability (6–10), plus Ops (11–15).

Ten continuous invariants hold across all phases — SIL monotonicity, additive-only ICD schemas, coverage non-regression, dual-repo sync, monograph traceability, and others — enforced by CI gates and procedure checks.

---

## Design Methodology

The build methodology synthesizes ISO systems-engineering standards (42010, 25010, 15288/12207), safety-critical practices (SIL-based rigor mapping, FMEA/FTA, formal verification), and operational philosophies drawn from SpaceX (responsible-engineer ownership, rapid build-test-build, HITL in CI), OpenAI (eval-driven development, staged rollouts, feature flags), and Anthropic (constitutional AI as executable specification, defense-in-depth safety). The core discipline is architecture-as-code: the SAD is machine-parsed into `architecture.yaml`, which drives a decorator registry (`@kernel_boundary`, `@tenant_scoped`, etc.) that stamps every module with its architectural contract. AST scanners block merges when decorators are missing or boundary crossings violate the ICD. Eval-driven development (EDDOps) governs the agent layer — property-based tests and adversarial eval suites gate every prompt and constitution change, treating behavioral specs as first-class versioned artifacts. The traceable chain runs: stakeholder concern → requirement → architecture decision → decorated code → automated test → deployment proof, enforced by fitness functions on every commit.

### Meta Procedure

| # | Step | Do | Produces | Driver |
|---|---|---|---|---|
| 1 | Ontological Foundation | Ground every concept in Allen (2026) formal definitions | Glossary, traceability index | Monograph |
| 2 | Architecture Description | Adopt ISO 42010 — stakeholder concerns → viewpoints → views | Viewpoint catalog, correspondence rules | ISO sweep |
| 3 | Quality Model | Adopt ISO 25010 — every decision cites a quality attribute | Quality attribute catalog, decision records | ISO sweep |
| 4 | Lifecycle Processes | Adopt ISO 15288/12207 — define verification method per requirement | Process tailoring doc, verification assignments | ISO sweep |
| 5 | Criticality Classification | Assign SIL-1 → SIL-3 per component by failure consequence | SIL matrix, verification requirements | SpaceX model |
| 6 | Failure Analysis (FMEA) | Enumerate every failure mode, assess severity, map mitigations | FMEA worksheets, residual risk register | Failure research |
| 7 | Formal Specification | TLA+ model-check kernel state machine + sandbox isolation | TLA+ specs, model-check results, assumption register | Failure research |
| 8 | Architecture-as-Code | SAD → YAML → decorator registry → AST scanner → CI gate | `architecture.yaml`, decorator registry, AST scanner | Fitness functions |
| 9 | Traceable Chain | Enforce concern → requirement → decision → code → test → proof | Living RTM, CI gate on broken links | ISO 15288 |
| 10 | EDDOps | Evals as source of truth; property-based + adversarial suites in CI | Eval framework, behavioral suites, eval CI stage | OpenAI methodology |
| 11 | Constitutional AI | Celestial L0–L4 as executable predicates, not documentation | Predicate functions, constitution gate in CI | Anthropic safety |
| 12 | Defense-in-Depth | Five independent safety layers: kernel, sandbox, egress, eval, HITL | Safety case docs, dissimilar verification channel | Anthropic safety |
| 13 | Spiral Execution | Thin vertical slice first; phase gates block progression | Phase gate checklists, spiral gate report | ISO + SpaceX + OpenAI |
| 14 | Staged Deployment | Feature flags → canary → progressive delivery → release safety case | Deployment pipeline, release safety case | OpenAI methodology |

> Full methodology details: [`docs/Design_Methodology_v1.0.docx`](docs/Design_Methodology_v1.0.docx)

### Task Derivation Protocol

To convert roadmap steps into development tasks, apply this procedure to each spiral slice.

**1. Select the slice.** Spiral execution (MP-13) determines scope. The first slice is always steps 1–3 + 3a. Subsequent slices are the remaining steps of the current phase, unlocked only after the preceding phase gate passes.

**2. Build the applicability matrix.** For each roadmap step in the slice, walk all 14 meta procedure rows and mark which apply. A meta procedure step applies when the roadmap step produces, consumes, or must comply with that MP step's artifact. Use this filter:

| MP Step | Applies when the roadmap step… |
|---|---|
| 1 Ontological Foundation | introduces or names a concept that must trace to the monograph |
| 2 Architecture Description | creates or modifies a 42010 view or viewpoint |
| 3 Quality Model | makes a design trade-off — must cite the quality attribute served |
| 4 Lifecycle Processes | requires a verification method assignment |
| 5 Criticality Classification | is a runtime component — must inherit its SIL level |
| 6 FMEA | is a runtime component at SIL-2 or SIL-3 |
| 7 Formal Specification | is a SIL-3 component with a state machine or isolation boundary |
| 8 Architecture-as-Code | produces or consumes `architecture.yaml`, decorators, or the AST scanner |
| 9 Traceable Chain | produces an artifact that must link to an upstream requirement or downstream test |
| 10 EDDOps | involves agent behavior, prompts, or constitutions |
| 11 Constitutional AI | defines or enforces Celestial (L0–L4) constraints |
| 12 Defense-in-Depth | implements or modifies a safety layer |
| 13 Spiral Execution | is a phase gate or slice boundary |
| 14 Staged Deployment | involves deploy, release, or rollout infrastructure |

**3. Decompose into tasks.** Each applicable MP cell becomes one or more tasks. Every task has four fields:

| Field | Definition |
|---|---|
| **Input** | What upstream artifact or code this task consumes |
| **Output** | What this task produces (code, config, test, document) |
| **Verification** | How correctness is checked — determined by the component's SIL level |
| **Acceptance** | The specific condition under which this task is done — derived from the MP step's "Produces" column |

**4. Sequence by dependency.** Tasks within a step may depend on each other (e.g., "define schema" before "write parser"). Tasks across steps follow roadmap order. Parallelize where no dependency exists.

**5. Execute and gate.** Complete all tasks for the slice. At the slice boundary (e.g., step 3a spiral gate), run the gate check. If it passes, select the next slice and repeat from step 1. If it fails, the gate output identifies which tasks need rework.

#### Worked Example — Roadmap Step 1 (Extract: SAD → `architecture.yaml`)

| MP | Applicable? | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 1 | Yes | Map SAD terms to monograph definitions | SAD, monograph glossary | Traceability annotations in YAML | Review | Every YAML concept traces to a monograph section |
| 2 | Yes | Preserve 42010 viewpoint structure in extraction | SAD (viewpoints) | Viewpoint-aware YAML schema | Review | Viewpoints survive round-trip SAD → YAML → SAD |
| 3 | Yes | Document quality attribute for extraction design | — | ADR citing maintainability | Review | ADR exists and cites 25010 attribute |
| 5 | Yes | Assign SIL to extraction pipeline | SIL matrix | SIL-2 designation | Review | SIL recorded in matrix |
| 8 | Yes | Write SAD parser (mermaid → AST) | SAD mermaid file | Parser module | Integration test | Parses current SAD without error |
| 8 | Yes | Define `architecture.yaml` schema | SAD structure | JSON Schema / Pydantic model | Property-based test | Schema validates current SAD output |
| 8 | Yes | Build extraction pipeline | Parser + schema | `architecture.yaml` | Property-based test | YAML round-trips without information loss |
| 9 | Yes | Link YAML entries to SAD source lines | SAD, YAML | Source-line annotations | CI check | Every YAML entry has a SAD line reference |

> Eight tasks derived from one roadmap step. Steps 2 and 3 produce similarly-sized task sets. The spiral gate (3a) then validates the full enforcement loop across all three steps before the slice expands.

## Execution Model

Phases follow a **spiral** cadence. Phase A steps 1–3 execute first, then a thin Kernel slice (B.15–B.16) validates the enforcement loop end-to-end before backfilling. Each phase ends with an explicit quality gate. Critical-path components (Kernel, Sandbox, Egress) carry **SIL-3 rigor** — formal specs, property-based tests, independent verification. Standard-path components carry **SIL-1**.

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

---

## Designer's Diary

### Entry #1 — 17 February 2026

Twelve research agents swept six domains today: ISO systems-engineering standards, SpaceX's engineering culture, OpenAI's deployment methodology, Anthropic's safety architecture, architecture fitness functions, and failure analysis techniques. The goal was to stress-test the v0.1 roadmap — 73 steps, 13 phases, linear execution — against what the field actually knows about building safety-critical autonomous systems.

The ISO sweep (42010, 25010, 15288, 12207) exposed the first gap: traceability was implicit. The plan said "we'll test things" but never enforced a structural chain from stakeholder concern through architecture decision to deployment proof. 15288's verification process definitions demanded a living Requirements Traceability Matrix, auto-generated from decorators so it can't drift. That became step 10, and fitness functions (step 9) became the CI-level enforcement mechanism — architecture constraints checked on every commit, not just at design review.

SpaceX's responsible-engineer model resolved the rigor question. The original plan treated all components uniformly, which is both wasteful (a config UI doesn't need formal verification) and dangerous (a kernel invariant enforcer needs more than unit tests). Their stratified requirements framework — safety constraints non-negotiable, performance constraints iteratively negotiable — mapped directly onto SIL-tiered rigor: SIL-3 for Kernel, Sandbox, and Egress; SIL-1 for Console and Config.

OpenAI's eval-driven development was the single largest structural addition. Their internal methodology treats evaluations, not prompts or code, as the source of truth for AI behavior. The original roadmap had testing but no eval infrastructure. This finding created Phase K (EDDOps) wholesale — steps 66–69 — and changed step 8 from unit tests to property-based boundary fuzzing. If evaluations define behavior, testing must be generative rather than example-based.

Anthropic contributed two things. First, constitutional AI as executable specification: Holly's Celestial L0–L4 goals aren't documentation, they're machine-checkable predicates running in the eval pipeline. Second, defense-in-depth exposed that the original safety model was single-layer. That drove the safety case steps (33, 84) — structured arguments in claims → evidence → context format — and the dissimilar verification step (20), because a safety check shouldn't rely solely on the mechanism it's checking.

The failure analysis research was sobering. Published data shows 41–87% failure rates in multi-agent systems without structural safeguards. Dominant failure modes: goal injection, sandbox escape, egress bypass, invariant desynchronization. This drove FMEA (step 13), TLA+ formal specs (step 14), and the requirement that every identified failure mode either has a mitigation traced to a test or is explicitly accepted as residual risk.

Two meta-conclusions emerged. First, execution had to shift from waterfall to spiral — you cannot validate an architecture by building it linearly. Step 3a (spiral gate) forces a thin vertical slice early: one kernel invariant enforced through one boundary crossing with one eval gate, proving the loop works before committing to 86 steps on top of it. Second, failure predicates needed promotion from implicit to explicit. The SAD defines eigenspectrum monitoring, K8 eval gates, and compensating actions, but nowhere did the plan specify what constitutes a failure predicate. The monograph formalizes this as the infeasibility residual — a measurable quantity — and steps 13–14 exist to produce an explicit, testable catalog rather than an implicit hope that monitoring catches problems.

Net result: 73 steps → 86. 13 phases → 14. Waterfall → spiral. Uniform rigor → SIL-tiered. Every addition traces to a specific research finding, and every finding traces to a specific gap.

### Entry #2 — 17 February 2026

The task manifest existed — 545 tasks across 15 spiral slices — but a simple question exposed the problem: could a developer actually build from it? The manifest says *what* to build and *when*. The SAD says *what exists* and *how it connects*. Neither says *what crosses each boundary*, *how each component behaves*, or *what "correct" means computationally*. Three documents were missing.

The first was the Interface Control Document. The SAD draws ~40 arrows between components but never specifies what flows along them. A developer implementing the MCP→Sandbox gRPC call wouldn't know the proto schema, error codes, timeout behavior, or tenant isolation strategy without reading the SAD comments and guessing. The ICD v0.1 now specifies 49 interface contracts — every boundary crossing in the SAD — with schema definitions, error contracts, latency budgets (in-process < 1ms, gRPC < 10ms, HTTP < 50ms, LLM < 30s), backpressure strategies, tenant isolation mechanisms, idempotency rules, and redaction requirements. Each contract inherits the SIL of its higher-rated endpoint and includes a cross-reference back to the SAD arrow that motivated it.

The second gap was behavioral. The SAD tells you the Kernel has eight invariant gates (K1–K8) but not their state machines. A developer implementing K3 bounds checking needs to know: what states exist, what transitions are legal, what failure predicates trigger, what invariants must hold across all states, and what happens when enforcement fails. The Component Behavior Specifications now formalize all three SIL-3 components — Kernel (KernelContext lifecycle + K1–K8 gate state machines), Sandbox (executor isolation with namespace/seccomp/resource limit state machines), and Egress (L7 filter pipeline with allowlist→redaction→rate-limit→logging stage ordering). Every state machine includes guard conditions, failure predicates, and the specific invariants that must be preserved. This document makes the TLA+ specs in Phase B (steps 14.1–14.3) directly implementable rather than requiring the developer to reverse-engineer behavior from prose.

The third gap was the goal hierarchy. The README describes Celestial L0–L4 and Terrestrial L5–L6 conceptually, but multiple tasks reference "goal compliance" as an acceptance criterion without defining what that means computationally. The Goal Hierarchy Formal Specification now defines every level as an executable predicate with typed inputs and outputs — L0 Safety returns a GoalResult with satisfaction distance, L4 Constitutional checks predicate sets against the constitution, and the lexicographic gating algorithm enforces strict L0 → L1 → … → L6 ordering. The spec also formalizes four APIs (GoalPredicate, LexicographicGate, GoalDecomposer, FeasibilityChecker) and three theorems (Celestial Inviolability, Terrestrial Subordination, Feasibility–Governance Equivalence) that must be verified during development. The infeasibility residual — the monograph's measure of how far a team topology is from satisfying its goal assignment — is now a computable quantity with a defined eigenspectrum monitoring interface.

Three agents generated these documents in parallel, then a fourth agent validated the entire 545-task manifest against all three. The validation was systematic: five passes covering ICD coverage, behavior spec coverage, goal hierarchy coverage, acceptance criteria specificity, and dependency sequence integrity. It found 38 missing tasks and 47 acceptance criteria that could be made more precise.

The ICD pass found 8 gaps — no tasks existed for building an ICD schema registry, an ICD validation test harness, ICD-specific fitness functions, or ICD-aware RLS policies on Postgres. The behavior spec pass found 12 gaps — no tasks for formal state machine validation, guard condition verification, invariant preservation testing, or runtime escape testing against adversarial inputs. The goal hierarchy pass found 12 gaps — no tasks for implementing individual L0–L4 predicates as executable functions, lexicographic gating enforcement, multi-agent feasibility checking, or verifying the three main theorems. Six cross-cutting tasks were added for ICD safety case integration, dissimilar verifier state machine formalization, and final pre-release validation of all formal specs.

The 47 acceptance criteria refinements replaced vague statements with specific document references. "Schema validated" became "Per ICD-006/007 Kernel boundary schema, YAML components map 1:1 to KernelContext entry points." "Goal compliance verified" became "Per Goal Hierarchy §2.0–2.4, each Celestial predicate returns GoalResult with satisfaction distance metric; zero violations in adversarial eval suite." "Failure mode tested" became "Per Behavior Spec §1.4 K3 state machine, BOUNDS_EXCEEDED state reached on over-budget input; compensating action fires within 100ms."

Net result: 545 → 583 tasks. 113 → 127 critical-path tasks. Three formal engineering documents now underpin every acceptance criterion. The task manifest is no longer a project management artifact disconnected from engineering specifications — it's a validated, cross-referenced development contract where every task traces to an ICD interface, a behavior spec state machine, or a goal hierarchy predicate.
