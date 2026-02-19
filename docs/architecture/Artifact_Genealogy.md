# Holly Grace — Artifact Genealogy & Derivation Graph

**Generated:** 17 February 2026
**Purpose:** Complete lineage of every artifact in the Holly Grace codebase. This document traces how the project was actually built — from first literature review through to the execution loop that produces code. Nothing in the repo exists without a derivation chain back to a source.

---

## 1  The Mega Graph

Every node is an artifact that exists (or existed as a research phase). Every edge is a derivation relationship: the target was produced *from* the source. Color coding: red = external research, blue = theory/monograph, green = architecture, orange = specifications, purple = process/governance, gray = execution outputs.

```mermaid
graph TD
    %% ═══════════════════════════════════════════
    %% PHASE α: RESEARCH & THEORY
    %% ═══════════════════════════════════════════

    subgraph ALPHA["Phase α - Research and Theory"]
        direction TB
        LIT["Literature Review\n62 sources: Landauer, Bennett,\nZurek, Baez, Friston, Anthropic"]
        ISO["ISO Sweep\n42010, 25010,\n15288, 12207"]
        SPX["SpaceX Model\nresponsible-engineer,\nSIL stratification"]
        OAI["OpenAI Methodology\neval-driven dev,\nstaged rollouts"]
        ANTH["Anthropic Safety\nconstitutional AI,\ndefense-in-depth"]
        FAIL["Failure Research\n41-87% multi-agent failure,\nFMEA/FTA"]
        FIT["Fitness Functions\nResearch"]
        MONO["Monograph v2.0\n289 pp, Allen 2026\nInformational Monism,\nMorphogenetic Agency,\nGoal-Spec Engineering"]
        DM["Design Methodology\nv1.0 docx"]

        LIT --> MONO
    end

    style ALPHA fill:#fef2f2,stroke:#dc2626

    %% ═══════════════════════════════════════════
    %% PHASE β: ARCHITECTURE
    %% ═══════════════════════════════════════════

    subgraph BETA["Phase β - Architecture"]
        direction TB
        SADTOOL["Custom SAD Iteration Tool\nrapid mermaid generation\n+ validation pipeline"]
        SAD["SAD v0.1.0.5\nSystem Architecture Document\nMermaid flowchart:\nL0-L5, 48 components"]
        RTD["RTD v0.1.0.4\nRepository Tree Document\nMermaid tree:\ndeploy/, holly/, console/,\ntests/, docs/"]
        REPOTREE["repo-tree.md\nFlat file listing"]
    end

    style BETA fill:#eff6ff,stroke:#2563eb

    %% ═══════════════════════════════════════════
    %% PHASE γ: SPECIFICATIONS
    %% ═══════════════════════════════════════════

    subgraph GAMMA["Phase γ - Specifications"]
        direction TB
        ICD["ICD v0.1\n49 interface contracts\nSchema, error, latency,\nbackpressure, redaction"]
        CBS["Component Behavior Specs\nSIL-3 state machines\nKernel, Sandbox, Egress"]
        GHS["Goal Hierarchy\nFormal Spec\n7-level hierarchy,\nL0-L6 predicates,\n3 theorems"]
        SIL["SIL Classification\nMatrix v1.0\n47 components,\nSIL-1/2/3"]
        DEV["Dev Environment\nSpec v1.0\ntoolchain, CI,\nbranch strategy"]
        MGE["Monograph Glossary\nExtract\n104 symbols,\ntheory-impl mapping"]
    end

    style GAMMA fill:#f0fdf4,stroke:#16a34a

    %% ═══════════════════════════════════════════
    %% PHASE δ: PROCESS & GOVERNANCE
    %% ═══════════════════════════════════════════

    subgraph DELTA["Phase δ - Process and Governance"]
        direction TB
        README["README.md\nMeta Procedure 14-step,\nTask Derivation Protocol,\nDesigners Diary"]
        TM["Task Manifest v2\n583 tasks, 15 slices,\n86 roadmap steps"]
        DPG["Development Procedure\nGraph v1.1\nP0-P11 execution loop"]
        TGS["Test Governance\nSpec v1.0\n62 controls, falsification-first,\nmaturity gates"]
        AUDIT["END_TO_END_AUDIT\nCHECKLIST\n12-stage, P0-P11,\n4 release gates"]
    end

    style DELTA fill:#fdf4ff,stroke:#9333ea

    %% ═══════════════════════════════════════════
    %% PHASE ε: EXECUTION OUTPUTS (future)
    %% ═══════════════════════════════════════════

    subgraph EPSILON["Phase ε - Execution Outputs Slice 1+"]
        direction TB
        SADPARSE["SAD Parser\nsad_parser.py\nmermaid -> AST"]
        SCHEMA["Architecture Schema\nschema.py\nPydantic models"]
        EXTRACT["Extraction Pipeline\nextract.py\nSAD -> YAML"]
        MPARSE["Manifest Parser\nmanifest_parser.py\nTask Manifest -> Manifest"]
        TRACK["Status Tracker\ntracker.py\nGantt + PROGRESS.md"]
        DEPS["Dependency Graph\ndependencies.py\nDAG + duration model"]
        GVALID["Gantt Validator\ngantt_validator.py\nmermaid rendering checks"]
        REG["Architecture Registry\nregistry.py\nsingleton loader"]
        DEC["Decorators\ndecorators.py\n5 arch decorators"]
        CLI["CLI Module\ncli.py\ncommand-line entry"]
        AYML["architecture.yaml"]
        GANTT["GANTT.mermaid\nGANTT_critical.mermaid"]
        PROG["PROGRESS.md"]
        STATYS["status.yaml"]
        TESTS["Test Suite\n2195 tests across\n43 test modules"]
        CODE["holly/ source tree"]
    end

    style EPSILON fill:#f9fafb,stroke:#6b7280

    %% ═══════════════════════════════════════════
    %% DERIVATION EDGES
    %% ═══════════════════════════════════════════

    %% Phase α internal
    ISO --> DM
    SPX --> DM
    OAI --> DM
    ANTH --> DM
    FAIL --> DM
    FIT --> DM

    %% Phase α → β (Theory → Architecture)
    MONO --> SAD
    MONO --> MGE
    DM --> SADTOOL
    SADTOOL --> SAD
    SAD --> RTD
    SAD --> REPOTREE

    %% Phase α → γ (Research → Specs)
    MONO --> GHS
    MONO --> CBS
    SPX --> SIL
    FAIL --> SIL
    ISO --> DEV
    OAI --> DEV
    ANTH --> CBS

    %% Phase β → γ (Architecture → Specs)
    SAD --> ICD
    SAD --> SIL
    SAD --> CBS
    SAD --> DEV
    RTD --> DEV

    %% Phase α+β → δ (Theory+Architecture → Process)
    MONO --> README
    DM --> README
    SAD --> README
    ISO --> README
    SPX --> README
    OAI --> README
    ANTH --> README

    %% Phase γ → δ (Specs → Process)
    README --> TM
    ICD --> TM
    CBS --> TM
    GHS --> TM
    SIL --> TM
    SAD --> TM

    %% Task Manifest validation loop
    TM -->|"validated against"| ICD
    TM -->|"validated against"| CBS
    TM -->|"validated against"| GHS

    %% Procedure Graph derivation
    TM --> DPG
    SIL --> DPG
    DEV --> DPG
    ICD --> DPG
    CBS --> DPG
    GHS --> DPG
    MGE --> DPG

    %% Test Governance derivation
    AUDIT --> TGS
    SIL --> TGS
    DPG --> TGS
    MONO --> TGS

    %% TGS feeds back into DPG
    TGS --> DPG

    %% Phase δ → ε (Process → Execution)
    DPG --> SADPARSE
    DPG --> MPARSE
    DPG --> TRACK
    DPG --> TESTS
    DPG --> CODE

    %% Specs → Execution (architecture)
    SAD --> SADPARSE
    SAD --> SCHEMA
    SAD --> EXTRACT
    SAD --> AYML
    ICD --> CODE
    CBS --> CODE
    GHS --> CODE
    SIL --> TESTS
    DEV --> CODE
    MGE --> CODE
    TGS --> TESTS

    %% Task Manifest → Execution (tracking)
    TM --> MPARSE
    TM --> TRACK
    TM --> DEPS

    %% Execution internal derivations
    SADPARSE --> SCHEMA
    SCHEMA --> EXTRACT
    EXTRACT --> AYML
    MPARSE --> TRACK
    MPARSE --> DEPS
    DEPS --> TRACK
    DEPS --> GANTT
    TRACK --> GANTT
    TRACK --> PROG
    GVALID --> TRACK
    STATYS --> TRACK
    STATYS --> PROG
    CLI --> TRACK
    CLI --> EXTRACT
    SCHEMA --> REG
    AYML --> REG
    RTD --> CODE
```

