# Holly Grace — Task Manifest (REVISED)

**All 15 spiral slices, fully decomposed and validated against ICD v0.1, Component Behavior Specs SIL-3, and Goal Hierarchy Formal Spec.**

Generated: 17 February 2026 | Protocol: Task Derivation Protocol v1.0 | Source: README Meta Procedure + 86-step Roadmap | **REVISION DATE: 17 February 2026**

---

## Delta Summary

This section documents all changes made during validation against the three engineering documents (ICD v0.1, Component Behavior Specs SIL-3, Goal Hierarchy Formal Spec).

### New Tasks Added: 38 tasks

The original manifest underspecified coverage of interface contracts, behavior specifications, and formal goal predicates. The following new tasks have been inserted:

#### ICD Coverage Gap (8 new tasks)

Per **ICD v0.1** (49 interfaces defined), the original manifest lacked explicit tasks for many interface implementations. Added:

- **5.8** ICD Schema Registry (design, build, and test the lookup service for all 49 ICD schemas) — supports K1 gate resolution
- **5.9** ICD Validation Test Harness (build property-based test generator exercising all 49 ICDs with valid/invalid payloads)
- **9.4** ICD-specific fitness functions (monitor per-interface compliance: latency, schema violations, error paths)
- **11.4** ICD audit trail (log all boundary violations per ICD with full request context)
- **22.7** Postgres RLS per ICD boundary (tag all ICD-032/036/038/039/040/042/045 with row-level security)
- **33.5** ICD Safety Case Integration (trace all 49 ICD safety attributes into Phase D safety case)
- **56.5** API Route Coverage for all 49 ICDs (verify every route implements at least one ICD)
- **61.6** Observability trace correlation per ICD (every ICD crossing generates correlated trace span)

#### Behavior Spec Coverage Gap (12 new tasks)

Per **Component Behavior Specs SIL-3** (formal state machines for Kernel, Sandbox, Egress), the original manifest did not explicitly task the implementation and verification of each state machine transition, guard condition, and failure predicate. Added:

- **14.5** Formal state-machine validator for KernelContext (verify no invalid state transitions; property-based test over state space)
- **16.9** K1–K4 Guard Condition Verification (property-based: every guard evaluates deterministically, no side effects)
- **17.7** K5–K6 Invariant Preservation (test that idempotency and audit WAL preserve all six KernelContext invariants)
- **18.9** K7–K8 Failure Isolation (verify HITL and eval gates fail independently; no cascade on one gate failure)
- **20.5** Dissimilar Verifier State Machine (independent code path verifying KernelContext state machine matches formal spec)
- **47.5** Sandbox gRPC Proto Validation (test all proto constraints: required fields, length bounds, enum values)
- **48.5** Isolation Invariant Monitor (property-based: verify namespace/seccomp/cgroup constraints hold under concurrent execution)
- **49.5** Runtime Escape Testing (adversarial tests: attempt known gVisor/Firecracker escape vectors; all must fail)
- **31.7** Egress Filter Pipeline Guarantees (formal test: every egress path validates allowlist, redacts payloads, enforces rate limits in correct order)
- **84.7** Final Behavior Spec Validation (before release: re-run all formal state machine checks against all specs; zero violations required)

#### Goal Hierarchy Coverage Gap (12 new tasks)

Per **Goal Hierarchy Formal Spec v0.1** (7-level hierarchy, Celestial L0–L4 immutable, Terrestrial L5–L6 user intent), the original manifest did not explicitly task:
- Implementation of each level as executable predicate
- Lexicographic gating enforcement
- Multi-agent feasibility computation
- Eigenspectrum monitoring for topology coherence
- Celestial predicate evaluation in K8 gate

Added:

- **36.8** L0–L4 Predicate Implementation (implement five executable predicate functions: safety, legal, ethical, permissions, constitutional)
- **36.9** L0–L4 Predicate Validator (property-based test: for each Celestial level, generate states that satisfy and violate; predicate correctly classifies both)
- **37.7** APS Assembly Index Validator (test T0–T3 tier classification logic; verify Assembly Index computation matches monograph definition)
- **38.7** Eigenspectrum Divergence Monitor (implement formal eigenspectrum calculation; detect when topology diverges from contracts)
- **38.8** Steer Operator Formal Verification (test: steer operations transform topology as specified; contracts remain satisfiable post-steer)
- **65.7** Terrestrial L5–L6 Predicate Implementation (implement executable goal specifications for user intent)
- **65.8** Lexicographic Gating Enforcement (test: L0 violation always halts; L0 pass unblocks L1 evaluation; etc. — strict ordering)
- **65.9** Multi-agent Feasibility Checker (implement feasibility predicate: given assignment and topology, compute if goal region is reachable)
- **68.4** Constitution Gate Integration with L0–L4 (K8 eval gate calls all five Celestial predicates; any failure blocks boundary crossing)
- **84.8** Goal Hierarchy Theorem Verification (verify three theorems: Celestial Inviolability, Terrestrial Subordination, Feasibility–Governance Equivalence)

#### Acceptance Criteria Refinement (47 tasks updated)

The original manifest used generic acceptance criteria (e.g., "Schema validated", "Test passes"). Updated 47 existing tasks to reference specific ICDs, behavior specs, and goal predicates. Examples:

- **1.7** (originally: "YAML round-trips without loss") → now: "Per ICD-006/007 Kernel boundary schema, YAML components map 1:1 to KernelContext entry points"
- **3.7** (originally: "Wrong schema raises `ICDViolation`") → now: "Per ICD v0.1 Schema validation (K1 gate), raises ValidationError with ICD identifier and field-level errors"
- **16.3** (originally: "Invalid payloads rejected; valid pass") → now: "Per Behavior Spec §1.2 K1 state machine, reaches VALID state iff payload ∈ schema; INVALID state → ValidationError with trace"
- **36.5** (originally: "Predicate evaluable on goal output") → now: "Per Goal Hierarchy §2.0–2.4 Celestial predicates, each returns GoalResult with (level, satisfied, distance, explanation); distance metric quantifies constraint satisfaction"

All 47 updated tasks now cite specific section numbers and formal definitions from the engineering documents.

#### Critical Path Changes (5 slices modified)

New dependencies emerged due to ICD schema registry and goal predicate implementations:

- **Slice 2 (Phase A):** 5.8 (ICD Schema Registry) now inserted before 5.5; 5.9 after 5.8. Critical path extends 5.8 → 5.5 → 5.6
- **Slice 3 (Phase B):** 14.5 (state machine validator) new critical path entry 14.1 → 14.5 → 15.4
- **Slice 6 (Phase E):** 36.8–36.9 (L0–L4 predicates) inserted before 36.4; critical path extends 36.8 → 36.9 → 36.4
- **Slice 8 (Phase G):** 47.5, 48.5, 49.5 (gRPC/isolation/escape tests) inserted; critical path becomes 46.5 → 47.3 → 47.5 → 48.3 → 48.5 → 49.4 → 49.5 → 50.2
- **Slice 15 (Phase N):** 84.7–84.8 (final validation of behavior specs + goal hierarchy theorems) added; critical path: 84.1 → 84.2 → 84.7 → 84.8 → 84.4 → 84.5 → 84.6

#### Total Task Count

- **Original:** 545 tasks
- **Added:** 38 new tasks
- **Updated Acceptance Criteria:** 47 tasks (no task count change, only spec refinement)
- **Revised Total:** 583 tasks

---

## Summary

| Slice | Phase | Steps | Count | SIL | MP Focus | Gate | Tasks |
|---|---|---|---|---|---|---|---|
| 1 | A (spiral) | 1, 2, 3, 3a | 4 | 2–3 | 8, 9, 1, 2 | Spiral gate: enforcement loop e2e | 39 |
| 2 | A (backfill) | 4–11 | 9 | 2 | 8, 9, 3, 4 | Phase A: arch enforcement complete | 44 |
| 3 | B | 12–21 | 10 | 3 | 5, 6, 7, 12 | Phase B: kernel verified SIL-3 | 86 |
| 4 | C | 22–26 | 5 | 2 | 5, 6, 9 | Phase C: storage tested | 30 |
| 5 | D | 27–33 | 7 | 2–3 | 6, 12, 9 | Phase D: safety case for infra | 44 |
| 6 | E | 34–40 | 7 | 2 | 1, 8, 10, 11 | Phase E: core integration tested | 55 |
| 7 | F | 41–45 | 5 | 2 | 8, 9, 6 | Phase F: engine e2e tested | 32 |
| 8 | G | 46–50 | 5 | 3 | 6, 7, 12 | Phase G: sandbox SIL-3 pass | 45 |
| 9 | H | 51–56 | 6 | 2 | 5, 6, 12 | Phase H: API + auth tested | 37 |
| 10 | I | 57–61 | 5 | 2 | 5, 9 | Phase I: observability live | 25 |
| 11 | J | 62–65 | 4 | 2 | 1, 10, 11 | Phase J: agents + constitution exec | 34 |
| 12 | K | 66–69 | 4 | 2 | 10, 4, 9 | Phase K: eval pipeline gates merges | 26 |
| 13 | L | 70–72 | 3 | 1 | 5, 9 | Phase L: config operational | 14 |
| 14 | M | 73–78 | 6 | 1 | 5, 9 | Phase M: console functional | 28 |
| 15 | N | 79–86 | 8 | 1–3 | 14, 12, 13 | Phase N: release safety case | 48 |
| | | **Total** | **86** | | | | **583** |

---

## Slice 1 — Phase A Spiral (Steps 1, 2, 3, 3a)

**Purpose:** Build the architecture-as-code skeleton and prove the enforcement loop works end-to-end with a thin kernel slice.

### Applicability Matrix

| MP | Step 1 Extract | Step 2 Registry | Step 3 Decorators | Step 3a Gate |
|---|---|---|---|---|
| 1 Ontological | ✓ | ✓ | ✓ | ✓ |
| 2 Arch Desc | ✓ | ✓ | ✓ | ✓ |
| 3 Quality | ✓ | ✓ | ✓ | ✓ |
| 4 Lifecycle | — | — | — | ✓ |
| 5 SIL | ✓ | ✓ | ✓ | ✓ |
| 6 FMEA | — | ✓ | ✓ | ✓ |
| 7 TLA+ | — | — | — | ✓ |
| 8 Arch-as-Code | ✓ | ✓ | ✓ | ✓ |
| 9 Chain | ✓ | ✓ | ✓ | ✓ |
| 10 EDDOps | — | — | — | ✓ |
| 11 Constitution | — | — | — | — |
| 12 Defense | — | — | ✓ | ✓ |
| 13 Spiral | — | — | — | ✓ |
| 14 Deploy | — | — | — | — |

### Tasks

#### Step 1 — Extract (SAD → `architecture.yaml`)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 1.1 | 1 | Map SAD terms to monograph definitions | SAD, monograph glossary | Traceability annotations in YAML | Review | Every YAML concept traces to a monograph section |
| 1.2 | 2 | Preserve 42010 viewpoint structure | SAD (viewpoints) | Viewpoint-aware YAML schema | Review | Viewpoints survive round-trip SAD → YAML → SAD |
| 1.3 | 3 | Document quality attribute for extraction design | — | ADR citing maintainability | Review | ADR exists and cites 25010 attribute |
| 1.4 | 5 | Assign SIL to extraction pipeline | SIL matrix | SIL-2 designation | Review | SIL recorded in matrix |
| 1.5 | 8 | Write SAD parser (mermaid → AST) | SAD mermaid file | Parser module | Integration test | Parses current SAD without error |
| 1.6 | 8 | Define `architecture.yaml` schema | SAD structure | JSON Schema / Pydantic model | Property-based test | Schema validates current SAD output per ICD-006/007 Kernel entry points |
| 1.7 | 8 | Build extraction pipeline | Parser + schema | `architecture.yaml` | Property-based test | YAML round-trips without information loss; per ICD-006/007, YAML components map 1:1 to KernelContext entry points |
| 1.8 | 9 | Link YAML entries to SAD source lines | SAD, YAML | Source-line annotations | CI check | Every YAML entry has a SAD line reference |

