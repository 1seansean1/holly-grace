# Holly Grace - Development Progress

_Generated: 2026-02-18_

| Slice | Phase | Done | Total | Progress | Critical Path |
|------:|-------|-----:|------:|---------:|---------------|
| 1 | Phase A Spiral (Steps 1, 2, 3, 3a) | 12 | 39 | 30% [###.......] | 12/12 |
| 2 | Phase A Backfill (Steps 4–11) | 5 | 39 | 12% [#.........] | 5/10 |
| 3 | Phase B: Failure Analysis & Kernel (Step | 0 | 62 | 0% [..........] | 0/19 |
| 4 | Phase C: Storage Layer (Steps 22–26) | 0 | 23 | 0% [..........] | 0/7 |
| 5 | Phase D: Safety & Infra (Steps 27–33) | 0 | 33 | 0% [..........] | 0/10 |
| 6 | Phase E: Core L2 (Steps 34–40) | 0 | 45 | 0% [..........] | 0/12 |
| 7 | Phase F: Engine L3 (Steps 41–45) | 0 | 24 | 0% [..........] | 0/6 |
| 8 | Phase G: Sandbox (Steps 46–50) | 0 | 29 | 0% [..........] | 0/10 |
| 9 | Phase H: API & Auth (Steps 51–56) | 0 | 24 | 0% [..........] | 0/8 |
| 10 | Phase I: Observability (Steps 57–61) | 0 | 21 | 0% [..........] | 0/7 |
| 11 | Phase J: Agents (Steps 62–65) | 0 | 25 | 0% [..........] | 0/10 |
| 12 | Phase K: Eval Infrastructure / EDDOps (S | 0 | 19 | 0% [..........] | 0/10 |
| 13 | Phase L: Config (Steps 70–72) | 0 | 12 | 0% [..........] | 0/4 |
| 14 | Phase M: Console L5 (Steps 73–78) | 0 | 18 | 0% [..........] | 0/7 |
| 15 | Phase N: Deploy & Ops (Steps 79–86) | 0 | 29 | 0% [..........] | 0/14 |
| **Σ** | **All** | **17** | **442** | **3%** | |

## Task Detail

| ID | Task | Status | Duration | Dependencies | Commit |
|---:|------|--------|----------|-------------|--------|
| | **Slice 1** | | | | |
| 1.1 | Map SAD terms to monograph definitions | pending | 0.5d |  |  |
| 1.2 | Preserve 42010 viewpoint structure | pending | 0.5d | 1.1 |  |
| 1.3 | Document quality attribute for extraction design | pending | 0.5d | 1.2 |  |
| 1.4 | Assign SIL to extraction pipeline | pending | 0.5d | 1.3 |  |
| 1.5 | Write SAD parser (mermaid → AST) | done (crit) | 1d | 1.4 | b829279 |
| 1.6 | Define architecture.yaml schema | done (crit) | 1d | 1.5 | b829279 |
| 1.7 | Build extraction pipeline | done (crit) | 1d | 1.6 | b829279 |
| 1.8 | Link YAML entries to SAD source lines | done (crit) | 0.5d | 1.7 | b829279 |
| 2.1 | Validate registry keys against monograph | pending | 0.5d |  |  |
| 2.2 | Expose per-viewpoint query API | pending | 0.5d | 2.1 |  |
| 2.3 | Document singleton/caching/thread-safety trade-off | pending | 0.5d | 2.2 |  |
| 2.4 | Assign SIL-2 | pending | 0.5d | 2.3 |  |
| 2.5 | Enumerate failure modes | pending | 0.5d | 2.4 |  |
| 2.6 | Implement singleton loader | done (crit) | 1d | 1.8, 2.5 |  |
| 2.7 | Implement component/boundary/ICD lookups | done (crit) | 1d | 2.6 |  |
| 2.8 | Implement hot-reload with validation | done (crit) | 1d | 2.7 |  |
| 2.9 | Link lookups to YAML source entries | pending | 0.5d | 2.8 |  |
| 3.1 | Map decorator names to monograph concepts | pending | 0.5d |  |  |
| 3.2 | Encode viewpoint membership in decorators | pending | 0.5d | 3.1 |  |
| 3.3 | Document decorator pattern trade-offs | pending | 0.5d | 3.2 |  |
| 3.4 | Assign SIL-2 | pending | 0.5d | 3.3 |  |
| 3.5 | Enumerate failure modes | pending | 0.5d | 3.4 |  |
| 3.6 | Implement core decorators | done (crit) | 1d | 2.8, 3.5 |  |
| 3.7 | Implement ICD contract enforcement | done (crit) | 1d | 3.6 | 6fb886b |
| 3.8 | Build AST scanner | pending | 1d | 3.7 |  |
| 3.9 | Map decorators to test requirements | pending | 0.5d | 3.8 |  |
| 3.10 | Verify decorators trigger kernel enforcement | pending | 1d | 3.9 |  |
| 3a.1 | Verify invariant names trace to monograph | pending | 0.5d |  |  |
| 3a.2 | Validate SAD → code path for one boundary | pending | 0.5d | 3a.1 |  |
| 3a.3 | Confirm quality attributes measurable in slice | pending | 0.5d | 3a.2 |  |
| 3a.4 | Assign verification method to gate | pending | 0.5d | 3a.3 |  |
| 3a.5 | Confirm SIL-3 rigor on kernel in slice | pending | 0.5d | 3a.4 |  |
| 3a.6 | Exercise ≥1 FMEA failure mode | pending | 0.5d | 3a.5 |  |
| 3a.7 | Write minimal TLA+ spec for K1 | pending | 1.5d | 3a.6 |  |
| 3a.8 | Validate full pipeline: YAML → registry → decorato | done (crit) | 1d | 3.7, 3a.7 |  |
| 3a.9 | Validate traceable chain for one requirement | pending | 0.5d | 3a.8 |  |
| 3a.10 | Implement minimal K8 eval gate | done (crit) | 1d | 3a.8, 3a.9 |  |
| 3a.11 | Verify kernel layer activates independently | pending | 1d | 3a.10 |  |
| 3a.12 | Run gate, produce pass/fail report | done (crit) | 0.5d | 3a.10, 3a.11 |  |
| | **Slice 2** | | | | |
| 10.1 | Define RTM schema | pending | 0.5d |  |  |
| 10.2 | Build RTM generator | pending (crit) | 0.5d | 9.2, 10.1 |  |
| 10.3 | Add gap detection | pending | 0.5d | 10.2 |  |
| 11.1 | Integrate drift, scanner, fitness, RTM into unifie | pending (crit) | 0.5d | 10.2 |  |
| 11.2 | Add staged canary for arch changes | pending | 0.5d | 11.1 |  |
| 11.3 | Define Phase A gate checklist | pending (crit) | 0.5d | 11.1, 11.2 |  |
| 11.4 | Implement ICD audit trail logging | pending | 0.5d | 11.3 |  |
| 4.1 | Verify package names trace to monograph | pending | 0.5d |  |  |
| 4.2 | Generate packages per 42010 viewpoint structure | pending | 0.5d | 4.1 |  |
| 4.3 | Document scaffold generation trade-offs | pending | 0.5d | 4.2 |  |
| 4.4 | Build scaffold generator from YAML | pending | 0.5d | 4.3 |  |
| 4.5 | Link packages to YAML components | pending | 0.5d | 4.4 |  |
| 5.1 | Map ICD terms to monograph boundary definitions | pending | 0.5d |  |  |
| 5.2 | Define ICD per 42010 boundary | pending | 0.5d | 5.1 |  |
| 5.3 | Document contract-vs-protocol trade-off | pending | 0.5d | 5.2 |  |
| 5.4 | Assign SIL per ICD based on connected components | pending | 0.5d | 5.3 |  |
| 5.5 | Implement ICD as Pydantic models | done (crit) | 0.5d | 5.8, 5.4 |  |
| 5.6 | Register ICDs in architecture.yaml | done (crit) | 0.5d | 5.5 |  |
| 5.7 | Link ICDs to SAD boundary crossings | pending | 0.5d |  |  |
| 5.8 | Build ICD Schema Registry | done (crit) | 0.5d | 5.7, 3a.12 |  |
| 5.9 | Implement ICD Validation Test Harness | pending | 0.5d | 5.8 |  |
| 5a.1 | Identify stakeholder scenarios | pending | 0.5d |  |  |
| 5a.2 | Evaluate architecture against scenarios | pending | 0.5d | 5a.1 |  |
| 5a.3 | Document ATAM verification results | pending | 0.5d | 5a.2 |  |
| 5a.4 | Link ATAM risks to fitness function parameters | pending | 0.5d | 5a.3 |  |
| 6.1 | Build drift detector | pending | 0.5d |  |  |
| 6.2 | Define drift severity levels | pending | 0.5d | 6.1 |  |
| 6.3 | Wire drift detection into CI pipeline | pending | 0.5d | 6.2 |  |
| 7.1 | Extend AST scanner with per-module rules | done (crit) | 0.5d | 5.6 |  |
| 7.2 | Add wrong-decorator detection | done (crit) | 0.5d | 7.1 |  |
| 7.3 | Wire scanner into CI pipeline | pending | 0.5d | 7.2 |  |
| 8.1 | Assign verification methods to arch contracts | pending | 0.5d |  |  |
| 8.2 | Implement SIL-appropriate test levels | pending | 0.5d | 8.1 |  |
| 8.3 | Write contract fixture generator | pending (crit) | 0.5d | 7.2, 8.2 |  |
| 8.4 | Map tests to decorators and requirements | pending | 0.5d | 8.3 |  |
| 9.1 | Derive fitness function parameters from ATAM | pending | 0.5d |  |  |
| 9.2 | Implement fitness functions | pending (crit) | 0.5d | 8.3, 9.1 |  |
| 9.3 | Wire into CI as per-commit checks | pending | 0.5d | 9.2 |  |
| 9.4 | Implement ICD-specific fitness functions | pending | 0.5d | 9.3 |  |
| | **Slice 3** | | | | |
| 12.1 | Classify every component by failure consequence | pending | 0.5d |  |  |
| 12.2 | Define verification requirements per SIL | pending | 0.5d | 12.1 |  |
| 12.3 | Link SIL assignments to YAML components | pending | 0.5d | 12.2 |  |
| 13.1 | FMEA: kernel invariant desynchronization | pending (crit) | 0.5d | 11.3 |  |
| 13.2 | FMEA: sandbox escape | pending | 0.5d | 13.1 |  |
| 13.3 | FMEA: egress bypass | pending | 0.5d | 13.2 |  |
| 13.4 | FMEA: goal injection (L0–L4 predicate violation) | pending | 0.5d | 13.3 |  |
| 13.5 | FMEA: topology desynchronization | pending | 0.5d | 13.4 |  |
| 13.6 | Compile residual risk register | pending | 0.5d | 13.5 |  |
| 13.7 | Link FMEA mitigations to roadmap steps | pending | 0.5d | 13.6 |  |
| 14.1 | TLA+ spec: kernel invariant state machine | pending (crit) | 1.5d | 13.1 |  |
| 14.2 | TLA+ spec: sandbox isolation | pending | 1.5d | 14.1 |  |
| 14.3 | TLA+ spec: egress filter pipeline | pending | 1.5d | 14.2 |  |
| 14.4 | Document assumption register | pending | 1.5d | 14.3 |  |
| 14.5 | Implement formal state-machine validator | pending (crit) | 1.5d | 14.1, 14.4 |  |
| 15.1 | Map KernelContext to monograph boundary concepts | pending | 0.5d |  |  |
| 15.2 | Confirm SIL-3 designation | pending | 0.5d | 15.1 |  |
| 15.3 | Review FMEA mitigations for kernel context lifecyc | pending | 0.5d | 15.2 |  |
| 15.4 | Implement per TLA+ state machine spec | pending (crit) | 1.5d | 14.5, 15.3 |  |
| 15.5 | Register in architecture.yaml, add decorator | pending | 1d | 15.4 |  |
| 15.6 | Link to requirement and test | pending | 0.5d | 15.5 |  |
| 15.7 | Verify independence from downstream layers | pending | 1d | 15.6 |  |
| 16.1 | Map K1–K4 to monograph channel constraints | pending | 0.5d |  |  |
| 16.2 | Review FMEA mitigations for K1–K4 | pending | 0.5d | 16.1 |  |
| 16.3 | Implement K1 schema validation per TLA+ | pending (crit) | 1.5d | 15.4, 16.2 |  |
| 16.4 | Implement K2 permission gating per TLA+ | pending (crit) | 1.5d | 16.3 |  |
| 16.5 | Implement K3 bounds checking per TLA+ | pending (crit) | 1.5d | 16.4 |  |
| 16.6 | Implement K4 trace injection per TLA+ | pending (crit) | 1.5d | 16.5 |  |
| 16.7 | Register K1–K4 in YAML, apply decorators | pending | 1d | 16.6 |  |
| 16.8 | Link each to requirement and test | pending | 0.5d | 16.7 |  |
| 16.9 | Verify K1–K4 Guard Condition Determinism | pending (crit) | 1.5d | 16.6, 16.8 |  |
| 17.1 | Map K5–K6 to monograph | pending | 0.5d |  |  |
| 17.2 | Review FMEA mitigations | pending | 0.5d | 17.1 |  |
| 17.3 | Implement K5 idempotency (RFC 8785) per TLA+ | pending (crit) | 1.5d | 16.9, 17.2 |  |
| 17.4 | Implement K6 audit WAL per TLA+ | pending (crit) | 1.5d | 17.3 |  |
| 17.5 | Register, decorate | pending | 1d | 17.4 |  |
| 17.6 | Link to requirements and tests | pending | 0.5d | 17.5 |  |
| 17.7 | Verify K5–K6 Invariant Preservation | pending (crit) | 1.5d | 17.4, 17.6 |  |
| 18.1 | Map K7–K8 to monograph goal hierarchy | pending | 0.5d |  |  |
| 18.2 | Review FMEA mitigations | pending | 0.5d | 18.1 |  |
| 18.3 | Implement K7 HITL gate per TLA+ | pending (crit) | 1.5d | 17.7, 18.2 |  |
| 18.4 | Implement K8 eval gate per TLA+ | pending (crit) | 1.5d | 18.3 |  |
| 18.5 | Define eval predicate interface | pending | 1d | 18.4 |  |
| 18.6 | Verify K7+K8 as independent safety layers | pending | 1d | 18.5 |  |
| 18.7 | Register, decorate | pending | 1d | 18.6 |  |
| 18.8 | Link to requirements and tests | pending | 0.5d | 18.7 |  |
| 18.9 | Verify K7–K8 Failure Isolation | pending (crit) | 1.5d | 18.4, 18.8 |  |
| 19.1 | Map exception hierarchy to monograph failure conce | pending | 0.5d |  |  |
| 19.2 | Inherit SIL-3 from kernel | pending | 0.5d | 19.1 |  |
| 19.3 | Implement exception classes | pending | 1d | 19.2 |  |
| 19.4 | Link to requirements | pending | 0.5d | 19.3 |  |
| 20.1 | Design dissimilar channel from FMEA | pending | 0.5d |  |  |
| 20.2 | Formally verify independence | pending | 1.5d | 20.1 |  |
| 20.3 | Implement dissimilar verification channel | pending (crit) | 1d | 18.9, 20.2 |  |
| 20.4 | Link to requirement and test | pending | 0.5d | 20.3 |  |
| 20.5 | Verify Dissimilar Verifier State Machine | pending (crit) | 1.5d | 20.3, 20.4 |  |
| 21.1 | Assign verification methods per SIL-3 | pending | 0.5d |  |  |
| 21.2 | Execute SIL-3 verification | pending (crit) | 0.5d | 20.5, 21.1 |  |
| 21.3 | Run TLA+ model checker against all kernel specs | pending | 1.5d | 21.2 |  |
| 21.4 | Validate RTM completeness for kernel | pending | 0.5d | 21.3 |  |
| 21.5 | Independent review of kernel safety | pending | 1d | 21.4 |  |
| 21.6 | Define Phase B gate checklist | pending (crit) | 0.5d | 21.2, 21.5 |  |
| | **Slice 4** | | | | |
| 22.1 | Map storage concepts to monograph (memory tiers, M | pending | 0.5d |  |  |
| 22.2 | Document storage architecture trade-offs | pending | 0.5d | 22.1 |  |
| 22.3 | Assign SIL-2 | pending | 0.5d | 22.2 |  |
| 22.4 | FMEA: connection pool exhaustion, RLS bypass, migr | pending | 0.5d | 22.3 |  |
| 22.5 | Implement async pool, models, RLS, migrations | pending (crit) | 0.5d | 22.4, 21.6 |  |
| 22.6 | Link to requirement and test | pending | 0.5d | 22.5 |  |
| 22.7 | Apply RLS per ICD Boundary | pending (crit) | 0.5d | 22.5, 22.6 |  |
| 23.1 | Inherit SIL-2 | pending | 0.5d |  |  |
| 23.2 | FMEA: orphan partition, failed archival, restore f | pending | 0.5d | 23.1 |  |
| 23.3 | Implement time-based partitions, auto-create, S3 a | pending (crit) | 0.5d | 22.7, 23.2 |  |
| 23.4 | Link to requirement and test | pending | 0.5d | 23.3 |  |
| 24.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 24.2 | FMEA: cache poisoning, pub/sub message loss, HA fa | pending | 0.5d | 24.1 |  |
| 24.3 | Implement pool, pub/sub, queues, cache, HA | pending (crit) | 0.5d | 23.3, 24.2 |  |
| 24.4 | Link to requirement and test | pending | 0.5d | 24.3 |  |
| 25.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 25.2 | FMEA: embedding drift, cross-tenant retrieval, col | pending | 0.5d | 25.1 |  |
| 25.3 | Implement client, tenant-isolated collections, emb | pending (crit) | 0.5d | 24.3, 25.2 |  |
| 25.4 | Link to requirement and test | pending | 0.5d | 25.3 |  |
| 26.1 | Assign SIL-2 verification methods | pending | 0.5d |  |  |
| 26.2 | Execute SIL-2 test suite | pending (crit) | 0.5d | 25.3, 26.1 |  |
| 26.3 | Validate RTM completeness for storage | pending | 0.5d | 26.2 |  |
| 26.4 | Phase C gate checklist | pending (crit) | 0.5d | 26.2, 26.3 |  |
| | **Slice 5** | | | | |
| 27.1 | Map redaction to monograph channel filtering | pending | 0.5d |  |  |
| 27.2 | Assign SIL-2 | pending | 0.5d | 27.1 |  |
| 27.3 | FMEA: incomplete redaction, redaction bypass via e | pending | 0.5d | 27.2 |  |
| 27.4 | Implement canonical redaction library | pending (crit) | 1d | 27.3, 26.4 |  |
| 27.5 | Link to requirement and test | pending | 0.5d | 27.4 |  |
| 28.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 28.2 | FMEA: sanitization bypass, injection via unicode,  | pending | 0.5d | 28.1 |  |
| 28.3 | Implement input sanitization, output redaction, in | pending (crit) | 1d | 27.4, 28.2 |  |
| 28.4 | Link to requirement and test | pending | 0.5d | 28.3 |  |
| 29.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 29.2 | FMEA: forbidden path bypass, incomplete code analy | pending | 0.5d | 29.1 |  |
| 29.3 | Implement forbidden paths, code review analysis | pending | 1d | 29.2 |  |
| 29.4 | Link | pending | 0.5d | 29.3 |  |
| 30.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 30.2 | FMEA: undetected secret pattern, false redaction o | pending | 0.5d | 30.1 |  |
| 30.3 | Implement detect + redact in traces per ICD-v0.1 r | pending (crit) | 1d | 28.3, 30.2 |  |
| 30.4 | Link | pending | 0.5d | 30.3 |  |
| 31.1 | Map egress to monograph channel boundary | pending | 0.5d |  |  |
| 31.2 | Assign SIL-3 | pending | 0.5d | 31.1 |  |
| 31.3 | FMEA: allowlist circumvention, redaction failure,  | pending | 0.5d | 31.2 |  |
| 31.4 | Implement per TLA+ egress spec | pending (crit) | 1.5d | 30.3, 31.3 |  |
| 31.5 | Verify egress as independent safety layer | pending (crit) | 1d | 31.4 |  |
| 31.6 | Link | pending | 0.5d | 31.5 |  |
| 31.7 | Verify Egress Filter Pipeline Guarantees | pending (crit) | 1.5d | 31.5, 31.6 |  |
| 32.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 32.2 | FMEA: key rotation failure, credential leak, vault | pending | 0.5d | 32.1 |  |
| 32.3 | Implement KMS/Vault client, rotation, credential s | pending | 1d | 32.2 |  |
| 32.4 | Link | pending | 0.5d | 32.3 |  |
| 33.1 | Aggregate FMEA results for D.27–D.32 | pending (crit) | 0.5d | 31.7 |  |
| 33.2 | Build structured safety argument | pending (crit) | 1d | 33.1 |  |
| 33.3 | Link safety case to FMEA and test artifacts | pending | 0.5d | 33.2 |  |
| 33.4 | Phase D gate checklist | pending (crit) | 0.5d | 33.5, 33.3 |  |
| 33.5 | Integrate all 49 ICDs into Phase D Safety Case | pending (crit) | 0.5d | 33.2 |  |
| | **Slice 6** | | | | |
| 34.1 | Map conversation to monograph channel theory | pending | 0.5d |  |  |
| 34.2 | Assign SIL-2 | pending | 0.5d | 34.1 |  |
| 34.3 | FMEA: WS connection hijack, message injection, rep | pending | 0.5d | 34.2 |  |
| 34.4 | Implement bidirectional WS chat per ICD-008, decor | pending | 0.5d | 34.3 |  |
| 34.5 | Link | pending | 0.5d | 34.4 |  |
| 35.1 | Map intent classification to monograph digital bra | pending | 0.5d |  |  |
| 35.2 | Assign SIL-2 | pending | 0.5d | 35.1 |  |
| 35.3 | FMEA: misclassification, prompt injection to force | pending | 0.5d | 35.2 |  |
| 35.4 | Implement classifier per ICD-009 (Intent → Goals), | pending | 0.5d | 35.3 |  |
| 35.5 | Register, decorate per ICD-009 | pending | 0.5d | 35.4 |  |
| 35.6 | Link | pending | 0.5d | 35.5 |  |
| 36.1 | Map to monograph goal predicate sets, codimension  | pending | 0.5d |  |  |
| 36.2 | Assign SIL-2 | pending | 0.5d | 36.1 |  |
| 36.3 | FMEA: goal injection, Celestial override, codimens | pending | 0.5d | 36.2 |  |
| 36.4 | Implement 7-level hierarchy + lexicographic gating | pending (crit) | 0.5d | 36.9, 36.3 |  |
| 36.5 | Implement Celestial L0–L4 as executable predicates | pending (crit) | 0.5d | 36.4 |  |
| 36.6 | Register, decorate per ICD-010 | pending | 0.5d |  |  |
| 36.7 | Link | pending | 0.5d | 36.6 |  |
| 36.8 | Implement L0–L4 Predicate Functions | pending (crit) | 0.5d | 36.7, 33.4 |  |
| 36.9 | Validate L0–L4 Predicates with Property-Based Test | pending (crit) | 0.5d | 36.8 |  |
| 37.1 | Map to monograph agency rank, cognitive light cone | pending | 0.5d |  |  |
| 37.2 | Assign SIL-2 | pending | 0.5d | 37.1 |  |
| 37.3 | FMEA: wrong tier classification, Assembly Index ov | pending | 0.5d | 37.2 |  |
| 37.4 | Implement T0–T3 classification + Assembly Index pe | pending (crit) | 0.5d | 36.5, 37.3 |  |
| 37.5 | Register, decorate per ICD-011 | pending | 0.5d | 37.4 |  |
| 37.6 | Link | pending | 0.5d | 37.5 |  |
| 37.7 | Validate APS Assembly Index per Goal Hierarchy Age | pending (crit) | 0.5d | 37.4, 37.6 |  |
| 38.1 | Map to monograph steering operators, assignment ma | pending | 0.5d |  |  |
| 38.2 | Assign SIL-2 | pending | 0.5d | 38.1 |  |
| 38.3 | FMEA: stale topology, eigenspectrum blind spot, st | pending | 0.5d | 38.2 |  |
| 38.4 | Implement spawn/steer/dissolve, contracts, eigensp | pending (crit) | 0.5d | 37.7, 38.3 |  |
| 38.5 | Register, decorate per ICD-012/015 | pending | 0.5d | 38.4 |  |
| 38.6 | Link | pending | 0.5d | 38.5 |  |
| 38.7 | Implement Eigenspectrum Monitor per Goal Hierarchy | pending | 0.5d | 38.6 |  |
| 38.8 | Verify Steer Operations maintain Contract Satisfac | pending (crit) | 0.5d | 38.4, 38.7 |  |
| 39.1 | Map to monograph K-scope crystallisation, memory t | pending | 0.5d |  |  |
| 39.2 | Assign SIL-2 | pending | 0.5d | 39.1 |  |
| 39.3 | FMEA: cross-tenant memory leak, crystallisation co | pending | 0.5d | 39.2 |  |
| 39.4 | Implement 3-tier: short (Redis via ICD-041), mediu | pending (crit) | 0.5d | 38.8, 39.3 |  |
| 39.5 | Link | pending | 0.5d | 39.4 |  |
| 40.1 | Assign SIL-2 verification methods | pending | 0.5d |  |  |
| 40.2 | Execute SIL-2 test suite | pending (crit) | 0.5d | 39.4, 40.1 |  |
| 40.3 | Run all Core eval suites | pending (crit) | 0.5d | 40.2 |  |
| 40.4 | Validate RTM completeness for Core | pending | 0.5d | 40.3 |  |
| 40.5 | Phase E gate checklist | pending (crit) | 0.5d | 40.3, 40.4 |  |
| | **Slice 7** | | | | |
| 41.1 | Map to monograph channel composition, macro-channe | pending | 0.5d |  |  |
| 41.2 | Assign SIL-2 | pending | 0.5d | 41.1 |  |
| 41.3 | FMEA: lane starvation, policy deadlock, dispatcher | pending | 0.5d | 41.2 |  |
| 41.4 | Implement lane manager, policy engine, dispatchers | pending (crit) | 0.5d | 41.3, 40.5 |  |
| 41.5 | Link | pending | 0.5d | 41.4 |  |
| 42.1 | Map to monograph tool permission masks, channel co | pending | 0.5d |  |  |
| 42.2 | Assign SIL-2 | pending | 0.5d | 42.1 |  |
| 42.3 | FMEA: permission escalation, tool introspection le | pending | 0.5d | 42.2 |  |
| 42.4 | Implement registry per ICD-019/020, per-agent perm | pending (crit) | 0.5d | 41.4, 42.3 |  |
| 42.5 | Link | pending | 0.5d | 42.4 |  |
| 43.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 43.2 | FMEA per builtin: code (sandbox escape via gRPC pe | pending | 0.5d | 43.1 |  |
| 43.3 | Implement code (gRPC→sandbox per ICD-022), web (HT | pending (crit) | 0.5d | 42.4, 43.2 |  |
| 43.4 | Link | pending | 0.5d | 43.3 |  |
| 44.1 | Map to monograph durable execution, compensation | pending | 0.5d |  |  |
| 44.2 | Document saga vs orchestration trade-off | pending | 0.5d | 44.1 |  |
| 44.3 | Assign SIL-2 | pending | 0.5d | 44.2 |  |
| 44.4 | FMEA: saga partial failure, dead-letter overflow,  | pending | 0.5d | 44.3 |  |
| 44.5 | Implement durable engine per ICD-021, saga, compen | pending (crit) | 0.5d | 43.3, 44.4 |  |
| 44.6 | Link | pending | 0.5d | 44.5 |  |
| 45.1 | Assign SIL-2 verification methods | pending | 0.5d |  |  |
| 45.2 | Execute SIL-2 test suite | pending (crit) | 0.5d | 44.5, 45.1 |  |
| 45.3 | Validate RTM completeness | pending | 0.5d | 45.2 |  |
| 45.4 | Phase F gate checklist | pending (crit) | 0.5d | 45.2, 45.3 |  |
| | **Slice 8** | | | | |
| 46.1 | Map to monograph Markov blanket isolation | pending | 0.5d |  |  |
| 46.2 | Document minimal-image trade-offs per Behavior Spe | pending | 0.5d | 46.1 |  |
| 46.3 | Assign SIL-3 | pending | 0.5d | 46.2 |  |
| 46.4 | FMEA per Behavior Spec §2: image supply-chain atta | pending | 0.5d | 46.3 |  |
| 46.5 | Build minimal container: no network, no Holly deps | pending (crit) | 1d | 46.4, 45.4 |  |
| 46.6 | Link | pending | 0.5d | 46.5 |  |
| 47.1 | Inherit SIL-3 | pending | 0.5d |  |  |
| 47.2 | FMEA per Behavior Spec §2: proto deserialization a | pending | 0.5d | 47.1 |  |
| 47.3 | Implement per TLA+ sandbox spec per Behavior Spec  | pending (crit) | 1.5d | 46.5, 47.2 |  |
| 47.4 | Link | pending | 0.5d | 47.3 |  |
| 47.5 | Validate gRPC Proto Constraints per ICD-022 | pending (crit) | 1.5d | 47.3, 47.4 |  |
| 48.1 | Inherit SIL-3 | pending | 0.5d |  |  |
| 48.2 | FMEA per Behavior Spec §2: namespace leak, seccomp | pending | 0.5d | 48.1 |  |
| 48.3 | Implement per TLA+ isolation spec per Behavior Spe | pending (crit) | 1.5d | 47.5, 48.2 |  |
| 48.4 | Verify isolation as independent safety layer per B | pending | 1d | 48.3 |  |
| 48.5 | Verify Isolation Invariant Preservation per Behavi | pending (crit) | 1.5d | 48.3, 48.4 |  |
| 48.6 | Link | pending | 0.5d | 48.5 |  |
| 49.1 | Document gVisor vs Firecracker trade-off per Behav | pending | 0.5d |  |  |
| 49.2 | Inherit SIL-3 | pending | 0.5d | 49.1 |  |
| 49.3 | FMEA per Behavior Spec §2: runtime-specific escape | pending | 0.5d | 49.2 |  |
| 49.4 | Implement production runtime configs per Behavior  | pending (crit) | 1d | 48.5, 49.3 |  |
| 49.5 | Adversarial Runtime Escape Testing per Behavior Sp | pending (crit) | 1.5d | 49.4 |  |
| 49.6 | Link | pending | 0.5d | 49.5 |  |
| 50.1 | Assign SIL-3 verification methods per Behavior Spe | pending | 0.5d |  |  |
| 50.2 | Execute SIL-3 test suite per Behavior Spec §2 Acce | pending (crit) | 0.5d | 49.5, 50.1 |  |
| 50.3 | Run TLA+ model checker against sandbox spec per Be | pending (crit) | 1.5d | 50.2 |  |
| 50.4 | Independent review of sandbox safety per Behavior  | pending | 1d | 50.3 |  |
| 50.5 | Validate RTM completeness | pending | 0.5d | 50.4 |  |
| 50.6 | Phase G gate checklist | pending (crit) | 0.5d | 50.3, 50.5 |  |
| | **Slice 9** | | | | |
| 51.1 | Document middleware stack trade-offs | pending | 0.5d |  |  |
| 51.2 | Assign SIL-2 | pending | 0.5d |  |  |
| 51.3 | FMEA: middleware bypass, request smuggling per ICD | pending | 0.5d |  |  |
| 51.4 | Implement Starlette app factory per ICD-001/002/00 | pending (crit) | 0.5d | 50.6 |  |
| 51.5 | Link | pending | 0.5d |  |  |
| 52.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 52.2 | FMEA: JWKS cache poisoning, token replay, revocati | pending | 0.5d |  |  |
| 52.3 | Implement JWKS verification per ICD-047, claims ex | pending (crit) | 0.5d | 51.4 |  |
| 52.4 | Link | pending | 0.5d |  |  |
| 53.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 53.2 | FMEA: privilege escalation, role confusion, claim  | pending | 0.5d |  |  |
| 53.3 | Implement RBAC enforcement from JWT claims per K2 | pending (crit) | 0.5d | 52.3 |  |
| 53.4 | Link | pending | 0.5d |  |  |
| 54.1 | Implement routes per ICD-003/023/024/025/026/027/0 | pending (crit) | 0.5d | 53.3 |  |
| 54.2 | Link | pending | 0.5d |  |  |
| 55.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 55.2 | FMEA: WS hijack, cross-tenant channel leak, re-aut | pending | 0.5d |  |  |
| 55.3 | Implement WS manager per ICD-025/027, 9 channels,  | pending (crit) | 0.5d | 54.1 |  |
| 55.4 | Link | pending | 0.5d |  |  |
| 56.1 | Assign SIL-2 verification methods | pending | 0.5d |  |  |
| 56.2 | Execute SIL-2 test suite per ICD routes | pending (crit) | 0.5d | 55.3 |  |
| 56.3 | Validate RTM completeness | pending | 0.5d |  |  |
| 56.4 | Phase H gate checklist | pending (crit) | 0.5d | 56.5 |  |
| 56.5 | Verify All 49 ICDs have Corresponding API Routes o | pending (crit) | 0.5d | 56.2 |  |
| | **Slice 10** | | | | |
| 57.1 | Map event bus to monograph channel composition | pending | 0.5d |  |  |
| 57.2 | Assign SIL-2 | pending | 0.5d |  |  |
| 57.3 | FMEA: event loss, backpressure failure, fanout cro | pending | 0.5d |  |  |
| 57.4 | Implement unified ingest per ICD-023/024, sampling | pending (crit) | 0.5d | 56.4 |  |
| 57.5 | Link | pending | 0.5d |  |  |
| 58.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 58.2 | Implement structured JSON logger per ICD-026, corr | pending (crit) | 0.5d | 57.4 |  |
| 58.3 | Link | pending | 0.5d |  |  |
| 59.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 59.2 | FMEA: trace payload leak, decision tree corruption | pending | 0.5d |  |  |
| 59.3 | Implement decision tree persistence per ICD-025, r | pending (crit) | 0.5d | 58.2 |  |
| 59.4 | Link | pending | 0.5d |  |  |
| 60.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 60.2 | Implement Prometheus collectors | pending (crit) | 0.5d | 59.3 |  |
| 60.3 | Link | pending | 0.5d |  |  |
| 61.1 | Assign SIL-2 | pending | 0.5d |  |  |
| 61.2 | Implement PG (partitioned per ICD-036) + Redis (re | pending (crit) | 0.5d | 60.2 |  |
| 61.3 | Link | pending | 0.5d |  |  |
| 61.4 | Validate RTM completeness for observability | pending | 0.5d |  |  |
| 61.5 | Phase I gate checklist | pending (crit) | 0.5d | 61.6 |  |
| 61.6 | Implement Observability Trace Correlation per ICD  | pending (crit) | 0.5d | 61.2 |  |
| | **Slice 11** | | | | |
| 62.1 | Map BaseAgent to monograph agency rank, digital br | pending | 0.5d |  |  |
| 62.2 | Document agent lifecycle trade-offs | pending | 0.5d |  |  |
| 62.3 | Assign SIL-2 | pending | 0.5d |  |  |
| 62.4 | FMEA: lifecycle leak, message protocol desync, ker | pending | 0.5d |  |  |
| 62.5 | Implement BaseAgent: lifecycle, message protocol p | pending (crit) | 0.5d | 61.5 |  |
| 62.6 | Register, decorate | pending | 0.5d |  |  |
| 62.7 | Link | pending | 0.5d |  |  |
| 63.1 | Map agent types to monograph competency continuum  | pending | 0.5d |  |  |
| 63.2 | Assign SIL-2 | pending | 0.5d |  |  |
| 63.3 | FMEA: unregistered agent call, capability mismatch | pending | 0.5d |  |  |
| 63.4 | Implement type catalog, capability declarations wi | pending (crit) | 0.5d | 62.5 |  |
| 63.5 | Link | pending | 0.5d |  |  |
| 64.1 | Map prompt roles to monograph agency types per Goa | pending | 0.5d |  |  |
| 64.2 | Implement Holly, researcher, builder, reviewer, pl | pending (crit) | 0.5d | 63.4 |  |
| 64.3 | Establish eval baselines | pending (crit) | 0.5d | 64.2 |  |
| 64.4 | Link | pending | 0.5d |  |  |
| 65.1 | Map Celestial/Terrestrial to monograph goal hierar | pending | 0.5d |  |  |
| 65.2 | Implement Celestial L0–L4 as executable predicate  | pending (crit) | 0.5d | 64.3 |  |
| 65.3 | Implement Terrestrial L5–L6 as executable goal spe | pending | 0.5d |  |  |
| 65.4 | Build constitution eval suite per Goal Hierarchy § | pending (crit) | 0.5d | 65.9 |  |
| 65.5 | Link | pending | 0.5d |  |  |
| 65.6 | Phase J gate checklist | pending (crit) | 0.5d | 65.4 |  |
| 65.7 | Implement Terrestrial L5–L6 Predicate Functions pe | pending (crit) | 0.5d | 65.2 |  |
| 65.8 | Verify Lexicographic Gating Enforcement per Goal H | pending (crit) | 0.5d | 65.7 |  |
| 65.9 | Implement Multi-Agent Feasibility Checker per Goal | pending (crit) | 0.5d | 65.8 |  |
| | **Slice 12** | | | | |
| 66.1 | Design eval harness architecture | pending | 0.5d |  |  |
| 66.2 | Implement eval framework harness | pending (crit) | 0.5d | 65.6 |  |
| 66.3 | Implement dataset loaders | pending (crit) | 0.5d | 66.2 |  |
| 66.4 | Implement metric collectors + regression tracker | pending (crit) | 0.5d | 66.3 |  |
| 66.5 | Assign verification methods for eval framework | pending | 0.5d |  |  |
| 66.6 | Link | pending | 0.5d |  |  |
| 67.1 | Build per-agent property-based eval suites per Goa | pending (crit) | 0.5d | 66.4 |  |
| 67.2 | Build adversarial eval suites per Goal Hierarchy C | pending (crit) | 0.5d | 67.1 |  |
| 67.3 | Establish production baselines per Goal Hierarchy  | pending (crit) | 0.5d | 67.2 |  |
| 67.4 | Link | pending | 0.5d |  |  |
| 68.1 | Implement constitution gate per Goal Hierarchy §2. | pending (crit) | 0.5d | 67.3 |  |
| 68.2 | Verify gate enforces lexicographic ordering per Go | pending | 0.5d |  |  |
| 68.3 | Link | pending | 0.5d |  |  |
| 68.4 | Integrate Constitution Gate with K8 Eval Gate | pending (crit) | 0.5d | 68.1 |  |
| 69.1 | Implement eval CI pipeline stage | pending (crit) | 0.5d | 68.4 |  |
| 69.2 | Verify eval CI as formal verification activity | pending | 0.5d |  |  |
| 69.3 | Link | pending | 0.5d |  |  |
| 69.4 | Validate RTM completeness for EDDOps | pending | 0.5d |  |  |
| 69.5 | Phase K gate checklist | pending (crit) | 0.5d | 69.1 |  |
| | **Slice 13** | | | | |
| 70.1 | Assign SIL-1 | pending | 0.5d |  |  |
| 70.2 | Implement Pydantic env-driven config | pending (crit) | 0.5d | 69.5 |  |
| 70.3 | Link | pending | 0.5d |  |  |
| 71.1 | Inherit SIL-1 | pending | 0.5d |  |  |
| 71.2 | Implement runtime hot reload without restart | pending (crit) | 0.5d | 70.2 |  |
| 71.3 | Link | pending | 0.5d |  |  |
| 72.1 | Inherit SIL-1 | pending | 0.5d |  |  |
| 72.2 | FMEA: dangerous key change without HITL, rollback  | pending | 0.5d |  |  |
| 72.3 | Implement change logging, HITL on dangerous keys,  | pending (crit) | 0.5d | 71.2 |  |
| 72.4 | Link | pending | 0.5d |  |  |
| 72.5 | Validate RTM completeness | pending | 0.5d |  |  |
| 72.6 | Phase L gate checklist | pending (crit) | 0.5d | 72.3 |  |
| | **Slice 14** | | | | |
| 73.1 | Assign SIL-1 | pending | 0.5d |  |  |
| 73.2 | Document frontend stack trade-offs | pending | 0.5d |  |  |
| 73.3 | Scaffold React + Vite + Tailwind + Zustand | pending (crit) | 0.5d | 72.6 |  |
| 73.4 | Link | pending | 0.5d |  |  |
| 74.1 | Implement chat panel per ICD-025/027, message bubb | pending (crit) | 0.5d | 73.3 |  |
| 74.2 | Link | pending | 0.5d |  |  |
| 75.1 | Map topology viz to monograph morphogenetic concep | pending | 0.5d |  |  |
| 75.2 | Implement live agent graph, contract cards per Goa | pending (crit) | 0.5d | 74.1 |  |
| 75.3 | Link | pending | 0.5d |  |  |
| 76.1 | Map goal viz to monograph Celestial/Terrestrial hi | pending | 0.5d |  |  |
| 76.2 | Implement tree explorer, celestial badges per Goal | pending (crit) | 0.5d | 75.2 |  |
| 76.3 | Link | pending | 0.5d |  |  |
| 77.1 | Implement lane monitor, task timeline per ICD-013/ | pending (crit) | 0.5d | 76.2 |  |
| 77.2 | Link | pending | 0.5d |  |  |
| 78.1 | Implement log viewer, trace tree, metrics dashboar | pending (crit) | 0.5d | 77.1 |  |
| 78.2 | Link | pending | 0.5d |  |  |
| 78.3 | Validate RTM completeness for console | pending | 0.5d |  |  |
| 78.4 | Phase M gate checklist | pending (crit) | 0.5d | 78.1 |  |
| | **Slice 15** | | | | |
| 79.1 | Document container strategy trade-offs | pending | 0.5d |  |  |
| 79.2 | Build Docker Compose (dev) + production Dockerfile | pending (crit) | 1d | 78.4 |  |
| 79.3 | Link | pending | 0.5d |  |  |
| 80.1 | Document AWS architecture trade-offs | pending | 0.5d |  |  |
| 80.2 | Implement VPC/CFn, ALB/WAF, ECS Fargate task defs  | pending (crit) | 0.5d | 79.2 |  |
| 80.3 | Link | pending | 0.5d |  |  |
| 81.1 | Implement Authentik OIDC flows per ICD-004/005/047 | pending (crit) | 1d | 80.2 |  |
| 81.2 | Link | pending | 0.5d |  |  |
| 82.1 | Implement feature flags | pending (crit) | 0.5d | 81.1 |  |
| 82.2 | Implement canary deploys per ICD staged deployment | pending (crit) | 0.5d | 82.1 |  |
| 82.3 | Implement progressive delivery gates per eval fram | pending (crit) | 0.5d | 82.2 |  |
| 82.4 | Link | pending | 0.5d |  |  |
| 83.1 | Implement scripts: seed_db, migrate, dev, partitio | pending | 0.5d |  |  |
| 83.2 | Link | pending | 0.5d |  |  |
| 84.1 | Aggregate all FMEA results across all phases (A–N) | pending (crit) | 0.5d | 82.3 |  |
| 84.2 | Build full system safety argument per ISO 42010, c | pending (crit) | 1d | 84.1 |  |
| 84.3 | Verify complete traceable chain from concern to co | pending | 0.5d |  |  |
| 84.4 | Verify all TLA+ specs pass final model check (kern | pending (crit) | 1.5d | 84.8 |  |
| 84.5 | Independent safety review per SIL-3 rigor (Kernel, | pending (crit) | 1d | 84.4 |  |
| 84.6 | Release gate: safety case complete? | pending (crit) | 0.5d | 84.5 |  |
| 84.7 | Final Behavior Spec Validation | pending (crit) | 1.5d | 84.2 |  |
| 84.8 | Verify Goal Hierarchy Theorems per Goal Hierarchy  | pending (crit) | 0.5d | 84.7 |  |
| 85.1 | Write operational runbook | pending | 0.5d |  |  |
| 85.2 | Link | pending | 0.5d |  |  |
| 86.1 | Write glossary | pending | 0.5d |  |  |
| 86.2 | Write sandbox security doc | pending | 0.5d |  |  |
| 86.3 | Write egress model doc | pending | 0.5d |  |  |
| 86.4 | Write deployment topology doc | pending | 0.5d |  |  |
| 86.5 | Phase N gate checklist | pending (crit) | 0.5d | 84.6 |  |