---

## 2  Phase Narrative

### Phase α — Research & Theory (completed)

The project began with a **literature review** spanning 62 academic sources (Landauer's erasure principle, Bennett's reversible computation, Zurek's quantum Darwinism, Baez's compositional frameworks, Friston's active inference, Anthropic's constitutional AI). This produced the **monograph** — 289 pages formalizing informational monism, channel theory, agency, goal-specification engineering, morphogenetic field theory, and the APS cascade.

In parallel, **six research agents** swept industry practices:

| Agent | Domain | Key Contribution |
|-------|--------|-----------------|
| ISO Sweep | 42010, 25010, 15288, 12207 | Traceability chain, verification process, quality model |
| SpaceX | Responsible-engineer model | SIL stratification, HITL in CI, rapid iteration |
| OpenAI | Eval-driven development | EDDOps (Phase K), property-based + adversarial suites |
| Anthropic | Constitutional AI, defense-in-depth | Executable predicates (not documentation), 5-layer safety |
| Failure Research | Multi-agent failure analysis | FMEA/FTA, 41–87% failure rates without structural safeguards |
| Fitness Functions | Architecture enforcement | CI gates, continuous compliance, decorator registry |

These six streams plus the monograph converged into the **Design Methodology v1.0** — the synthesis document that established all 14 meta-procedure steps.

### Phase β — Architecture (completed)

A **custom SAD iteration tool** was built for rapid mermaid diagram generation with structural validation. This tool produced the **SAD v0.1.0.5** (System Architecture Document) — a mermaid flowchart defining 48 components across 6 layers (VPC/Cloud L0, Kernel L1, Core L2, Engine L3, Observability L4, Console L5) with data stores, sandbox, and egress.

The SAD was then projected into the **RTD v0.1.0.4** (Repository Tree Document) — a mermaid tree diagram mapping every SAD component to a file path. The RTD plus SAD together define the structural contract that all code must conform to.

### Phase γ — Specifications (completed)

Seven specification documents were derived from the SAD, monograph, and research:

| Document | Derived From | Content |
|----------|-------------|---------|
| **ICD v0.1** | SAD (49 boundary-crossing edges → 49 contracts) | Schema, error codes, latency budgets, backpressure, tenant isolation, redaction per interface |
| **Component Behavior Specs** | SAD (SIL-3 nodes) + Monograph (state machines) + Anthropic (defense-in-depth) | Formal state machines for Kernel, Sandbox, Egress |
| **Goal Hierarchy Formal Spec** | Monograph (Ch 6–9) | 7-level hierarchy, L0–L6 predicates, 3 theorems, 4 APIs |
| **SIL Classification Matrix** | SAD (48 components) + SpaceX (stratification) + Failure Research (consequence analysis) | SIL-1/2/3 per component, verification requirements |
| **Dev Environment Spec** | SAD + RTD + ISO (process) + OpenAI (CI) | Toolchain, 10-stage CI, branch strategy, ADR template |
| **Monograph Glossary Extract** | Monograph (289 pp) + SAD (implementation constructs) | 104 symbols, bidirectional theory↔impl mapping |
| **Design Methodology** | All 6 research agents | 14-step meta procedure, worked examples |

The **Task Manifest** was then derived from the README's meta procedure applied to all 86 roadmap steps, producing 583 tasks. A validation pass against ICD, Behavior Specs, and Goal Hierarchy added 38 tasks and refined 47 acceptance criteria.

### Phase δ — Process & Governance (completed)

Three process documents govern execution:

| Document | Derived From | Role |
|----------|-------------|------|
| **Development Procedure Graph** | Task Manifest + all γ specs + Monograph Glossary | Top-level execution loop (P0–P11) consumed by every dev cycle |
| **Test Governance Spec** | END_TO_END_AUDIT_CHECKLIST + SIL Matrix + Procedure Graph | 62-control library, per-task test derivation, maturity gates |
| **README** (Meta Procedure + Task Derivation Protocol) | Monograph + Design Methodology + SAD + all research | Entry point; contains 14-step MP, TDP, Designer's Diary |

### Phase ε — Execution (current: Slice 1 in progress)

Phase ε execution has begun. The tooling foundation (Tasks 1.5-1.8) is complete, producing:

| Module | Task | Role |
|--------|------|------|
| `sad_parser.py` | 1.5 | Parses mermaid SAD into structured AST |
| `schema.py` | 1.6 | Pydantic models for architecture.yaml schema |
| `extract.py` | 1.7 | Full pipeline: SAD mermaid -> architecture.yaml |
| `manifest_parser.py` | 1.8 | Parses Task Manifest markdown into structured Manifest |
| `tracker.py` | (infra) | Merges Manifest + status.yaml, generates Gantt + PROGRESS.md |
| `dependencies.py` | (infra) | Builds task dependency DAG, MP-based duration estimation |
| `gantt_validator.py` | (infra) | Validates mermaid Gantt charts for rendering correctness |
| `registry.py` | 2.6, 2.7, 2.8 | Thread-safe singleton loader + component/boundary/ICD lookups + hot-reload |
| `decorators.py` | 3.6 | Core architectural decorators: @kernel_boundary, @tenant_scoped, @lane_dispatch, @mcp_tool, @eval_gated |
| `cli.py` | (infra) | Command-line entry point for arch-tool operations |

The tracker pipeline now includes a mandatory rendering validation gate: generated Gantt charts are validated for undefined alias references, circular dependencies, unicode issues, and label truncation before being written to disk. This prevents silent rendering failures in mermaid.js viewers.

945 unit tests across 16 test modules verify the complete extraction, tracking, registry, decorator, kernel exception schema, AST scanner, ICD cross-validation, and contract fixture pipeline. The test harness covers SAD parsing, schema validation, architecture extraction, manifest parsing, dependency graph construction, Gantt generation, Gantt rendering validation, registry singleton lifecycle, component/boundary/ICD lookups, hot-reload with validation, core architectural decorators (property-based), kernel exceptions (SIL-3 state machines), schema registry validation, K1 pipeline orchestration, ICD-aware wrong-decorator detection, and contract fixture generation with Hypothesis strategies for all 49 ICDs.

Remaining Slice 1 critical path: `3.7 -> 3a.8 -> 3a.10 -> 3a.12` (ICD enforcement, pipeline validation, eval gate, spiral gate).

---

## 3  Full Artifact Inventory