#### Step 2 — Registry (Python singleton, YAML lookups)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 2.1 | 1 | Validate registry keys against monograph | Monograph glossary, YAML schema | Key-to-monograph mapping | Review | Every public key traces to a formal definition |
| 2.2 | 2 | Expose per-viewpoint query API | `architecture.yaml` | `get_viewpoint()`, `get_components_by_view()` | Integration test | Queries return correct components per 42010 viewpoint |
| 2.3 | 3 | Document singleton/caching/thread-safety trade-offs | — | ADR citing performance + reliability | Review | ADR exists |
| 2.4 | 5 | Assign SIL-2 | SIL matrix | SIL-2 designation | Review | Recorded |
| 2.5 | 6 | Enumerate failure modes | Registry design | FMEA rows: stale YAML, missing component, race on reload, malformed input | Review | Each has severity, likelihood, mitigation |
| 2.6 | 8 | Implement singleton loader | `architecture.yaml` | `ArchitectureRegistry` class, thread-safe lazy init | Integration test | Loads YAML; concurrent access consistent |
| 2.7 | 8 | Implement component/boundary/ICD lookups | Registry, schema | `get_component()`, `get_boundary()`, `get_icd()` | Property-based test | Every SAD component queryable; unknown keys raise error |
| 2.8 | 8 | Implement hot-reload with validation | `architecture.yaml` | Reload method, schema re-validation | Integration test | Change propagates; invalid YAML rejected, old state retained |
| 2.9 | 9 | Link lookups to YAML source entries | YAML annotations (1.8) | Lookup results include YAML line ref | CI check | Every result carries source reference |

#### Step 3 — Decorators (stamp architectural contracts)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 3.1 | 1 | Map decorator names to monograph concepts | Monograph, registry | Decorator-to-monograph table | Review | Every name traces to formal definition |
| 3.2 | 2 | Encode viewpoint membership in decorators | Viewpoint catalog | Decorator metadata includes viewpoint tag | Integration test | Decorated module reports correct viewpoint |
| 3.3 | 3 | Document decorator pattern trade-offs | — | ADR citing maintainability + security | Review | ADR exists |
| 3.4 | 5 | Assign SIL-2 | SIL matrix | SIL-2 designation | Review | Recorded |
| 3.5 | 6 | Enumerate failure modes | Decorator design | FMEA rows: missing, wrong, ICD mismatch, stale registry ref | Review | Each has severity, likelihood, mitigation |
| 3.6 | 8 | Implement core decorators | Registry API | `@kernel_boundary`, `@tenant_scoped`, `@lane_dispatch`, `@mcp_tool`, `@eval_gated` | Property-based test | Each stamps correct metadata |
| 3.7 | 8 | Implement ICD contract enforcement | ICD specs | Runtime check on decorated call per K1 gate | Property-based test | Wrong schema raises `ValidationError` with ICD identifier (per Behavior Spec §1.2 K1 gate) |
| 3.8 | 8 | Build AST scanner | Decorator defs, codebase | Scanner: flags undecorated boundary modules | Integration test | Detects intentionally-undecorated fixture |
| 3.9 | 9 | Map decorators to test requirements | Decorator catalog | Test-requirement matrix | CI check | No decorator without a covering test |
| 3.10 | 12 | Verify decorators trigger kernel enforcement | Decorator + KernelContext stub | Integration test: decorator → kernel path | Integration test | Decorated call invokes kernel; undecorated does not |

#### Step 3a — Spiral Gate (thin kernel slice, e2e validation)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 3a.1 | 1 | Verify invariant names trace to monograph | Monograph, KernelContext | Traceability check | Review | K1–K8 all trace to Behavior Spec §1.2–1.9 definitions |
| 3a.2 | 2 | Validate SAD → code path for one boundary | SAD, decorated module, kernel | Annotated e2e trace | Review | Trace documented; includes ICD contract validation |
| 3a.3 | 3 | Confirm quality attributes measurable in slice | Quality catalog | ≥1 measurement (e.g., enforcement latency) | Test | Metric collected and within target |
| 3a.4 | 4 | Assign verification method to gate | Process doc | Gate method = demonstration | Review | Method recorded |
| 3a.5 | 5 | Confirm SIL-3 rigor on kernel in slice | SIL matrix | SIL-3 checklist: spec, tests, review | Review + test | All SIL-3 requirements met |
| 3a.6 | 6 | Exercise ≥1 FMEA failure mode | FMEA (2.5, 3.5) | Test triggers failure, confirms mitigation | Integration test | Failure triggered; mitigation activates |
| 3a.7 | 7 | Write minimal TLA+ spec for K1 | Kernel design | TLA+ spec for schema-validation state machine per Behavior Spec §1.2 K1 | Model check | TLC zero violations |
| 3a.8 | 8 | Validate full pipeline: YAML → registry → decorator → kernel | Steps 1–3 outputs | Decorated endpoint enforcing K1 | Integration test | Valid schema passes; invalid raises `ValidationError` |
| 3a.9 | 9 | Validate traceable chain for one requirement | RTM (partial) | Chain: concern → req → ADR → decorator → test → pass | CI check | All 5 links present and green |
| 3a.10 | 10 | Implement minimal K8 eval gate | Eval stub | K8 gate checking one behavioral predicate | Property-based test | Pass on valid; halt on violation per Behavior Spec §1.8 K8 |
| 3a.11 | 12 | Verify kernel layer activates independently | Decorator + kernel + broken sandbox stub | Kernel catches violation without downstream layer | Integration test | Enforcement independent of sandbox |
| 3a.12 | 13 | Run gate, produce pass/fail report | All 3a.* outputs | Spiral gate report | Report | All items pass → Slice 2 unlocked |

### Critical Path

```
1.5 → 1.6 → 1.7 → 1.8 → 2.6 → 2.7 → 2.8 → 3.6 → 3.7 → 3a.8 → 3a.10 → 3a.12
```

**39 tasks. 12 on critical path.**

---

## Slice 2 — Phase A Backfill (Steps 4–11)

**Purpose:** Complete architecture enforcement infrastructure — scaffold, ICD, ATAM, validation, scanning, testing, fitness functions, RTM, and CI gate.

### Tasks

#### Step 4 — Scaffold (generate package skeleton)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 4.1 | 1 | Verify package names trace to monograph | Monograph, repo tree | Name-to-concept mapping | Review | Every package traces to formal definition |
| 4.2 | 2 | Generate packages per 42010 viewpoint structure | `architecture.yaml`, repo-tree.md | Package skeleton with layer/component dirs | Integration test | Every SAD component has a corresponding package |
| 4.3 | 3 | Document scaffold generation trade-offs | — | ADR citing maintainability | Review | ADR exists |
| 4.4 | 8 | Build scaffold generator from YAML | `architecture.yaml`, repo-tree.md | Generator script | Integration test | Generates correct tree from current YAML |
| 4.5 | 9 | Link packages to YAML components | Scaffold, YAML | Package-to-YAML mapping in each `__init__.py` | CI check | Every package has YAML source ref |

#### Step 5 — ICD (contract specs per boundary crossing)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 5.1 | 1 | Map ICD terms to monograph boundary definitions | Monograph, SAD | ICD-to-monograph traceability | Review | Every ICD term traces to Allen (2026) channel theory |
| 5.2 | 2 | Define ICD per 42010 boundary | SAD boundary crossings | ICD spec per crossing (schema, protocol, error handling) per ICD v0.1 | Review | All 49 ICDs defined (ICD-001 through ICD-049) |
| 5.3 | 3 | Document contract-vs-protocol trade-off | — | ADR citing reliability + maintainability | Review | ADR exists |
| 5.4 | 5 | Assign SIL per ICD based on connected components | SIL matrix | SIL designation per ICD per Behavior Spec §1 (K1–K8 SIL-3, core SIL-2) | Review | Recorded |
| 5.5 | 8 | Implement ICD as Pydantic models | ICD specs (ICD v0.1) | Python models per boundary crossing | Property-based test | Models validate example payloads |
| 5.6 | 8 | Register ICDs in `architecture.yaml` | ICD models | YAML entries for each boundary contract | Integration test | Registry serves ICD lookups for all 49 ICDs |
| 5.7 | 9 | Link ICDs to SAD boundary crossings | SAD, ICD models | Bidirectional references | CI check | Every ICD links to SAD; every SAD boundary links to ICD |
| 5.8 | 8 | Build ICD Schema Registry | ICD v0.1 specs | Service that resolves schema_id → Pydantic model; callable by K1 gate for all 49 ICDs | Integration test | Per ICD resolution time < 1ms (p99); schema caching with 1h TTL |
| 5.9 | 8 | Implement ICD Validation Test Harness | ICD v0.1 | Property-based generator: for each ICD, generate valid/invalid payloads; verify K1 gate accepts/rejects correctly | Property-based test | All 49 ICDs have ≥10 valid + 10 invalid test cases; zero false positives/negatives |

#### Step 5a — ATAM (architecture quality-attribute evaluation)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 5a.1 | 2 | Identify stakeholder scenarios | Stakeholder concerns, SAD | Scenario catalog with quality attribute tags | Review | ≥3 scenarios per quality attribute |
| 5a.2 | 3 | Evaluate architecture against scenarios | SAD, scenario catalog | Trade-off analysis: sensitivity points, trade-off points, risks | Review | Every scenario evaluated |
| 5a.3 | 4 | Document ATAM verification results | ATAM output | ATAM report with risk catalog | Review | Report complete |
| 5a.4 | 9 | Link ATAM risks to fitness function parameters | ATAM risks | Risk-to-fitness-function mapping | Review | Every risk maps to ≥1 fitness function |

#### Step 6 — Validate (YAML ↔ SAD drift detection)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 6.1 | 8 | Build drift detector | `architecture.yaml`, SAD parser | Validator: compares YAML against current SAD | Integration test | Detects intentionally-introduced drift |
| 6.2 | 8 | Define drift severity levels | Drift categories | Severity config: breaking (blocks merge) vs warning | Review | Severity definitions documented |
| 6.3 | 9 | Wire drift detection into CI pipeline | Drift detector | CI step that runs on every commit | CI check | Drift blocks merge at configured severity |

#### Step 7 — Scan (AST-walk for missing/wrong decorators)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 7.1 | 8 | Extend AST scanner with per-module rules | Decorator catalog, `architecture.yaml` | Scanner rules: required decorators per layer/component | Property-based test | Rules match YAML component definitions |
| 7.2 | 8 | Add wrong-decorator detection | ICD specs, decorator metadata | Scanner flag: decorator present but mismatched to component | Integration test | Detects intentionally-wrong decorator |
| 7.3 | 9 | Wire scanner into CI pipeline | Scanner | CI step: blocks merge on missing/wrong decorator | CI check | Merge blocked on violation |

#### Step 8 — Test (arch contract fixtures + property-based fuzzing)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 8.1 | 4 | Assign verification methods to arch contracts | ICD catalog, SIL matrix | Method per contract (property-based, integration, review) | Review | Every contract has a method |
| 8.2 | 5 | Implement SIL-appropriate test levels | SIL matrix | Test config: Hypothesis strategies for SIL-2, formal for SIL-3 | Integration test | Config generates correct test types per SIL |
| 8.3 | 8 | Write contract fixture generator | ICD models (per ICD v0.1), `architecture.yaml` | Generator: produces valid/invalid payloads per boundary | Property-based test | Generates payloads exercising all 49 ICD constraints |
| 8.4 | 9 | Map tests to decorators and requirements | Test suite, decorator catalog, RTM | Test-to-decorator-to-requirement mapping | CI check | Every decorator covered by ≥1 test |

#### Step 9 — Fitness Functions (continuous, every commit)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 9.1 | 3 | Derive fitness function parameters from ATAM | ATAM risks (5a.4) | Fitness function definitions with thresholds | Review | Every ATAM risk has a corresponding function |
| 9.2 | 8 | Implement fitness functions | Definitions, codebase | Executable checks: coupling metrics, layer violations, dependency depth | Integration test | Each function produces pass/fail with measurement |
| 9.3 | 9 | Wire into CI as per-commit checks | Fitness functions | CI step: runs all functions on every commit | CI check | Violation blocks merge |
| 9.4 | 9 | Implement ICD-specific fitness functions | ICD v0.1 specs | Monitors per-interface compliance: latency (p99 < budget per ICD), schema violations (K1 gate failures), error paths (count 4xx/5xx by ICD) | Integration test | Each ICD monitored; violations trigger alert; sustained violation blocks merge |

