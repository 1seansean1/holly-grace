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
   - [Task Execution Checklist](#task-execution-checklist) — before / during / after every task
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

### Task Execution Checklist

Every task — without exception — follows this checklist. The steps map to DPG nodes (P0–P7) and invariant I15. Skipping any step is a process violation.

**Before (P0–P2):**

1. **Sync state.** Confirm `status.yaml`, `PROGRESS.md`, README progress table, and Artifact Genealogy counts are mutually consistent. If any disagree, resolve before proceeding.
2. **Verify alignment.** Run `python -m holly.arch gantt` and diff the three outputs (`GANTT.mermaid`, `GANTT_critical.mermaid`, `PROGRESS.md`) against the checked-in versions. Zero diff expected; any delta means a prior task left dirty state.
3. **Determine next task.** Consult Task Manifest critical path. The next pending `(crit)` task whose dependencies are all `done` is the target.
4. **Review DPG P0–P1.** Context sync: read the task spec (ID, MP step, input, output, verification, acceptance). Task derivation: confirm the task traces to at least one of ICD interface, Behavior Spec state machine, or Goal Hierarchy predicate. If it doesn't, the task is under-specified — halt and fix the manifest.
5. **Spec pre-check (P2).** Verify the task's acceptance criteria are concrete and testable. Vague criteria ("works correctly") must be sharpened against the γ-phase specs before implementation begins.

**During (P3–P5):**

6. **Implement (P3A).** Write production code in the module specified by the RTD. Follow existing patterns (typing, docstrings, `__slots__`, ruff compliance).
7. **Formal verification (P3B).** If the task is SIL-3 or involves a TLA+ spec, verify the formal model covers the new behavior. (SIL-1/2 tasks: skip.)
8. **Test authoring (P3C).** Write tests that exercise the acceptance criteria. Property-based tests for invariant-heavy code; integration tests for cross-module behavior; at minimum one negative test (invalid input, failure path).
9. **Verification (P4).** Run `ruff check holly tests` (zero errors) and `pytest tests/ -q` (all pass, zero regressions).
10. **Regression gate (P5).** Confirm the pre-existing test count still passes. No test may be deleted or weakened to make a new task pass.

**After (P6–P7):**

11. **Update `status.yaml` (P6.1a).** Mark the task `done` with date and note (include test count contribution).
12. **Regenerate tracking artifacts.** Run `python -m holly.arch gantt` to regenerate `GANTT.mermaid`, `GANTT_critical.mermaid`, `PROGRESS.md`.
13. **Diff `PROGRESS.md`.** Confirm the done count and critical-path count incremented as expected. If `PROGRESS.md` is unchanged after a task completion, the pipeline is broken — halt and investigate.
14. **Update README progress table.** Match the Slice 1 row (and Σ row) to the new `PROGRESS.md` totals.
15. **Update Artifact Genealogy.** Increment test count and module count in: mermaid node, prose paragraph, inventory table, and chronology section.
16. **Commit (P7).** Stage only the files touched by this task. Commit message format: `Task <ID>: <summary>`. Push to both remotes (`gitlab main`, `github main:master`).

---

## Current System State

Audit instrument: [`Artifact_Genealogy_Checklist.md`](docs/audit/Artifact_Genealogy_Checklist.md)

### Task Manifest and Current Progress

442 specified tasks across 15 spiral slices (583 planned; 141 deferred to later slices), validated against ICD v0.1, Component Behavior Specs SIL-3, and Goal Hierarchy Formal Spec. Full manifest: [`Task_Manifest.md`](docs/Task_Manifest.md) | Progress: [`PROGRESS.md`](docs/architecture/PROGRESS.md) | Gantt: [`GANTT.mermaid`](docs/architecture/GANTT.mermaid) | Critical path: [`GANTT_critical.mermaid`](docs/architecture/GANTT_critical.mermaid)

| Slice | Phase | Done | Total | Progress | Critical Path |
|------:|-------|-----:|------:|---------:|---------------|
| 1 | Phase A Spiral (Steps 1, 2, 3, 3a) | 10 | 39 | 25% [##........] | 10/12 |
| 2 | Phase A Backfill (Steps 4-11) | 0 | 39 | 0% [..........] | 0/10 |
| 3 | Phase B: Failure Analysis & Kernel | 0 | 62 | 0% [..........] | 0/19 |
| 4 | Phase C: Storage Layer (Steps 22-26) | 0 | 23 | 0% [..........] | 0/7 |
| 5 | Phase D: Safety & Infra (Steps 27-33) | 0 | 33 | 0% [..........] | 0/10 |
| 6 | Phase E: Core L2 (Steps 34-40) | 0 | 45 | 0% [..........] | 0/12 |
| 7 | Phase F: Engine L3 (Steps 41-45) | 0 | 24 | 0% [..........] | 0/6 |
| 8 | Phase G: Sandbox (Steps 46-50) | 0 | 29 | 0% [..........] | 0/10 |
| 9 | Phase H: API & Auth (Steps 51-56) | 0 | 24 | 0% [..........] | 0/8 |
| 10 | Phase I: Observability (Steps 57-61) | 0 | 21 | 0% [..........] | 0/7 |
| 11 | Phase J: Agents (Steps 62-65) | 0 | 25 | 0% [..........] | 0/10 |
| 12 | Phase K: Eval / EDDOps (Steps 66-69) | 0 | 19 | 0% [..........] | 0/10 |
| 13 | Phase L: Config (Steps 70-72) | 0 | 12 | 0% [..........] | 0/4 |
| 14 | Phase M: Console L5 (Steps 73-78) | 0 | 18 | 0% [..........] | 0/7 |
| 15 | Phase N: Deploy & Ops (Steps 79-86) | 0 | 29 | 0% [..........] | 0/14 |
| **Σ** | **All** | **10** | **442** | **2%** | |

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

> **Standing Process Reminder — execute before every task:**
> 1. Sync state: `status.yaml` ↔ `PROGRESS.md` ↔ README table ↔ Genealogy counts
> 2. Verify alignment: run `python -m holly.arch gantt` and diff outputs
> 3. Determine next task: consult Task Manifest critical path
> 4. Review DPG P0–P1: context sync + task derivation
> 5. After task completion: P6.1a is mandatory — regenerate PROGRESS.md, update README progress table, update Artifact Genealogy counts

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

> **Standing Process Reminder — execute before every task:**
> 1. Sync state: `status.yaml` ↔ `PROGRESS.md` ↔ README table ↔ Genealogy counts
> 2. Verify alignment: run `python -m holly.arch gantt` and diff outputs
> 3. Determine next task: consult Task Manifest critical path
> 4. Review DPG P0–P1: context sync + task derivation
> 5. After task completion: P6.1a is mandatory — regenerate PROGRESS.md, update README progress table, update Artifact Genealogy counts

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

> **Standing Process Reminder — execute before every task:**
> 1. Sync state: `status.yaml` ↔ `PROGRESS.md` ↔ README table ↔ Genealogy counts
> 2. Verify alignment: run `python -m holly.arch gantt` and diff outputs
> 3. Determine next task: consult Task Manifest critical path
> 4. Review DPG P0–P1: context sync + task derivation
> 5. After task completion: P6.1a is mandatory — regenerate PROGRESS.md, update README progress table, update Artifact Genealogy counts

### Entry #4 — 18 February 2026

We used it. The Artifact Genealogy Checklist v2.0 ran its first audit today — run ID `AGC-2026-02-17-001` — against the full specification corpus. Seven parallel agents executed §0 through §9 in two waves: §0 first to extract state variables, then §1-2, §3-4, §5, §6, §7, and §9 simultaneously. The run took roughly 20 minutes and covered 183 base checkboxes.

Initial disposition: CONDITIONAL PASS. 148 of 158 applicable checks passed, 22 were correctly N/A (Phase ε at slice 0), and 10 failed. All 10 failures were document-control items — exactly the category the checklist was designed to catch.

The findings split into three classes. First, stale version references — the prior X-003 fix renamed SAD and RTD files and updated the inventory table, but missed the mermaid node labels, the README ASCII chain, and two narrative paragraphs. All four still said v0.1.0.2. This is the same propagation failure pattern that X-001 demonstrated: a fix applied at one layer of a document without cascading to all layers. The checklist's §7 (Version Consistency) caught it.

Second, count discrepancies. The §0 state variable extraction produced plausible but incorrect values for three variables. N_sil was recorded as 50; verified recount yields 43. N_nodes was recorded as 34; verified recount yields 35. N_artifacts was recorded as 14; the inventory table has 16. The §0 agent estimated counts from partial reads rather than performing exhaustive enumeration — the same "assert rather than count" pattern the external audit identified. Two other discrepancies (N_edges, N_sad) turned out to be agent miscounts rather than real defects: verified recounts confirmed the §0 values of 80 and 45 respectively.

Third, a structural inconsistency. The Design Methodology (DM) was placed in the γ (Specifications) subgraph of the Genealogy mermaid diagram, but the inventory table classified it as phase α (Research & Theory). The derivation edges confirm α: DM's inputs are ISO, SpaceX, OpenAI, Anthropic, Failure, and Fitness research — all α nodes. DM is a research-derived methodology, not a SAD-derived specification. The mermaid was wrong.

All 12 findings (10 original + 2 discovered during remediation) were fixed in a single remediation pass. The audit results file was updated from CONDITIONAL PASS to PASS post-remediation. The finding register now contains the complete resolution history.

The meta-lesson is about agent reliability as auditors. Of the 7 agents, two produced incorrect counts (§6 counted 77 edges instead of 80; §7 counted ~34 SAD components instead of 45). Both were caused by incomplete reads — the agent's context window truncated the input, and it counted what it could see rather than flagging that it couldn't see everything. The §0 agent made the same error with N_sil (50 instead of 43). The fix is structural: any agent reporting a count must also report its read coverage (bytes read / file size) and flag when coverage is incomplete. The checklist doesn't currently require this, but it should — the count verification procedure needs a completeness attestation, not just a number.

Net result: first audit run complete, 12/12 findings resolved, specification corpus internally consistent, baseline established. The repo is clean for slice 1.

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Task 3a.8 — Full pipeline validation. Remaining critical path: `3a.8 → 3a.10 → 3a.12`.

> **Standing Process Reminder — execute before every task:**
> 1. Sync state: `status.yaml` ↔ `PROGRESS.md` ↔ README table ↔ Genealogy counts
> 2. Verify alignment: run `python -m holly.arch gantt` and diff outputs
> 3. Determine next task: consult Task Manifest critical path
> 4. Review DPG P0–P1: context sync + task derivation
> 5. After task completion: P6.1a is mandatory — regenerate PROGRESS.md, update README progress table, update Artifact Genealogy counts

### Entry #5 — 18 February 2026

Six findings from an external review landed today, all validated, all fixed in a single pass. The pattern across all six is the same one the prior entries keep documenting: state propagation failure across documents. The interesting part this time was that three of the six were *infrastructure* failures — tooling and audit machinery that had drifted — not just prose counts.

Finding #1 was a genuine runtime defect. The Gantt generator emits task labels containing Unicode comparison operators (U+2265 `≥`, U+2264 `≤`, U+2260 `≠`) inherited from the Task Manifest. On Windows, `--stdout` and `--critical` paths write to `sys.stdout`, which defaults to `cp1252` — a codec that cannot encode these codepoints. The fix was two-layered: `_mermaid_safe()` now normalizes Unicode operators to ASCII equivalents (`>=`, `<=`, `!=`), and `cli.py` wraps stdout in a `UTF-8 TextIOWrapper` for the console output paths. The normalization is the real fix; the wrapper is defense-in-depth for any future Unicode that escapes sanitization.

Finding #2 exposed a configuration management gap in the audit machinery itself. Findings F-001 through F-012 all cited `resolved_commit=9d10de8` — a SHA that doesn't exist in the git history. It was a real commit once, but the force-push consolidation (commit `aec0cd5`) that unified the GitHub/GitLab mirrors rewrote history and orphaned it. The finding register was never updated because the consolidation fix (F-018/F-022) focused on forward SHAs, not backward reconciliation. All 10 affected entries now reference `aec0cd5`. The lesson: when history rewriting occurs, *all* SHA references in audit artifacts must be cascaded, not just the ones in the current finding scope.

Finding #3 was the 583-vs-442 task count discrepancy. Diary Entry #2 documents the sequence: 545 original tasks + 38 added by validation = 583 planned. But the manifest parser only extracts 442 tasks from the elaborated tables — the remaining 141 exist as planned items not yet promoted to the slice tables. The README now states "442 specified tasks (583 planned; 141 deferred)" to match the Σ row. The prior wording asserted 583 as if all were specified, which was incorrect.

Finding #4: `architecture.yaml` contains 48 components; the Genealogy mermaid and narrative cited 45. The 45 figure was correct at the time it was written but was never updated when three components were added during SAD iteration. Three locations in `Artifact_Genealogy.md` updated.

Finding #5 covered quality gate failures. Two ruff errors: a quoted return annotation in `registry.py:143` (UP037) and import block ordering in `test_hot_reload.py` (I001). Ten mypy errors in `decorators.py` — all the same root cause: `functools.wraps` returns a `_Wrapped` type that mypy doesn't unify with the `TypeVar F`, and the existing `type: ignore[arg-type]` comments targeted the wrong error code. Changed to `type: ignore[return-value]`. Both linters now pass clean.

Finding #6: F-022, F-023, and F-024 all had `resolved_commit=pending` despite being marked `RESOLVED`. These were created during the fourth external audit round but the closure commit was never backfilled. All three now reference `aec0cd5`.

The meta-pattern across entries #3, #4, and #5 is worth noting. Every external audit round uncovers the same category of defect: stale counts, phantom references, and assertion-without-enumeration. The specification corpus is structurally sound — the defects are never architectural or logical. They're always configuration management failures: a value was asserted rather than derived, and subsequent changes didn't propagate. The audit machinery (checklist, finding register) catches these reliably. The question is whether to automate the propagation — a CI check that extracts component counts from `architecture.yaml` and diffs them against every document that asserts a count — or to continue relying on manual audit sweeps. The former is the right answer; it belongs in the fitness function infrastructure (Task Manifest step 9).

Six findings registered (F-025 through F-030), 195 tests passing, ruff and mypy clean.

> **Checkpoint:** [Task Manifest](docs/Task_Manifest.md) | **Next:** Task 3a.8 — Full pipeline validation. Remaining critical path: `3a.8 → 3a.10 → 3a.12`.

> **Standing Process Reminder — execute before every task:**
> 1. Sync state: `status.yaml` ↔ `PROGRESS.md` ↔ README table ↔ Genealogy counts
> 2. Verify alignment: run `python -m holly.arch gantt` and diff outputs
> 3. Determine next task: consult Task Manifest critical path
> 4. Review DPG P0–P1: context sync + task derivation
> 5. After task completion: P6.1a is mandatory — regenerate PROGRESS.md, update README progress table, update Artifact Genealogy counts

---

> Previous codebase (ecom-agents / Holly v2) archived on `archive/v2` branch.