| # | Artifact | Path | Phase | Size | Derived From |
|---|----------|------|-------|------|-------------|
| 1 | Monograph v2.0 | `(external PDF, 289 pp)` | α | 289 pp | Literature review (62 sources) |
| 2 | Design Methodology v1.0 | `docs/Design_Methodology_v1.0.docx` | α | 22 KB | ISO + SpaceX + OpenAI + Anthropic + Failure + Fitness research |
| 3 | SAD v0.1.0.5 | `docs/architecture/SAD_0.1.0.5.mermaid` | β | 11 KB | Monograph + custom SAD iteration tool |
| 4 | RTD v0.1.0.4 | `docs/architecture/RTD_0.1.0.4.mermaid` | β | 10 KB | SAD |
| 5 | repo-tree.md | `docs/architecture/repo-tree.md` | β | 32 KB | SAD + RTD |
| 6 | ICD v0.1 | `docs/ICD_v0.1.md` | γ | 99 KB | SAD (40+ boundary arrows) |
| 7 | Component Behavior Specs | `docs/Component_Behavior_Specs_SIL3.md` | γ | 88 KB | SAD (SIL-3 nodes) + Monograph + Anthropic |
| 8 | Goal Hierarchy Formal Spec | `docs/Goal_Hierarchy_Formal_Spec.md` | γ | 56 KB | Monograph (Ch 6–9) |
| 9 | SIL Classification Matrix | `docs/SIL_Classification_Matrix.md` | γ | 65 KB | SAD + SpaceX + Failure Research |
| 10 | Dev Environment Spec | `docs/Dev_Environment_Spec.md` | γ | 39 KB | SAD + RTD + ISO + OpenAI |
| 11 | Monograph Glossary Extract | `docs/Monograph_Glossary_Extract.md` | γ | 27 KB | Monograph (full 289 pp scan) |
| 12 | README.md | `README.md` | δ | 30 KB | Monograph + DM + SAD + all research |
| 13 | Task Manifest v2 | `docs/Task_Manifest.md` | δ | 98 KB | README (MP + TDP) + all γ specs |
| 14 | Development Procedure Graph | `docs/Development_Procedure_Graph.md` | δ | 32 KB | Task Manifest + all γ specs + Glossary |
| 15 | Test Governance Spec | `docs/Test_Governance_Spec.md` | δ | 25 KB | Audit Checklist + SIL Matrix + DPG |
| 16 | Artifact Genealogy | `docs/architecture/Artifact_Genealogy.md` | δ | (this file) | All of the above |
| 17 | SAD Parser | `holly/arch/sad_parser.py` | ε | 8 KB | SAD + DPG (Task 1.5) |
| 18 | Architecture Schema | `holly/arch/schema.py` | ε | 6 KB | SAD + SAD Parser (Task 1.6) |
| 19 | Extraction Pipeline | `holly/arch/extract.py` | ε | 7 KB | Schema + SAD Parser (Task 1.7) |
| 20 | Manifest Parser | `holly/arch/manifest_parser.py` | ε | 9 KB | Task Manifest + DPG (Task 1.8) |
| 21 | Status Tracker | `holly/arch/tracker.py` | ε | 14 KB | Manifest Parser + status.yaml + DPG |
| 22 | Dependency Graph | `holly/arch/dependencies.py` | ε | 7 KB | Manifest Parser + Task Manifest |
| 23 | Gantt Validator | `holly/arch/gantt_validator.py` | ε | 8 KB | Tracker (rendering correctness) |
| 24 | CLI Module | `holly/arch/cli.py` | ε | 3 KB | Tracker + Extraction Pipeline |
| 25 | status.yaml | `docs/status.yaml` | ε | 4 KB | Task Manifest (task completion state) |
| 26 | GANTT.mermaid | `docs/architecture/GANTT.mermaid` | ε | 18 KB | Tracker + Dep Graph + status.yaml |
| 27 | GANTT_critical.mermaid | `docs/architecture/GANTT_critical.mermaid` | ε | 7 KB | Tracker + Dep Graph + status.yaml |
| 28 | PROGRESS.md | `docs/architecture/PROGRESS.md` | ε | 25 KB | Tracker + Dep Graph + status.yaml |
| 29 | Architecture Registry | `holly/arch/registry.py` | ε | 9 KB | Schema + Extract (Tasks 2.6, 2.7, 2.8) |
| 30 | Core Decorators | `holly/arch/decorators.py` | ε | 12 KB | Registry API (Task 3.6) |
| 31 | AST Scanner | `holly/arch/scanner.py` | ε | 12 KB | Decorators + Registry + Schema (Task 7.1) |
| 32 | Test Suite (2195 tests) | `tests/unit/test_*.py`, `tests/integration/test_*.py` (43 modules) | ε | 96 KB | All ε modules + TGS |
| — | END_TO_END_AUDIT_CHECKLIST | `(external, user desktop)` | α | 12 KB | Audit process research (Allen) |
| — | **Total in-repo documentation + code** | | | **~750 KB** | |

---

## 4  Derivation Rules

These rules govern how new artifacts enter the genealogy:

1. **No orphan artifacts.** Every new file in the repo must have at least one derivation edge back to an existing artifact. If it doesn't, it's either undocumented (fix the genealogy) or unjustified (remove it).

2. **Phase ordering is strict.** α → β → γ → δ → ε. An artifact in phase γ cannot be derived solely from phase ε outputs — that would be circular. Feedback loops (e.g., TGS ↔ DPG) are permitted within the same phase.

3. **The monograph is root.** Every derivation chain, if followed far enough, terminates at either the monograph, one of the six research streams, or the audit checklist. These are the axioms of the system.

4. **Architecture documents are structural.** SAD and RTD define the physical structure. All specifications (γ) must be consistent with SAD. If a specification implies a component not in the SAD, either update the SAD first or the specification is invalid.

5. **The Development Procedure Graph is the only execution entry point.** No code is written except through the P0–P11 cycle. The DPG consumes all other documents; no other document directly produces code.

---

## 5  How This Was Actually Built (Chronological)