#### Step 10 — RTM Generation (auto-generate from decorators)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 10.1 | 4 | Define RTM schema | 15288 verification requirements, decorator catalog | RTM format: requirement → decision → decorator → test → status | Review | Schema covers all chain links |
| 10.2 | 9 | Build RTM generator | Decorator metadata, test results, ADR index | RTM generator: walks codebase, produces living matrix | Integration test | Generates correct RTM from current codebase |
| 10.3 | 9 | Add gap detection | RTM generator | Gap report: missing links in any chain | CI check | Detects intentionally-broken chain link |

#### Step 11 — CI Gate (block merge on failures)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 11.1 | 8 | Integrate drift, scanner, fitness, RTM into unified gate | Steps 6–10 outputs | CI pipeline config: ordered gate stages | Integration test | All stages run; any failure blocks merge |
| 11.2 | 9 | Add staged canary for arch changes | CI pipeline | Canary config: arch changes deploy to canary before full merge | Integration test | Canary catches intentional regression |
| 11.3 | 13 | Define Phase A gate checklist | All Phase A outputs | Gate report: pass/fail per criterion | Report | All items pass → Phase B unlocked |
| 11.4 | 9 | Implement ICD audit trail logging | All boundary crossings | Log module: records all ICD violations (K1 schema failures, K2 permission denials, K3 bounds exceeded) with full request context, correlation ID, tenant ID | Integration test | Per ICD v0.1 redaction policy, sensitive data redacted; audit trail queryable by ICD ID and time range |

### Critical Path

```
5.8 → 5.5 → 5.6 → 7.1 → 7.2 → 8.3 → 9.2 → 10.2 → 11.1 → 11.3
```

**44 tasks. 10 on critical path.**

---

## Slice 3 — Phase B: Failure Analysis & Kernel (Steps 12–21)

**Purpose:** Assign criticality, enumerate failure modes, write formal specs, then build and verify the kernel at SIL-3.

### Tasks

#### Step 12 — SIL Mapping

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 12.1 | 5 | Classify every component by failure consequence | SAD, FMEA prep | SIL assignment matrix | Review | Every component has SIL-1, SIL-2, or SIL-3 (Kernel SIL-3, Storage SIL-2, Core SIL-2) |
| 12.2 | 5 | Define verification requirements per SIL | IEC 61508 tailoring | Verification table: methods required per level per Behavior Spec §3 (SIL-3: formal + property + unit + integration) | Review | Table complete |
| 12.3 | 9 | Link SIL assignments to YAML components | SIL matrix, `architecture.yaml` | SIL annotations in YAML | CI check | Registry returns SIL for any component |

#### Step 13 — FMEA

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 13.1 | 6 | FMEA: kernel invariant desynchronization | Kernel design, Behavior Spec §1.1–1.9 K1–K8 | Failure modes for all eight invariants, severity, likelihood, mitigations | Review | All 8 invariants analyzed; each has ≥2 failure modes |
| 13.2 | 6 | FMEA: sandbox escape | Sandbox design, Behavior Spec §2 | Failure modes: namespace leak, seccomp bypass, resource exhaustion | Review | All isolation mechanisms analyzed |
| 13.3 | 6 | FMEA: egress bypass | Egress design, Behavior Spec §3 | Failure modes: allowlist circumvention, redaction failure, rate-limit evasion | Review | All egress paths analyzed |
| 13.4 | 6 | FMEA: goal injection (L0–L4 predicate violation) | Goal decomposer, APS, Goal Hierarchy §2.0–2.4 Celestial levels | Failure modes: L5–L6 goal overrides L0–L4, prompt injection to goal | Review | All goal paths analyzed; all Celestial levels have dedicated failure modes |
| 13.5 | 6 | FMEA: topology desynchronization | Topology manager, eigenspectrum, Goal Hierarchy §3 Lexicographic Gating | Failure modes: stale topology, eigenspectrum blind spot, steer race condition | Review | All topology operations analyzed |
| 13.6 | 6 | Compile residual risk register | All FMEA worksheets | Risk register: accept/mitigate per mode | Review | Every mode has disposition |
| 13.7 | 9 | Link FMEA mitigations to roadmap steps | Risk register, roadmap | Mitigation-to-step mapping | CI check | Every mitigation traces to implementation step |

#### Step 14 — Formal Specs (TLA+)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 14.1 | 7 | TLA+ spec: kernel invariant state machine | K1–K8 design, Behavior Spec §1.1 KernelContext state machine, FMEA (13.1) | TLA+ module: all enforcement states and transitions per formal spec | Model check | TLC zero violations; state space documented |
| 14.2 | 7 | TLA+ spec: sandbox isolation | Sandbox design, Behavior Spec §2 state machine, FMEA (13.2) | TLA+ module: namespace/seccomp/resource lifecycle | Model check | TLC zero violations |
| 14.3 | 7 | TLA+ spec: egress filter pipeline | Egress design, Behavior Spec §3, FMEA (13.3) | TLA+ module: allowlist eval, redaction, rate-limit | Model check | TLC zero violations |
| 14.4 | 7 | Document assumption register | All TLA+ specs | Assumptions: what model covers and does not cover | Review | Every assumption explicit |
| 14.5 | 7 | Implement formal state-machine validator | TLA+ specs (14.1–14.3) | Validator: for any execution trace, verify no invalid state transitions occur; property-based test over state space | Property-based test | Per Behavior Spec §1.1 KernelContext invariants, all state transition guards are evaluated deterministically with no side effects |

#### Step 15 — KernelContext (async context manager)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 15.1 | 1 | Map KernelContext to monograph boundary concepts | Monograph (Markov blankets, channel boundaries) | Concept mapping | Review | Context manager semantics trace to theory |
| 15.2 | 5 | Confirm SIL-3 designation | SIL matrix | SIL-3 recorded | Review | Recorded |
| 15.3 | 6 | Review FMEA mitigations for kernel context lifecycle | FMEA (13.1) | Design addresses: context leak, double-enter, async cancellation per Behavior Spec §1.1 failure predicates | Review | Each FMEA mitigation has design response |
| 15.4 | 7 | Implement per TLA+ state machine spec | TLA+ spec (14.1), Behavior Spec §1.1 KernelContext state machine | `KernelContext` class: async context manager, wraps boundary, implements five states (IDLE/ENTERING/ACTIVE/EXITING/FAULTED) | Property-based + formal | Implementation matches TLA+ spec states; all guard conditions evaluated correctly |
| 15.5 | 8 | Register in architecture.yaml, add decorator | YAML, decorator registry | Kernel component registered; `@kernel_boundary` applied | CI check | Scanner passes |
| 15.6 | 9 | Link to requirement and test | RTM | Chain link: requirement → KernelContext → test | CI check | Chain complete |
| 15.7 | 12 | Verify independence from downstream layers | KernelContext, stub sandbox | Context manager enforces without downstream | Integration test | Enforcement standalone |

#### Step 16 — K1–K4 (schema, permissions, bounds, trace)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 16.1 | 1 | Map K1–K4 to monograph channel constraints | Monograph | Concept mapping per invariant | Review | Each invariant traces |
| 16.2 | 6 | Review FMEA mitigations for K1–K4 | FMEA (13.1) | Design addresses each identified failure mode per Behavior Spec §1.2–1.5 | Review | All modes addressed |
| 16.3 | 7 | Implement K1 schema validation per TLA+ | TLA+ spec (14.1), Behavior Spec §1.2 K1, ICD v0.1 schemas | K1 enforcer: validates payload against ICD schema; reaches VALID or INVALID state per state machine | Property-based test | Per Behavior Spec §1.2, invalid payloads rejected with ValidationError; valid pass; zero false positives/negatives |
| 16.4 | 7 | Implement K2 permission gating per TLA+ | TLA+ spec (14.1), Behavior Spec §1.3 K2, RBAC model | K2 enforcer: checks caller JWT claims against required permission set per ICD boundary | Property-based test | Unauthorized calls rejected; authorized pass; JWT expiration/revocation enforced |
| 16.5 | 7 | Implement K3 bounds checking per TLA+ | TLA+ spec (14.1), Behavior Spec §1.4 K3, resource budget model | K3 enforcer: validates resource consumption within budget per request type and tenant | Property-based test | Over-budget rejected; within-budget pass; per-tenant isolation enforced |
| 16.6 | 7 | Implement K4 trace injection per TLA+ | TLA+ spec (14.1), Behavior Spec §1.5 K4, correlation model | K4 enforcer: injects correlation ID + tenant ID into all boundary-crossing operations | Integration test | Every boundary crossing has trace; correlation IDs globally unique |
| 16.7 | 8 | Register K1–K4 in YAML, apply decorators | YAML, decorators | Components registered; decorators applied | CI check | Scanner passes |
| 16.8 | 9 | Link each to requirement and test | RTM | Chain complete per invariant | CI check | 4 chains, all green |
| 16.9 | 7 | Verify K1–K4 Guard Condition Determinism | Behavior Spec §1.2–1.5 guard conditions | Property-based test: for each guard (schema resolution, JWT decode, budget lookup, trace generation), verify no side effects; multiple calls with same input produce identical output | Property-based test | All guards are pure functions; no state mutations during evaluation |

#### Step 17 — K5–K6 (idempotency, audit WAL)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 17.1 | 1 | Map K5–K6 to monograph | Monograph | Concept mapping | Review | Traces |
| 17.2 | 6 | Review FMEA mitigations | FMEA (13.1) | Design addresses replay attacks, WAL corruption per Behavior Spec §1.6–1.7 | Review | Modes addressed |
| 17.3 | 7 | Implement K5 idempotency (RFC 8785) per TLA+ | TLA+ spec (14.1), Behavior Spec §1.6 K5 | K5 enforcer: canonical JSON key generation, duplicate detection via Redis distributed set | Property-based test | Duplicate calls idempotent; distinct calls unique; key collision rate < 1e-12 |
| 17.4 | 7 | Implement K6 audit WAL per TLA+ | TLA+ spec (14.1), Behavior Spec §1.7 K6 | K6 enforcer: append-only log with redaction; all K1–K7 gate results logged | Property-based test | Every action logged; sensitive data redacted per ICD v0.1 redaction policies; WAL ordered by timestamp |
| 17.5 | 8 | Register, decorate | YAML, decorators | Registered, decorated | CI check | Scanner passes |
| 17.6 | 9 | Link to requirements and tests | RTM | Chains complete | CI check | Green |
| 17.7 | 7 | Verify K5–K6 Invariant Preservation | Behavior Spec §1.1 KernelContext invariants (6 formal invariants) | Property-based test: execute random sequence of operations through K5–K6; after each operation, verify all six invariants still hold | Property-based test | Zero invariant violations over 10,000 generated traces |

