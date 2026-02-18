# Holly Grace

**Autonomous operations with kernel-enforced trust.**

Holly Grace is the reference implementation of the theoretical framework developed in:

> **Allen, S. P. (2026).** *Informational Monism, Morphogenetic Agency, and Goal-Specification Engineering: A Unified Framework.* v2.0, 289 pp.

---

## Contents

1. [From Informational Monism to Autonomous Operations](#from-informational-monism-to-autonomous-operations) — the theory
2. [Architecture](#architecture) — the system
3. [Artifact Genealogy](#artifact-genealogy) — the derivation chain
4. [Development Procedure](#development-procedure) — the process
5. [Current System State](#current-system-state) — where we are now
6. [Designer's Diary](#designers-diary) — how we got here

---

## From Informational Monism to Autonomous Operations

The framework begins from a single ontological commitment: every system — computational, biological, organizational — is a network of information channels, and the dynamics that matter are the dynamics of those channels. Channel theory supplies the microdynamics: tokens flow through typed conduits whose capacity, noise, and coupling are measurable quantities. When channels compose, they induce macro-channels with emergent bandwidth and loss characteristics that are not simple sums of their parts. Admissibility conditions distinguish passive transport — information flowing through a structure — from active regeneration, where a subsystem reconstructs and redirects its own channels. That distinction is the formal boundary between mechanism and agency.

Agency is defined by three properties: digital branching (the capacity to select among discrete successor states), a feedback Jacobian (sensitivity of future channel structure to current output), and agency rank (the dimensionality of the state space an agent can steer). Together these yield a cognitive light cone — the region of the system's future that a given agent can causally influence within its resource and time budget. A single agent with high rank and a wide light cone can solve problems unilaterally. An agent with narrow rank must compose with others, and the terms of that composition are not negotiable — they are set by the mathematics of multi-agent feasibility.

Goal structure follows directly. A goal is a predicate set over the system's state space: a region the system must reach or remain within. Goals have codimension — the number of independent constraints they impose — and they compose into hierarchies where higher-level goals lexicographically dominate lower ones. Holly formalizes this as two regimes: **Celestial goals (L0–L4)** are immutable safety constraints — permission boundaries, constitutional rules, invariant enforcement — that no lower-level goal can override. **Terrestrial goals (L5–L6)** are the user's actual intent, decomposed into executable subgoals. Lexicographic gating means a Terrestrial goal can never satisfy itself by violating a Celestial constraint.

Multi-agent feasibility determines whether a given assignment of goals to agents is satisfiable. Steering operators map agent outputs to goal-state transitions; assignment matrices bind agents to subgoals; the infeasibility residual measures the gap between what a team can collectively steer and what the goal hierarchy demands. When the residual is nonzero, the topology must change — agents added, removed, or re-scoped — and adaptive governance defines how that change happens safely. Epsilon-band compliance gives each agent a tolerance envelope; repartitioning restructures team boundaries when compliance degrades; and the feasibility–governance equivalence theorem guarantees that if governance constraints are satisfied, the system remains within the feasible operating region. Steering power analysis quantifies the coupling scaling laws and governance margins that bound how much morphogenetic flexibility a topology can sustain before coherence breaks down.

---

## Architecture

Holly instantiates this theory as a three-layer stack. **Kernel (L1)** is an in-process library that wraps every boundary crossing with invariant enforcement: schema validation, permission gating, bounds checking, trace injection, idempotency, HITL gates, and eval gates. **Core (L2)** receives declarative intent via natural language, classifies it (direct solve, team spawn, or clarify), decomposes it into the 7-level goal hierarchy, and routes it through the APS Controller. APS classifies each goal into one of four tiers — **T0 Reflexive** (single-agent, no coordination), **T1 Deliberative** (single-agent, multi-step reasoning), **T2 Collaborative** (multi-agent team with fixed contracts), **T3 Morphogenetic** (dynamic team that restructures mid-execution) — and dispatches accordingly. The Team Topology Manager spawns agent teams with three binding constraints: inter-agent contracts, per-agent MCP tool permissions, and resource budgets. T3 topologies reshape via steer operations; the eigenspectrum monitors communication patterns against contracted topology and triggers steer or dissolve when divergence exceeds threshold. **Engine (L3)** runs durable workflows with effectively-once semantics across concurrent lanes, an MCP tool registry with per-agent permission masks, and sandboxed code execution over gRPC. Failure detection operates at three levels: K8 eval gates halt on behavioral check failure, the workflow engine fires compensating actions on task-graph node failure, and eigenspectrum divergence triggers topological restructuring. All storage, observability, and egress are tenant-isolated by default. Auth is JWKS-based via Authentik OIDC with short-lived tokens and Redis-backed revocation.

---

## Artifact Genealogy

Every artifact in this codebase traces back through a five-phase derivation chain. No artifact exists without provenance.

```
α Research & Theory          62 sources + monograph (289 pp)
  → β Architecture           Custom SAD tool → SAD v0.1.0.5 + RTD v0.1.0.4
    → γ Specifications        ICD, Behavior Specs, Goal Hierarchy, SIL Matrix
      → δ Process & Governance Design Methodology, Task Manifest, Test Governance, Development Procedure
        → ε Execution          Code, tests, evidence, audit artifacts — the 15-slice spiral
```

The complete derivation graph — every node, every edge — is in [`Artifact_Genealogy.md`](docs/architecture/Artifact_Genealogy.md). The re-entrant audit instrument that verifies this graph is the [`Artifact_Genealogy_Checklist.md`](docs/audit/Artifact_Genealogy_Checklist.md).

---

## Development Procedure

All development follows a single executable graph defined in [`Development_Procedure_Graph.md`](docs/Development_Procedure_Graph.md). The graph is iterative — it loops per task batch within a slice and per slice across the 15-slice spiral. No development work occurs outside this graph.

```
P0 Context Sync → P1 Task Derivation (+Test Governance) → P2 Spec Pre-Check
    → [P3A Implementation ‖ P3B Formal Verification ‖ P3C Test Authoring]
    → P4 Verification → P5 Regression Gate → P6 Doc Sync → P7 Commit
    → P8 Spiral Gate Check → P9 Phase Gate Ceremony → loop or P11 Release
```

Full design methodology, meta procedure, and task derivation protocol: [`Design_Methodology_v1.0.docx`](docs/Design_Methodology_v1.0.docx)

---

## Current System State

Audit instrument: [`Artifact_Genealogy_Checklist.md`](docs/audit/Artifact_Genealogy_Checklist.md)

### Task Manifest

583 tasks across 15 spiral slices, validated against ICD v0.1, Component Behavior Specs SIL-3, and Goal Hierarchy Formal Spec. Full manifest: [`Task_Manifest.md`](docs/Task_Manifest.md)

| Slice | Phase | Steps | Tasks | SIL | Gate |
|---|---|---|---|---|---|
| 1 | A (spiral) | 1, 2, 3, 3a | 39 | 2–3 | Spiral gate: enforcement loop e2e |
| 2 | A (backfill) | 4–11 | 44 | 2 | Phase A: arch enforcement complete |
| 3 | B | 12–21 | 86 | 3 | Phase B: kernel verified SIL-3 |
| 4 | C | 22–26 | 30 | 2 | Phase C: storage tested |
| 5 | D | 27–33 | 44 | 2–3 | Phase D: safety case for infra |
| 6 | E | 34–40 | 55 | 2 | Phase E: core integration tested |
| 7 | F | 41–45 | 32 | 2 | Phase F: engine e2e tested |
| 8 | G | 46–50 | 45 | 3 | Phase G: sandbox SIL-3 pass |
| 9 | H | 51–56 | 37 | 2 | Phase H: API + auth tested |
| 10 | I | 57–61 | 25 | 2 | Phase I: observability live |
| 11 | J | 62–65 | 34 | 2 | Phase J: agents + constitution exec |
| 12 | K | 66–69 | 26 | 2 | Phase K: eval pipeline gates merges |
| 13 | L | 70–72 | 14 | 1 | Phase L: config operational |
| 14 | M | 73–78 | 28 | 1 | Phase M: console functional |
| 15 | N | 79–86 | 48 | 1–3 | Phase N: release safety case |
| | | **86 steps** | **583** | | |

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

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Task 1.5 — Write SAD parser (mermaid → AST), first implementation task on the Slice 1 critical path.

### Entry #2 — 17 February 2026

The task manifest existed — 545 tasks across 15 spiral slices — but a simple question exposed the problem: could a developer actually build from it? The manifest says *what* to build and *when*. The SAD says *what exists* and *how it connects*. Neither says *what crosses each boundary*, *how each component behaves*, or *what "correct" means computationally*. Three documents were missing.

The first was the Interface Control Document. The SAD draws ~40 arrows between components but never specifies what flows along them. A developer implementing the MCP→Sandbox gRPC call wouldn't know the proto schema, error codes, timeout behavior, or tenant isolation strategy without reading the SAD comments and guessing. The ICD v0.1 now specifies 49 interface contracts — every boundary crossing in the SAD — with schema definitions, error contracts, latency budgets (in-process < 1ms, gRPC < 10ms, HTTP < 50ms, LLM < 30s), backpressure strategies, tenant isolation mechanisms, idempotency rules, and redaction requirements. Each contract inherits the SIL of its higher-rated endpoint and includes a cross-reference back to the SAD arrow that motivated it.

The second gap was behavioral. The SAD tells you the Kernel has eight invariant gates (K1–K8) but not their state machines. A developer implementing K3 bounds checking needs to know: what states exist, what transitions are legal, what failure predicates trigger, what invariants must hold across all states, and what happens when enforcement fails. The Component Behavior Specifications now formalize all three SIL-3 components — Kernel (KernelContext lifecycle + K1–K8 gate state machines), Sandbox (executor isolation with namespace/seccomp/resource limit state machines), and Egress (L7 filter pipeline with allowlist→redaction→rate-limit→logging stage ordering). Every state machine includes guard conditions, failure predicates, and the specific invariants that must be preserved. This document makes the TLA+ specs in Phase B (steps 14.1–14.3) directly implementable rather than requiring the developer to reverse-engineer behavior from prose.

The third gap was the goal hierarchy. The README describes Celestial L0–L4 and Terrestrial L5–L6 conceptually, but multiple tasks reference "goal compliance" as an acceptance criterion without defining what that means computationally. The Goal Hierarchy Formal Specification now defines every level as an executable predicate with typed inputs and outputs — L0 Safety returns a GoalResult with satisfaction distance, L4 Constitutional checks predicate sets against the constitution, and the lexicographic gating algorithm enforces strict L0 → L1 → … → L6 ordering. The spec also formalizes four APIs (GoalPredicate, LexicographicGate, GoalDecomposer, FeasibilityChecker) and three theorems (Celestial Inviolability, Terrestrial Subordination, Feasibility–Governance Equivalence) that must be verified during development. The infeasibility residual — the monograph's measure of how far a team topology is from satisfying its goal assignment — is now a computable quantity with a defined eigenspectrum monitoring interface.

Three agents generated these documents in parallel, then a fourth agent validated the entire 545-task manifest against all three. The validation was systematic: five passes covering ICD coverage, behavior spec coverage, goal hierarchy coverage, acceptance criteria specificity, and dependency sequence integrity. It found 38 missing tasks and 47 acceptance criteria that could be made more precise.

The ICD pass found 8 gaps — no tasks existed for building an ICD schema registry, an ICD validation test harness, ICD-specific fitness functions, or ICD-aware RLS policies on Postgres. The behavior spec pass found 12 gaps — no tasks for formal state machine validation, guard condition verification, invariant preservation testing, or runtime escape testing against adversarial inputs. The goal hierarchy pass found 12 gaps — no tasks for implementing individual L0–L4 predicates as executable functions, lexicographic gating enforcement, multi-agent feasibility checking, or verifying the three main theorems. Six cross-cutting tasks were added for ICD safety case integration, dissimilar verifier state machine formalization, and final pre-release validation of all formal specs.

The 47 acceptance criteria refinements replaced vague statements with specific document references. "Schema validated" became "Per ICD-006/007 Kernel boundary schema, YAML components map 1:1 to KernelContext entry points." "Goal compliance verified" became "Per Goal Hierarchy §2.0–2.4, each Celestial predicate returns GoalResult with satisfaction distance metric; zero violations in adversarial eval suite." "Failure mode tested" became "Per Behavior Spec §1.4 K3 state machine, BOUNDS_EXCEEDED state reached on over-budget input; compensating action fires within 100ms."

Net result: 545 → 583 tasks. 113 → 127 critical-path tasks. Three formal engineering documents now underpin every acceptance criterion. The task manifest is no longer a project management artifact disconnected from engineering specifications — it's a validated, cross-referenced development contract where every task traces to an ICD interface, a behavior spec state machine, or a goal hierarchy predicate.

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Task 1.5 — Write SAD parser (mermaid → AST), begin Phase ε Execution Slice 1.

### Entry #3 — 18 February 2026

The specification corpus passed its first external audit today. The methodology was systematic: normalize all 12 markdown documents into a canonical ID scheme, extract every quantitative claim, verify every cross-reference, classify every assertion by evidence status, and map the whole thing against ISO/IEC/safety benchmarks. Design philosophy scored Strong. Coherence scored Adequate. Consistency scored Weak. That last verdict was correct and useful.

The audit surfaced six defects, four of which were hard conflicts. The most instructive was X-001: the Test Governance Spec enumerates exactly 62 control IDs (SEC-015, TST-015, ARC-006, OPS-009, CQ-010, GOV-007) but four documents — the DPG, the Artifact Genealogy mermaid, the genealogy timeline, and formerly the README — all claimed 65. The number 65 was never counted; it was asserted once and propagated. That is exactly the failure mode the v2.0 audit checklist was designed to catch: a cardinal snapshot hardens into an unquestioned constant and drifts from the source of truth. §7 of the checklist (Version & Count Consistency) would have flagged this on the first run. The fix was mechanical — four string replacements — but the lesson is structural: counts are state variables, not constants, and every assertion of a count must trace to an enumeration, not to a prior assertion.

X-003 was the worst one architecturally. The SAD file was named `SAD_0.1.0.2.mermaid` but declared `v0.1.0.5` internally. The RTD was named `RTD_0.1.0.2.mermaid` but synced to `v0.1.0.4`. The filenames were fossils from an earlier iteration that survived five rounds of internal revision without anyone renaming them. The ICD correctly referenced `v0.1.0.5` because it was generated from the SAD's internal declaration, not its filename. This is a textbook configuration management failure: the identifier visible to the file system disagreed with the identifier visible to the document consumer. Both files were renamed to match their internal versions, and all cross-references (Genealogy inventory table, DPG P0.6 parse targets) were cascaded.

X-006 caught a dangling reference: `docs/Component_Behavior_Specs.md` in the Dev Environment Spec, when the actual file is `Component_Behavior_Specs_SIL3.md`. The `_SIL3` suffix was added during generation to make the scope explicit, but the reference in the Dev Environment Spec was written before the file existed and never updated. Same pattern as X-001 — an assertion made before its referent materialized, never reconciled afterward.

The audit also noted two framing tensions that weren't defects but deserve tracking. First, the README describes a "three-layer stack" (Kernel L1, Core L2, Engine L3) but the SAD defines six layers (L0–L5 including Cloud/VPC, Observability, Console). Both are correct at different abstraction levels — the README describes the runtime request-processing stack, the SAD describes the full deployment topology — but an engineer reading one after the other will stumble. Second, `deployment-topology.md` is referenced in the SAD, RTD, and Dev Environment Spec but doesn't exist yet. That's design intent, not a broken link — the file is planned for Phase N — but a future audit run should distinguish "planned artifact" from "missing artifact."

The broader finding matters more than any individual defect. The audit's core thesis: *the specification corpus is conceptually advanced and methodologically rigorous, but document-control discipline is the bottleneck.* Philosophy is strong. Translation from theory to process is unusually good. But the mundane work of keeping version numbers, control counts, file paths, and cross-references synchronized across 12+ documents is where integrity degrades. This is not surprising — it's the same failure mode that ISO 15288 configuration management processes exist to prevent, and it's the same failure mode that the v2.0 checklist's cascade verification (§8) was designed to detect. The lesson is that the checklist isn't optional tooling for later — it needs to run now, before execution begins, to establish a clean baseline.

The README was also restructured today. The old version mixed contextualization with reference material — the full 86-step execution model, the meta procedure table, the task derivation protocol with worked example were all inline. A skilled engineer arriving at the repo had to parse 280 lines before understanding the project. The restructured version is 141 lines organized as: theory (why) → architecture (what) → genealogy (provenance) → procedure (how) → current state (where) → diary (narrative). Reference material is linked, not inlined. The task manifest summary table — 15 slices, task counts, SIL levels, gates — lives in the Current System State section because it's the living dashboard, not the Execution Model section because it's not a static reference.

Net result: six document-control defects fixed (X-001 through X-006), README cut from 282 to 141 lines, audit checklist v2.0 pushed, and the first external validation confirms the specification corpus is structurally sound. The limiting factor going forward is not design or specification — it's configuration management discipline. The tooling exists (the checklist). The question is whether we use it.

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Run the Artifact Genealogy Checklist v2.0 to establish clean baseline before Slice 1 execution.

### Entry #4 — 18 February 2026

We used it. The Artifact Genealogy Checklist v2.0 ran its first audit today — run ID `AGC-2026-02-17-001` — against the full specification corpus. Seven parallel agents executed §0 through §9 in two waves: §0 first to extract state variables, then §1-2, §3-4, §5, §6, §7, and §9 simultaneously. The run took roughly 20 minutes and covered 183 base checkboxes.

Initial disposition: CONDITIONAL PASS. 148 of 158 applicable checks passed, 22 were correctly N/A (Phase ε at slice 0), and 10 failed. All 10 failures were document-control items — exactly the category the checklist was designed to catch.

The findings split into three classes. First, stale version references — the prior X-003 fix renamed SAD and RTD files and updated the inventory table, but missed the mermaid node labels, the README ASCII chain, and two narrative paragraphs. All four still said v0.1.0.2. This is the same propagation failure pattern that X-001 demonstrated: a fix applied at one layer of a document without cascading to all layers. The checklist's §7 (Version Consistency) caught it.

Second, count discrepancies. The §0 state variable extraction produced plausible but incorrect values for three variables. N_sil was recorded as 50; verified recount yields 43. N_nodes was recorded as 34; verified recount yields 35. N_artifacts was recorded as 14; the inventory table has 16. The §0 agent estimated counts from partial reads rather than performing exhaustive enumeration — the same "assert rather than count" pattern the external audit identified. Two other discrepancies (N_edges, N_sad) turned out to be agent miscounts rather than real defects: verified recounts confirmed the §0 values of 80 and 45 respectively.

Third, a structural inconsistency. The Design Methodology (DM) was placed in the γ (Specifications) subgraph of the Genealogy mermaid diagram, but the inventory table classified it as phase α (Research & Theory). The derivation edges confirm α: DM's inputs are ISO, SpaceX, OpenAI, Anthropic, Failure, and Fitness research — all α nodes. DM is a research-derived methodology, not a SAD-derived specification. The mermaid was wrong.

All 12 findings (10 original + 2 discovered during remediation) were fixed in a single remediation pass. The audit results file was updated from CONDITIONAL PASS to PASS post-remediation. The finding register now contains the complete resolution history.

The meta-lesson is about agent reliability as auditors. Of the 7 agents, two produced incorrect counts (§6 counted 77 edges instead of 80; §7 counted ~34 SAD components instead of 45). Both were caused by incomplete reads — the agent's context window truncated the input, and it counted what it could see rather than flagging that it couldn't see everything. The §0 agent made the same error with N_sil (50 instead of 43). The fix is structural: any agent reporting a count must also report its read coverage (bytes read / file size) and flag when coverage is incomplete. The checklist doesn't currently require this, but it should — the count verification procedure needs a completeness attestation, not just a number.

Net result: first audit run complete, 12/12 findings resolved, specification corpus internally consistent, baseline established. The repo is clean for slice 1.

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Task 1.5 — Write SAD parser (mermaid → AST). Slice 1 critical path: `1.5 → 1.6 → 1.7 → 1.8 → 2.6 → 2.7 → 2.8 → 3.6 → 3.7 → 3a.8 → 3a.10 → 3a.12`.

---

> Previous codebase (ecom-agents / Holly v2) archived on `archive/v2` branch.