```
2026-02-10  Monograph v2.0 finalized (289 pp)
2026-02-17  06:00  Six research agents launched (ISO, SpaceX, OpenAI, Anthropic, Failure, Fitness)
2026-02-17  08:00  Research synthesis → Design Methodology v1.0
2026-02-17  09:00  Custom SAD iteration tool built
2026-02-17  10:00  SAD v0.1.0.2 generated (6 iterations)
2026-02-17  10:30  RTD v0.1.0.2 projected from SAD
2026-02-17  11:00  README.md written (Meta Procedure, Task Derivation Protocol)
2026-02-17  12:00  Three parallel spec agents launched:
                     Agent 1: ICD v0.1 (49 interfaces from SAD arrows)
                     Agent 2: Component Behavior Specs (SIL-3 state machines)
                     Agent 3: Goal Hierarchy Formal Spec (from monograph Ch 6-9)
2026-02-17  14:00  Task Manifest v1 generated (545 tasks from MP × 86 steps)
2026-02-17  15:00  Validation agent: Task Manifest vs ICD + Behavior Specs + Goal Hierarchy
                     → +38 tasks, +47 refined acceptance criteria → Task Manifest v2 (583 tasks)
2026-02-17  16:00  Designer's Diary Entries #1 and #2 written
2026-02-17  17:00  SIL Classification Matrix generated (51 components)
2026-02-17  18:00  Dev Environment Spec generated
2026-02-17  19:00  Monograph Glossary Extract — full 289-page scan begun
2026-02-17  21:00  Monograph Glossary Extract completed (60+ symbols mapped)
2026-02-17  22:00  Development Procedure Graph v1.0 written (P0-P11), later bumped to v1.1
2026-02-17  23:00  END_TO_END_AUDIT_CHECKLIST analyzed
                   Test Governance Spec v1.0 written (62 controls)
                   Development Procedure Graph enriched with test governance hooks
                   README updated with procedure graph prominence
2026-02-17  23:30  Artifact Genealogy graph generated (this document)
                   ──── Phase δ complete. Ready for Phase ε (Slice 1). ────
2026-02-18  Tasks 1.5-1.8 completed:
                     sad_parser.py — mermaid SAD to AST
                     schema.py — architecture.yaml Pydantic models
                     extract.py — full SAD extraction pipeline
                     manifest_parser.py — Task Manifest markdown parser
                     tracker.py — Gantt + PROGRESS.md generation
                     status.yaml initialized (4 tasks done)
                     12 unit tests (parser, schema, extract, tracker)
2026-02-18  Dependency graph module (dependencies.py):
                     DAG from 3 sources (critical path, step-internal, inter-slice gates)
                     MP-based duration estimation with SIL multipliers
                     Gantt `after` syntax integration
                     18 dependency tests
2026-02-18  Gantt rendering validator (gantt_validator.py):
                     Alias uniqueness, reference integrity, cycle detection
                     Unicode/truncation warnings
                     Integrated into tracker pipeline (raise on error)
                     16 validator tests
                     98 total tests across 8 test modules
2026-02-18  Architecture registry singleton (registry.py, Task 2.6):
                     Thread-safe lazy init, Pydantic validation gate
                     architecture.yaml generated from SAD (48 components)
                     18 registry tests (singleton, threads, validation)
                     116 total tests across 8 test modules
2026-02-18  Component/boundary/ICD lookups (registry.py, Task 2.7):
                     get_component(), get_boundary(), get_icd()
                     ComponentNotFoundError for unknown keys
                     24 lookup tests (property-based, exhaustive real YAML)
                     140 total tests across 9 test modules
2026-02-18  Hot-reload with validation (registry.py, Task 2.8):
                     reload() method with atomic document swap
                     Generation counter for staleness detection
                     Failed reload retains previous state
                     18 hot-reload tests (lifecycle, thread-safety, failure retention)
                     195 total tests across 11 test modules
2026-02-18  Core decorators (decorators.py, Task 3.6):
                     @kernel_boundary, @tenant_scoped, @lane_dispatch,
                     @mcp_tool, @eval_gated with registry validation
                     Property-based tests via hypothesis
                     37 decorator tests (metadata stamping, registry validation, cross-decorator)
                     195 total tests across 11 test modules
2026-02-18  Kernel exceptions, schema registry, and K1 orchestration (Task 3.7):
                     holly/kernel/exceptions.py — SIL-3 exception hierarchy
                     holly/kernel/schema_registry.py — jsonschema>=4.20 validation registry
                     holly/kernel/k1.py — K1 orchestration layer
                     tests/unit/test_k1.py — 37 new tests covering exceptions, schema validation, K1 pipeline
                     302 total tests across 15 test modules
                     External dependency added: jsonschema>=4.20
2026-02-18  Artifact Genealogy updated with Phase ε Task 3.7 completion
2026-02-18  Task 3a.10: K8 eval gate
                     holly/kernel/k8.py — K8 eval gate implementation
                     holly/kernel/predicate_registry.py — thread-safe predicate store
                     tests/unit/test_k8_eval_gate.py — 26 new tests
2026-02-18  Task 3a.12: Spiral gate report
                     holly/arch/gate_report.py — gate evaluation + markdown report
                     tests/unit/test_gate_report.py — 17 new tests
                     docs/architecture/GATE_REPORT_S1.md — generated gate report
                     319 total tests across 16 test modules
                     Slice 1 critical path complete (12/12) — Slice 2 unlocked
2026-02-18  Task 5.8: ICD Schema Registry (Slice 2 begins)
                     holly/kernel/icd_schema_registry.py — Pydantic model resolution with TTL cache
                     tests/unit/test_icd_schema_registry.py — 32 new tests
                     351 total tests across 17 test modules
2026-02-18  Task 5.5: 49 ICD Pydantic models
                     holly/kernel/icd_models.py — all 49 ICD boundary models with enums
                     tests/unit/test_icd_models.py — 120 new tests
                     471 total tests across 18 test modules
2026-02-18  Task 5.6: Register ICDs in architecture.yaml
                     docs/architecture.yaml — 49 ICD entries with component mapping, protocol, SIL
                     holly/arch/schema.py — ICDEntry model
                     holly/arch/registry.py — ICD lookup methods
                     tests/unit/test_icd_registration.py — 165 new tests
                     636 total tests across 19 test modules
2026-02-18  Task 7.1: AST scanner with per-module rules
                     holly/arch/scanner.py — layer→decorator mapping, component overrides
                     tests/unit/test_scanner.py — 31 new tests (property-based)
                     667 total tests across 20 test modules
2026-02-18  Task 7.2: ICD-aware wrong-decorator detection
                     holly/arch/scanner.py — ICD_MISMATCH findings, scan_full() pipeline
                     tests/integration/test_scanner_icd.py — 32 new tests (ICD cross-validation)
                     699 total tests across 21 test modules
2026-02-18  Task 8.3: Contract fixture generator
                     holly/kernel/contract_fixtures.py — valid/invalid/Hypothesis for all 49 ICDs
                     tests/unit/test_contract_fixtures.py — 597 new tests (property-based)
                     1296 total tests across 22 test modules
2026-02-18  Task 9.2: Architecture fitness functions
                     holly/arch/fitness.py — layer violations, coupling metrics, dependency depth
                     tests/integration/test_fitness.py — 67 new tests (synthetic + live codebase)
                     1363 total tests across 23 test modules
2026-02-18  Task 10.2: RTM generator
                     holly/arch/rtm.py — decorator discovery, test discovery, RTM correlation, CSV export
                     tests/integration/test_rtm.py — 30 new tests (synthetic + live codebase)
                     1446 total tests across 26 test modules
2026-02-18  Tasks 11.1, 11.3: CI gate + Phase A gate report
                     holly/arch/ci_gate.py — 4-stage pipeline, fail-fast, blocking/warning/info
                     holly/arch/gate_report.py — 10-item Phase A gate checklist, all PASS
                     Code review fixes: F-031–F-035 (gate_pass enforcement, drift isolation, C010
                     timeout 180s, gantt --stdout dep_graph, jsonschema>=4.0 in pyproject.toml)
                     1454 total tests across 27 test modules (Slice 2: 10/10 complete)
2026-02-18  Code review F-036–F-039
                     holly/kernel/exceptions.py — KernelInvariantError (F-036)
                     holly/kernel/k1.py — assert→KernelInvariantError post-validation guard (F-036)
                     holly/kernel/schema_registry.py — _STRUCTURAL_KEYS frozenset, anyOf/$ref/etc accepted (F-037)
                     holly/arch/cli.py — cmd_gate :: line-count stable test-count (F-038)
                     holly/arch/audit.py — C011 uses sys.executable not hardcoded "python" (F-039)
                     1454 total tests (no new tests; all existing 1454 pass)
2026-02-19  Task 13.1: FMEA kernel invariant desynchronization
                     docs/FMEA_Kernel_Invariants.md — KernelContext + K1–K8, 3 failure modes
                     each, S/O/D/RPN/mitigation, 5 open high-RPN items (Slice 3 begins: 1/19)
                     1454 total tests (document-only task; no new tests)
2026-02-19  Task 14.1: TLA+ spec kernel invariant state machine
                     docs/tla/KernelInvariants.tla — KernelContext state machine (5 states,
                     8 actions, 8 safety invariants, 5 liveness properties under WF fairness)
                     docs/tla/KernelInvariants.cfg — TLC model configuration
                     docs/tla/KernelInvariants_ModelCheck.md — TLC 2.20 report: 14 distinct
                     states, 25 generated, depth 5, 0 violations (Slice 3: 2/19)
                     1454 total tests (formal methods artifact; TLC is the verification tool)
2026-02-19  Task 14.5: Formal state-machine validator
                     holly/kernel/state_machine.py — KernelState/KernelEvent StrEnums (5/8),
                     VALID_TRANSITIONS frozenset (8 pairs), _EVENT_TRANSITION dict, pure guards
                     validate_transition/apply_event/validate_trace/reachable_from, stateful
                     KernelStateMachineValidator; mirrors TLA+ spec from Task 14.1 (Slice 3: 3/19)
                     tests/unit/test_state_machine.py — structure, unit, Hypothesis property-based
                     (determinism, purity, state-space, trace/transition consistency, invariant
                     preservation) — 96 new tests
                     1550 total tests (+96 new)
2026-02-19  Task 15.4: KernelContext async context manager
                     holly/kernel/context.py — KernelContext: async context manager,
                     5-state lifecycle (IDLE/ENTERING/ACTIVE/EXITING/FAULTED) driven by
                     KernelStateMachineValidator; pluggable gate sequence (K1-K8 wired
                     in Tasks 16-18); corr_id auto-gen (UUID4); exit cleanup stub;
                     all paths (happy/gate-fail/cancel/exit-fail) return to IDLE
                     satisfying TLA+ liveness EventuallyIdle (Slice 3: 4/19)
                     tests/unit/test_kernel_context.py — lifecycle, gates, re-entrancy,
                     exception identity, Hypothesis property-based — 41 new tests
                     1591 total tests (+41 new)
2026-02-19  Task 16.3: K1 schema validation gate — KernelContext integration
                     holly/kernel/k1.py — k1_gate factory added: Gate-protocol async
                     adapter wrapping k1_validate; all failure paths (ValidationError,
                     SchemaNotFoundError, PayloadTooLargeError) advance ENTERING->FAULTED->IDLE
                     satisfying TLA+ liveness EventuallyIdle; composes with other gates
                     in KernelContext(gates=[k1_gate(payload, schema_id)]) (Slice 3: 5/19)
                     holly/kernel/__init__.py — exports k1_gate
                     tests/unit/test_k1_gate.py — structure, happy-path, gate-fail,
                     schema-not-found, too-large, ordering, liveness, Hypothesis
                     property-based (zero FP/FN) — 29 new tests
                     1620 total tests (+29 new)
2026-02-19  Task 16.4: K2 RBAC permission gate — KernelContext integration
                     holly/kernel/exceptions.py — JWTError, ExpiredTokenError,
                     RevokedTokenError, PermissionDeniedError, RoleNotFoundError,
                     RevocationCacheError added to exception hierarchy
                     holly/kernel/permission_registry.py — NEW: thread-safe class-level
                     PermissionRegistry singleton; register_role / get_permissions /
                     has_role / registered_roles / clear; RoleNotFoundError on miss
                     holly/kernel/k2.py — NEW: RevocationCache Protocol +
                     NullRevocationCache + FailRevocationCache; k2_check_permissions
                     (pre-decoded claims dict; exp/jti/RBAC checks); k2_gate factory:
                     Gate-protocol async adapter; all failure paths advance
                     ENTERING->FAULTED->IDLE (TLA+ EventuallyIdle); composes with
                     k1_gate; fail-safe revocation deny (Slice 3: 6/19)
                     holly/kernel/__init__.py — exports k2_check_permissions, k2_gate,
                     PermissionRegistry + K2 exception classes
                     tests/unit/test_k2.py — NEW: structure, happy-path, permission-
                     denied, missing-JWT, malformed-claims, expiry, revocation, role-
                     not-found, ordering, PermissionRegistry unit, Hypothesis property-
                     based (authorized/unauthorized/expired all IDLE) — 42 new tests
                     1662 total tests (+42 new)
2026-02-19  Task 16.5: K3 resource bounds gate — KernelContext integration
                     holly/kernel/exceptions.py — BoundsExceeded, BudgetNotFoundError,
                     InvalidBudgetError, UsageTrackingError added to exception hierarchy
                     holly/kernel/budget_registry.py — NEW: thread-safe class-level
                     BudgetRegistry singleton; keyed by (tenant_id, resource_type) →
                     int; register / get / has_budget / registered_keys / clear;
                     InvalidBudgetError on negative limit, BudgetNotFoundError on miss
                     holly/kernel/k3.py — NEW: UsageTracker Protocol +
                     InMemoryUsageTracker (thread-safe, reset for test isolation) +
                     FailUsageTracker; k3_check_bounds (7-step: validate requested,
                     resolve budget, validate limit, fetch usage, validate usage, bounds
                     check, increment); k3_gate factory: Gate-protocol async adapter;
                     per-tenant isolation; fail-safe deny on tracker failure (Slice 3: 7/19)
                     holly/kernel/__init__.py — exports k3_check_bounds, k3_gate,
                     BudgetRegistry + K3 exception classes
                     tests/unit/test_k3.py — NEW: structure, happy-path, bounds-exceeded,
                     budget-not-found, invalid-budget, negative-requested, tracker-fail,
                     per-tenant isolation, ordering, InMemoryTracker unit, Hypothesis
                     property-based (within-budget IDLE / over-budget BoundsExceeded) —
                     40 new tests
                     1702 total tests (+40 new)
2026-02-19  Task 16.6: K4 trace injection gate — KernelContext integration
                     holly/kernel/exceptions.py — TenantContextError added to
                     exception hierarchy; raised when JWT claims lack tenant_id
                     holly/kernel/context.py — UPDATED: _tenant_id + _trace_started_at
                     slots added; tenant_id + trace_started_at read-only properties;
                     _set_trace(tenant_id, corr_id, started_at) internal injection
                     method; __repr__ updated to include tenant_id
                     holly/kernel/k4.py — NEW: k4_inject_trace standalone function
                     (validates claims, resolves/validates UUID correlation ID,
                     returns (corr_id, tenant_id) without side effects); k4_gate
                     factory: Gate-protocol async adapter; injects tenant_id +
                     corr_id + trace_started_at into context; UUID format validation
                     via uuid.UUID(); fail-safe: TenantContextError or ValueError →
                     ENTERING→FAULTED→IDLE (Slice 3: 8/19)
                     holly/kernel/__init__.py — exports k4_inject_trace, k4_gate,
                     TenantContextError
                     tests/unit/test_k4.py — NEW: structure (8), happy-path (10),
                     tenant-missing (7), invalid-corr-id (5), immutability (3),
                     ordering K1+K2+K3+K4 compose (2), Hypothesis property-based
                     (valid tenant IDLE / valid UUID IDLE / non-UUID raises) (3) —
                     39 new tests
                     1741 total tests (+39 new)
2026-02-19  Task 16.9: K1-K4 guard condition determinism — INV-4 verification
                     tests/integration/test_k1_k4_guard_determinism.py — NEW:
                     property-based test suite verifying Behavior Spec §1.1 INV-4
                     (guards are pure functions; no side effects on evaluation);
                     TestK1Determinism (6): valid payload idempotent, invalid
                     idempotent, unknown schema, registry not mutated, Hypothesis
                     valid always passes, Hypothesis wrong type always fails;
                     TestK2Determinism (5): authorized idempotent, unauthorized
                     idempotent, None claims, registry not mutated, Hypothesis
                     sub-field variation always passes with correct role;
                     TestK3Determinism (6): within-budget idempotent (fresh
                     tracker), over-budget idempotent, same usage same outcome,
                     registry not mutated, Hypothesis deterministic given state;
                     TestK4Determinism (6): auto corr_id stable, provided corr_id
                     returned, missing tenant raises, invalid UUID raises, no
                     global state mutated, Hypothesis same input same output;
                     TestCrossGuardIsolation (5+3): K1 doesn't pollute K2, K2
                     doesn't pollute K3, K3 doesn't pollute K1, K4 doesn't pollute
                     any registry, all four guards interleaved deterministic —
                     31 new tests (Slice 3: 9/19)
                     1772 total tests (+31 new)
2026-02-19  Task 17.3: K5 idempotency gate — RFC 8785 key generation
                     pyproject.toml — jcs>=0.2 added to production dependencies
                     holly/kernel/exceptions.py — CanonicalizeError added
                     (RFC 8785 canonicalization failure); DuplicateRequestError
                     added (already-seen idempotency key)
                     holly/kernel/k5.py — NEW: IdempotencyStore runtime-
                     checkable Protocol (check_and_mark atomic semantics);
                     InMemoryIdempotencyStore (in-memory, single-process, for
                     testing); k5_generate_key standalone pure function (jcs
                     RFC 8785 canonicalize + SHA-256 + hexdigest, 64 chars);
                     k5_gate factory: Gate-protocol async adapter, checks store
                     then raises DuplicateRequestError on repeat; None payload
                     raises ValueError; non-serializable raises CanonicalizeError;
                     TLA+ liveness: all paths reach IDLE (Slice 3: 10/19)
                     holly/kernel/__init__.py — exports k5_generate_key, k5_gate,
                     IdempotencyStore, InMemoryIdempotencyStore,
                     CanonicalizeError, DuplicateRequestError
                     tests/unit/test_k5.py — NEW: TestStructure (6), TestDeterminism
                     (5), TestFieldOrderIndependence (4), TestUnicodeNormalization (4),
                     TestDistinctPayloads (7), TestNonJsonRejection (5),
                     TestIdempotencyStore (5), TestK5Gate (6), TestCompose (2),
                     TestPropertyBased (4) — 48 new tests
                     1820 total tests (+48 new)
2026-02-19  Task 17.4: K6 WAL gate — append-only audit log with redaction
                     holly/kernel/exceptions.py — WALWriteError added (backend
                     write failure, context→FAULTED); WALFormatError added
                     (malformed WALEntry, missing required fields); RedactionError
                     added (redaction engine unexpected failure)
                     holly/kernel/k6.py — NEW: WALEntry @dataclass(slots=True)
                     with 24 fields (required: id, tenant_id, correlation_id,
                     timestamp, boundary_crossing, caller_user_id, caller_roles,
                     exit_code, k1_valid, k2_authorized, k3_within_budget;
                     optional K1-K8 gate results; redaction metadata);
                     WALBackend @runtime_checkable Protocol (append(entry) method);
                     InMemoryWALBackend (ordered list, fail-mode for tests);
                     redact() function (5 rules: email→[email hidden],
                     api_key→[secret redacted], credit_card→****-****-****-XXXX,
                     ssn→[pii redacted], phone→[pii redacted]); _detect_pii()
                     (pre-redaction PII detection for contains_pii_before_redaction
                     flag); k6_write_entry() (validate→detect_pii→redact→append);
                     k6_gate() factory (stamps corr_id + tenant_id from context
                     at gate-fire time; Slice 3: 11/19)
                     holly/kernel/__init__.py — exports WALEntry, WALBackend,
                     InMemoryWALBackend, k6_write_entry, k6_gate, redact,
                     WALWriteError, WALFormatError, RedactionError
                     tests/unit/test_k6.py — NEW: TestWALEntryStructure (6),
                     TestWALBackend (5), TestRedactionEmail (4),
                     TestRedactionAPIKey (5), TestRedactionCreditCard (4),
                     TestRedactionPII (4), TestRedactionMultiple (3),
                     TestDetectPII (5), TestK6WriteEntry (8), TestK6Gate (6),
                     TestTimestampOrdering (3), TestPropertyBased (4) — 57 new
                     1877 total tests (+57 new)

2026-02-19  Task 17.7: K5-K6 Invariant Preservation — property-based
            integration tests verifying all six KernelContext invariants
            hold across randomly-generated K5+K6 operation sequences
            Traces to: Behavior Spec §1.1 (INV-1—INV-6), TLA+ spec §14.1
            New files:
                     tests/integration/test_k5_k6_invariants.py — NEW:
                     TestINV1GateRequiresContext (3) — structural gate sig,
                     TestINV2NoReentrancy (6) — success/fail/body-exc/seq,
                     TestINV3ValidStateAlways (4) — valid state every path,
                     TestINV4GuardDeterminism (8) — k5 + redact determinism
                       + property tests (200 examples each),
                     TestINV5ActiveRequiresGatesPass (6) — ACTIVE gate guard
                       + property test (100 examples),
                     TestINV6WALEntryFields (6) — corr_id/tenant_id/timestamp
                       + property test (200 examples),
                     TestMasterInvariantPreservation (3) — 10,000-operation
                       trace test (acceptance criterion satisfied), random
                       sequence property (200 examples), mixed failure seq
                     36 tests total, zero invariant violations
                     1913 total tests (+36 new)

2026-02-19  Task 18.3: K7 HITL gate
                     holly/kernel/k7.py — NEW: ApprovalRequest @dataclass(frozen,
                       slots); HumanDecision @dataclass(frozen, slots);
                       ConfidenceEvaluator/ThresholdConfig/ApprovalChannel
                       @runtime_checkable Protocols; InMemoryApprovalChannel
                       (inject_approve/inject_reject/inject_decision/
                       set_fail_emit/set_timeout_all test helpers);
                       FixedConfidenceEvaluator, FailConfidenceEvaluator,
                       FixedThresholdConfig, MappedThresholdConfig;
                       k7_check_confidence() pure guard (INV-4);
                       k7_gate() factory — EVALUATING→CONFIDENT→PASS |
                       EVALUATING→UNCERTAIN→BLOCKED→{HUMAN_APPROVED→PASS |
                       HUMAN_REJECTED→FAULTED | APPROVAL_TIMEOUT→FAULTED};
                       fail-safe deny on all exception paths
                     holly/kernel/exceptions.py — MODIFIED: +ConfidenceError,
                       +ApprovalTimeout, +OperationRejected, +ApprovalChannelError
                     tests/unit/test_k7.py — NEW: TestK7CheckConfidence (11),
                       TestK7HighConfidencePath (5), TestK7LowConfidenceBlocks (3),
                       TestK7HumanApproval (3), TestK7HumanRejection (3),
                       TestK7ApprovalTimeout (3), TestK7ReviewerRecorded (3),
                       TestK7FailSafeDeny (4), TestK7ThresholdConfiguration (4),
                       TestK7ChannelFailSafe (3), TestK7GateInterfaceAndComposition (3),
                       TestK7FixedConfidenceEvaluator (4), TestK7MappedThresholdConfig (3)
                     52 tests total, all 10 AC covered
                     1965 total tests (+52 new)

2026-02-19  Task 18.4: K8 full gate factory
                     holly/kernel/k8.py — MODIFIED: +CELESTIAL_PREDICATE_IDS
                       tuple[str, ...] (5 entries L0-L4);
                       +k8_gate(*, output, predicate_ids) -> Gate factory;
                       CELESTIAL_PREDICATE_IDS = ("celestial:L0:authorization_boundary",
                       "celestial:L1:system_integrity", "celestial:L2:privacy_boundary",
                       "celestial:L3:failure_recovery", "celestial:L4:agent_autonomy_limit");
                       k8_gate() validates non-empty predicate_ids at factory time;
                       _k8_gate() iterates predicate_ids in strict order, calls k8_evaluate()
                       per predicate — fail-fast on first EvalGateFailure; Gate protocol
                       async adapter; EvalGateFailure/PredicateNotFoundError/EvalError
                       all propagate without suppression (fail-safe paths)
                     tests/unit/test_k8_gate.py — NEW: TestK8GateFactory (5),
                       TestK8AllPredicatesPass (5), TestK8FailFast (7),
                       TestK8OrderEnforcement (2), TestK8FailSafe (4),
                       TestK8ContextIntegration (4), TestK8CelestialPredicateIds (9),
                       TestK8PropertyBased (2)
                     38 tests total, all 9 AC covered
                     2003 total tests (+38 new)

2026-02-19  Task 18.9: K7-K8 Failure Isolation
                     tests/integration/test_k7_k8_isolation.py — NEW:
                       TestK7FailsIndependently (6): K7 failures raise K7-specific
                       exceptions only (ConfidenceError/ApprovalTimeout/
                       OperationRejected/ApprovalChannelError); _AlwaysRejectChannel
                       subclass enables OperationRejected injection without UUID foreknowledge;
                       TestK8FailsIndependently (5): K8 failures raise K8-specific
                       exceptions only (EvalGateFailure/PredicateNotFoundError/EvalError);
                       UUID-suffixed predicate IDs prevent PredicateAlreadyRegisteredError;
                       TestK7FailK8NotCalled (4): _SpyGate.call_count==0 confirms K8 gate
                       never invoked when K7 fails (fail-fast gate chain, no cascade);
                       TestK7PassK8Fail (4): K7-pass+K8-fail raises only K8 exceptions,
                       never K7 exceptions; TestBothGatesPass (3): K7→K8 chain succeeds,
                       context reaches ACTIVE then IDLE; TestExceptionClassIsolation (6):
                       issubclass checks confirm K7/K8 exception classes are mutually
                       exclusive subtrees; all 7 classes derive from KernelError;
                       TestPropertyBased (2): Hypothesis @given sync tests using
                       asyncio.run() (avoids asyncio_mode="auto" async-Hypothesis
                       incompatibility)
                     30 tests total, all 7 AC covered
                     2033 total tests (+30 new)

2026-02-19  Task 20.3: Dissimilar Verification Channel
                     holly/kernel/dissimilar.py — NEW (dissimilar verification channel):
                       VerificationViolation dataclass (entry_id, invariant, detail)
                       VerificationReport dataclass (passed, entries_checked, violations)
                       check_k1..check_k8 — 8 independent per-entry invariant checkers
                         operating solely on WALEntry audit fields, no kernel gate imports
                       check_tenant_isolation — cross-entry: same correlation_id => same tenant_id
                       check_no_duplicate_ids — cross-entry: all WALEntry.id values unique
                       verify_wal_entries(entries, *, strict=True) — main API;
                         strict=True raises DissimilarVerificationError on first violation;
                         strict=False collects all violations into VerificationReport
                     holly/kernel/exceptions.py — MODIFIED:
                       DissimilarVerificationError(KernelError) added with invariant + entry_id slots
                     tests/unit/test_dissimilar_verifier.py — NEW:
                       TestCheckK1 (3): pass, violation, boundary in detail
                       TestCheckK2 (3): pass, violation, boundary in detail
                       TestCheckK3 (5): pass, violation, arithmetic cross-check, budget mismatch
                       TestCheckK4 (4): pass, tenant_id empty, correlation_id empty, tz-naive
                       TestCheckK5 (3): None key passes, blank key violation, present+non-empty passes
                       TestCheckK6 (4): pass, id empty, caller_roles not list, exit_code negative
                       TestCheckK7 (5): pass, confidence OOB, human_approved False+exit0, None approved
                       TestCheckK8 (3): pass, eval_passed False+exit0, eval_passed True passes
                       TestCrossEntryChecks (4): tenant isolation violation, isolation passes,
                         duplicate IDs caught, unique IDs pass
                       TestVerifyWalEntries (7): strict raises, non-strict reports, injected bug
                         zero-false-negatives (K1+K2+K3+K7+K8 all caught), empty list passes,
                         clean batch passes, multiple violations in non-strict mode
                     tests/integration/test_dissimilar_channel.py — NEW:
                       TestCleanGateChainPasses (4): single crossing, multiple crossings,
                         K7 fields populated, K8 field populated
                       TestInjectedBugsCaught (8): K1-K8 bug injection via dataclasses.replace
                         on real WALEntries from live K4+K6 gate execution
                       TestCrossEntryInvariants (2): tenant isolation, duplicate entry IDs
                       TestLegitimateFailurePasses (2): K2 denial exit_code=1, non-strict no-raise
                     57 tests total, all 5 AC covered (AC 1-5 from Task_Manifest.md §20.3)
                     2090 total tests (+57 new)

2026-02-19  Task 20.5: Verify Dissimilar Verifier State Machine
                     holly/kernel/dissimilar_sm.py — NEW (independent SM verifier):
                       _VALID_STATES frozenset[str] — 5 states, hardcoded, no state_machine.py import
                       _VALID_TRANSITIONS frozenset[tuple[str,str]] — 8 pairs matching Behavior Spec §1.1
                       ExecutionTrace dataclass (frozen, slots): entry_id, states: tuple[str, ...]
                       StateViolation dataclass (slots): detail, entry_id, invariant, step
                       StateMachineReport dataclass (slots): passed, traces_checked, violations list
                       TraceCollector class (slots): record(state), to_trace(entry_id), reset()
                       parse_trace(entry_id, states) — construct ExecutionTrace from serialized data
                       check_valid_state_names(trace) — SM_unknown_state invariant
                       check_initial_state(trace) — SM_initial_state invariant
                       check_terminal_state(trace) — SM_terminal_state invariant
                       check_each_transition(trace) — SM_invalid_transition invariant
                       verify_execution_traces(traces, *, strict=True) — main API; strict raises
                         DissimilarVerificationError on first violation; strict=False collects all
                     tests/unit/test_dissimilar_sm.py — NEW:
                       TestCheckValidStateNames (4): all valid pass, one unknown fails, multiple unknown
                       TestCheckInitialState (4): IDLE start passes, ENTERING start fails, empty trace
                       TestCheckTerminalState (4): IDLE end passes, ACTIVE end fails, single-state traces
                       TestCheckEachTransition (8): clean success, clean gate-fail, invalid IDLE->ACTIVE,
                         invalid ENTERING->EXITING, valid ACTIVE->FAULTED, invalid FAULTED->ACTIVE,
                         valid EXITING->FAULTED, self-loop IDLE->IDLE
                       TestParseTrace (2): round-trip fidelity, empty states tuple
                       TestTraceCollector (3): record+to_trace, reset, StrEnum member coercion
                       TestVerifyExecutionTraces (7): strict raises DissimilarVerificationError with
                         entry_id+invariant, non-strict returns StateMachineReport, passed=True for
                         clean traces, empty list passes, multiple traces one buggy, all 4 bug types
                     tests/integration/test_dissimilar_sm_verifier.py — NEW:
                       _TracedKernelContext — KernelContext subclass overriding _run_exit_cleanup
                         to capture transient EXITING state (not observable from __aexit__ caller)
                       _run_and_trace() — produces real ["IDLE","ENTERING","ACTIVE","EXITING","IDLE"]
                       _run_gate_fail_trace() — verifies ctx.state==IDLE post-KernelError, returns
                         canonical ["IDLE","ENTERING","FAULTED","IDLE"] via parse_trace
                       TestCleanTracesPasses (4): single crossing, 3 sequential crossings,
                         gate-failure path, empty trace list
                       TestInjectedViolationsCaught (7): SM_initial_state, SM_terminal_state,
                         SM_invalid_transition (IDLE->ACTIVE), SM_invalid_transition (ENTERING->EXITING),
                         SM_unknown_state, non-strict collects multiple violations, all 4 bug categories
                       TestDissimilarityGuarantee (3): state_machine module not imported (regex-anchored),
                         KernelContext not imported at runtime, K1-K8 gate modules not imported
                     47 tests total, all 2 AC covered (AC 1-2 from Task_Manifest.md §20.5)
                     2137 total tests (+47 new)

**Task 21.2** (2026-02-19) — SIL-3 Kernel Verification (K1-K8, Behavior Spec §1.2-1.9)
```
New: tests/integration/test_sil3_kernel_verification.py (58 tests, 8 classes)
Modified: holly/kernel/k6.py — Python 3.10 compat shim for datetime.UTC
Modified: holly/kernel/k7.py — Python 3.10 compat shim for datetime.UTC
Modified: holly/kernel/state_machine.py — Python 3.10 compat shim for StrEnum

