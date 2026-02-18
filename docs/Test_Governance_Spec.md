# Holly Grace — Test Governance Specification v1.0

**Generated:** 17 February 2026
**Source Authority:** END_TO_END_AUDIT_CHECKLIST.md (Allen, 2026), SIL Classification Matrix v1.0, Development Procedure Graph v1.1
**Purpose:** This document is the binding specification for how every test in Holly Grace is conceived, authored, traced, and validated. It is consumed by P1 (Task Derivation) and P3C (Test Authoring) of the Development Procedure Graph. No test may be written outside this governance framework. No task may be marked DONE unless its test governance obligations are discharged.

---

## 1  Governing Principle: Falsification-First

Every test exists to *falsify* a specific claim. Tests are not confirmations; they are failed attempts to break a guarantee. This principle (derived from Audit Checklist §11 "Falsification-first validation per fix") governs all test authoring:

1. **State the claim** — the invariant, contract, predicate, or behavior being asserted.
2. **Construct the adversary** — an input, sequence, or condition designed to violate the claim.
3. **Verify the adversary fails** — the system correctly rejects, blocks, or handles the violation.
4. **Verify the happy path only after the adversary** — positive tests exist to demonstrate the claim holds, but they are secondary to negative tests.

A test suite where all tests are happy-path confirmations is *noncompliant* with this specification regardless of coverage percentage.

---

## 2  Control Library (Holly-Specialized)

The audit checklist defines six control domains (SEC/TST/ARC/OPS/CQ/GOV). Holly specializes these into an enumerated control library. Every control has a unique ID, a SIL threshold (minimum SIL at which the control is mandatory), and a verification method.

### 2.1  Security Controls (SEC)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| SEC-001 | No hardcoded secrets in source | All | Secret scanner (P4 stage) | §5 P4 |
| SEC-002 | Authentication enforced on all protected endpoints | All | Dynamic test: unauthenticated → 401 | §6 P5 |
| SEC-003 | Authorization enforced (RBAC from JWT claims) | All | Dynamic test: low-privilege → 403 | §6 P5 |
| SEC-004 | Cross-tenant data isolation | SIL-2+ | Dynamic test: tenant A cannot read tenant B | §6 P5 |
| SEC-005 | Input sanitization (no SQLi, XSS) | All | SAST + property-based injection fuzzing | §5 P4 |
| SEC-006 | Output redaction (PII, secrets stripped before persist/egress) | SIL-2+ | Redaction validation test | §6 P5 |
| SEC-007 | Rate limiting enforced | SIL-2+ | Dynamic test: exceed rate → 429 + Retry-After | §6 P5 |
| SEC-008 | Malformed/oversized payload → 400 (not 500) | All | Property-based payload fuzzing | §6 P5 |
| SEC-009 | Server errors do not leak internals | All | Dynamic test: trigger error, inspect response | §6 P5 |
| SEC-010 | Webhook/callback validation | SIL-2+ | Dynamic test: tampered webhook rejected | §6 P5 |
| SEC-011 | Sandbox network escape prevention | SIL-3 | Adversarial escape vector suite | §6 P5 agentic |
| SEC-012 | Egress payload secret redaction | SIL-3 | Outbound LLM payload inspection | §6 P5 agentic |
| SEC-013 | Capability manifest boundary enforcement | SIL-2+ | MCP tool permission violation test | §6 P5 agentic |
| SEC-014 | Container image minimal + pinned | SIL-2+ | Container scan (no High/Critical CVEs) | §5 P4 |
| SEC-015 | Dependency vulnerability scan clean | All | `pip-audit` / `npm audit` (CVSS < 7.0) | §5 P4 |