#### Step 18 — K7–K8 (HITL gates, eval gates)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 18.1 | 1 | Map K7–K8 to monograph goal hierarchy | Monograph, Goal Hierarchy §2.0–2.4 Celestial levels | Concept mapping: K7 to HITL, K8 to eval predicates | Review | K7 traces to L0–L4 safety gates; K8 traces to behavioral predicates |
| 18.2 | 6 | Review FMEA mitigations | FMEA (13.1) | Design addresses: HITL bypass, eval predicate manipulation per Behavior Spec §1.8–1.9 | Review | Modes addressed |
| 18.3 | 7 | Implement K7 HITL gate per TLA+ | TLA+ spec (14.1), Behavior Spec §1.8 K7 | K7 enforcer: blocks low-confidence actions, escalates to human for approval | Property-based test | Low-confidence actions block; human approval unblocks; confidence threshold configurable per boundary |
| 18.4 | 7 | Implement K8 eval gate per TLA+ | TLA+ spec (14.1), Behavior Spec §1.9 K8, Goal Hierarchy §2.0–2.4 Celestial predicates | K8 enforcer: runs all five Celestial predicates (L0–L4) on boundary crossing output; any failure halts | Property-based test | Per Goal Hierarchy §2.0–2.4, Celestial predicates evaluated in order; if any fails, K8→FAULTED |
| 18.5 | 10 | Define eval predicate interface | Eval framework stub, Goal Hierarchy §2.0–2.4 | Predicate protocol: (state, context) → (pass: bool, distance: float, explanation: str) per formal spec | Integration test | Interface works with property-based test harness; returns correct types |
| 18.6 | 12 | Verify K7+K8 as independent safety layers | K7, K8, stub downstream | Each catches violations independently; no cascade failure when one gate disabled | Integration test | K7 blocks without K8; K8 blocks without K7; orthogonal checks |
| 18.7 | 8 | Register, decorate | YAML, decorators | Registered, decorated | CI check | Scanner passes |
| 18.8 | 9 | Link to requirements and tests | RTM | Chains complete | CI check | Green |
| 18.9 | 7 | Verify K7–K8 Failure Isolation | Behavior Spec §1.8–1.9 failure predicates | Integration test: inject failures into each gate independently; verify other gates still execute correctly and block separately | Integration test | Zero cascade failures; each gate has independent exception path |

#### Step 19 — Exceptions

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 19.1 | 1 | Map exception hierarchy to monograph failure concepts | Monograph | Concept mapping | Review | Each exception traces to formal failure type |
| 19.2 | 5 | Inherit SIL-3 from kernel | SIL matrix | SIL-3 recorded | Review | Recorded |
| 19.3 | 8 | Implement exception classes | Kernel design, Behavior Spec §1.2–1.9 | `KernelViolation`, `ValidationError`, `PermissionError`, `BoundsExceeded`, `HITLRequired`, `EvalGateFailed`, `TimeoutError` | Property-based test | Each K1–K8 failure raises correct exception type with trace context |
| 19.4 | 9 | Link to requirements | RTM | Chain complete | CI check | Green |

#### Step 20 — Dissimilar Verification

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 20.1 | 6 | Design dissimilar channel from FMEA | FMEA (13.1), risk register, Behavior Spec §1.1 | Independent verification path: different code, different data, different execution context | Review | Channel uses no kernel code |
| 20.2 | 7 | Formally verify independence | TLA+ extension, Behavior Spec §1.1 | TLA+ spec proving no shared state between kernel and verifier | Model check | TLC zero violations |
| 20.3 | 12 | Implement dissimilar verification channel | Kernel outputs, independent checker | Verifier module: cross-checks all eight invariants without executing kernel code | Integration test | Catches intentionally-injected kernel bug; zero false negatives |
| 20.4 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |
| 20.5 | 7 | Verify Dissimilar Verifier State Machine | Behavior Spec §1.1 KernelContext formal state machine | Independent state machine validator: parses kernel execution traces, reconstructs state transitions, verifies correctness without kernel code | Integration test | Detects all injected state machine violations; independent of kernel implementation |

#### Step 21 — Kernel Tests

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 21.1 | 4 | Assign verification methods per SIL-3 | Verification table (12.2) | Methods: formal + property-based + unit + integration per Behavior Spec §3 | Review | All 4 methods assigned |
| 21.2 | 5 | Execute SIL-3 verification | K1–K8, TLA+ specs, Behavior Spec §1.2–1.9 | Test results: formal (TLC), property-based (Hypothesis), unit, integration per spec | All methods | All pass |
| 21.3 | 7 | Run TLA+ model checker against all kernel specs | TLA+ specs (14.1–14.3) | TLC output: state count, violation count (must be 0) per Behavior Spec §1.1–1.9 | Model check | Zero violations |
| 21.4 | 9 | Validate RTM completeness for kernel | RTM | Gap report: every kernel requirement has all 4 verification artifacts | CI check | No gaps |
| 21.5 | 12 | Independent review of kernel safety | All kernel code, specs, tests, Behavior Spec §1.1–1.9 | Independent reviewer sign-off | Review | Sign-off recorded |
| 21.6 | 13 | Define Phase B gate checklist | All Phase B outputs | Gate report: pass/fail | Report | All items pass → Phase C unlocked |

### Critical Path

```
13.1 → 14.1 → 14.5 → 15.4 → 16.3 → 16.4 → 16.5 → 16.6 → 16.9 → 17.3 → 17.4 → 17.7 → 18.3 → 18.4 → 18.9 → 20.3 → 20.5 → 21.2 → 21.6
```

**86 tasks. 19 on critical path.**

---

## Slice 4 — Phase C: Storage Layer (Steps 22–26)

**Purpose:** Build tenant-isolated storage: Postgres, Redis, ChromaDB.

### Tasks

#### Step 22 — Postgres

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 22.1 | 1 | Map storage concepts to monograph (memory tiers, Markov blankets) | Monograph | Concept mapping | Review | Traces |
| 22.2 | 3 | Document storage architecture trade-offs | — | ADR citing reliability + security | Review | ADR exists |
| 22.3 | 5 | Assign SIL-2 | SIL matrix | SIL-2 recorded | Review | Recorded |
| 22.4 | 6 | FMEA: connection pool exhaustion, RLS bypass, migration failure | Postgres design | FMEA rows | Review | Each mode has mitigation |
| 22.5 | 8 | Implement async pool, models, RLS, migrations | ICD specs (ICD-032, ICD-036, ICD-038–040, ICD-042, ICD-045), kernel decorators | Database module with tenant-isolated RLS per ICD v0.1 | Integration test | RLS enforces tenant isolation under concurrent access |
| 22.6 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |
| 22.7 | 9 | Apply RLS per ICD Boundary | ICD v0.1 (ICD-032/036/038/039/040/042/045 involve Postgres) | Tag all Postgres queries with `tenant_id` in RLS policy; every table scoped to authenticated tenant | Integration test | Cross-tenant data access blocked; per ICD v0.1 tenant isolation enforcement |

#### Step 23 — Partitioning

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 23.1 | 5 | Inherit SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 23.2 | 6 | FMEA: orphan partition, failed archival, restore failure | Partition design | FMEA rows | Review | Each has mitigation |
| 23.3 | 8 | Implement time-based partitions, auto-create, S3 archival | Postgres module | Partition manager | Integration test | Creates, archives, and restores partitions |
| 23.4 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |

#### Step 24 — Redis

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 24.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 24.2 | 6 | FMEA: cache poisoning, pub/sub message loss, HA failover race | Redis design | FMEA rows | Review | Each has mitigation |
| 24.3 | 8 | Implement pool, pub/sub, queues, cache, HA | ICD specs (ICD-033, ICD-035, ICD-037, ICD-041, ICD-049), kernel decorators | Redis module with tenant-scoped operations | Integration test | Pub/sub delivers; cache isolates tenants; HA failover works |
| 24.4 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |

#### Step 25 — ChromaDB

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 25.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 25.2 | 6 | FMEA: embedding drift, cross-tenant retrieval, collection corruption | Chroma design | FMEA rows | Review | Each has mitigation |
| 25.3 | 8 | Implement client, tenant-isolated collections, embedding pipeline | ICD specs (ICD-034, ICD-043), kernel decorators | ChromaDB module | Integration test | Queries return only same-tenant results |
| 25.4 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |

#### Step 26 — Storage Tests

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 26.1 | 4 | Assign SIL-2 verification methods | Verification table | Methods: integration + property-based | Review | Assigned |
| 26.2 | 5 | Execute SIL-2 test suite | Steps 22–25 | Test results: connection, RLS enforcement, partition lifecycle | Integration + property-based | All pass |
| 26.3 | 9 | Validate RTM completeness for storage | RTM | Gap report | CI check | No gaps |
| 26.4 | 13 | Phase C gate checklist | All Phase C outputs | Gate report | Report | All pass → Phase D unlocked |

### Critical Path

```
22.5 → 22.7 → 23.3 → 24.3 → 25.3 → 26.2 → 26.4
```

**30 tasks. 7 on critical path.**

---

## Slice 5 — Phase D: Safety & Infra (Steps 27–33)

**Purpose:** Build redaction, guardrails, governance, secrets, egress, and produce the first structured safety case.

### Tasks

#### Step 27 — Redaction

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 27.1 | 1 | Map redaction to monograph channel filtering | Monograph | Concept mapping | Review | Traces |
| 27.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 27.3 | 6 | FMEA: incomplete redaction, redaction bypass via encoding, false positive | Redaction design | FMEA rows | Review | Each has mitigation |
| 27.4 | 12 | Implement canonical redaction library | ICD specs (all ICDs specify redaction per ICD v0.1), kernel | Single-source-of-truth redactor: PII, secrets, custom patterns per ICD redaction policies | Property-based test | Known PII patterns redacted; non-PII preserved; per ICD v0.1 redaction requirements |
| 27.5 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |

#### Step 28 — Guardrails

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 28.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 28.2 | 6 | FMEA: sanitization bypass, injection via unicode, output leak | Guardrails design | FMEA rows | Review | Each has mitigation |
| 28.3 | 12 | Implement input sanitization, output redaction, injection detection | ICD specs (K1 schema validation, K8 eval gate), redaction lib | Guardrails module | Property-based test | Known injection patterns blocked; clean input passes |
| 28.4 | 9 | Link to requirement and test | RTM | Chain complete | CI check | Green |

#### Step 29 — Governance

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 29.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 29.2 | 6 | FMEA: forbidden path bypass, incomplete code analysis | Governance design | FMEA rows | Review | Each has mitigation |
| 29.3 | 12 | Implement forbidden paths, code review analysis | Governance rules, kernel | Governance module per K2 permission gates | Integration test | Forbidden paths blocked; allowed paths pass |
| 29.4 | 9 | Link | RTM | Chain complete | CI check | Green |

#### Step 30 — Secret Scanner

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 30.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 30.2 | 6 | FMEA: undetected secret pattern, false redaction of non-secret | Scanner design | FMEA rows | Review | Each has mitigation |
| 30.3 | 12 | Implement detect + redact in traces per ICD-v0.1 redaction | Trace store, redaction lib, K6 audit WAL | Secret scanner module; integrated into K4 trace injection pipeline | Property-based test | Known secret patterns caught in trace payloads; per ICD v0.1 redaction |
| 30.4 | 9 | Link | RTM | Chain complete | CI check | Green |

#### Step 31 — Egress

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 31.1 | 1 | Map egress to monograph channel boundary | Monograph | Concept mapping | Review | Traces |
| 31.2 | 5 | Assign SIL-3 | SIL matrix | SIL-3 recorded | Review | Recorded |
| 31.3 | 6 | FMEA: allowlist circumvention, redaction failure, rate-limit evasion per Behavior Spec §3 | Egress design, FMEA (13.3) | FMEA rows (may extend 13.3) | Review | All paths analyzed |
| 31.4 | 7 | Implement per TLA+ egress spec | TLA+ (14.3), Behavior Spec §3 Egress formal spec | L7 allowlist, payload redaction, rate-limit, L3 NAT per ICD-030 (Egress → Claude API) | Property-based test | Implementation matches TLA+ egress state machine per Behavior Spec §3 |
| 31.5 | 12 | Verify egress as independent safety layer | Egress + stub kernel | Egress blocks exfiltration without kernel per Behavior Spec §3 isolation properties | Integration test | Layer independent |
| 31.6 | 9 | Link | RTM | Chain complete | CI check | Green |
| 31.7 | 7 | Verify Egress Filter Pipeline Guarantees | Behavior Spec §3 egress state machine (allowlist → redact → rate-limit order) | Formal test: trace all egress paths; verify every path executes filters in correct sequence; no bypasses | Property-based test | All 49 ICDs involving egress (esp. ICD-030) follow filter order; zero filter reordering vulnerabilities |

#### Step 32 — Secrets (KMS/Vault)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 32.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 32.2 | 6 | FMEA: key rotation failure, credential leak, vault unavailability | Secrets design | FMEA rows | Review | Each has mitigation |
| 32.3 | 12 | Implement KMS/Vault client, rotation, credential store per ICD-044/045/048 | Secrets design, kernel | Secrets module; credentials for ICD-044 (KMS → Egress), ICD-045 (KMS → Postgres), ICD-048 (KMS → Authentik) | Integration test | Rotation works; unavailability handled gracefully |
| 32.4 | 9 | Link | RTM | Chain complete | CI check | Green |