Test classes:
  TestK1SIL3Verification (§1.2, 7 tests): AC1 valid pass, AC2 invalid-always-fails
    property (Hypothesis 200 examples), AC3 schema caching, AC4 error details,
    AC6 oversized rejection, AC7 immutability property, valid-name-always-passes
  TestK2SIL3Verification (§1.3, 8 tests): AC1 valid claims, AC2 None→JWTError
    property, AC3 expired token + past-exp property, AC5 permission denied,
    AC7 fail-safe deny on cache error, missing-sub property
  TestK3SIL3Verification (§1.4, 7 tests): AC1 within-budget+increment, AC2 exceed
    budget, AC3 atomicity property (sequential), AC4 tenant isolation, AC6 fail
    tracker, over-budget-always-raises property, bounds-semantics property
  TestK4SIL3Verification (§1.5, 9 tests): AC1 tenant extraction, AC2 corr propagate,
    AC3 fresh UUID4 gen, AC4 provided UUID verbatim + property, AC6 missing tenant
    raises, AC7 tenant-preserved property + UUID4-format property
  TestK5SIL3Verification (§1.6, 5 tests): AC1 determinism property, AC2 field-order
    independence, AC5 different-payloads collision property, AC6 non-serializable,
    AC7 hex64 format property
  TestK6SIL3Verification (§1.7, 5 tests): AC1 one-entry-per-crossing property,
    AC3 redaction applied, AC5 timestamp ordering property, AC6 corr_id linked,
    AC7 WALWriteError on backend failure property
  TestK7SIL3Verification (§1.8, 10 tests): AC1 high-confidence no-emit + property,
    AC2 low-confidence emits request, AC3 human approval passes, AC4 rejection
    raises OperationRejected, AC5 timeout raises, AC7 fail-evaluator raises,
    AC8 per-operation-type thresholds, check_confidence correctness + determinism
  TestK8SIL3Verification (§1.9, 7 tests): AC1 true predicate passes, AC2 false→
    EvalGateFailure, AC5 missing predicate, AC6 determinism property,
    AC7 predicate exception→EvalError, deny-always-raises property,
    allow-always-true property