### 2.2  Testing Controls (TST)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| TST-001 | Full test suite passes with zero failures | All | CI pipeline | §8 P7 |
| TST-002 | Coverage meets SIL threshold (SIL-3: ≥95%, SIL-2: ≥85%, SIL-1: ≥70%) | All | Coverage report | §8 P7 |
| TST-003 | Test pyramid maintained (unit > integration > e2e) | All | Test count by category | §8 P7 |
| TST-004 | Critical path has ≥1 integration test per flow | SIL-2+ | Trace matrix | §8 P7 |
| TST-005 | Property-based tests exist for all Pydantic models | SIL-2+ | Hypothesis test presence | §8 P7 |
| TST-006 | Adversarial tests exist for all SIL-3 components | SIL-3 | Test file inventory | §8 P7 |
| TST-007 | Formal verification (TLA+) for SIL-3 state machines | SIL-3 | TLC zero violations | §8 P7 |
| TST-008 | Dissimilar verification for SIL-3 safety checks | SIL-3 | Independent code path | §8 P7 |
| TST-009 | No production credentials in test code | All | Scan test files for credential patterns | §8 P7 |
| TST-010 | No live external calls in tests (all mocked/stubbed) | All | Network call detection in test runner | §8 P7 |
| TST-011 | Flake rate < 1% (measured over last 20 CI runs) | SIL-2+ | CI history analysis | §8 P7 |
| TST-012 | Regression test exists for every resolved finding | All | Finding → test trace | §11 remediation |
| TST-013 | Falsification-first: negative tests ≥ positive tests for SIL-3 | SIL-3 | Test polarity audit | §11 remediation |
| TST-014 | Concurrency tests for shared-state components | SIL-2+ | Thread safety test presence | §8 P7 |
| TST-015 | Boundary condition tests for all bounded resources | SIL-2+ | Bounds test presence | §8 P7 |

### 2.3  Architecture Controls (ARC)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| ARC-001 | All boundary crossings pass through KernelContext | All | AST scanner / import graph | §7 P6 invariants |
| ARC-002 | No upward layer imports (L3→L2, L2→L1 forbidden) | All | Import DAG validation | §7 P6 |
| ARC-003 | ICD schema defined for every inter-component interface | SIL-2+ | ICD count vs. actual interface count | P2 spec pre-check |
| ARC-004 | Decorators present on all architectural boundaries | All | AST scanner | §7 P6 |
| ARC-005 | SAD/RTD synchronized with actual repo tree | All | Drift detection | P0 context sync |
| ARC-006 | SIL inheritance on boundaries (higher SIL wins) | SIL-2+ | Boundary SIL audit | P5 regression |

### 2.4  Operations Controls (OPS)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| OPS-001 | Health endpoint returns meaningful component status | SIL-2+ | Integration test | §9 P8 |
| OPS-002 | Graceful shutdown implemented | SIL-2+ | Shutdown test | §9 P8 |
| OPS-003 | Structured logging (no print statements) | All | Lint rule | §9 P8 |
| OPS-004 | Rollback procedure documented and tested | SIL-2+ | Rollback test | §9 P8 |
| OPS-005 | CI/CD includes lint → test → build → deploy stages | All | Pipeline config validation | §9 P8 |
| OPS-006 | CI actions pinned to immutable SHAs | All | CI config audit | §9 P8 |
| OPS-007 | SLOs/SLIs defined and measurable | SIL-2+ | Metric existence check | §9 P8 |
| OPS-008 | Alerts configured with runbook links | SIL-2+ | Alert config audit | §9 P8 |
| OPS-009 | Reproducible container build (pinned images, lockfiles) | SIL-2+ | Docker build determinism test | §9 P8 |

### 2.5  Code Quality Controls (CQ)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| CQ-001 | Linter clean (ruff) | All | CI stage | §7 P6 |
| CQ-002 | Type checker clean (mypy strict) | All | CI stage | §7 P6 |
| CQ-003 | No silent exception swallowing | All | Lint rule + code review | §7 P6 |
| CQ-004 | Error handling includes context logging | SIL-2+ | Code review checklist | §7 P6 |
| CQ-005 | No unresolved stubs/placeholders (TODO without task ID) | All | Grep + CI gate | §7 P6 |
| CQ-006 | Thread safety reviewed for shared-state code | SIL-2+ | Code review + concurrency test | §7 P6 |
| CQ-007 | Boundary conditions reviewed | SIL-2+ | Code review checklist | §7 P6 |
| CQ-008 | Docstrings on all public APIs | All | Lint rule | Dev Env Spec |
| CQ-009 | Idempotency verified for side-effecting operations | SIL-2+ | Property-based test | §7 P6 strategy |
| CQ-010 | Multi-tenant isolation verified in data flows | SIL-2+ | RLS + isolation tests | §7 P6 strategy |

### 2.6  Governance Controls (GOV)