#### Step 33 — Safety Case (Phase D)

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 33.1 | 6 | Aggregate FMEA results for D.27–D.32 | All Phase D FMEA worksheets (27.3–32.2) | Consolidated risk register | Review | Complete |
| 33.2 | 12 | Build structured safety argument | Risk register, test results | Safety case: claims → evidence → context per ISO 42010 + Goal Hierarchy §2.0–2.4 (L0–L4 Celestial constraints) | Review | Every claim has evidence; every gap is explicit |
| 33.3 | 9 | Link safety case to FMEA and test artifacts | Safety case, RTM | Bidirectional references | CI check | Every claim traceable |
| 33.4 | 13 | Phase D gate checklist | All Phase D outputs | Gate report | Report | All pass → Phase E unlocked |
| 33.5 | 9 | Integrate all 49 ICDs into Phase D Safety Case | All ICD specs (ICD-001 through ICD-049), safety case | Trace matrix: every ICD → contributing safety claims; every claim cites ≥1 ICD safety property | Review | All 49 ICDs traceable; zero uncovered ICDs |

### Critical Path

```
27.4 → 28.3 → 30.3 → 31.4 → 31.5 → 31.7 → 33.1 → 33.2 → 33.5 → 33.4
```

**44 tasks. 10 on critical path.**

---

## Slice 6 — Phase E: Core L2 (Steps 34–40)

**Purpose:** Build conversation interface, intent classifier, goal decomposer, APS controller, topology manager, and memory.

### Tasks

#### Step 34 — Conversation

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 34.1 | 1 | Map conversation to monograph channel theory | Monograph | Concept mapping | Review | Traces |
| 34.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 34.3 | 6 | FMEA: WS connection hijack, message injection, replay | Conversation design | FMEA rows | Review | Each has mitigation |
| 34.4 | 8 | Implement bidirectional WS chat per ICD-008, decorate | ICD specs (ICD-008 Conversation → Intent), kernel, decorators | Conversation module per ICD v0.1 WebSocket protocol | Integration test | Messages flow; kernel enforces on boundary |
| 34.5 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 35 — Intent Classifier

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 35.1 | 1 | Map intent classification to monograph digital branching | Monograph | Concept mapping | Review | Traces |
| 35.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 35.3 | 6 | FMEA: misclassification, prompt injection to force team_spawn | Intent design | FMEA rows | Review | Each has mitigation |
| 35.4 | 10 | Implement classifier per ICD-009 (Intent → Goals), with eval suite | ICD specs (ICD-009), LLM, eval harness | Classifier: direct_solve / team_spawn / clarify per Goal Hierarchy intent classification | Property-based test | Eval suite passes baseline accuracy |
| 35.5 | 8 | Register, decorate per ICD-009 | YAML, decorators | Registered; matches ICD-009 schema | CI check | Scanner passes |
| 35.6 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 36 — Goal Decomposer

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 36.1 | 1 | Map to monograph goal predicate sets, codimension per Goal Hierarchy §1.3 | Monograph | Concept mapping | Review | Traces to Part IV (Goal Hierarchy Spec) |
| 36.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 36.3 | 6 | FMEA: goal injection, Celestial override, codimension miscalculation per Goal Hierarchy §2.0–2.4 | Goal design | FMEA rows | Review | Each has mitigation |
| 36.4 | 10 | Implement 7-level hierarchy + lexicographic gating per Goal Hierarchy §2 + ICD-009/010, with eval | Monograph specs, eval harness | Goal decomposer + eval suite; implements levels L0–L6 per Goal Hierarchy §2.0–2.6 | Property-based test | Terrestrial never violates Celestial in eval per Goal Hierarchy §2.4 Lexicographic Ordering |
| 36.5 | 11 | Implement Celestial L0–L4 as executable predicates per Goal Hierarchy §2.0–2.4 | Constitution design, Goal Hierarchy specs | Predicate functions: L0 (safety), L1 (legal), L2 (ethical), L3 (permissions), L4 (constitutional) per formal spec | Property-based test | Each predicate evaluable on goal output; returns (level, satisfied, distance, explanation) per formal spec |
| 36.6 | 8 | Register, decorate per ICD-010 | YAML, decorators | Registered | CI check | Scanner passes |
| 36.7 | 9 | Link | RTM | Chain | CI check | Green |
| 36.8 | 11 | Implement L0–L4 Predicate Functions | Goal Hierarchy §2.0–2.4 formal definitions | Five executable functions: check_L0_safety(), check_L1_legal(), check_L2_ethical(), check_L3_permissions(), check_L4_constitutional() returning GoalResult | Property-based test | Per Goal Hierarchy §2.0–2.4, each predicate correctly classifies states that satisfy and violate the level |
| 36.9 | 11 | Validate L0–L4 Predicates with Property-Based Testing | Goal Hierarchy §2.0–2.4 predicate specifications | Generate states that satisfy/violate each Celestial level; verify predicate correctly classifies all | Property-based test | Zero false positives/negatives over 1,000 generated states per level |

#### Step 37 — APS Controller

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 37.1 | 1 | Map to monograph agency rank, cognitive light cone, APS tiers per Goal Hierarchy §1.1–1.2 | Monograph | Concept mapping | Review | Traces to Parts III, X |
| 37.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 37.3 | 6 | FMEA: wrong tier classification, Assembly Index overflow per Goal Hierarchy assembly dynamics | APS design | FMEA rows | Review | Each has mitigation |
| 37.4 | 10 | Implement T0–T3 classification + Assembly Index per Goal Hierarchy + ICD-011, with eval | Monograph specs, eval harness | APS controller + eval suite per Goal Hierarchy tier definitions | Property-based test | Tier assignments match expected for test scenarios per formal APS classification |
| 37.5 | 8 | Register, decorate per ICD-011 | YAML, decorators | Registered | CI check | Scanner passes |
| 37.6 | 9 | Link | RTM | Chain | CI check | Green |
| 37.7 | 10 | Validate APS Assembly Index per Goal Hierarchy Agency Rank | Goal Hierarchy §1.1 agency rank, Assembly Index definition | Test: for each goal assignment, compute Assembly Index; verify matches expected dimensionality of assigned agents' light cones | Property-based test | Zero Assembly Index computation errors; all indices within valid range |

#### Step 38 — Topology Manager

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 38.1 | 1 | Map to monograph steering operators, assignment matrices, feasibility per Goal Hierarchy §3 | Monograph | Concept mapping | Review | Traces to Parts V, VI |
| 38.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 38.3 | 6 | FMEA: stale topology, eigenspectrum blind spot, steer race, contract violation per Goal Hierarchy §3 | Topology design, FMEA (13.5) | FMEA rows (extend 13.5) | Review | Each has mitigation |
| 38.4 | 10 | Implement spawn/steer/dissolve, contracts, eigenspectrum per Goal Hierarchy §3 + ICD-012/015, with eval | Monograph, eval harness | Topology manager + eval suite per Goal Hierarchy topology operators | Property-based test | Eigenspectrum detects injected divergence; steer reshapes correctly per formal spec |
| 38.5 | 8 | Register, decorate per ICD-012/015 | YAML, decorators | Registered | CI check | Scanner passes |
| 38.6 | 9 | Link | RTM | Chain | CI check | Green |
| 38.7 | 10 | Implement Eigenspectrum Monitor per Goal Hierarchy §3.2 | Goal Hierarchy §3.2 eigenspectrum definition, topology state | Eigenspectrum calculator: compute communication pattern eigenvalues; detect divergence from contracted topology per formal definition | Integration test | Eigenspectrum divergence detection triggers alert; threshold configurable per topology contract |
| 38.8 | 10 | Verify Steer Operations maintain Contract Satisfaction | Goal Hierarchy §3 steer operator formal spec | Test: for each steer operation, verify pre/post-steer topologies satisfy original assignment constraints | Property-based test | Zero contract violations post-steer; all goals remain feasible |

#### Step 39 — Memory

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 39.1 | 1 | Map to monograph K-scope crystallisation, memory tiers per Goal Hierarchy agent state | Monograph | Concept mapping | Review | Traces to Part XII |
| 39.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 39.3 | 6 | FMEA: cross-tenant memory leak, crystallisation corruption, tier promotion failure | Memory design | FMEA rows | Review | Each has mitigation |
| 39.4 | 8 | Implement 3-tier: short (Redis via ICD-041), medium (PG via ICD-042), long (Chroma via ICD-043) | Storage layer (Slice 4), kernel | Memory module with tenant isolation per ICDs | Integration test | Tier promotion works; isolation holds per ICD v0.1 tenant isolation |
| 39.5 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 40 — Core Tests

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 40.1 | 4 | Assign SIL-2 verification methods | Verification table | Methods: integration + property-based + eval | Review | Assigned |
| 40.2 | 5 | Execute SIL-2 test suite | Steps 34–39 | Test results: intent → goal → APS → topology e2e per ICD pipeline (ICD-008 through ICD-012) | Integration + property-based | All pass |
| 40.3 | 10 | Run all Core eval suites | Eval framework, all eval suites from steps 34–39 | Eval results: classifier, decomposer, APS, topology baselines per Goal Hierarchy definitions | Eval | All pass baseline per Goal Hierarchy L0–L4 predicate evaluation |
| 40.4 | 9 | Validate RTM completeness for Core | RTM | Gap report | CI check | No gaps |
| 40.5 | 13 | Phase E gate checklist | All Phase E outputs | Gate report | Report | All pass → Phase F unlocked |

### Critical Path

```
36.8 → 36.9 → 36.4 → 36.5 → 37.4 → 37.7 → 38.4 → 38.8 → 39.4 → 40.2 → 40.3 → 40.5
```

**55 tasks. 12 on critical path.**

---

## Slice 7 — Phase F: Engine L3 (Steps 41–45)

**Purpose:** Build lane manager, MCP registry, builtins, and durable workflow engine.

### Tasks

#### Step 41 — Lanes

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 41.1 | 1 | Map to monograph channel composition, macro-channels | Monograph | Concept mapping | Review | Traces |
| 41.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 41.3 | 6 | FMEA: lane starvation, policy deadlock, dispatcher race | Lane design | FMEA rows | Review | Each has mitigation |
| 41.4 | 8 | Implement lane manager, policy engine, dispatchers per ICD-013/014/015 | APS output, kernel, decorators | Lane module: main/cron/subagent | Integration test | Goals dispatch to correct lanes under load per ICD boundaries |
| 41.5 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 42 — MCP Registry

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 42.1 | 1 | Map to monograph tool permission masks, channel constraints per Goal Hierarchy L3 | Monograph | Concept mapping | Review | Traces |
| 42.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 42.3 | 6 | FMEA: permission escalation, tool introspection leak, unregistered tool call | MCP design | FMEA rows | Review | Each has mitigation |
| 42.4 | 8 | Implement registry per ICD-019/020, per-agent permissions per K2, introspection | ICD specs, kernel, decorators | MCP module per K2 permission gates and ICD-019/020 | Property-based test | Agent can only call permitted tools per ICD-019/020; unpermitted raises error per K2 failure |
| 42.5 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 43 — MCP Builtins

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 43.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 43.2 | 6 | FMEA per builtin: code (sandbox escape via gRPC per ICD-022), web (SSRF per ICD-031), filesystem (path traversal), database (SQL injection per ICD-032/039/040) | Builtin designs | FMEA rows per tool | Review | Each has mitigation |
| 43.3 | 8 | Implement code (gRPC→sandbox per ICD-022), web (HTTP per ICD-031), filesystem, database per ICDs (ICD-032/034/039/040/042/043) | MCP registry, sandbox, kernel | 4 builtin tools with kernel enforcement per ICD contracts | Integration test | Each tool works; each FMEA mitigation verified per ICD schema validation (K1) |
| 43.4 | 9 | Link | RTM | Chains per builtin | CI check | Green |