58 tests total, all AC1-AC8 covered per gate (AC-numbered docstrings)
≥3 Hypothesis property-based tests per K gate, deadline=None
2195 total tests (+58 new)
```

**Task 21.6** (2026-02-19) — Phase B Gate Checklist

```
New: holly/arch/gate_report.py — EXTENDED:
  GATE_ITEMS_PHASE_B: list[tuple[str, str, str, str]] — 18 items (Steps 13-21 critical path)
  evaluate_phase_b_gate(task_statuses, test_count, audit_pass) → GateReport
  render_phase_b_report(report) → str

New: holly/arch/cli.py — EXTENDED:
  cmd_gate_b() — Phase B gate CLI handler
  gate-b subcommand registered in main()

New: tests/unit/test_phase_b_gate.py (68 tests, 7 classes)
  TestEvaluatePhaseBGateAllPass (7 tests): AC1 all done→all_pass, slice_id=3, gate_name
  TestEvaluatePhaseBGateFailure (37 tests): AC2 parametrized per task_id missing→FAIL
  TestTask212AutoCheck (4 tests): AC3 test_count=0 → FAIL, test_count>0 → PASS
  TestRenderPhaseBReport (9 tests): AC4 header/verdict text/gate decision section
  TestVerdictAccounting (3 tests): AC5 passed+failed+waived+skipped==len(items)
  TestGateItemsCoverage (5 tests): AC6 18 entries, check_types valid, 21.2 auto
  TestPhaseBGateProperties (3 Hypothesis property tests): AC verdict valid, all_pass iff
    zero_failed, item_count always == GATE_ITEMS_PHASE_B length; 200 examples each