| ID | Control | SIL Threshold | Verification | Audit Checklist Ref |
|----|---------|---------------|--------------|---------------------|
| GOV-001 | ADR exists for every architectural decision | All | ADR inventory | Dev Env Spec §10 |
| GOV-002 | Every implementation traces to monograph concept (SIL-2+) | SIL-2+ | Glossary cross-reference | P2 pre-check |
| GOV-003 | HITL required for APS T2+ transitions | SIL-2+ | HITL gate test | K7 spec |
| GOV-004 | Config changes to dangerous keys require HITL | SIL-2+ | Config gate test | Config spec |
| GOV-005 | Celestial L0–L4 predicates are executable, not documentation | SIL-2+ | Predicate execution test | Goal Hierarchy Spec |
| GOV-006 | Every finding resolved or waived per policy | All | Finding register audit | §10 P9 |
| GOV-007 | Waivers have compensating controls + expiration + owner | All | Waiver register audit | §10 P9 |

---

## 3  Per-Task Test Governance Protocol

This protocol executes within P1 (Task Derivation) of the Development Procedure Graph. For EVERY task selected into a batch, the following derivation runs BEFORE any code is written.

### 3.1  Step 1: Control Applicability Matrix

For each task, determine which controls from §2 apply:

```
For ctrl in CONTROL_LIBRARY:
    if task.sil_level >= ctrl.sil_threshold:
        if ctrl.domain intersects task.affected_domains:
            mark ctrl as APPLICABLE
    else:
        mark ctrl as NOT_APPLICABLE (SIL below threshold)
```

**Affected domains** are derived from the task's component classification:

| Component Category | Applicable Domains |
|--------------------|--------------------|
| Kernel (K1–K8) | SEC, TST, ARC, CQ, GOV |
| Sandbox | SEC, TST, ARC, CQ |
| Egress | SEC, TST, ARC, CQ |
| Core (Goals, APS, Topology, Memory) | SEC, TST, ARC, CQ, GOV |
| Engine (Lanes, MCP, Workflow) | SEC, TST, ARC, CQ |
| Storage (PG, Redis, Chroma) | SEC, TST, ARC, OPS |
| API (Server, JWT, Routes, WS) | SEC, TST, ARC, OPS |
| Observability | TST, ARC, OPS |
| Config | TST, ARC, OPS, GOV |
| Console (UI) | TST, ARC, CQ |
| Agents (BaseAgent, Registry, Prompts) | SEC, TST, CQ, GOV |
| Constitution (Celestial, Terrestrial) | SEC, TST, GOV |
| Infra (Secrets, Docker, AWS) | SEC, OPS |

### 3.2  Step 2: Test Requirement Derivation

For each APPLICABLE control, derive the specific test requirement:

```
test_requirement = {
    ctrl_id: control.id,
    claim: "The system satisfies {control.description}",
    adversary: "Input/condition designed to violate {control.description}",
    verification_method: control.verification,
    test_type: classify(control)  // unit | integration | property | adversarial | formal
    falsification_required: task.sil_level >= SIL-2,
    evidence_artifact: "{test_file}:{test_function} → {ctrl_id}"
}
```

### 3.3  Step 3: Trace Chain Assembly

Every test requirement must participate in a complete trace chain:

```
Monograph Concept (Glossary Extract)
  → Requirement (ICD / Behavior Spec / Goal Hierarchy)
    → Control (this spec, §2)
      → Test (test file:function)
        → Finding (if test fails) or Evidence (if test passes)
```

The trace chain is recorded in the task's **trace_matrix_entries** field, which is appended to the project-level `trace_matrix.csv` when the task completes.

### 3.4  Step 4: Test Artifact Checklist

Before a task can exit P3C (Test Authoring), the following artifacts must exist:

#### SIL-3 Task Checklist

```
[ ] TLA+ spec written/updated (P3B)
[ ] TLC model check: zero violations
[ ] Hypothesis property-based tests: ≥3 properties per component
[ ] Unit tests: ≥95% branch coverage on touched code
[ ] Integration tests: every affected ICD interface exercised
[ ] Adversarial tests: ≥1 per identified failure mode (from FMEA)
[ ] Dissimilar verification: independent code path
[ ] Falsification ratio: negative tests ≥ positive tests
[ ] Concurrency tests: shared-state race condition coverage
[ ] Boundary tests: all bounded resources tested at/beyond limits
[ ] Regression test: fails on old behavior, passes on new
[ ] Trace chain: every test → control → requirement → monograph concept
[ ] No hardcoded credentials in test code
[ ] No live external calls (all mocked)
```