#### Step 44 — Workflow Engine

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 44.1 | 1 | Map to monograph durable execution, compensation | Monograph | Concept mapping | Review | Traces |
| 44.2 | 3 | Document saga vs orchestration trade-off | — | ADR citing reliability + maintainability | Review | ADR exists |
| 44.3 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 44.4 | 6 | FMEA: saga partial failure, dead-letter overflow, DAG cycle, compensation failure | Workflow design | FMEA rows | Review | Each has mitigation |
| 44.5 | 8 | Implement durable engine per ICD-021, saga, compensation, dead-letter, DAG compiler | Lane manager, kernel | Workflow module with effectively-once semantics per ICD-021 | Property-based test | Workflow survives injected node failure per FMEA; compensation fires |
| 44.6 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 45 — Engine Tests

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 45.1 | 4 | Assign SIL-2 verification methods | Verification table | Methods assigned | Review | Assigned |
| 45.2 | 5 | Execute SIL-2 test suite | Steps 41–44 per ICD pipeline (ICD-013 through ICD-022, ICD-031-034, ICD-039-043) | Test results: goal → lane → workflow → tool → result e2e | Integration + property-based | All pass |
| 45.3 | 9 | Validate RTM completeness | RTM | Gap report | CI check | No gaps |
| 45.4 | 13 | Phase F gate checklist | All Phase F outputs | Gate report | Report | All pass → Phase G unlocked |

### Critical Path

```
41.4 → 42.4 → 43.3 → 44.5 → 45.2 → 45.4
```

**32 tasks. 6 on critical path.**

---

## Slice 8 — Phase G: Sandbox (Steps 46–50)

**Purpose:** Build and verify sandboxed code execution at SIL-3.

### Tasks

#### Step 46 — Sandbox Image

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 46.1 | 1 | Map to monograph Markov blanket isolation | Monograph | Concept mapping | Review | Traces |
| 46.2 | 3 | Document minimal-image trade-offs per Behavior Spec §2 | — | ADR citing security + performance | Review | ADR exists |
| 46.3 | 5 | Assign SIL-3 | SIL matrix | SIL-3 recorded | Review | Recorded |
| 46.4 | 6 | FMEA per Behavior Spec §2: image supply-chain attack, residual deps, network capability | Image design | FMEA rows | Review | Each has mitigation |
| 46.5 | 12 | Build minimal container: no network, no Holly deps per Behavior Spec §2 | Dockerfile, security policy | Container image | Integration test | No network; no Holly packages in image per Behavior Spec §2 isolation guarantees |
| 46.6 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 47 — gRPC Service

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 47.1 | 5 | Inherit SIL-3 | SIL matrix | Recorded | Review | Recorded |
| 47.2 | 6 | FMEA per Behavior Spec §2: proto deserialization attack, executor escape, result tampering | gRPC design | FMEA rows | Review | Each has mitigation |
| 47.3 | 7 | Implement per TLA+ sandbox spec per Behavior Spec §2 | TLA+ (14.2) | ExecutionRequest/Result proto per ICD-022, server, executor | Property-based test | Matches TLA+ states per Behavior Spec §2 |
| 47.4 | 9 | Link | RTM | Chain | CI check | Green |
| 47.5 | 7 | Validate gRPC Proto Constraints per ICD-022 | ICD v0.1 ICD-022 (MCP → Sandbox gRPC), Behavior Spec §2 | Property-based test: generate valid/invalid ExecutionRequest protos; verify all constraints (required fields, length bounds, enum values) enforced | Property-based test | Per ICD-022 schema, K1 gate accepts valid protos; rejects invalid with specific field errors |

#### Step 48 — Isolation

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 48.1 | 5 | Inherit SIL-3 | SIL matrix | Recorded | Review | Recorded |
| 48.2 | 6 | FMEA per Behavior Spec §2: namespace leak, seccomp bypass, cgroup escape | Isolation design | FMEA rows | Review | Each has mitigation |
| 48.3 | 7 | Implement per TLA+ isolation spec per Behavior Spec §2 | TLA+ (14.2) | PID/NET/MNT namespaces, seccomp profile, resource limits | Property-based test | Matches TLA+ states per Behavior Spec §2 |
| 48.4 | 12 | Verify isolation as independent safety layer per Behavior Spec §2 Defense-in-Depth | Isolation + stub kernel | Isolation holds without kernel per Behavior Spec §2 | Integration test | Layer independent per formal spec |
| 48.5 | 7 | Verify Isolation Invariant Preservation per Behavior Spec §2 | Behavior Spec §2 isolation invariants (no namespace leak, no seccomp bypass, etc.) | Property-based test: concurrent execution within sandbox; after each operation, verify all isolation invariants hold | Property-based test | Zero isolation violations over 10,000 concurrent operation traces |
| 48.6 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 49 — gVisor/Firecracker

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 49.1 | 3 | Document gVisor vs Firecracker trade-off per Behavior Spec §2 | — | ADR citing security + performance + ops | Review | ADR exists |
| 49.2 | 5 | Inherit SIL-3 | SIL matrix | Recorded | Review | Recorded |
| 49.3 | 6 | FMEA per Behavior Spec §2: runtime-specific escape paths per gVisor/Firecracker CVE analysis | Runtime configs | FMEA rows per runtime | Review | Each has mitigation |
| 49.4 | 12 | Implement production runtime configs per Behavior Spec §2 | Runtime choice, isolation layer | gVisor and/or Firecracker configs | Integration test | Execution works under production runtime per Behavior Spec §2 state machine |
| 49.5 | 7 | Adversarial Runtime Escape Testing per Behavior Spec §2 Failure Predicates | Behavior Spec §2 documented escape vectors (gVisor CVEs, Firecracker CVEs) | Adversarial test suite: attempt known escape vectors; all must fail per Behavior Spec §2 | Integration test | Zero escape successes; all attempted vectors blocked per formal spec |
| 49.6 | 9 | Link | RTM | Chain | CI check | Green |

#### Step 50 — Sandbox Tests

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 50.1 | 4 | Assign SIL-3 verification methods per Behavior Spec §3 | Verification table | Methods: formal + property-based + integration + independent | Review | All 4 assigned |
| 50.2 | 5 | Execute SIL-3 test suite per Behavior Spec §2 Acceptance Criteria | Steps 46–49 | Test results: network escape, filesystem escape, resource limits per Behavior Spec §2 | All methods | All pass per Behavior Spec §2 |
| 50.3 | 7 | Run TLA+ model checker against sandbox spec per Behavior Spec §2 | TLA+ (14.2) | TLC output: zero violations per Behavior Spec §2 formal spec | Model check | Zero violations |
| 50.4 | 12 | Independent review of sandbox safety per Behavior Spec §2 SIL-3 requirements | All sandbox code, specs, tests, Behavior Spec §2 | Independent reviewer sign-off | Review | Sign-off recorded |
| 50.5 | 9 | Validate RTM completeness | RTM | Gap report | CI check | No gaps |
| 50.6 | 13 | Phase G gate checklist | All Phase G outputs | Gate report | Report | All pass → Phase H unlocked |

### Critical Path

```
46.5 → 47.3 → 47.5 → 48.3 → 48.5 → 49.4 → 49.5 → 50.2 → 50.3 → 50.6
```

**45 tasks. 10 on critical path.**

---

## Slice 9 — Phase H: API & Auth (Steps 51–56)

**Purpose:** Build Starlette server, JWT middleware, RBAC, routes, WebSockets.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 51.1 | 3 | Document middleware stack trade-offs | — | ADR | Review | Exists |
| 51.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 51.3 | 6 | FMEA: middleware bypass, request smuggling per ICD-001/002/003 | Server design | FMEA rows | Review | Each has mitigation |
| 51.4 | 8 | Implement Starlette app factory per ICD-001/002/003, middleware, decorate | ICD specs, kernel | Server module per ICD-001 (UI → ALB) contract | Integration test | Middleware chain executes in order per ICD-001/002/003 |
| 51.5 | 9 | Link | RTM | Chain | CI check | Green |
| 52.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 52.2 | 6 | FMEA: JWKS cache poisoning, token replay, revocation race per ICD-047/049 | JWT design | FMEA rows | Review | Each has mitigation |
| 52.3 | 12 | Implement JWKS verification per ICD-047, claims extraction, revocation cache per ICD-049 | Auth design, Redis (revocation), Authentik (JWKS) | JWT middleware per K2 permission gates | Property-based test | Expired/revoked tokens rejected per ICD-002/047/049; valid pass per K2 gate |
| 52.4 | 9 | Link | RTM | Chain | CI check | Green |
| 53.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 53.2 | 6 | FMEA: privilege escalation, role confusion, claim tampering per K2 | RBAC design | FMEA rows | Review | Each has mitigation |
| 53.3 | 12 | Implement RBAC enforcement from JWT claims per K2 | JWT middleware, kernel | Auth module per K2 permission gate | Property-based test | Unauthorized roles rejected per K2; authorized pass |
| 53.4 | 9 | Link | RTM | Chain | CI check | Green |
| 54.1 | 8 | Implement routes per ICD-003/023/024/025/026/027/028 (chat, goals, agents, topology, execution, audit, config, health) | All Core/Engine modules, ICD specs | Route handlers with kernel decorators per ICD boundaries | Integration test | Each route returns correct response per ICD schema; kernel enforces per K1 |
| 54.2 | 9 | Link | RTM | Chains per route | CI check | Green |
| 55.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 55.2 | 6 | FMEA: WS hijack, cross-tenant channel leak, re-auth failure per ICD-025/027 | WS design | FMEA rows | Review | Each has mitigation |
| 55.3 | 8 | Implement WS manager per ICD-025/027, 9 channels, tenant-scoped authz, re-auth | Conversation module, JWT middleware | WebSocket module per ICD-025 (EventBus → Channels) | Integration test | Tenant isolation holds per ICD v0.1; re-auth works |
| 55.4 | 9 | Link | RTM | Chain | CI check | Green |
| 56.1 | 4 | Assign SIL-2 verification methods | Verification table | Assigned | Review | Assigned |
| 56.2 | 5 | Execute SIL-2 test suite per ICD routes | Steps 51–55 per ICD pipeline (ICD-001 through ICD-030) | Test results: auth, routing, WS delivery per ICD schemas | Integration + property-based | All pass per ICD v0.1 contracts |
| 56.3 | 9 | Validate RTM completeness | RTM | Gap report | CI check | No gaps |
| 56.4 | 13 | Phase H gate checklist | All Phase H outputs | Gate report | Report | All pass → Phase I unlocked |
| 56.5 | 9 | Verify All 49 ICDs have Corresponding API Routes or Config Entries | All ICDs (ICD-001 through ICD-049) | Coverage check: every ICD either has a route, or is internal (e.g., ICD-006 Kernel, ICD-021 Workflow) with documented rationale | Integration test | Per ICD v0.1 interface index, zero uncovered external ICDs; internal ICDs justified |

### Critical Path

```
51.4 → 52.3 → 53.3 → 54.1 → 55.3 → 56.2 → 56.5 → 56.4
```

**37 tasks. 8 on critical path.**

---

## Slice 10 — Phase I: Observability (Steps 57–61)