New: docs/audit/phase_b_gate_report.md — Generated by `python -m holly.arch gate-b`
  18 PASS, 0 FAIL, 0 WAIVED — Phase C (Slice 4) unlocked

68 tests total, all 6 AC covered
2263 total tests (+68 new)
```

---

**Task 22.5** (2026-02-19) — Async Postgres Storage Layer

```
New: holly/storage/postgres.py — CREATED (Slice 4, Step 22)
  TenantCredentials dataclass (frozen, slots) — ICD-045 credential fetch
  ConnectionProto / PoolProto / PoolFactory — Protocol-based abstraction (mockable)
  TenantIsolatedPool — acquire() sets SET LOCAL app.current_tenant=$1 (RLS activation)
  _with_deadlock_retry() — exponential backoff 1ms→2ms→4ms→max 100ms (ICD-032)
  SchemaManager — 11 CREATE TABLE (ICD-032/036/038/039/040/042) + 16 indexes
    _RLS_TABLES: 10 tables with tenant_isolation policy
    kernel_audit_log: RLS-exempt (append-only per ICD-038)
    RLS policy: USING (tenant_id = current_setting('app.current_tenant',TRUE)::uuid)
  GoalRow / AgentRow / AuditRow / CheckpointRow / TaskStateRow / MemoryRow
  GoalsRepo — insert/get/list_by_status/update_status (ICD-032)
  AuditRepo — append() non-fatal, 1s timeout (ICD-038)
  CheckpointsRepo — upsert/get/list_workflow (ICD-039)
  TaskStateRepo — upsert() non-fatal, get() (ICD-040)
  MemoryRepo — insert/list_for_agent (ICD-042)
  PostgresBackend — facade + from_credentials() classmethod (ICD-045)
  Bug fix during test: TaskStateRepo.upsert try/except wraps async with, not inside it