#### SIL-2 Task Checklist

```
[ ] Hypothesis property-based tests: ≥2 properties per component
[ ] Unit tests: ≥85% branch coverage on touched code
[ ] Integration tests: every affected ICD interface exercised
[ ] FMEA-driven tests: ≥1 per identified failure mode
[ ] Falsification: ≥1 negative test per positive test path
[ ] Concurrency tests: if component has shared state
[ ] Boundary tests: all bounded resources tested at/beyond limits
[ ] Regression test: fails on old behavior, passes on new
[ ] Trace chain: every test → control → requirement
[ ] No hardcoded credentials in test code
[ ] No live external calls (all mocked)
```

#### SIL-1 Task Checklist

```
[ ] Unit tests: ≥70% branch coverage on touched code
[ ] Integration tests: critical paths covered
[ ] Regression test: fails on old behavior, passes on new
[ ] No hardcoded credentials in test code
[ ] No live external calls (all mocked)
```

---

## 4  Agentic/AI-Specific Test Requirements

Holly is an autonomous agent platform. The audit checklist (§6 P5 agentic, §7 P6 agentic, §9 P8 agentic) defines additional test categories that apply to all agent-related components (Phases E, J, K).

### 4.1  Agentic Dynamic Security Tests

These tests apply to any task touching agents, LLM integration, MCP tools, or sandbox:

| Test | Applies To | Method | Audit Ref |
|------|-----------|--------|-----------|
| WebSocket origin bypass/CSWSH | API (WS channels) | Dynamic: forge Origin header, verify rejection | §6 P5 |
| Plugin endpoint unauthenticated access | MCP Registry | Dynamic: call tool endpoint without JWT | §6 P5 |
| Outbound LLM payload secret redaction | LLM Router, Egress | Dynamic: inject API key in prompt context, verify stripped before egress | §6 P5 |
| Capability manifest boundary violation | MCP permissions | Dynamic: agent invokes tool outside its mask | §6 P5 |
| Brute force simulation (HTTP + WS) | API Server | Dynamic: rapid auth attempts, verify lockout/rate-limit | §6 P5 |
| Prompt injection detection | Intent Classifier, Agents | Property-based: generate adversarial prompts, verify classification | §7 P6 |
| Guardrail bypass attempts | Safety layer | Adversarial: known jailbreak patterns against constitution predicates | §7 P6 |
| Loop detection | Workflow Engine | Dynamic: create circular goal dependency, verify detection and halt | §7 P6 |

### 4.2  Agentic Code Review Pipeline

When reviewing agent-related code (P6 in audit, P4 in procedure graph), apply the 5-stage agentic review:

```
S1: Structure analysis — agent lifecycle, message protocol, kernel binding
S2: Security analysis — prompt injection surface, tool permission scope, egress exposure
S3: Performance analysis — token budget, latency, concurrency limits
S4: Summary — quality score (1–10)
S5: Human escalation — if score < 5 or critical issue found
```

### 4.3  Agentic Operational Readiness

Before any agent-related phase gate (E, J, K), verify:

```
[ ] Security profiles enforced (dev/local-safe/lan-hardened)
[ ] Startup fail-closed checks on bad configuration
[ ] Canary triggers defined (abnormal tool invocation rate, permission violations)
[ ] Degradation behaviors defined (read-only fallback, tool kill-switch, HITL escalation)
[ ] Plugin/skill capability manifests match deployed permissions
```

---

## 5  Maturity Profile Progression

The audit checklist defines three maturity profiles (Early, Operational, Hardened). Holly's 15-slice spiral maps to this progression:

| Slices | Maturity Profile | Applicable Gates | Rationale |
|--------|-----------------|------------------|-----------|
| 1–5 (Phases A–D) | **Early** | Security Gate, Test Gate | Foundation being laid; <50 tests initially; single-dev context |
| 6–10 (Phases E–I) | **Operational** | Security Gate, Test Gate, Traceability Gate | Core + Engine operational; 50–500 tests; CI pipeline active |
| 11–15 (Phases J–N) | **Hardened** | Security Gate, Test Gate, Traceability Gate, Ops Gate | Full system; 500+ tests; prod-ready; release safety case |

### Gate Criteria by Maturity