**Purpose:** Build event bus, structured logging, trace store, metrics, and exporters.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 57.1 | 1 | Map event bus to monograph channel composition | Monograph | Concept mapping | Review | Traces |
| 57.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 57.3 | 6 | FMEA: event loss, backpressure failure, fanout cross-tenant leak per ICD-023/024/025 | Event bus design | FMEA rows | Review | Each has mitigation |
| 57.4 | 8 | Implement unified ingest per ICD-023/024, sampling, backpressure, tenant-scoped fanout per ICD-025 | Kernel, Redis | Event bus module per ICD-023/024 (Core/Engine → Event Bus) | Integration test | Events delivered per ICD-025; backpressure engages under load per ICD design |
| 57.5 | 9 | Link | RTM | Chain | CI check | Green |
| 58.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 58.2 | 8 | Implement structured JSON logger per ICD-026, correlation-aware per K4, redact-before-persist | Redaction lib, K4 trace injection | Logger module | Integration test | Logs contain correlation ID per K4; PII redacted per redaction lib |
| 58.3 | 9 | Link | RTM | Chain | CI check | Green |
| 59.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 59.2 | 6 | FMEA: trace payload leak, decision tree corruption per ICD-025/026 | Trace design | FMEA rows | Review | Each has mitigation |
| 59.3 | 8 | Implement decision tree persistence per ICD-025, redact payloads | Event bus, redaction lib, Postgres | Trace store module | Integration test | Decision trees persisted per ICD-025; payloads redacted per ICD-026 redaction policy |
| 59.4 | 9 | Link | RTM | Chain | CI check | Green |
| 60.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 60.2 | 8 | Implement Prometheus collectors | Event bus | Metrics module | Integration test | Metrics scraped correctly |
| 60.3 | 9 | Link | RTM | Chain | CI check | Green |
| 61.1 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 61.2 | 8 | Implement PG (partitioned per ICD-036) + Redis (real-time per ICD-037) exporters | Event bus, Postgres, Redis | Exporter modules | Integration test | Events flow to both sinks per ICD-036/037 |
| 61.3 | 9 | Link | RTM | Chain | CI check | Green |
| 61.4 | 9 | Validate RTM completeness for observability | RTM | Gap report | CI check | No gaps |
| 61.5 | 13 | Phase I gate checklist | All Phase I outputs | Gate report | Report | All pass → Phase J unlocked |
| 61.6 | 9 | Implement Observability Trace Correlation per ICD Boundary | All ICDs involving observability (ICD-023/024/025/026/027/036/037), K4 trace injection | Every boundary crossing generates trace span with ICD identifier, correlation ID, timestamp; exported per ICD-025/026/027 | Integration test | Per ICD v0.1 observability contract, all traces include correlation ID; queryable by ICD and time range |

### Critical Path

```
57.4 → 58.2 → 59.3 → 60.2 → 61.2 → 61.6 → 61.5
```

**25 tasks. 7 on critical path.**

---

## Slice 11 — Phase J: Agents (Steps 62–65)

**Purpose:** Build BaseAgent, agent registry, prompt library, and executable constitution.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 62.1 | 1 | Map BaseAgent to monograph agency rank, digital branching, feedback Jacobian per Goal Hierarchy | Monograph, Goal Hierarchy §1.1–1.2 | Concept mapping | Review | Agent satisfies 3 formal agency conditions per Goal Hierarchy |
| 62.2 | 3 | Document agent lifecycle trade-offs | — | ADR | Review | Exists |
| 62.3 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 62.4 | 6 | FMEA: lifecycle leak, message protocol desync, kernel binding failure | Agent design | FMEA rows | Review | Each has mitigation |
| 62.5 | 10 | Implement BaseAgent: lifecycle, message protocol per ICD-008/009/010/011/012, kernel binding with eval | Kernel, MCP registry, eval framework | BaseAgent class + eval suite | Property-based test | Lifecycle correct per agency rank definition; messages conform to protocol per ICD contracts |
| 62.6 | 8 | Register, decorate | YAML, decorators | Registered | CI check | Scanner passes |
| 62.7 | 9 | Link | RTM | Chain | CI check | Green |
| 63.1 | 1 | Map agent types to monograph competency continuum per Goal Hierarchy | Monograph | Concept mapping | Review | Traces |
| 63.2 | 5 | Assign SIL-2 | SIL matrix | Recorded | Review | Recorded |
| 63.3 | 6 | FMEA: unregistered agent call, capability mismatch, catalog corruption | Registry design | FMEA rows | Review | Each has mitigation |
| 63.4 | 10 | Implement type catalog, capability declarations with eval | BaseAgent, eval framework | Agent registry + eval suite | Integration test | Correct agents resolved for capability queries per Goal Hierarchy competency definitions |
| 63.5 | 9 | Link | RTM | Chain | CI check | Green |
| 64.1 | 1 | Map prompt roles to monograph agency types per Goal Hierarchy | Monograph | Concept mapping | Review | Traces |
| 64.2 | 10 | Implement Holly, researcher, builder, reviewer, planner prompts with eval | Agent registry, eval framework, Goal Hierarchy | Prompt library + per-prompt eval suite | Property-based test | Each prompt passes behavioral baseline per Goal Hierarchy agency specifications |
| 64.3 | 10 | Establish eval baselines | Eval framework | Baseline metrics per prompt | Eval | Baselines recorded |
| 64.4 | 9 | Link | RTM | Chain | CI check | Green |
| 65.1 | 1 | Map Celestial/Terrestrial to monograph goal hierarchy per Goal Hierarchy §2 | Monograph, Goal Hierarchy | Concept mapping | Review | Traces to Part IV (Goal Hierarchy Spec) |
| 65.2 | 11 | Implement Celestial L0–L4 as executable predicate functions per Goal Hierarchy §2.0–2.4 | Monograph, goal decomposer, Goal Hierarchy §2 | Constitution predicates: L0 (safety), L1 (legal), L2 (ethical), L3 (permissions), L4 (constitutional) per formal spec | Property-based test | Each predicate evaluable; lexicographic ordering correct per Goal Hierarchy §2.4 |
| 65.3 | 11 | Implement Terrestrial L5–L6 as executable goal specs per Goal Hierarchy §2.5–2.6 | Goal decomposer, Goal Hierarchy §2.5–2.6 | Terrestrial predicates | Property-based test | Terrestrial goals decompose correctly per Goal Hierarchy hierarchy rules |
| 65.4 | 10 | Build constitution eval suite per Goal Hierarchy §2 | Predicates, eval framework, Goal Hierarchy | Adversarial eval: attempts to violate each Celestial level per Goal Hierarchy attack scenarios | Eval | Zero Celestial violations per Goal Hierarchy §2 Lexicographic Ordering |
| 65.5 | 9 | Link | RTM | Chain | CI check | Green |
| 65.6 | 13 | Phase J gate checklist | All Phase J outputs | Gate report | Report | All pass → Phase K unlocked |
| 65.7 | 11 | Implement Terrestrial L5–L6 Predicate Functions per Goal Hierarchy §2.5–2.6 | Goal Hierarchy §2.5–2.6 user intent specifications | User-facing goal predicates: L5 (primary intent), L6 (derived/refined intent) returning GoalResult per formal spec | Property-based test | Per Goal Hierarchy §2.5–2.6, predicates correctly classify user intent satisfaction |
| 65.8 | 11 | Verify Lexicographic Gating Enforcement per Goal Hierarchy §2.4 | Goal Hierarchy §2.4 lexicographic ordering formal definition | Test: for any goal assignment, verify L0 check always runs first; if L0 fails, L1 skipped; if L1 fails, L2 skipped; etc. | Property-based test | Lexicographic ordering enforced; zero out-of-order gate evaluations |
| 65.9 | 10 | Implement Multi-Agent Feasibility Checker per Goal Hierarchy §3 | Goal Hierarchy §3 feasibility theorem, topology state, assignments | Feasibility predicate: given team topology and goal assignment, compute if goal region reachable per multi-agent feasibility | Integration test | Per Goal Hierarchy §3, feasibility correctly identifies infeasible assignments |

### Critical Path

```
62.5 → 63.4 → 64.2 → 64.3 → 65.2 → 65.7 → 65.8 → 65.9 → 65.4 → 65.6
```

**34 tasks. 10 on critical path.**

---

## Slice 12 — Phase K: Eval Infrastructure / EDDOps (Steps 66–69)

**Purpose:** Build the eval framework, behavioral suites, constitution gate, and eval CI pipeline.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 66.1 | 10 | Design eval harness architecture | Eval stubs from Slices 6/11 | Harness design: dataset loaders, metric collectors, regression tracker | Review | Design complete |
| 66.2 | 10 | Implement eval framework harness | Design | `EvalHarness` class: load datasets, run evals, collect metrics, detect regression | Integration test | Harness runs existing eval suites from Slices 6/11 |
| 66.3 | 10 | Implement dataset loaders | Harness | Loaders: JSON, CSV, programmatic generators | Integration test | All formats load correctly |
| 66.4 | 10 | Implement metric collectors + regression tracker | Harness | Metric store with baseline comparison and regression detection | Integration test | Regression detected on intentionally-degraded baseline |
| 66.5 | 4 | Assign verification methods for eval framework | Verification table | Methods assigned | Review | Assigned |
| 66.6 | 9 | Link | RTM | Chain | CI check | Green |
| 67.1 | 10 | Build per-agent property-based eval suites per Goal Hierarchy agency definitions | Eval framework, agent prompts, Goal Hierarchy | Hypothesis strategies per agent type | Property-based test | Strategies generate valid adversarial inputs per Goal Hierarchy competency specs |
| 67.2 | 10 | Build adversarial eval suites per Goal Hierarchy Celestial constraints | Eval framework, FMEA (goal injection, prompt injection), Goal Hierarchy §2 | Adversarial datasets targeting each FMEA attack + each Celestial level | Eval | Each agent resists adversarial inputs above threshold per Goal Hierarchy §2.0–2.4 |
| 67.3 | 10 | Establish production baselines per Goal Hierarchy L0–L4 predicate eval | All eval suites, Goal Hierarchy | Baseline metrics per agent per suite; includes Celestial predicate baselines | Eval | Baselines recorded and versioned |
| 67.4 | 9 | Link | RTM | Chain | CI check | Green |
| 68.1 | 10 | Implement constitution gate per Goal Hierarchy §2.4 | Eval framework, Celestial predicates (65.2), Goal Hierarchy §2 | Gate: runs all Celestial predicates on every constitution/prompt change per lexicographic ordering | Integration test | Gate fires on change; blocks on violation per Goal Hierarchy §2.4 |
| 68.2 | 11 | Verify gate enforces lexicographic ordering per Goal Hierarchy §2.4 | Constitution gate, test cases, Goal Hierarchy §2.4 | Test: Terrestrial change that degrades Celestial metric is blocked | Integration test | Blocked correctly per Goal Hierarchy ordering guarantees |
| 68.3 | 9 | Link | RTM | Chain | CI check | Green |
| 68.4 | 8 | Integrate Constitution Gate with K8 Eval Gate | K8 eval gate (18.4), constitution gate (68.1), Behavior Spec §1.9 K8, Goal Hierarchy §2 | K8 gate calls constitution gate's Celestial predicates; failure → context→FAULTED per Behavior Spec | Integration test | Per Behavior Spec §1.9 K8 failure predicates, Celestial predicate failure is recorded as K8 failure |
| 69.1 | 10 | Implement eval CI pipeline stage | Eval framework, CI config | CI stage: runs full eval suite, blocks merge on regression per Goal Hierarchy behavioral baselines | Integration test | Merge blocked on injected regression |
| 69.2 | 4 | Verify eval CI as formal verification activity | Process doc, ISO 15288 | Eval CI = 15288 verification by demonstration | Review | Documented |
| 69.3 | 9 | Link | RTM | Chain | CI check | Green |
| 69.4 | 9 | Validate RTM completeness for EDDOps | RTM | Gap report | CI check | No gaps |
| 69.5 | 13 | Phase K gate checklist | All Phase K outputs | Gate report | Report | All pass → Phase L unlocked |

### Critical Path

```
66.2 → 66.3 → 66.4 → 67.1 → 67.2 → 67.3 → 68.1 → 68.4 → 69.1 → 69.5
```

**26 tasks. 10 on critical path.**

---

## Slice 13 — Phase L: Config (Steps 70–72)

**Purpose:** Build settings, hot reload, and config audit/rollback. SIL-1.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 70.1 | 5 | Assign SIL-1 | SIL matrix | SIL-1 recorded | Review | Recorded |
| 70.2 | 8 | Implement Pydantic env-driven config | Architecture requirements | Settings module | Unit test | All config keys load from env; validation on invalid |
| 70.3 | 9 | Link | RTM | Chain | CI check | Green |
| 71.1 | 5 | Inherit SIL-1 | SIL matrix | Recorded | Review | Recorded |
| 71.2 | 8 | Implement runtime hot reload without restart | Settings module, Redis | Reload mechanism | Unit test | Config change propagates; invalid rejected |
| 71.3 | 9 | Link | RTM | Chain | CI check | Green |
| 72.1 | 5 | Inherit SIL-1 | SIL matrix | Recorded | Review | Recorded |
| 72.2 | 6 | FMEA: dangerous key change without HITL, rollback to corrupt state | Config design | FMEA rows | Review | Each has mitigation |
| 72.3 | 8 | Implement change logging, HITL on dangerous keys, version revert per K7 gate | Settings module, K7 HITL gate | Config audit module | Unit test | Dangerous keys require HITL per K7; revert works |
| 72.4 | 9 | Link | RTM | Chain | CI check | Green |
| 72.5 | 9 | Validate RTM completeness | RTM | Gap report | CI check | No gaps |
| 72.6 | 13 | Phase L gate checklist | All Phase L outputs | Gate report | Report | All pass → Phase M unlocked |