New: tests/integration/test_postgres_rls.py (41 tests, 11 classes + property tests)
  TestTenantIsolatedPoolRLS (5 tests): AC1 RLS context set, exact tenant string, once per acquire
  TestCrossTenantIsolation (2 tests): AC2 two tenants set different RLS values
  TestDeadlockRetry (3 tests): AC3 retries until success, immediate pass, args passthrough
  TestGoalsRepo (4 tests): AC4 insert/get/list/update SQL calls
  TestAuditRepo (3 tests): AC5 non-fatal swallow, 1s timeout
  TestCheckpointsRepo (3 tests): AC6 ON CONFLICT upsert, get, list_workflow
  TestTaskStateRepo (3 tests): AC7 non-fatal upsert, get
  TestMemoryRepo (3 tests): AC8 insert upsert SQL, list_for_agent
  TestSchemaManager (8 tests): AC9 DDL/index/RLS-policy execution, 10 RLS tables
  TestPostgresBackendFactory (4 tests): AC10 DSN injection, all repos present
  TestRLSProperty (3 Hypothesis property tests, 200 examples): AC1 invariants

41 tests total, all 10 AC covered
2304 total tests (+41 new)
```

---

*This document is the map of the map. Every artifact in Holly Grace traces through this graph back to the monograph, the six research streams, or the audit checklist. No artifact exists without provenance.*