#### Security Gate (all slices)
- Zero open Critical findings
- Zero open High findings OR all waived with compensating controls
- SEC-001 through SEC-015 applicable controls satisfied

#### Test Gate (all slices)
- TST-001: Full test suite zero failures
- TST-002: Coverage meets SIL thresholds
- TST-009/TST-010: No credentials/live calls in tests

#### Traceability Gate (slices 6+)
- Zero orphan Tier 1 controls (controls without tests)
- Zero orphan Tier 1 requirements (requirements without controls)
- Tier 1 trace coverage ≥ 90%

#### Ops Gate (slices 11+)
- OPS-001: Health endpoint meaningful
- OPS-004: Rollback documented and tested
- OPS-005: CI includes lint + test + build
- OPS-008: Critical alerts have runbook links

---

## 6  Continuous Monitoring Integration

The audit checklist §14 defines continuous monitoring. In Holly, this maps to the Observability layer (Phase I) and must be verified during Phases I–N.

### Canary Trigger Coverage (verified at Phase I gate)

| Trigger | Holly Component | Metric |
|---------|----------------|--------|
| Repeated auth failures per IP | JWT Middleware | `auth.failure.rate{ip}` |
| Abnormal tool invocation rate | MCP Registry | `mcp.invocation.rate{agent_id}` |
| Plugin permission violations | K2 Permission Gate | `kernel.k2.denied{agent_id}` |
| Outbound LLM secret pattern detection | Egress Control | `egress.redaction.triggered` |
| Exec denied spike | Sandbox | `sandbox.exec.denied.rate` |
| Goal predicate failure rate | K8 Eval Gate | `kernel.k8.failure.rate{predicate}` |
| Eigenspectrum divergence | Topology Manager | `topology.eigenspectrum.divergence` |

### Degradation Behavior Readiness (verified at Phase J+ gates)

| Behavior | Trigger Condition | Test |
|----------|-------------------|------|
| Read-only fallback | Persistent storage failure | Kill PG, verify system enters read-only |
| High-risk tool kill-switch | Repeated tool failures | Trigger 3 consecutive failures, verify tool disabled |
| HITL escalation | APS T2+ threshold crossed | Trigger threshold, verify human notification |
| Security event surfacing | Any SEC control violation | Trigger violation, verify console alert |

### Learning Loop (post-incident, ongoing)

```
For each incident or near-miss:
  1. Postmortem completed → lessons documented
  2. Regression test added (TST-012) → fails on old behavior
  3. Control library updated if new control needed
  4. Trace matrix updated with new test → control link
  5. This specification updated if gap identified
```

---

## 7  Test Artifact Production Requirements

### 7.1  Per-Task Artifacts

Every task that includes test authoring (which is every task, per this spec) must produce:

| Artifact | Format | Location | Content |
|----------|--------|----------|---------|
| Test files | `test_*.py` | `tests/{unit,integration,property,adversarial}/` | Executable tests |
| Control applicability record | Row in `trace_matrix.csv` | `docs/audit/trace_matrix.csv` | task_id → ctrl_ids → test_functions |
| Coverage delta | JSON | CI artifact | Per-file branch coverage before/after |
| Falsification evidence | Test output log | CI artifact | Negative test results demonstrating adversary failure |

### 7.2  Per-Slice Artifacts (at gate)

| Artifact | Format | Location | Content |
|----------|--------|----------|---------|
| `gate_assessment.csv` | CSV | `docs/audit/` | Per-gate pass/fail with evidence |
| `finding_register.csv` | CSV | `docs/audit/` | All findings from this slice (if any) |
| `kpi_snapshot.csv` | CSV | `docs/audit/` | Test count, coverage, flake rate, finding counts |

### 7.3  Per-Maturity-Transition Artifacts (at profile upgrade)

| Artifact | Format | Location | Content |
|----------|--------|----------|---------|
| `trace_matrix.csv` | CSV | `docs/audit/` | Full requirement → control → test chain |
| `control_library.csv` | CSV | `docs/audit/` | Active control inventory with status |
| `waiver_register.csv` | CSV | `docs/audit/` | Any accepted deviations with compensating controls |

---

## 8  Integration Points with Development Procedure Graph

This specification modifies the Development Procedure Graph at the following points:

### P1 (Task Derivation) — NEW SUBSTEP P1.6a

After P1.6 extracts task metadata, insert:

```
P1.6a  Test Governance Derivation (per Test_Governance_Spec.md §3):
  P1.6a.1  Build control applicability matrix (§3.1)
  P1.6a.2  Derive test requirements per applicable control (§3.2)
  P1.6a.3  Assemble trace chain stubs (§3.3)
  P1.6a.4  Select SIL-appropriate test artifact checklist (§3.4)
  P1.6a.5  Append to Task Batch: {test_requirements[], trace_stubs[],
            artifact_checklist, applicable_controls[], maturity_gates[]}
```

### P3C (Test Authoring) — ENHANCED

P3C now consumes the test governance derivation from P1.6a:

```
P3C.0  (NEW) Load test_requirements from P1.6a for each task
P3C.1  Author tests per test_requirements (not just per SIL level)
         - Each test must cite the ctrl_id it verifies
         - Each test must follow falsification-first protocol
         - Naming: test_{component}_{ctrl_id}_{adversary}_{expected}
P3C.5  (NEW) Verify artifact checklist completion (§3.4)
P3C.6  (NEW) Write trace_matrix_entries for all new tests
```

### P4 (Verification) — NEW SUBSTEP P4.5a

After acceptance criteria verification, insert:

```
P4.5a  Test Governance Compliance Check:
  P4.5a.1  All applicable controls have at least one test
  P4.5a.2  Falsification ratio meets SIL threshold (SIL-3: neg ≥ pos; SIL-2: neg ≥ 50% of pos)
  P4.5a.3  Trace chain complete: every test → control → requirement → (monograph concept if SIL-2+)
  P4.5a.4  No orphan tests (tests not linked to any control)
  P4.5a.5  No orphan controls (applicable controls without tests)
  P4.5a.6  Artifact checklist fully checked
  Gate: ALL must pass. On failure → return to P3C with specific gaps identified.
```

### P8 (Spiral Gate) — ENHANCED

Gate check now includes maturity-appropriate gates from §5:

```
P8.2.6  (NEW) Maturity gate evaluation:
           Slices 1–5:  Security Gate + Test Gate pass
           Slices 6–10: Security Gate + Test Gate + Traceability Gate pass
           Slices 11–15: All four gates pass (Security + Test + Traceability + Ops)
```

---

## 9  Procedure Self-Test (Meta-Validation)

At every phase gate (P9), run these self-test checks to verify the test governance framework itself is functioning:

```
ST-01  trace_matrix.csv exists and has ≥1 entry per applicable control domain
ST-02  control_library.csv includes all Tier 1 controls for current maturity profile
ST-03  trace_matrix.csv has zero orphan Tier 1 controls
ST-04  All findings have severity assigned
ST-05  Every Critical/High finding is resolved or waived per §2.6 GOV-006/GOV-007
ST-06  Every evidence file has SHA-256 hash in evidence_manifest
ST-07  All applicable release gates evaluated (§5)
ST-08  Test governance compliance check (P4.5a) has passed for every task in this slice
ST-09  Falsification ratio meets SIL threshold for every SIL-2+ task
ST-10  Audit duration (if full audit cycle ran) computable from timestamps
```

---

## 10  Canonical Fix Order

When test failures or findings require remediation, fixes follow this priority order (from audit checklist §11):

```
Priority 1: Immediate exposure / auth bypass / RCE
Priority 2: Isolation boundary hardening (tenant, sandbox, egress)
Priority 3: Trust boundary enforcement (JWT, RBAC, K2)
Priority 4: Data protection controls (redaction, PII, encryption)
Priority 5: Hardening controls (rate limits, bounds, input validation)
Priority 6: Supply chain and CI guarantees (pinned deps, immutable SHAs)
Priority 7: Continuous assurance controls (monitoring, alerting, canary)
```

Each fix follows the falsification-first validation cycle:

```
1. Write regression test that FAILS on old (broken) behavior
2. Verify regression test PASSES on fixed behavior
3. Add negative test (adversarial attempt that must be blocked)
4. Capture runtime enforcement evidence (logs/metrics) if applicable
```

---

*This document is consumed by the Development Procedure Graph at P1.6a, P3C, P4.5a, and P8.2.6. It is the binding specification for all test authoring in Holly Grace. The control library (§2) is the enumerated set of guarantees the system must maintain. The per-task protocol (§3) ensures no task completes without full governance coverage. The maturity progression (§5) ensures governance scales with system complexity.*