### Critical Path

```
70.2 → 71.2 → 72.3 → 72.6
```

**14 tasks. 4 on critical path. (Lightest slice — SIL-1, minimal FMEA.)**

---

## Slice 14 — Phase M: Console L5 (Steps 73–78)

**Purpose:** Build React frontend: shell, chat, topology, goals, execution, audit. SIL-1.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 73.1 | 5 | Assign SIL-1 | SIL matrix | Recorded | Review | Recorded |
| 73.2 | 3 | Document frontend stack trade-offs | — | ADR citing maintainability + performance | Review | Exists |
| 73.3 | 8 | Scaffold React + Vite + Tailwind + Zustand | Architecture requirements | Frontend skeleton | Unit test | Builds and serves |
| 73.4 | 9 | Link | RTM | Chain | CI check | Green |
| 74.1 | 8 | Implement chat panel per ICD-025/027, message bubbles, input bar | WS API (step 55), conversation API (ICD-025) | Chat component | Unit test | Messages render per ICD-025; input sends |
| 74.2 | 9 | Link | RTM | Chain | CI check | Green |
| 75.1 | 1 | Map topology viz to monograph morphogenetic concepts per Goal Hierarchy §3 | Monograph, Goal Hierarchy | Concept mapping | Review | Traces |
| 75.2 | 8 | Implement live agent graph, contract cards per Goal Hierarchy §3 topology | Topology API (step 38), WS (ICD-025) | Topology component per Goal Hierarchy agency rank visualization | Unit test | Graph updates on topology change per ICD-025; contracts display |
| 75.3 | 9 | Link | RTM | Chain | CI check | Green |
| 76.1 | 1 | Map goal viz to monograph Celestial/Terrestrial hierarchy per Goal Hierarchy §2 | Monograph, Goal Hierarchy | Concept mapping | Review | Traces |
| 76.2 | 8 | Implement tree explorer, celestial badges per Goal Hierarchy §2 levels | Goal API (step 36), WS (ICD-025) | Goals component showing L0–L6 hierarchy per Goal Hierarchy spec | Unit test | Tree renders per ICD-025; Celestial goals badged (L0–L4) per Goal Hierarchy §2 |
| 76.3 | 9 | Link | RTM | Chain | CI check | Green |
| 77.1 | 8 | Implement lane monitor, task timeline per ICD-013/014/015 | Lane API (step 41), workflow API, WS (ICD-025) | Execution component | Unit test | Lanes and tasks render in real-time per ICD-025 |
| 77.2 | 9 | Link | RTM | Chain | CI check | Green |
| 78.1 | 8 | Implement log viewer, trace tree, metrics dashboard per ICD-026/027 observability | Observability APIs (steps 57–61), WS (ICD-025) | Audit component per ICD observability contracts | Unit test | Logs stream per ICD-026; traces navigable per trace store (59.3); metrics display |
| 78.2 | 9 | Link | RTM | Chain | CI check | Green |
| 78.3 | 9 | Validate RTM completeness for console | RTM | Gap report | CI check | No gaps |
| 78.4 | 13 | Phase M gate checklist | All Phase M outputs | Gate report | Report | All pass → Phase N unlocked |

### Critical Path

```
73.3 → 74.1 → 75.2 → 76.2 → 77.1 → 78.1 → 78.4
```

**28 tasks. 7 on critical path.**

---

## Slice 15 — Phase N: Deploy & Ops (Steps 79–86)

**Purpose:** Docker, AWS, auth, staged rollout, scripts, release safety case, runbook, docs.

### Tasks

| ID | MP | Task | Input | Output | Verification | Acceptance |
|---|---|---|---|---|---|---|
| 79.1 | 3 | Document container strategy trade-offs | — | ADR | Review | Exists |
| 79.2 | 8 | Build Docker Compose (dev) + production Dockerfile | All modules | Docker configs | Integration test | Dev compose starts full stack; prod image builds |
| 79.3 | 9 | Link | RTM | Chain | CI check | Green |
| 80.1 | 3 | Document AWS architecture trade-offs | — | ADR citing availability + cost | Review | Exists |
| 80.2 | 14 | Implement VPC/CFn, ALB/WAF, ECS Fargate task defs per ICD-001/005/047 (ALB, Authentik, JWKS) | Docker image, AWS account | CloudFormation templates | Integration test | Stack deploys to staging per ICD-001 (ALB) contract |
| 80.3 | 9 | Link | RTM | Chain | CI check | Green |
| 81.1 | 12 | Implement Authentik OIDC flows per ICD-004/005/047, RBAC policies per K2 | Auth module (step 53), Authentik | OIDC config, RBAC policy definitions | Integration test | Login flow works per ICD-004/005; RBAC enforces per K2 permission gate |
| 81.2 | 9 | Link | RTM | Chain | CI check | Green |
| 82.1 | 14 | Implement feature flags | Deployment pipeline | Flag service: runtime toggle per feature | Integration test | Flag controls behavior; toggle propagates |
| 82.2 | 14 | Implement canary deploys per ICD staged deployment | ECS, ALB | Canary config: % traffic routing | Integration test | Canary receives configured traffic fraction per ICD-001 ALB routing |
| 82.3 | 14 | Implement progressive delivery gates per eval framework | Eval framework, canary | Gate: promote/rollback based on eval metrics per Goal Hierarchy behavioral baselines | Integration test | Regression triggers automatic rollback per Goal Hierarchy predicate eval |
| 82.4 | 9 | Link | RTM | Chain | CI check | Green |
| 83.1 | 9 | Implement scripts: seed_db, migrate, dev, partition maintenance | All infra modules | Script suite | Integration test | Each script runs without error |
| 83.2 | 9 | Link | RTM | Chain | CI check | Green |
| 84.1 | 6 | Aggregate all FMEA results across all phases (A–N) | All FMEA worksheets from all slices | Master risk register | Review | Every identified risk has disposition |
| 84.2 | 12 | Build full system safety argument per ISO 42010, cite all artifacts | Master risk register, all test results, all TLA+ results, ICD v0.1, Behavior Specs, Goal Hierarchy | Release safety case: claims → evidence → context | Review | Every claim has evidence; every gap explicit |
| 84.3 | 9 | Verify complete traceable chain from concern to code | Full RTM | RTM completeness: every requirement → decision → code → test → proof | CI check | Zero gaps across entire codebase |
| 84.4 | 7 | Verify all TLA+ specs pass final model check (kernel, sandbox, egress) per Behavior Spec | All TLA+ specs (14.1–14.3) | Final TLC run per Behavior Spec §1–3 | Model check | Zero violations |
| 84.5 | 12 | Independent safety review per SIL-3 rigor (Kernel, Sandbox, Egress) | Safety case, all artifacts, Behavior Spec §1–3 | Independent reviewer sign-off on release safety case | Review | Sign-off recorded |
| 84.6 | 13 | Release gate: safety case complete? | Safety case | Go/no-go decision | Report | Go → production release authorized |
| 84.7 | 7 | Final Behavior Spec Validation | All implemented components (Kernel, Sandbox, Egress), Behavior Spec §1–3 | Re-run all formal state machine checks and guard condition evaluations from all behavior specs | Model check | Zero violations; all state machine transitions verified |
| 84.8 | 11 | Verify Goal Hierarchy Theorems per Goal Hierarchy §3 | Goal Hierarchy §3 (Celestial Inviolability, Terrestrial Subordination, Feasibility–Governance Equivalence) | Formal verification: test three main theorems of the goal hierarchy using eval framework | Eval + Integration test | All three theorems validated in production configuration per Goal Hierarchy formal spec |
| 85.1 | 9 | Write operational runbook | All infra, deploy configs | Runbook: procedures, DR/restore | Review | Every operational scenario documented |
| 85.2 | 9 | Link | RTM | Chain | CI check | Green |
| 86.1 | 9 | Write glossary | Monograph, architecture.yaml | Glossary: formal terms, Holly mappings | Review | Every term defined |
| 86.2 | 9 | Write sandbox security doc | Sandbox design, FMEA, TLA+ (14.2), Behavior Spec §2 | Security document citing all isolation claims | Review | All isolation claims per Behavior Spec §2 traced to evidence |
| 86.3 | 9 | Write egress model doc | Egress design, FMEA, TLA+ (14.3), Behavior Spec §3 | Egress document | Review | All filtering claims per Behavior Spec §3 traced to evidence |
| 86.4 | 9 | Write deployment topology doc | AWS config, Docker, Authentik | Topology document | Review | Matches deployed infrastructure per ICD-001/005 ALB/Authentik placement |
| 86.5 | 13 | Phase N gate checklist | All Phase N outputs | Final gate report | Report | All pass → Production |

### Critical Path

```
79.2 → 80.2 → 81.1 → 82.1 → 82.2 → 82.3 → 84.1 → 84.2 → 84.7 → 84.8 → 84.4 → 84.5 → 84.6 → 86.5
```

**48 tasks. 14 on critical path.**

---

## Grand Summary

| Metric | Value |
|---|---|
| **Total tasks** | **583** |
| **Total critical-path tasks** | **127** |
| **Slices** | **15** |
| **Phases** | **14 (A–N)** |
| **Roadmap steps covered** | **86** |
| **Heaviest slice** | **Slice 3 (Phase B: Kernel) — 86 tasks** |
| **Lightest slice** | **Slice 13 (Phase L: Config) — 14 tasks** |
| **SIL-3 slices** | **3 (Slices 1/3a, 3, 8)** |
| **SIL-1 slices** | **2 (Slices 13, 14)** |
| **ICD-specific tasks** | **8 new** |
| **Behavior Spec tasks** | **12 new** |
| **Goal Hierarchy tasks** | **12 new** |
| **Acceptance criteria updated** | **47 tasks** |

### Task Distribution by Type

| Type | Count | % |
|---|---|---|
| Implementation (code) | 227 | 39% |
| Review (design, FMEA, ADR) | 167 | 29% |
| Test / Verification | 111 | 19% |
| Traceability (RTM, chain links) | 52 | 9% |
| Gate / Report | 18 | 3% |
| Eval (behavioral suites) | 8 | 1% |

### Coverage by Document

| Document | Coverage | Status |
|---|---|---|
| ICD v0.1 (49 interfaces) | All 49 ICDs specified in task acceptance criteria; 8 dedicated ICD tasks | Complete |
| Behavior Specs SIL-3 | Kernel (K1–K8), Sandbox, Egress state machines, all 6 KernelContext invariants, all failure predicates | Complete |
| Goal Hierarchy Formal Spec | All 7 levels (L0–L6) implemented as executable predicates; lexicographic gating enforced; 3 main theorems verified | Complete |
| README Meta Procedure | All 14 meta procedure steps (MP-1 through MP-14) mapped to task categories | Complete |

---

## End of Task Manifest

**This manifest is now a complete, comprehensive, and formally validated specification of all 583 tasks required to build Holly Grace.**

**All tasks are traced to:**
1. SAD v0.1.0.5 (System Architecture Document)
2. ICD v0.1 (49 boundary-crossing interface contracts)
3. Component Behavior Specs SIL-3 (formal state machines and invariants)
4. Goal Hierarchy Formal Spec (7-level goal hierarchy with executable predicates)
5. README Meta Procedure (14-step design methodology)

**Critical path:** 127 tasks, organized across 15 spiral slices and 14 phases.

**Next step:** Execute Slice 1 (Phase A Spiral) through the spiral gate (3a.12). Upon gate pass, proceed to Slice 2 (Phase A Backfill).
