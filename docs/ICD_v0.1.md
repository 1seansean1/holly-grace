# Holly Grace — Interface Control Document v0.1

**Generated:** 17 February 2026
**Source:** SAD v0.1.0.5
**Status:** DRAFT — Formal Phase A (Architecture Enforcement)

---

## Overview

This Interface Control Document (ICD) specifies the formal contract for every boundary crossing in the Holly Grace system. The SAD (System Architecture Document) defines the component structure and connections; this ICD operationalizes those connections as enforced service contracts.

Each interface in this document corresponds to one or more **connection arrows** in the SAD's CONNECTIONS section. The interface defines:

- **Protocol and transport layer** — How data physically travels (HTTP, gRPC, in-process, WebSocket)
- **Direction and cardinality** — Unidirectional or bidirectional, one-to-one or fanout
- **Schema** — Exact structure of request/response payloads (with examples where needed)
- **Safety level (SIL)** — Inherited from the higher-SIL endpoint per ISO 26262
- **Error contract** — What can go wrong, status codes, retry semantics, timeout behavior
- **Latency budget** — Target p99 latency for time-sensitive operations
- **Backpressure and throttling** — How overload is handled, rate limits, queue behavior
- **Tenant isolation** — Multi-tenancy enforcement at every boundary
- **Idempotency** — Whether operations are safe to retry, key strategies
- **Redaction policy** — What PII/secrets must be stripped before crossing
- **Traceability** — Correlation IDs, trace injection, audit trail binding

All interfaces enforce the **Kernel discipline**: every boundary crossing is wrapped by KernelContext (an async context manager in Layer 1) that validates schema, checks permissions, injects trace IDs, detects idempotency key collisions, and enforces abort conditions (HITL gates, eval gates, bounds checks).

### How to Use This Document

1. **For implementation:** Treat each ICD entry as a binding contract. Code that violates the schema, SIL level, error handling, or latency budget is out of spec.
2. **For testing:** Every interface must have integration tests that validate the schema, error paths, idempotency, and latency budget.
3. **For operations:** The latency budgets and backpressure models inform alerting thresholds and scaling policies.
4. **For security review:** The tenant isolation and redaction sections define the trust boundary; any deviation is a security incident.

---

## Interface Index

| # | ID | From | To | Protocol | SIL | Direction |
|---|---|---|---|---|---|---|
| 1 | ICD-001 | UI | ALB | HTTPS | 2 | Unidirectional |
| 2 | ICD-002 | ALB | JWT Middleware | Forward | 2 | Unidirectional |
| 3 | ICD-003 | JWT Middleware | Core | In-Process | 2 | Unidirectional |
| 4 | ICD-004 | Authentik | UI | OIDC Redirect | 2 | Bidirectional |
| 5 | ICD-005 | ALB | Authentik | HTTP/Redirect | 2 | Bidirectional |
| 6 | ICD-006 | Core | Kernel | In-Process | 2 | Bidirectional |
| 7 | ICD-007 | Engine | Kernel | In-Process | 2 | Bidirectional |
| 8 | ICD-008 | Conversation | Intent Classifier | In-Process | 2 | Unidirectional |
| 9 | ICD-009 | Intent Classifier | Goal Decomposer | In-Process | 2 | Unidirectional |
| 10 | ICD-010 | Goal Decomposer | APS Controller | In-Process | 2 | Unidirectional |
| 11 | ICD-011 | APS Controller | Topology Manager | In-Process | 2 | Unidirectional |
| 12 | ICD-012 | Topology Manager | Engine | In-Process | 2 | Unidirectional |
| 13 | ICD-013 | Core | Main Lane | In-Process | 2 | Unidirectional |
| 14 | ICD-014 | Core | Cron Lane | In-Process | 2 | Unidirectional |
| 15 | ICD-015 | Topology Manager | Subagent Lane | In-Process | 2 | Unidirectional |
| 16 | ICD-016 | Lane Policy | Main Lane | In-Process | 2 | Bidirectional |
| 17 | ICD-017 | Lane Policy | Cron Lane | In-Process | 2 | Bidirectional |
| 18 | ICD-018 | Lane Policy | Subagent Lane | In-Process | 2 | Bidirectional |
| 19 | ICD-019 | Main Lane | MCP Registry | In-Process | 2 | Unidirectional |
| 20 | ICD-020 | Subagent Lane | MCP Registry | In-Process | 2 | Unidirectional |
| 21 | ICD-021 | MCP Registry | Workflow Engine | In-Process | 2 | Bidirectional |
| 22 | ICD-022 | MCP Registry | Sandbox | gRPC | 3 | Bidirectional |
| 23 | ICD-023 | Engine | Event Bus | In-Process | 2 | Unidirectional |
| 24 | ICD-024 | Core | Event Bus | In-Process | 2 | Unidirectional |
| 25 | ICD-025 | Event Bus | WebSocket Channels | In-Process | 2 | Unidirectional |
| 26 | ICD-026 | Event Bus | Structured Logging | In-Process | 2 | Unidirectional |
| 27 | ICD-027 | Observability | UI (WebSocket) | WebSocket | 2 | Unidirectional |
| 28 | ICD-028 | Core | Egress Gateway | In-Process | 2 | Unidirectional |
| 29 | ICD-029 | Subagent | Egress Gateway | In-Process | 2 | Unidirectional |
| 30 | ICD-030 | Egress Gateway | Claude API | HTTPS | 3 | Bidirectional |
| 31 | ICD-031 | Core | Ollama | HTTP | 2 | Bidirectional |
| 32 | ICD-032 | Core | PostgreSQL | Async TCP | 2 | Bidirectional |
| 33 | ICD-033 | Core | Redis | Async TCP | 2 | Bidirectional |
| 34 | ICD-034 | Core | ChromaDB | HTTP/Async | 2 | Bidirectional |
| 35 | ICD-035 | Engine | Redis | Async TCP | 2 | Bidirectional |
| 36 | ICD-036 | Observability | PostgreSQL | Async TCP | 2 | Bidirectional |
| 37 | ICD-037 | Observability | Redis | Async TCP | 2 | Bidirectional |
| 38 | ICD-038 | Kernel | PostgreSQL | Async TCP | 2 | Bidirectional |
| 39 | ICD-039 | Workflow Engine | PostgreSQL | Async TCP | 2 | Bidirectional |
| 40 | ICD-040 | Engine | PostgreSQL | Async TCP | 2 | Bidirectional |
| 41 | ICD-041 | Memory System | Redis | Async TCP | 2 | Bidirectional |
| 42 | ICD-042 | Memory System | PostgreSQL | Async TCP | 2 | Bidirectional |
| 43 | ICD-043 | Memory System | ChromaDB | HTTP/Async | 2 | Bidirectional |
| 44 | ICD-044 | KMS | Egress Gateway | In-Process | 3 | Unidirectional |
| 45 | ICD-045 | KMS | PostgreSQL | Async TCP | 3 | Bidirectional |
| 46 | ICD-046 | KMS | MCP Registry | In-Process | 3 | Unidirectional |
| 47 | ICD-047 | Authentik | JWT Middleware | HTTPS (JWKS) | 2 | Unidirectional |
| 48 | ICD-048 | KMS | Authentik | In-Process | 3 | Unidirectional |
| 49 | ICD-049 | JWT Middleware | Redis | Async TCP | 2 | Unidirectional |

---

## Interface Specifications

### ICD-001: UI → ALB

| Field | Value |
|---|---|
| **From** | Console (React Web UI) |
| **To** | Application Load Balancer (AWS ALB) |
| **Direction** | Unidirectional (client → server) |
| **Protocol** | HTTPS (HTTP/2 preferred) |
| **Transport** | TLS 1.3, Certificate pinning on client optional |
| **SIL** | 2 (inherited from ALB SIL-2) |
| **Auth** | Browser session + JWT bearer token in Authorization header (post-login) |
| **Schema** | HTTP request: all requests must include valid JWT (except /auth/* paths). Content-Type: application/json or multipart/form-data for uploads. Response: JSON or binary (for file downloads). |
| **Error Contract** | 4xx: client error (bad request, 400; unauthorized, 401; forbidden, 403; not found, 404). 5xx: server error (500 internal, 502 bad gateway, 503 service unavailable). Retry: safe on 408 (timeout), 429 (rate limit), 503 (unavailable). Do not retry 4xx. Max 3 exponential backoff retries. |
| **Latency Budget** | p99 < 100ms for cache hits; p99 < 500ms for cache misses; WebSocket upgrade < 50ms. |
| **Backpressure** | ALB enforces per-client rate limit: 1000 req/min per IP. Excess requests return 429. Client must honor Retry-After header. WebSocket connections: max 10k concurrent per ALB. |
| **Tenant Isolation** | JWT claim `tenant_id` extracted by ALB; forwarded in X-Tenant-ID header to Core. ALB WAF enforces tenant claim validity. |
| **Idempotency** | Not required for GET/HEAD. POST requests should include Idempotency-Key header (RFC 9110 compatible). ALB does not enforce; Core enforces via Kernel. |
| **Redaction** | Client should not include secrets in query parameters. ALB logs request headers and body (redacted by WAF for secrets matching patterns like api_key, password, token). |
| **Traceability** | ALB generates X-Request-ID (UUID). ALB also forwards existing X-Trace-ID if present. Correlation ID propagated to all downstream services. |

---

### ICD-002: ALB → JWT Middleware

| Field | Value |
|---|---|
| **From** | Application Load Balancer |
| **To** | JWT Middleware (in-process in Core service) |
| **Direction** | Unidirectional (forward) |
| **Protocol** | In-process function call (not a network hop) |
| **Transport** | N/A (local process memory) |
| **SIL** | 2 |
| **Auth** | JWT middleware is a Core internal component; no additional auth. |
| **Schema** | Forwarded request: HTTP method, path, headers (including Authorization: Bearer {token}), body, source IP, X-Request-ID, X-Tenant-ID. Response: validated claims object (sub, tenant_id, roles, exp) or error. |
| **Error Contract** | MalformedToken (400): JWT missing, malformed, or signature invalid. ExpiredToken (401): exp claim < now. InvalidClaims (403): tenant_id or roles missing/invalid. RevocationListError (500): Redis lookup failed. On error, return 401 with WWW-Authenticate header. Retry: safe on 500 only. |
| **Latency Budget** | p99 < 5ms. JWKS verification must not block (cache keys with TTL 1h). Redis revocation lookup must not exceed 1ms p99. |
| **Backpressure** | JWT middleware is synchronous, no queue. If Redis lookup is slow, timeout at 100ms and fail open (allow token if valid signature but revocation unavailable). |
| **Tenant Isolation** | JWT claims extracted and tenant_id added to request context. Middleware does not validate tenant_id against database; that is Core's responsibility. |
| **Idempotency** | Not applicable; JWT validation is deterministic for a given token state. |
| **Redaction** | Token itself must not be logged. Only claims (sub, tenant_id, roles) logged for audit. |
| **Traceability** | X-Request-ID and X-Trace-ID extracted from headers and injected into request context. New trace span created for JWT validation. |

---

### ICD-003: JWT Middleware → Core

| Field | Value |
|---|---|
| **From** | JWT Middleware |
| **To** | Core (Orchestrator) |
| **Direction** | Unidirectional (forward) |
| **Protocol** | In-process function call (async/await) |
| **Transport** | Shared memory, no serialization |
| **SIL** | 2 |
| **Auth** | All authentication performed upstream by JWT middleware; Core trusts validated claims. |
| **Schema** | AuthenticatedRequest: method, path, validated_claims (sub: user_id, tenant_id, roles: List[str], exp: Unix timestamp), body, headers, source_ip. Core exposes route handlers (GET /chat, POST /goals, etc.). Response: JSON, status code, headers. |
| **Error Contract** | InvalidSchema (400): request body does not match handler signature. PermissionDenied (403): user's role not in allowed_roles for this route. NotFound (404): path not recognized. ConflictState (409): operation conflicts with current state (e.g., resuming a completed goal). InternalError (500): unhandled exception. |
| **Latency Budget** | p99 < 50ms for simple queries; p99 < 200ms for goal decomposition; p99 < 1s for topology computation. WebSocket upgrade < 20ms. |
| **Backpressure** | Core enforces per-tenant request limit: 100 concurrent requests per tenant. Excess requests queued with max queue depth 500. Requests waiting >5s timeout with 503. Backpressure signaled via X-RateLimit-Remaining header. |
| **Tenant Isolation** | tenant_id from JWT claims used to scope all subsequent operations. Core queries filter on tenant_id. No cross-tenant data exposure. |
| **Idempotency** | POST requests with Idempotency-Key managed by Kernel. Duplicate keys within 24h window return cached result. |
| **Redaction** | User input (natural language, goal text) is redacted before logging if flagged as sensitive. API response bodies redacted for PII before logging. |
| **Traceability** | X-Request-ID and X-Trace-ID propagated through all Core functions. New span created per handler. Trace exported to Event Bus. |

---

### ICD-004: Authentik → UI (OIDC Login/Redirect)

| Field | Value |
|---|---|
| **From** | Authentik (out-of-band identity provider) |
| **To** | Console (React UI) |
| **Direction** | Bidirectional (redirect chain) |
| **Protocol** | HTTPS + browser redirect (302, 303, or 307) |
| **Transport** | TLS 1.3 |
| **SIL** | 2 |
| **Auth** | OAuth 2.0 authorization code flow with PKCE (RFC 7636). Client ID and secret held by Authentik; no shared secret with UI. |
| **Schema** | Request (UI → Authentik): GET /authorize?client_id={id}&redirect_uri={uri}&response_type=code&scope=openid+profile+email&state={state}&code_challenge={challenge} (PKCE). Response (Authentik → UI): 302 redirect to redirect_uri?code={code}&state={state}. UI then exchanges code for token server-side (ALB → Authentik). |
| **Error Contract** | InvalidClientId (400): client_id not registered. RedirectMismatchError (400): redirect_uri does not match registered URI. AuthenticationFailed (403): user authentication failed (bad password, MFA failed). ServerError (500): Authentik backend failure. |
| **Latency Budget** | p99 < 2s for full OIDC flow (including user login time). Token response < 200ms. |
| **Backpressure** | Authentik enforces account lockout after 5 failed login attempts in 15min window. Rate limit: 10 auth requests per minute per IP. |
| **Tenant Isolation** | Authentik tenant (organization) mapped 1:1 to Holly tenant_id via OIDC claim `org`. |
| **Idempotency** | OIDC state parameter ensures authorization code cannot be replayed. Code expires in 60s. Codes are single-use. |
| **Redaction** | Password never transmitted to Holly; handled entirely by Authentik. Tokens contain no PII in the JWT payload (only subject ID). |
| **Traceability** | Authentik logs all auth events (login, MFA, code issuance) with timestamp and user ID. Holly logs token issuance in audit trail (KernelContext K6 WAL). |

---

### ICD-005: ALB → Authentik (/auth/* path)

| Field | Value |
|---|---|
| **From** | Application Load Balancer |
| **To** | Authentik (OIDC provider) |
| **Direction** | Bidirectional |
| **Protocol** | HTTPS |
| **Transport** | TLS 1.3, direct HTTP connection (ALB → Authentik via private VPC routing) |
| **SIL** | 2 |
| **Auth** | OAuth 2.0 server-to-server: ALB (acting as Core) sends client_id + client_secret (from KMS) in POST body with code. Authentik verifies and issues access token + ID token. |
| **Schema** | Token exchange request: POST /oauth/token with code, client_id, client_secret, grant_type=authorization_code, redirect_uri, code_verifier (PKCE). Response: { access_token, id_token, token_type: Bearer, expires_in: 600 }. |
| **Error Contract** | InvalidGrant (400): authorization code invalid or expired. InvalidClient (401): client_id/secret mismatch. ServerError (500): Authentik backend failure. |
| **Latency Budget** | p99 < 100ms for token exchange. |
| **Backpressure** | Rate limit: 100 token requests per minute per client. Excess requests return 429. |
| **Tenant Isolation** | Authentik validates tenant_id from OIDC configuration; no mixed-tenant tokens issued. |
| **Idempotency** | Code is single-use; resubmitting same code returns 400. No retry on token exchange. |
| **Redaction** | client_secret never logged. Only token expiry and issued_at logged. |
| **Traceability** | Each token exchange logged with correlation ID (state parameter). Authentik audit log tied to Holly's X-Request-ID. |

---

### ICD-006: Core ↔ Kernel (In-Process, KernelContext)

| Field | Value |
|---|---|
| **From** | Core (all components: Conversation, Intent, Goals, APS, Topology, Memory, Config) |
| **To** | Kernel (Layer 1: KernelContext, K1–K8 enforcer) |
| **Direction** | Bidirectional |
| **Protocol** | In-process async context manager (Python AsyncContextManager) |
| **Transport** | Shared memory, event loop cooperative multitasking |
| **SIL** | 2 |
| **Auth** | All Core components use the same Kernel context; no per-component authentication. Auth is enforced once at ALB/JWT layer. |
| **Schema** | KernelContext entry: async with KernelContext(boundary_id, tenant_id, user_id, operation, schema_definition, permission_mask): ... Core's operation (function call) runs inside this context. Kernel validates request at entry; emits audit event at exit. Response: (result, audit_log_entry). |
| **Error Contract** | SchemaValidationError: request does not match schema_definition → raise KernelViolation(400, "schema mismatch"). PermissionDenied: operation not in permission_mask → raise KernelViolation(403, "permission denied"). BoundsExceeded: operation size > limit → raise KernelViolation(413, "bounds exceeded"). HITLRequired: operation flagged for human approval → raise HITL(operation_id, pending_approval=True). EvalGateFailed: operation fails eval predicate → raise EvalViolation(eval_id, reason). Idempotency collision: duplicate key with different payload → raise IdempotencyMismatch(400). |
| **Latency Budget** | Kernel overhead: p99 < 0.5ms. Schema validation < 1ms. Permission check < 0.1ms. Trace injection < 0.1ms. Total KernelContext entry/exit < 2ms. |
| **Backpressure** | Kernel does not introduce backpressure; Core is responsible for request rate limiting (see ICD-003). Kernel audit log is asynchronous (non-blocking append to WAL). |
| **Tenant Isolation** | tenant_id parameter is immutable within a KernelContext. All operations scoped by tenant_id. Kernel does not allow tenant_id override or bypass. |
| **Idempotency** | Idempotency-Key header converted to RFC 8785 canonical form. Kernel deduplicates within 24h window. Duplicate keys with identical payload return original result. Duplicate keys with different payload raise IdempotencyMismatch. |
| **Redaction** | Kernel applies redaction rules before WAL append. Sensitive fields (passwords, API keys, PII) redacted in audit log. Redaction rules defined in canonical library (Phase D, step 27). |
| **Traceability** | trace_id and span_id generated at KernelContext entry. All K1–K8 operations stamped with trace_id. Audit WAL includes trace_id, timestamp, user_id, operation, input_hash, output_hash, violations. |

---

### ICD-007: Engine ↔ Kernel (In-Process, KernelContext)

| Field | Value |
|---|---|
| **From** | Engine (all components: Lanes, MCP, Workflow, Policy) |
| **To** | Kernel (Layer 1: KernelContext, K1–K8 enforcer) |
| **Direction** | Bidirectional |
| **Protocol** | In-process async context manager (same as ICD-006) |
| **Transport** | Shared memory, event loop cooperative multitasking |
| **SIL** | 2 |
| **Auth** | Engine components authenticated once at Core layer; Kernel does not re-authenticate. |
| **Schema** | Same KernelContext interface as ICD-006. Engine operations: lane dispatch, MCP tool invocation, workflow checkpoint, compensation action. Each operation has schema_definition and permission_mask. |
| **Error Contract** | Same as ICD-006: SchemaValidationError, PermissionDenied, BoundsExceeded, HITLRequired, EvalGateFailed, IdempotencyMismatch. All raise KernelViolation or subclass. |
| **Latency Budget** | Same as ICD-006: p99 Kernel overhead < 0.5ms. Engine operations must not timeout waiting for Kernel. |
| **Backpressure** | Kernel does not backpressure Engine. Engine manages its own queue depths (Lane queues, MCP registry queue). |
| **Tenant Isolation** | tenant_id immutable in KernelContext. All Engine operations scoped by tenant_id. No cross-tenant task execution. |
| **Idempotency** | Workflow Engine owns idempotency key generation and deduplication for task-graph nodes. Kernel enforces RFC 8785 canonical form. |
| **Redaction** | Kernel redacts sensitive fields from workflow checkpoints and task state before persisting to PostgreSQL. |
| **Traceability** | trace_id flows from Core → Kernel → Engine → Workflow → MCP → Sandbox. Every hop adds span. trace_id matches Event Bus events (see ICD-023, ICD-024). |

---

### ICD-008: Conversation → Intent Classifier (In-Process)

| Field | Value |
|---|---|
| **From** | Conversation (message input handler) |
| **To** | Intent Classifier (goal-classification LLM call) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal to Core; no authentication. |
| **Schema** | Request: { message: str, user_id: str, tenant_id: str, conversation_context: List[Message], conversation_id: str }. Message = { role: "user" \| "assistant", content: str, timestamp: Unix timestamp }. Response: { intent: "direct_solve" \| "team_spawn" \| "clarify", confidence: float [0, 1], reasoning: str, next_action: dict }. |
| **Error Contract** | ClassificationError: LLM call fails → return { intent: "clarify", confidence: 0, reasoning: "Unable to classify. Please clarify your intent.", next_action: {} }. Do not raise exception; Intent Classifier is in the happy path. |
| **Latency Budget** | p99 < 2s (includes LLM call). Classification must be non-blocking; use timeout of 5s. |
| **Backpressure** | Not applicable; Conversation serializes messages (one classification at a time per user session). |
| **Tenant Isolation** | tenant_id passed through; Intent Classifier does not store state across tenants. |
| **Idempotency** | Not applicable; Intent Classifier is stateless. Same message always produces same classification (within rounding). |
| **Redaction** | User message redacted if contains PII/secrets (password patterns, credit card regexes, API keys). Redaction applied before LLM call and before logging. |
| **Traceability** | trace_id injected from Conversation. Intent Classifier emits a span to Event Bus. Classification result logged. |

---

### ICD-009: Intent Classifier → Goal Decomposer (In-Process)

| Field | Value |
|---|---|
| **From** | Intent Classifier |
| **To** | Goal Decomposer (7-level hierarchy builder) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal to Core; no authentication. |
| **Schema** | Request: { intent: "direct_solve" \| "team_spawn" \| "clarify", original_message: str, user_id: str, tenant_id: str, conversation_context: List[Message] }. Response: { goals: List[Goal], hierarchy: GoalHierarchy }. Goal = { level: 0..6, codimension: int, predicate: str, lexicographic_parent: Goal \| null, celestial: bool, deadline: Unix timestamp \| null, resource_budget: dict }. GoalHierarchy = { L0: [Goals], L1: [Goals], ..., L6: [Goals] }. |
| **Error Contract** | DecompositionError: cannot decompose intent → return partial hierarchy with clarification request at L6. Do not raise exception. |
| **Latency Budget** | p99 < 3s (includes nested LLM calls for hierarchy construction). |
| **Backpressure** | Not applicable; Goal Decomposer processes one intent at a time per conversation. |
| **Tenant Isolation** | tenant_id passed through. Goal Decomposer stores no state across tenants. |
| **Idempotency** | Same intent produces same goal hierarchy (within LLM temperature variance). For SIL-2 compliance, cache goal hierarchies by (user_id, intent_hash, conversation_hash) with 1h TTL in Redis (see ICD-041). |
| **Redaction** | Original message redacted before logging. Goal predicates are not PII; no redaction needed. |
| **Traceability** | trace_id propagated from Intent. Goal Decomposer emits spans per level (L0, L1, ..., L6). Each Goal tagged with trace_id. |

---


### ICD-010: Goal Decomposer → APS Controller (In-Process)

| Field | Value |
|---|---|
| **From** | Goal Decomposer |
| **To** | APS Controller (T0–T3 tier classifier and router) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal to Core; no authentication. |
| **Schema** | Request: { goals: List[Goal], hierarchy: GoalHierarchy, user_id: str, tenant_id: str, conversation_id: str, deadline: Unix timestamp \| null }. Response: { tier: "T0" \| "T1" \| "T2" \| "T3", assembly_index: int, dispatch_plan: DispatchPlan, resource_allocation: dict }. DispatchPlan = { steps: List[Step], parallelizable_groups: List[Set[Step]] }. |
| **Error Contract** | AssemblyError: multi-agent feasibility check fails → return tier "T1" (single-agent fallback) with assembly_index 0. Do not raise exception. |
| **Latency Budget** | p99 < 2s. Feasibility computation (eigenspectrum analysis) < 1.5s. |
| **Backpressure** | Not applicable; APS processes one goal set at a time per conversation. |
| **Tenant Isolation** | tenant_id immutable. APS stores no cross-tenant state. |
| **Idempotency** | Same goal set produces same tier classification (deterministic). Cache tier decisions by (goal_set_hash, deadline_hash) in Redis with 24h TTL. |
| **Redaction** | Goal predicates not sensitive; no redaction needed. Resource allocation not PII. |
| **Traceability** | trace_id propagated. APS emits tier classification span. assembly_index logged. |

---

### ICD-011: APS Controller → Topology Manager (In-Process)

| Field | Value |
|---|---|
| **From** | APS Controller |
| **To** | Team Topology Manager (spawn/steer/dissolve) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal to Core; no authentication. |
| **Schema** | Request: { tier: "T0" \| "T1" \| "T2" \| "T3", dispatch_plan: DispatchPlan, goals: List[Goal], user_id: str, tenant_id: str, deadline: Unix timestamp \| null, resource_budget: dict }. Response: { topology_id: UUID, agents: List[AgentBinding], inter_agent_contracts: List[Contract], monitoring: MonitoringSpec }. AgentBinding = { agent_id: UUID, agent_type: str, role: str, assigned_goals: List[Goal], mcp_permissions: List[str], resource_limit: dict }. Contract = { source_agent: UUID, sink_agent: UUID, data_schema: dict, latency_budget_ms: int }. |
| **Error Contract** | TopologyInfeasible: cannot spawn sufficient agents → return topology with degraded assembly_index. Do not raise exception. |
| **Latency Budget** | p99 < 1s. Agent pool lookup < 100ms. Eigenspectrum init < 500ms. Contract generation < 200ms. |
| **Backpressure** | Topology Manager enforces per-tenant agent pool limit: max 50 active agents per tenant. Excess spawn requests return degraded topology (T1 fallback). |
| **Tenant Isolation** | tenant_id immutable. Topology Manager maintains per-tenant agent registries. No cross-tenant agent binding. |
| **Idempotency** | Same dispatch plan produces deterministic topology (same agent roles, same contracts). For repeated decompositions, reuse existing topology (steer rather than respawn). |
| **Redaction** | Agent configurations not PII. Resource limits not sensitive. No redaction needed. |
| **Traceability** | trace_id propagated. Topology creation logged with topology_id. Agent bindings logged. Contracts logged. |

---

### ICD-012: Topology Manager → Engine (In-Process)

| Field | Value |
|---|---|
| **From** | Team Topology Manager |
| **To** | Execution Engine (lane manager, dispatcher) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal to Core; no authentication. |
| **Schema** | Request: { topology_id: UUID, goals: List[Goal], agents: List[AgentBinding], dispatch_plan: DispatchPlan, deadline: Unix timestamp \| null, user_id: str, tenant_id: str }. Response: { execution_id: UUID, lanes: List[LaneHandle], monitoring_channels: List[str] }. LaneHandle = { lane_id: UUID, lane_type: "main" \| "cron" \| "subagent", max_concurrency: int, mcp_registry_handle: Handle }. |
| **Error Contract** | EngineOverloaded: all lanes at capacity → return error with suggested retry_after_ms. Caller (Core) must respect retry_after and resubmit. |
| **Latency Budget** | p99 < 100ms. Lane allocation < 50ms. Monitoring channel setup < 30ms. |
| **Backpressure** | Engine enforces total concurrency limit: 500 concurrent tasks across all tenants. Per-tenant limit: 100 concurrent tasks. Excess dispatch requests return 503 with Retry-After header. |
| **Tenant Isolation** | tenant_id immutable. Each lane serves a single tenant. No cross-tenant task interleaving. |
| **Idempotency** | Same topology_id + goals produces same lane assignment (deterministic). Resubmitting same execution_plan returns same execution_id (cached for 5 min). |
| **Redaction** | Execution plan not sensitive. Lane configs not PII. No redaction. |
| **Traceability** | trace_id propagated to Engine. execution_id generated and logged. Lane handles logged. Monitoring channels named by execution_id. |

---

### ICD-013: Core → Main Lane (In-Process Dispatch)

| Field | Value |
|---|---|
| **From** | Core (APS/Topology) |
| **To** | Main Lane (user-initiated task execution) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call (enqueue) |
| **Transport** | Shared memory queue (Lane.queue: asyncio.Queue[Task]) |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | Task = { task_id: UUID, goal: Goal, user_id: str, tenant_id: str, deadline: Unix timestamp \| null, idempotency_key: str, resource_budget: dict, mcp_tools: List[str], context: dict }. Enqueue request: { task: Task, priority: int }. |
| **Error Contract** | QueueFull: main_lane.queue.qsize() >= max_queue_depth (500) → return error, caller backs off. Do not drop tasks. |
| **Latency Budget** | Enqueue: p99 < 1ms. |
| **Backpressure** | Lane Policy enforces queue depth. Enqueue blocks if queue full (no timeout). Core must use timeout when calling Main Lane. |
| **Tenant Isolation** | tenant_id immutable in Task. Main Lane partitions queues by tenant internally (one logical queue per tenant). |
| **Idempotency** | idempotency_key included in Task. Duplicate idempotency_keys within 24h return cached result. Engine deduplicates via Kernel (see ICD-007). |
| **Redaction** | Task context redacted before queue append. Sensitive fields removed. |
| **Traceability** | trace_id propagated to Task. task_id = UUID. Main Lane emits "task_enqueued" event to Event Bus. |

---

### ICD-014: Core → Cron Lane (In-Process Schedule)

| Field | Value |
|---|---|
| **From** | Core (Config Control Plane, scheduled task manager) |
| **To** | Cron Lane (time-triggered execution) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call (schedule) |
| **Transport** | Shared memory (Cron Lane maintains a priority queue of { scheduled_time, Task }) |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | ScheduledTask = { task: Task, scheduled_time: Unix timestamp, recurrence: null \| CronExpression, max_retries: int }. Schedule request: { scheduled_task: ScheduledTask }. Response: { schedule_id: UUID, next_execution_time: Unix timestamp \| null }. |
| **Error Contract** | PastScheduleTime: scheduled_time < now → error, task not enqueued. Caller must provide future timestamp. InvalidCronExpression: recurrence not parseable → error. Do not schedule. |
| **Latency Budget** | Schedule enqueue: p99 < 1ms. Cron evaluation (checking due tasks): p99 < 100ms per evaluation cycle (10s polling). |
| **Backpressure** | Same as ICD-013. Cron Lane shares queue depth with Main Lane (total 500 per tenant). |
| **Tenant Isolation** | tenant_id immutable in ScheduledTask.task. Cron Lane partitions schedules by tenant. |
| **Idempotency** | schedule_id = UUID. Same scheduled_task submitted twice returns same schedule_id (cached). |
| **Redaction** | ScheduledTask redacted before storage. Task context redacted. |
| **Traceability** | trace_id propagated. schedule_id logged. Cron Lane emits "scheduled_task_triggered" event to Event Bus on execution. |

---

### ICD-015: Topology Manager → Subagent Lane (In-Process Spawn)

| Field | Value |
|---|---|
| **From** | Team Topology Manager |
| **To** | Subagent Lane (team-parallel execution) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call (spawn) |
| **Transport** | Shared memory queue |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | SubagentTask = { agent_binding: AgentBinding, goals: List[Goal], parent_execution_id: UUID, user_id: str, tenant_id: str, deadline: Unix timestamp \| null, message_queue: Handle (for inter-agent comms) }. Spawn request: { subagent_task: SubagentTask, priority: int }. Response: { subagent_execution_id: UUID, monitoring_channels: List[str] }. |
| **Error Contract** | AgentSpawnFailed: agent not available (pool exhausted) → return error with suggested resource wait time. Topology Manager must handle and provide fallback (degrade to T1). |
| **Latency Budget** | Spawn enqueue: p99 < 2ms. Agent initialization (loading checkpoint, connecting to message queue): p99 < 500ms. |
| **Backpressure** | Subagent Lane shares concurrency limit with Main/Cron (max 100 per tenant). Spawn requests enqueued; excess requests wait. |
| **Tenant Isolation** | tenant_id immutable. Subagent Lane partitions queues by tenant. No cross-tenant agent comms. |
| **Idempotency** | SubagentTask includes parent_execution_id + agent_binding.agent_id. Duplicate spawn requests (same parent + agent) within 1min return cached execution_id. |
| **Redaction** | SubagentTask redacted before queue. message_queue handle does not contain sensitive data. |
| **Traceability** | trace_id propagated. subagent_execution_id logged. Agent spawn logged as event. parent_execution_id linked to subagent_execution_id. |

---

### ICD-016: Lane Policy ↔ Main Lane (In-Process Governs)

| Field | Value |
|---|---|
| **From** | Lane Policy (policy engine) |
| **To** | Main Lane (queue manager) |
| **Direction** | Bidirectional (policy set → lane; lane queries → policy; lane reports metrics → policy) |
| **Protocol** | In-process async function calls and shared state updates |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | PolicyUpdate = { max_concurrency: int, per_tenant_limit: int, rate_limit_rps: float, max_queue_depth: int, timeout_ms: int }. Metrics = { queue_depth: int, active_tasks: int, completed_tasks_5min: int, error_rate_5min: float, p99_latency_ms: float }. Policy query: lane calls policy.compute_backpressure(tenant_id, metrics) → backpressure_factor: float [0, 1]. |
| **Error Contract** | PolicyNotFound: tenant_id not in policy table → use default policy (concurrency=10, queue_depth=500). InvalidPolicyUpdate: new_max_concurrency < 1 → reject. Do not apply. |
| **Latency Budget** | Policy query: p99 < 1ms. Policy update: p99 < 5ms. |
| **Backpressure** | Policy engine itself has no backpressure; queries are synchronous. Lane enforces policy decisions. |
| **Tenant Isolation** | Policy indexed by tenant_id. All metrics per-tenant. No cross-tenant policy sharing. |
| **Idempotency** | Not applicable; policy updates are applied immediately and idempotent (last write wins). |
| **Redaction** | Metrics may contain task counts (not PII). No redaction. |
| **Traceability** | Policy changes logged with timestamp and reason (admin action, auto-scaling trigger, etc.). trace_id injected if triggered by user request. |

---

### ICD-017: Lane Policy ↔ Cron Lane (In-Process Governs)

| Field | Value |
|---|---|
| **From** | Lane Policy |
| **To** | Cron Lane |
| **Direction** | Bidirectional (same as ICD-016) |
| **Protocol** | In-process async function calls and shared state |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | Same PolicyUpdate and Metrics as ICD-016. Cron Lane also reports { scheduled_tasks_count: int, overdue_tasks: int, next_scheduled_time: Unix timestamp }. |
| **Error Contract** | Same as ICD-016. |
| **Latency Budget** | Policy query: p99 < 1ms. |
| **Backpressure** | Same as ICD-016. |
| **Tenant Isolation** | Same as ICD-016. Policy per-tenant. |
| **Idempotency** | Same as ICD-016. |
| **Redaction** | Same as ICD-016. |
| **Traceability** | Same as ICD-016. |

---

### ICD-018: Lane Policy ↔ Subagent Lane (In-Process Governs)

| Field | Value |
|---|---|
| **From** | Lane Policy |
| **To** | Subagent Lane |
| **Direction** | Bidirectional (same as ICD-016) |
| **Protocol** | In-process async function calls and shared state |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | Same PolicyUpdate and Metrics as ICD-016. Subagent Lane also reports { spawned_agents: int, agents_by_type: dict, inter_agent_messages: int }. |
| **Error Contract** | Same as ICD-016. |
| **Latency Budget** | Same as ICD-016. |
| **Backpressure** | Same as ICD-016. |
| **Tenant Isolation** | Same as ICD-016. |
| **Idempotency** | Same as ICD-016. |
| **Redaction** | Same as ICD-016. Agent type counts not PII. |
| **Traceability** | Same as ICD-016. |

---

### ICD-019: Main Lane → MCP Registry (In-Process)

| Field | Value |
|---|---|
| **From** | Main Lane (task dequeuer) |
| **To** | MCP Tool Registry (tool lookup and invocation) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Main Lane knows agent_id and mcp_permissions (from AgentBinding). Registry validates permissions. |
| **Schema** | ToolInvocationRequest = { tool_name: str, agent_id: UUID, tenant_id: str, user_id: str, input: dict, idempotency_key: str }. Response: { tool_result: dict, execution_time_ms: float, tokens_used: int \| null } \| { error: dict, error_code: str, execution_time_ms: float }. |
| **Error Contract** | ToolNotFound: tool_name not in registry → error "tool_not_found". PermissionDenied: agent_id not in mcp_permissions[tool_name] → error "permission_denied". ToolExecutionError: tool raises exception → error "tool_execution_error" with message. LLMError: LLM-based tool fails → error "llm_error" with retry_after_ms. |
| **Latency Budget** | Tool lookup: p99 < 1ms. Permissions check: p99 < 1ms. Tool execution: p99 < 5s (LLM tools may hit 30s budget; see ICD-028). |
| **Backpressure** | Registry maintains per-tool concurrency limit (default: 10 per tool per tenant). Excess invocations queued. Queue timeout: 30s (caller must handle timeout). |
| **Tenant Isolation** | tenant_id immutable. Registry isolates tool invocations by tenant. Tool state is per-tenant. |
| **Idempotency** | idempotency_key passed through. Registry deduplicates via Kernel (K5). Duplicate invocations return cached result within 24h. |
| **Redaction** | Tool input redacted if contains secrets (API keys, passwords). Output redacted if contains PII. Redaction applied before returning to Main Lane. |
| **Traceability** | trace_id propagated from task. Registry emits tool_invoked event to Event Bus. Tool execution logged with trace_id. |

---

### ICD-020: Subagent Lane → MCP Registry (In-Process)

| Field | Value |
|---|---|
| **From** | Subagent Lane (spawned agent task dequeuer) |
| **To** | MCP Tool Registry |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call (same as ICD-019) |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Subagent Lane knows agent_id and mcp_permissions. Registry validates. |
| **Schema** | Same ToolInvocationRequest and Response as ICD-019. Subagent invocations tagged with agent_id (not user_id). |
| **Error Contract** | Same as ICD-019. |
| **Latency Budget** | Same as ICD-019. p99 < 5s. |
| **Backpressure** | Same as ICD-019. Per-tool concurrency limit applies across Main and Subagent lanes. |
| **Tenant Isolation** | Same as ICD-019. Subagent operations scoped by tenant_id. |
| **Idempotency** | Same as ICD-019. Idempotency key deduplication cross-lane. |
| **Redaction** | Same as ICD-019. Agent outputs redacted before returning. |
| **Traceability** | trace_id propagated. Agent ID also logged. Subagent tool invocations logged as separate events from Main Lane. |

---

### ICD-021: MCP Registry ↔ Workflow Engine (In-Process)

| Field | Value |
|---|---|
| **From** | MCP Tool Registry (tool invocation coordinator) |
| **To** | Workflow Engine (task graph executor, checkpointing) |
| **Direction** | Bidirectional |
| **Protocol** | In-process async function calls |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | WorkflowTaskRequest = { task_graph_id: UUID, node_id: UUID, tool_name: str, input: dict, parent_nodes: List[UUID], deadline: Unix timestamp \| null }. WorkflowTaskResponse = { node_id: UUID, result: dict, checkpoint_ref: str, idempotency_key: str, execution_time_ms: float }. Checkpoint = { workflow_id: UUID, node_id: UUID, output_state: dict, timestamp: Unix timestamp, output_hash: str (for dedup detection) }. |
| **Error Contract** | NodeNotFound: node_id not in task_graph → error "node_not_found". ParentsFailed: parent nodes failed → skip node (no execution). ParentsPending: parent nodes not complete → wait (no timeout; async). CheckpointError: checkpoint persist fails → return error "checkpoint_error", retry eligible. TaskGraphInvalid: task_graph structure violated → error "invalid_task_graph". |
| **Latency Budget** | Node enqueue: p99 < 1ms. Checkpoint persist: p99 < 50ms (async, non-blocking return). Parent graph traversal: p99 < 100ms. |
| **Backpressure** | Workflow Engine maintains per-workflow queue depth limit (1000 pending nodes per workflow). Excess node enqueues wait up to 30s. |
| **Tenant Isolation** | tenant_id immutable across workflow. All nodes in task_graph scoped by tenant_id. |
| **Idempotency** | Workflow Engine owns idempotency; node re-execution deduped by (task_graph_id, node_id, input_hash) within 24h. MCP Registry passes idempotency_key through to checkpoint. |
| **Redaction** | Node input/output redacted before checkpoint persist. Sensitive fields removed. |
| **Traceability** | trace_id propagated from MCP invocation. Workflow Engine stamps each checkpoint with trace_id. Node execution logged with trace_id. |

---

### ICD-022: MCP Registry → Sandbox (gRPC)

| Field | Value |
|---|---|
| **From** | MCP Tool Registry (code execution tool) |
| **To** | Sandbox (isolated code executor, gRPC service) |
| **Direction** | Bidirectional (request-response) |
| **Protocol** | gRPC with Protocol Buffers |
| **Transport** | TCP, TLS mutual (mTLS) |
| **SIL** | 3 (inherited from Sandbox SIL-3) |
| **Auth** | mTLS: Registry and Sandbox authenticate via client/server certificates (issued by internal CA, rotated every 30 days). No per-call authentication; cert rotation enforces freshness. |
| **Schema** | ExecutionRequest = { code: bytes, language: "python" \| "javascript" \| "bash", input_data: dict, timeout_ms: int, memory_limit_mb: int, allowed_syscalls: List[str] }. ExecutionResult = { output: bytes, exit_code: int, stderr: bytes, execution_time_ms: float, memory_used_mb: int } \| { error: ExecutionError, error_code: str }. ExecutionError = { kind: "timeout" \| "memory_exceeded" \| "sandbox_escape_attempt" \| "invalid_syscall" \| "runtime_error", message: str }. |
| **Error Contract** | Timeout: execution_time > timeout_ms → ExecutionError (timeout). MemoryExceeded: memory_used > memory_limit → ExecutionError (memory_exceeded). SandboxEscape: process attempts network, filesystem outside mount, or privileged syscall → ExecutionError (sandbox_escape_attempt). InvalidSyscall: syscall not in allowed_syscalls → ExecutionError (invalid_syscall). RuntimeError: code raises exception → ExecutionError (runtime_error). On error, Registry must not retry automatically (execution may have had side effects). Caller (MCP user) decides retry based on error kind. |
| **Latency Budget** | Sandbox RPC round-trip: p99 < 100ms (excluding code execution time). Code execution: depends on code; timeout enforced per request (default 30s for LLM-generated code, 5s for tool code). |
| **Backpressure** | Sandbox enforces per-container concurrency limit: max 10 concurrent executions per container. Excess ExecutionRequests queued in gRPC server with max queue depth 100. Requests waiting > 30s timeout with gRPC deadline_exceeded. |
| **Tenant Isolation** | ExecutionRequest includes tenant_id (as opaque tag, not enforced by Sandbox). Sandbox container isolated by Linux namespace (PID, network, mount); tenant_id is logical tag only. Multi-tenant Sandbox instances: each container runs one tenant's code. No code from tenant A can observe tenant B's memory or syscall trace. |
| **Idempotency** | Not applicable; code execution may have side effects (file writes, network calls within allowed set). Execution is not retryable without semantic analysis. Caller responsible for idempotency if needed (e.g., write-once files). |
| **Redaction** | ExecutionRequest.code and input_data not redacted (assumed already safe by caller). ExecutionResult.output and stderr redacted before returning to Registry (remove any PII/secrets that code may have printed). |
| **Traceability** | ExecutionRequest includes trace_id and span_id from MCP Registry. Sandbox logs all execution events (start, syscall, exit) with trace_id. Logs sent to local syslog, aggregated by observability system. |


### ICD-023: Engine → Event Bus (In-Process Emit Events)

| Field | Value |
|---|---|
| **From** | Engine (all components) |
| **To** | Event Bus (unified event ingest, filtering, fanout) |
| **Direction** | Unidirectional (fire-and-forget) |
| **Protocol** | In-process async function call (non-blocking) |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | Event = { event_type: str, source: str, tenant_id: str, user_id: str, timestamp: Unix timestamp (ns), trace_id: UUID, span_id: UUID, data: dict, severity: "debug" \| "info" \| "warn" \| "error" }. Emit request: fire_event(event: Event). Response: immediate return (async append). |
| **Error Contract** | BufferFull: Event Bus internal buffer at capacity → drop event (sampling). No exception raised; Engine continues. Dropped events sampled at 1% (store 1 out of 100 dropped). EventBusError: internal error → swallow and log to stderr (do not crash Engine). |
| **Latency Budget** | Event emit: p99 < 0.1ms (non-blocking append to ring buffer). |
| **Backpressure** | Event Bus enforces backpressure via sampling: if ingestion rate exceeds 100k events/sec per tenant, sample down to 100k/sec. Dropped events logged as summary metrics. |
| **Tenant Isolation** | tenant_id immutable in Event. Event Bus partitions queues by tenant. WebSocket fanout (see ICD-025) filters by tenant. |
| **Idempotency** | Not applicable; events are fire-and-forget. Duplicate events allowed (idempotency at consumer level, not producer). |
| **Redaction** | Event.data redacted for PII/secrets before append. Redaction rules applied per event_type (see Phase D, step 27). |
| **Traceability** | trace_id and span_id propagated from caller. Event stamped with trace_id for end-to-end correlation. |

---

### ICD-024: Core → Event Bus (In-Process Emit Events)

| Field | Value |
|---|---|
| **From** | Core (all components) |
| **To** | Event Bus |
| **Direction** | Unidirectional (fire-and-forget) |
| **Protocol** | In-process async function call (same as ICD-023) |
| **Transport** | Shared memory |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | Same Event schema as ICD-023. Core emits: intent_classified, goals_decomposed, topology_spawned, topology_steered, config_updated, etc. |
| **Error Contract** | Same as ICD-023. |
| **Latency Budget** | Same as ICD-023. p99 < 0.1ms. |
| **Backpressure** | Same as ICD-023. Sampling at 100k/sec per tenant. |
| **Tenant Isolation** | Same as ICD-023. |
| **Idempotency** | Same as ICD-023. |
| **Redaction** | Same as ICD-023. Core events redacted for user input, goal predicates, etc. |
| **Traceability** | Same as ICD-023. Core component events tagged with component name and operation. |

---

### ICD-025: Event Bus → WebSocket Channels (In-Process Filtered Stream)

| Field | Value |
|---|---|
| **From** | Event Bus (event multiplexer) |
| **To** | WebSocket Channels (9 per-tenant broadcast channels) |
| **Direction** | Unidirectional (async pub-sub) |
| **Protocol** | In-process async pub-sub (async context manager subscriptions) |
| **Transport** | Shared memory (ring buffer per channel) |
| **SIL** | 2 |
| **Auth** | WebSocket channel authorization (per ICD-027). Event Bus does not authenticate; it filters by tenant_id. |
| **Schema** | Event Bus → Channel fanout: for each Event in bus, match { event_type in channel.subscribed_types, tenant_id == channel.tenant_id }. If match, write event to channel's ring buffer. Channel consumers (WebSocket handlers) read from ring buffer. Channels: agent_trace, goal_progress, team_topology, lane_status, memory_ops, tool_invocations, error_stream, metrics, notify. |
| **Error Contract** | ChannelFull: ring buffer at capacity (1000 events per channel per tenant) → drop oldest event (FIFO). Consumers not notified. Missed events detected by Event ID sequencing on consumer side. |
| **Latency Budget** | Event fanout: p99 < 1ms per channel (1-9 channels per tenant). |
| **Backpressure** | Event Bus applies backpressure to event producers (Core, Engine) if all channels' ring buffers are full. Sample rate reduced (see ICD-023). |
| **Tenant Isolation** | Each channel scoped to tenant_id. Event Bus does not mix tenants. WebSocket handler enforces per-channel tenant authz (see ICD-027). |
| **Idempotency** | Not applicable; events streamed in order. Consumers must use Event ID for dedup if needed. |
| **Redaction** | Events redacted before append (see ICD-023, ICD-024). Channel consumers receive redacted events. |
| **Traceability** | trace_id preserved in Event. WebSocket consumer can correlate received events to trace spans. |

---

### ICD-026: Event Bus → Structured Logging (In-Process)

| Field | Value |
|---|---|
| **From** | Event Bus |
| **To** | Structured Logging (JSON logger, correlation-aware) |
| **Direction** | Unidirectional (append-only) |
| **Protocol** | In-process async function call (non-blocking) |
| **Transport** | Shared memory queue → external logger (Pydantic models for schema) |
| **SIL** | 2 |
| **Auth** | Internal; no authentication. |
| **Schema** | LogEntry = { timestamp: Unix timestamp (ns), level: "DEBUG" \| "INFO" \| "WARN" \| "ERROR", logger: str, message: str, trace_id: UUID, span_id: UUID, user_id: str, tenant_id: str, component: str, event_data: dict (JSON-serialized). Structured fields: http_method, http_path, status_code, latency_ms, error_type, error_message, request_id, user_agent. |
| **Error Contract** | LogWriteError: logger backend (file, syslog) fails → swallow error, do not crash. Log to stderr as fallback. |
| **Latency Budget** | Log append: p99 < 5ms (async, non-blocking). |
| **Backpressure** | Logger maintains per-tenant per-level rate limits: max 1M log lines/day per tenant per level. Excess logs sampled and summarized. |
| **Tenant Isolation** | tenant_id in LogEntry. Logs partitioned by tenant at storage layer (PostgreSQL partitions; see ICD-036). |
| **Idempotency** | Not applicable; logs are append-only and immutable. |
| **Redaction** | Log entries redacted before append. Event data redacted per event_type. All JSON values scanned for PII/secrets. |
| **Traceability** | trace_id and span_id propagated. Logs queryable by trace_id (see ICD-036). |

---

### ICD-027: Observability → UI (WebSocket Stream)

| Field | Value |
|---|---|
| **From** | Observability (WebSocket server) |
| **To** | Console UI (WebSocket client) |
| **Direction** | Bidirectional (server push + client subscribe/unsubscribe) |
| **Protocol** | WebSocket (RFC 6455) over HTTPS |
| **Transport** | TLS 1.3, persistent connection |
| **SIL** | 2 |
| **Auth** | WebSocket upgrade: JWT token validated (see ICD-003). Per-channel authz: user's tenant_id must match channel's tenant_id. No cross-tenant channel access. Per-channel permissions: role-based (e.g., analyst can view audit, metrics; developer can view agent_trace, lane_status). |
| **Schema** | Client message (subscribe/unsubscribe): { "action": "subscribe" \| "unsubscribe", "channel": str, "filters": { "event_types": [str], "severity_min": str } }. Server message (event stream): { "channel": str, "event": Event (from ICD-025), "sequence_number": int }. |
| **Error Contract** | InvalidChannel: channel name not in [agent_trace, goal_progress, team_topology, lane_status, memory_ops, tool_invocations, error_stream, metrics, notify] → send error frame {"error": "invalid_channel"}. Do not close connection. PermissionDenied: user's role cannot access channel → send error frame {"error": "permission_denied"}. Do not close connection. ConnectionLost: network failure → client reconnects (with exponential backoff). Server buffers events for 30s; client can replay missed events. |
| **Latency Budget** | Event delivery: p99 < 100ms (from Event Bus to WebSocket client). |
| **Backpressure** | WebSocket server enforces per-connection message queue: max 10k pending messages. If client slow, queue fills → close connection (after warning). Client must reconnect and re-subscribe. |
| **Tenant Isolation** | WebSocket handler validates tenant_id from JWT claim. Only channels for user's tenant_id accessible. Channel subscriptions scoped per tenant. |
| **Idempotency** | Not applicable; events streamed. Sequence numbers allow client to detect gaps. |
| **Redaction** | Events redacted before sending (see ICD-025). Sensitive fields removed from event data. |
| **Traceability** | trace_id included in event payload. Client can filter by trace_id to follow a single request's lifecycle. |

---

### ICD-028: Core → Egress Gateway (In-Process LLM Call)

| Field | Value |
|---|---|
| **From** | Core (Intent, Goals, APS, Topology components making LLM calls) |
| **To** | Egress Gateway (L7 allowlist, redaction, rate limiter) |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call |
| **Transport** | Shared memory |
| **SIL** | 2 (Core) → 3 (Egress) → 3 (Claude API) |
| **Auth** | Egress Gateway authenticates Core via KMS-issued API key (see ICD-044). No per-request auth; authentication at startup. |
| **Schema** | LLMRequest = { prompt: str, model: "claude-opus-4.6" \| "claude-sonnet-4.5", temperature: float [0, 2], max_tokens: int, system: str, context_window_tokens: int, user_id: str, tenant_id: str, trace_id: UUID, idempotency_key: str }. LLMResponse = { completion: str, tokens_used: { input: int, output: int }, finish_reason: "end_turn" \| "stop_sequence" \| "max_tokens", model: str, latency_ms: float } \| { error: str, error_type: str, retry_after_ms: int }. |
| **Error Contract** | RateLimitExceeded: per-tenant rate limit exceeded (default 1000 req/min per tenant) → return error "rate_limit_exceeded" with retry_after_ms. PromptInjectionDetected: prompt contains forbidden patterns (e.g., "ignore all previous instructions") → return error "prompt_injection_detected", do not send to Claude. RedactionFailed: cannot redact prompt (unknown PII pattern) → log warning and send redacted best-effort. ContentPolicyViolation: Claude API rejects due to policy → return error "content_policy_violation". TokenBudgetExceeded: estimated tokens > budget → return error "token_budget_exceeded". LLMServiceUnavailable: Claude API 5xx → return error "service_unavailable" with retry_after_ms. |
| **Latency Budget** | Egress Gateway check (allowlist, redaction, rate limit): p99 < 50ms. Entire LLM call (including Claude API): p99 < 30s (typical ~5-10s for Opus). Timeout: 40s absolute (no hanging requests). |
| **Backpressure** | Rate limit: 1000 req/min per tenant, 50 concurrent per tenant. Excess requests queued with 60s timeout. Queue size: 1000 per tenant. |
| **Tenant Isolation** | tenant_id in LLMRequest. Egress Gateway isolates rate limits, budgets, and logging by tenant. |
| **Idempotency** | idempotency_key in LLMRequest. Egress Gateway deduplicates within 5min window (Claude API idempotency not 100% guaranteed, so Holly caches). Duplicate keys return cached response. |
| **Redaction** | Prompt redacted for PII/secrets before sending to Claude. Completion redacted for sensitive output before returning to Core. |
| **Traceability** | trace_id propagated. LLM call logged with prompt_hash (not raw prompt), completion_hash, tokens, and latency. |

---

### ICD-029: Subagent → Egress Gateway (In-Process Agent LLM Call)

| Field | Value |
|---|---|
| **From** | Subagent (autonomous agent spawned by Topology Manager) |
| **To** | Egress Gateway |
| **Direction** | Unidirectional |
| **Protocol** | In-process async function call (same as ICD-028) |
| **Transport** | Shared memory |
| **SIL** | 2 (Subagent) → 3 (Egress) → 3 (Claude API) |
| **Auth** | Same as ICD-028. |
| **Schema** | Same LLMRequest and LLMResponse as ICD-028, but agent_id instead of user_id. |
| **Error Contract** | Same as ICD-028. |
| **Latency Budget** | Same as ICD-028. p99 < 30s. |
| **Backpressure** | Subagent requests share same rate limit bucket as Core (1000 req/min per tenant total). Excess requests wait with 60s timeout. |
| **Tenant Isolation** | Same as ICD-028. tenant_id immutable. Subagent operations scoped by tenant. |
| **Idempotency** | Same as ICD-028. Deduplication by idempotency_key. |
| **Redaction** | Same as ICD-028. Agent prompts redacted. |
| **Traceability** | Same as ICD-028, but agent_id also logged. |

---

### ICD-030: Egress Gateway → Claude API (HTTPS Allowlisted)

| Field | Value |
|---|---|
| **From** | Egress Gateway (L7 proxy) |
| **To** | Claude API (Anthropic LLM service) |
| **Direction** | Bidirectional (request-response) |
| **Protocol** | HTTPS (HTTP/2) |
| **Transport** | TLS 1.3, DNS: api.anthropic.com (allowlisted domain) |
| **SIL** | 3 |
| **Auth** | HTTP header `x-api-key: {key}` (issued by Anthropic to Holly tenant). Key stored in KMS. |
| **Schema** | Request: POST /v1/messages with JSON body { model, messages, max_tokens, system, temperature, top_k, top_p, tools[], tool_choice, metadata }. Response: { id, type, content[], model, usage: { input_tokens, output_tokens }, stop_reason }. Per Anthropic SDK v0.52+. |
| **Error Contract** | 400 Bad Request: malformed request → Egress logs and returns to caller as "llm_error". 401 Unauthorized: API key invalid or expired → Egress logs and returns "auth_error" (KMS to refresh key). 429 Too Many Requests: rate limit from Anthropic → Egress returns with retry_after_ms from response header. 500/502/503: Anthropic backend error → Egress returns with retry_after_ms (default 30s). Egress implements exponential backoff (1s, 2s, 4s, 8s, max 60s) for retryable errors. |
| **Latency Budget** | API round-trip: p99 < 30s (depends on Anthropic). Egress timeout: 40s. |
| **Backpressure** | Claude API rate limit: 10 req/s per API key (Anthropic limit). Holly's per-tenant rate limit (1000 req/min) is looser. If Anthropic returns 429, Egress backs off and signals to caller. |
| **Tenant Isolation** | API key is per Holly tenant (1 key per org). Anthropic enforces rate limits per key. |
| **Idempotency** | Claude API supports idempotency via `anthropic-idempotency-header: {idempotency_key}`. Egress injects idempotency key. 24h window. |
| **Redaction** | Egress must not leak API key in logs/traces. Egress REDACTS API key from all event/log output (replace with [REDACTED]). |
| **Traceability** | Egress injects `X-Request-ID` header (uuid). Claude API echoes in response header. Egress correlates request ↔ response via ID. |

---

### ICD-031: Core → Ollama (HTTP Local Inference)

| Field | Value |
|---|---|
| **From** | Core (Intent, Goals, APS components) |
| **To** | Ollama (local inference engine, cost-sensitive tasks) |
| **Direction** | Bidirectional (request-response) |
| **Protocol** | HTTP REST (http://ollama:11434/api/generate or /api/chat) |
| **Transport** | TCP, unencrypted (VPC-internal, no TLS needed) |
| **SIL** | 2 |
| **Auth** | No authentication (Ollama running in private VPC subnet, no public access). |
| **Schema** | Request (chat): POST /api/chat { model: "mistral:latest" \| "llama2:latest", messages, temperature, num_ctx: 2048 }. Request (generate): POST /api/generate { model, prompt, temperature, num_predict: 1024 }. Response: { message: { content: str, role: "assistant" } } or { response: str, context: [] }. Streaming: response is newline-delimited JSON. |
| **Error Contract** | ModelNotFound: model not loaded in Ollama → return error "model_not_found". TimeOut: inference > 30s → return error "timeout". MemoryError: Ollama OOM → return error "memory_error". ConnectionRefused: Ollama not running → return error "service_unavailable" (circuit breaker triggers after 3 failures). |
| **Latency Budget** | Ollama inference: p99 < 10s (local model, much faster than API). Request round-trip: p99 < 11s. Timeout: 15s absolute. |
| **Backpressure** | Ollama per-tenant limit: max 5 concurrent inferences per tenant. Excess requests wait in queue (max queue depth 50). Queue timeout: 30s. |
| **Tenant Isolation** | Request may include tenant_id (for logging). Ollama runs shared; responses not isolated (assume benign). No sensitive tenant data passed. |
| **Idempotency** | Not applicable; Ollama responses may vary due to temperature. Idempotency at Core level (cache by prompt_hash if needed). |
| **Redaction** | Prompt redacted for PII before sending. Response redacted before returning. |
| **Traceability** | Core injects trace_id in custom header (x-trace-id). Ollama logs echoed to observability system. |

---

### ICD-032: Core ↔ PostgreSQL (State/History)

| Field | Value |
|---|---|
| **From** | Core (Intent, Goals, APS, Topology, Memory, Config) |
| **To** | PostgreSQL (RLS-enforced transactional store) |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (asyncpg driver) |
| **Transport** | Private VPC subnet, no TLS (localhost:5432 or RDS endpoint in private subnet) |
| **SIL** | 2 |
| **Auth** | PostgreSQL role: `holly_core_{tenant_id}` (per-tenant role). RLS policies enforce row-level filtering. Connection pooling (asyncpg pool, 10 connections per tenant). |
| **Schema** | Tables (per SAD): agents (id, type, config, checkpoint), goals (id, level, predicate, deadline, status, celestial), topologies (id, agents, contracts, eigenspectrum_state), conversations (id, user_id, messages, context), goals_history (id, goal_id, delta_state, timestamp). Queries: INSERT/UPDATE goals, SELECT agents WHERE tenant_id = %s, INSERT goal_history. |
| **Error Contract** | UniqueViolationError: constraint violation → return error "conflict". Caller decides retry. DeadlockError: transaction conflict → async retry with exponential backoff (1ms, 2ms, 4ms, max 100ms). Query timeout (30s) → return error "query_timeout", caller backs off. RLS violation: attempt to access other tenant's row → PostgreSQL returns 0 rows (silent deny). |
| **Latency Budget** | Single row INSERT: p99 < 10ms. SELECT with index (goal by id): p99 < 5ms. Complex join (agents + contracts): p99 < 50ms. Batch INSERT (100 rows): p99 < 100ms. |
| **Backpressure** | Connection pool: 10 per tenant. Excess queries wait up to 30s for available connection. Queue size: 100 per tenant. If exceeded, return error "database_overloaded". |
| **Tenant Isolation** | PostgreSQL role scoped per tenant. RLS policies enforce: SELECT ... WHERE tenant_id = current_user_id (tenant_id embedded in role name). No cross-tenant data leakage. |
| **Idempotency** | Application-level idempotency key stored in idempotency_keys table. Core checks before INSERT. If key exists, return cached result. TTL: 24h. |
| **Redaction** | Sensitive columns (passwords, API keys): NOT stored in PostgreSQL. Config table stores only non-sensitive key-value pairs. Secrets fetched from KMS (see ICD-045). |
| **Traceability** | Every INSERT/UPDATE includes user_id, timestamp, trace_id. Audit log (goal_history, topology_history) tracks mutations. |

---

### ICD-033: Core ↔ Redis (Short-Term Memory)

| Field | Value |
|---|---|
| **From** | Core (Intent, Goals, APS, Topology, Memory) |
| **To** | Redis (fast cache and queue) |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (aioredis driver) |
| **Transport** | Private VPC subnet, no TLS (cluster or Sentinel for HA) |
| **SIL** | 2 |
| **Auth** | Redis AUTH with password (stored in KMS, see ICD-044). Connection pool: 20 connections per tenant. |
| **Schema** | Keys: goal_hierarchy:{user_id}:{intent_hash} (TTL 1h, value: GoalHierarchy JSON), tier_classification:{goal_set_hash} (TTL 24h), conversation_context:{conversation_id} (TTL 7 days), agent_checkpoint:{agent_id} (TTL 30 days), idempotency_cache:{key} (TTL 24h). |
| **Error Contract** | ConnectionError: Redis unavailable → circuit breaker triggers after 3 failures. Core falls back to slower path (direct LLM calls, skip caching). MemoryError: Redis OOM → evict LRU keys (Redis configured with maxmemory-policy=allkeys-lru). TimeoutError: operation > 5s → return error "cache_timeout" (fail open, continue without cache). |
| **Latency Budget** | SET (simple cache): p99 < 1ms. GET (lookup): p99 < 1ms. HGETALL (goal hierarchy): p99 < 5ms. |
| **Backpressure** | Redis enforces connection limits (pool size 20). Excess requests wait up to 100ms. If timeout, fail open (continue without cache). |
| **Tenant Isolation** | Keys namespaced by tenant_id: `tenant:{tenant_id}:{key_name}`. Redis ACL (if Redis 6+) restricts per-tenant access. Multi-tenant Redis (shared cluster): rely on key namespacing. |
| **Idempotency** | idempotency_cache:{key} stores (request_hash, response) with 24h TTL. Lookup on every request. |
| **Redaction** | Cache values must not contain secrets. Configuration hashes cached; raw config fetched from KMS on demand. |
| **Traceability** | Cache operations logged: CACHE_HIT, CACHE_MISS, CACHE_UPDATE. Correlated via trace_id. |

---

### ICD-034: Core ↔ ChromaDB (Long-Term Memory)

| Field | Value |
|---|---|
| **From** | Core (Memory System, semantic search) |
| **To** | ChromaDB (vector store, tenant-isolated collections) |
| **Direction** | Bidirectional |
| **Protocol** | HTTP REST (Chroma client library) or gRPC |
| **Transport** | Private VPC subnet, unencrypted (localhost:8000 or internal endpoint) |
| **SIL** | 2 |
| **Auth** | ChromaDB running in private VPC; no public access. Optional: shared key (not used; rely on VPC isolation). |
| **Schema** | Collections (per tenant): "memory_{tenant_id}" (documents stored as { id: msg_id, embedding: vec[1536], metadatas: { user_id, timestamp, source }, documents: [conversation_text] }). Queries: upsert (store new messages), query (semantic search top-k), delete (old messages >30d). |
| **Error Contract** | CollectionNotFound: "memory_{tenant_id}" collection does not exist → Core creates on first use (Chroma auto-creates). DuplicateDocumentError: embedding with same ID already exists → update instead of insert. QueryError: malformed query → return empty results (fail safe). |
| **Latency Budget** | Upsert (embedding + store): p99 < 500ms (includes network roundtrip). Query (semantic search, top-10): p99 < 1s. |
| **Backpressure** | ChromaDB queue: max 1000 pending requests per tenant. Excess requests wait. Timeout: 30s. |
| **Tenant Isolation** | Collection name includes tenant_id. ChromaDB multi-tenancy: each tenant has separate collection. No cross-tenant document visibility. |
| **Idempotency** | Upsert by document ID (msg_id). Same msg_id upserted twice → idempotent (replace with new embedding). |
| **Redaction** | Documents stored include conversation text; assume already redacted by Memory System before upsert. |
| **Traceability** | Each upsert/query logged with trace_id. ChromaDB server logs stored externally. |

---

### ICD-035: Engine ↔ Redis (Queue/Pub-Sub)

| Field | Value |
|---|---|
| **From** | Engine (Lanes, Workflow, MCP) |
| **To** | Redis (task queue, pub-sub channels) |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (aioredis) |
| **Transport** | Private VPC subnet, no TLS |
| **SIL** | 2 |
| **Auth** | Redis AUTH via KMS password (see ICD-044). |
| **Schema** | Queues: main_queue_{tenant_id} (LPUSH/RPOP tasks), cron_queue_{tenant_id} (sorted set by execution_time), subagent_queue_{tenant_id}. Pub-Sub: lane_status_{execution_id} (notifications when task completes). Metrics stream: engine_metrics_{tenant_id} (XADD for real-time metrics). |
| **Error Contract** | ConnectionError: Redis unavailable → circuit breaker (3 failures) → Engine continues with in-memory queue (loses durability across restart). QueueFull: queue at max depth → enqueue blocks or returns error (depends on Lane config). TimeoutError: operation > 5s → fail open, continue. |
| **Latency Budget** | LPUSH (enqueue task): p99 < 1ms. RPOP (dequeue): p99 < 1ms. XADD (metric): p99 < 2ms. |
| **Backpressure** | Same as ICD-033. Connection pool 20 per tenant. Queue depth limit 10k per tenant. |
| **Tenant Isolation** | Queue names namespaced by tenant_id. Pub-Sub channels include execution_id (per-execution isolation). |
| **Idempotency** | Not applicable; queues are ephemeral. Durability owned by Workflow Engine checkpoints (see ICD-039). |
| **Redaction** | Queue values (Task JSON) redacted before LPUSH (same as ICD-013). |
| **Traceability** | trace_id included in Task. Pub-Sub notifications include trace_id. |

---

### ICD-036: Observability ↔ PostgreSQL (Partitioned Logs)

| Field | Value |
|---|---|
| **From** | Observability (Event Bus, Logger) |
| **To** | PostgreSQL (time-series logs table, partitioned by tenant + date) |
| **Direction** | Bidirectional (write + query) |
| **Protocol** | Async TCP (asyncpg) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | PostgreSQL role: `holly_observability`. RLS: SELECT ... WHERE tenant_id = context.current_tenant. |
| **Schema** | Table: logs (id SERIAL, tenant_id UUID, timestamp BIGINT, level VARCHAR, logger VARCHAR, message TEXT, trace_id UUID, span_id UUID, user_id UUID, component VARCHAR, event_data JSONB, redacted_hash VARCHAR). Partitions: logs_2026_02_17_tenant_a, logs_2026_02_17_tenant_b, etc. (date + tenant). TTL: 90 days (older partitions archived to S3, then dropped). |
| **Error Contract** | PartitionNotFound: partition for future date does not exist → PostgreSQL auto-create before INSERT. WriteError: replica lag causes write to standby → retry (only write to primary). QueryError: SELECT timeout > 30s → return error "query_too_slow", suggest adding trace_id filter. |
| **Latency Budget** | INSERT log batch (100 rows): p99 < 50ms. SELECT by trace_id: p99 < 100ms (index on trace_id). |
| **Backpressure** | Connection pool 10. Writes queued if pool exhausted. Timeout: 30s. Excess writes buffered in memory (max 10k rows per tenant). |
| **Tenant Isolation** | Partition by tenant + date. RLS policies enforce tenant scoping. No cross-tenant log leakage. |
| **Idempotency** | Logs are append-only; idempotency not applicable. |
| **Redaction** | Logs redacted before INSERT (see ICD-026). JSONB fields scanned for secrets and redacted. |
| **Traceability** | trace_id + span_id in every log entry. User can query: SELECT * FROM logs WHERE trace_id = %s to get full request trace. |

---

### ICD-037: Observability ↔ Redis (Real-Time Metrics)

| Field | Value |
|---|---|
| **From** | Observability (metrics collector) |
| **To** | Redis (real-time streams, dashboards) |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (aioredis) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | Redis AUTH via KMS. |
| **Schema** | Streams: metrics_{tenant_id} (XADD with field:value pairs). Example: { p99_latency_ms: 45, active_tasks: 12, error_rate_5m: 0.01, agents_spawned: 3 }. TTL: streams expire after 7 days (or manual XTRIM). |
| **Error Contract** | ConnectionError: Redis unavailable → metrics buffered in memory, flushed when Redis recovers. StreamFull: stream > 1M events → trim oldest 10%. |
| **Latency Budget** | XADD (append metric): p99 < 5ms. XRANGE (query range): p99 < 100ms (read-only). |
| **Backpressure** | Same as ICD-035. |
| **Tenant Isolation** | Stream names namespaced by tenant_id. |
| **Idempotency** | Not applicable; metrics are time-series. |
| **Redaction** | Metrics are aggregates (counts, latencies); no PII. No redaction. |
| **Traceability** | Metrics include timestamp. Correlation to trace_id optional (can tag events by request type). |

---

### ICD-038: Kernel ↔ PostgreSQL (Audit WAL)

| Field | Value |
|---|---|
| **From** | Kernel (KernelContext, K1–K8 enforcement) |
| **To** | PostgreSQL (kernel_audit_log table) |
| **Direction** | Unidirectional (append-only) |
| **Protocol** | Async TCP (asyncpg) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 (Core) → 3 (Kernel SIL-3, but only audit logging, not operational) |
| **Auth** | PostgreSQL role: `holly_kernel_audit` (write-only to kernel_audit_log). RLS: not enforced (audit table is append-only). |
| **Schema** | Table: kernel_audit_log (id SERIAL, tenant_id UUID, boundary_id VARCHAR, operation VARCHAR, input_hash VARCHAR, output_hash VARCHAR, violations: JSONB[], timestamp BIGINT, trace_id UUID, user_id UUID, permission_mask VARCHAR). Append-only, never updated or deleted. Partitioned by date. |
| **Error Contract** | WriteError: INSERT fails → log to stderr and continue (audit failure does not block operation). Kernel prioritizes forward progress over audit logging. |
| **Latency Budget** | INSERT audit row: p99 < 2ms (asynchronous, non-blocking append). |
| **Backpressure** | Audit writes queued. Timeout: 1s. Excess writes dropped (sampled; log summary). Do not block Kernel. |
| **Tenant Isolation** | tenant_id in audit log. Rows partitioned by tenant + date. |
| **Idempotency** | Not applicable; audit log is append-only. Same operation audited twice = two log entries. |
| **Redaction** | input_hash and output_hash are cryptographic hashes; raw payloads not stored. Kernel applies redaction rules before hashing (see Phase D, step 27). |
| **Traceability** | trace_id stored in audit log. User can query audit log by trace_id for debugging. |

---

### ICD-039: Workflow Engine ↔ PostgreSQL (Checkpoints/Source of Truth)

| Field | Value |
|---|---|
| **From** | Workflow Engine (task graph executor, durability owner) |
| **To** | PostgreSQL (workflow_checkpoints table) |
| **Direction** | Bidirectional (write checkpoints, query for recovery) |
| **Protocol** | Async TCP (asyncpg) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | PostgreSQL role: `holly_engine_writer`. RLS: SELECT/INSERT ... WHERE tenant_id = role_tenant. |
| **Schema** | Table: workflow_checkpoints (workflow_id UUID, node_id UUID, output_state JSONB, checkpoint_timestamp BIGINT, idempotency_key VARCHAR, output_hash VARCHAR, execution_time_ms INT, parent_node_ids UUID[], tenant_id UUID, user_id UUID, trace_id UUID). Primary key: (workflow_id, node_id). Insert mode: UPSERT (ON CONFLICT DO UPDATE). Source of truth for recovery. |
| **Error Contract** | DuplicateKeyError: same (workflow_id, node_id) checkpointed twice → UPSERT, keep latest. ConflictError: constraint violation (e.g., output_hash mismatch) → log warning (idempotency mismatch detected), return cached output. WriteError: I/O error → retry with exponential backoff (1ms, 2ms, 4ms, max 1s). If all retries fail, mark workflow as "needs_manual_recovery". |
| **Latency Budget** | UPSERT checkpoint: p99 < 50ms. SELECT for recovery (scan all nodes in workflow): p99 < 200ms. |
| **Backpressure** | Write queue: max 1000 pending checkpoints per tenant. Timeout: 30s. If exceeded, return error (caller must implement retry). |
| **Tenant Isolation** | tenant_id immutable in checkpoint. All checkpoints for a workflow scoped by tenant. |
| **Idempotency** | Workflow Engine deduplicates by (workflow_id, node_id, input_hash). On re-execution, Kernel (K5) detects idempotency key collision and returns cached output. Checkpoint stores output_hash for verification. |
| **Redaction** | output_state may contain sensitive data (LLM completions, file contents); redacted before checkpoint persist. Sensitive fields removed or hashed. |
| **Traceability** | trace_id stored with checkpoint. On recovery, Workflow Engine logs "recovering_from_checkpoint" with trace_id. |

---

### ICD-040: Engine ↔ PostgreSQL (Task State / Queryable Projection)

| Field | Value |
|---|---|
| **From** | Engine (Lanes, task manager) |
| **To** | PostgreSQL (task_state table) |
| **Direction** | Bidirectional (write + query) |
| **Protocol** | Async TCP (asyncpg) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | PostgreSQL role: `holly_engine_writer`. |
| **Schema** | Table: task_state (task_id UUID, execution_id UUID, status VARCHAR, started_at BIGINT, completed_at BIGINT, result JSONB, error JSONB, retries_attempted INT, next_retry_time BIGINT, lane_type VARCHAR, tenant_id UUID, user_id UUID, trace_id UUID). Updated on task state change (enqueued → running → completed/failed). Queryable projection (not source of truth). Source of truth: Workflow Engine checkpoints (ICD-039). |
| **Error Contract** | WriteError: INSERT or UPDATE fails → log and continue (task_state is for monitoring, not critical). QueryError: SELECT timeout → return partial results or error "query_too_slow". |
| **Latency Budget** | UPDATE on state change: p99 < 20ms. SELECT all tasks for tenant: p99 < 100ms (with index on tenant_id, status). |
| **Backpressure** | Write queue: max 5000 pending updates per tenant. Timeout: 30s. Excess updates dropped (task_state is eventually consistent). |
| **Tenant Isolation** | tenant_id in task_state. RLS: SELECT ... WHERE tenant_id = current_tenant. |
| **Idempotency** | Task state updates are idempotent (status: running → completed, never goes backward). Duplicate state changes merged. |
| **Redaction** | result and error fields may contain sensitive data; redacted before INSERT. |
| **Traceability** | trace_id in task_state. User can query task by trace_id to see state timeline. |

---

### ICD-041: Memory System ↔ Redis (Short-Term Memory)

| Field | Value |
|---|---|
| **From** | Memory System (L2 cache manager) |
| **To** | Redis |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (aioredis) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | Redis AUTH via KMS. |
| **Schema** | Keys: conversation_context:{conversation_id} (TTL 7 days, value: [Message]), agent_short_term_{agent_id} (TTL 30 min, value: { recent_memories: [str] }), goal_hierarchy_cache:{user_id}:{intent_hash} (TTL 1h). |
| **Error Contract** | ConnectionError: Redis unavailable → Memory System falls back to PostgreSQL (slower). KeyNotFound: expected key missing → return empty result (cache miss). |
| **Latency Budget** | GET: p99 < 1ms. SET: p99 < 1ms. |
| **Backpressure** | Same as ICD-033. |
| **Tenant Isolation** | Keys namespaced by tenant_id. |
| **Idempotency** | Cache misses tolerated; eventual consistency. |
| **Redaction** | Cache values redacted before SET. Conversation context assumed already redacted. |
| **Traceability** | Cache operations logged (CACHE_HIT, CACHE_MISS). Correlated via trace_id. |

---

### ICD-042: Memory System ↔ PostgreSQL (Medium-Term Memory)

| Field | Value |
|---|---|
| **From** | Memory System (L1 in-process + L2 cache manager) |
| **To** | PostgreSQL (memory_store table) |
| **Direction** | Bidirectional |
| **Protocol** | Async TCP (asyncpg) |
| **Transport** | Private VPC subnet |
| **SIL** | 2 |
| **Auth** | PostgreSQL role: `holly_memory_writer`. |
| **Schema** | Table: memory_store (id UUID, conversation_id UUID, agent_id UUID, memory_type VARCHAR ("conversation" \| "decision" \| "fact"), content TEXT, embedding_id UUID (links to ChromaDB), timestamp BIGINT, tenant_id UUID, retention_days INT). TTL: 30 days (or specified in retention_days). |
| **Error Contract** | WriteError: INSERT fails → log and continue (memory loss tolerated for forward progress). QueryError: SELECT timeout → return partial results. |
| **Latency Budget** | INSERT memory: p99 < 20ms. SELECT memories for agent: p99 < 100ms. |
| **Backpressure** | Write queue: max 1000 per tenant. Timeout: 30s. |
| **Tenant Isolation** | tenant_id in memory_store. RLS enforces row-level scoping. |
| **Idempotency** | Same memory inserted twice (same conversation_id + content_hash) → idempotent (ignore duplicate). |
| **Redaction** | Memory content redacted before INSERT. Sensitive fields removed. |
| **Traceability** | embedding_id links to ChromaDB vector. trace_id optional (logged separately). |

---

### ICD-043: Memory System ↔ ChromaDB (Long-Term Memory)

| Field | Value |
|---|---|
| **From** | Memory System (semantic search coordinator) |
| **To** | ChromaDB |
| **Direction** | Bidirectional |
| **Protocol** | HTTP REST or gRPC |
| **Transport** | Private VPC subnet, unencrypted |
| **SIL** | 2 |
| **Auth** | VPC isolation (no auth). |
| **Schema** | Collection: "memory_{tenant_id}". Documents: { id: memory_id, embedding: vec[1536], metadatas: { conversation_id, agent_id, memory_type, timestamp }, documents: [content] }. Operations: upsert (store memory with embedding), query (semantic search for related memories), delete (old memories >30d). |
| **Error Contract** | Same as ICD-034. |
| **Latency Budget** | Same as ICD-034. Upsert: p99 < 500ms. Query: p99 < 1s. |
| **Backpressure** | Same as ICD-034. |
| **Tenant Isolation** | Collection per tenant (memory_{tenant_id}). |
| **Idempotency** | Same as ICD-034. Upsert by memory_id is idempotent. |
| **Redaction** | Same as ICD-034. Documents assumed redacted. |
| **Traceability** | Each upsert/query logged with trace_id. |

---

### ICD-044: KMS → Egress Gateway (API Keys)

| Field | Value |
|---|---|
| **From** | Secrets Manager (KMS / AWS Secrets Manager / Vault) |
| **To** | Egress Gateway (in-process initialization) |
| **Direction** | Unidirectional (fetch on startup) |
| **Protocol** | In-process (KMS client SDK call) or HTTPS (to Secrets Manager API) |
| **Transport** | Private VPC subnet, TLS if external call |
| **SIL** | 3 |
| **Auth** | IAM role (EC2 instance profile on ECS task). No explicit auth needed; AWS handles role assumption. |
| **Schema** | Request: GET /secret/holly/claude_api_key_{tenant_id}. Response: { secret: "sk-ant-...", arn: "arn:aws:secretsmanager:...", version_id: UUID, rotation_timestamp: Unix timestamp }. Egress caches in memory with TTL 1h (re-fetch periodically). |
| **Error Contract** | SecretNotFound: key does not exist → Egress fails startup (fatal error). Auth failure: IAM role lacks permission → Egress fails startup. RateLimitError: Secrets Manager rate limit → retry with exponential backoff. Decryption failed: KMS unavailable → retry. |
| **Latency Budget** | Fetch (on startup): p99 < 100ms. In-memory lookup (during request): p99 < 0.01ms. |
| **Backpressure** | Startup only (no per-request fetches). Caching avoids repeated calls. |
| **Tenant Isolation** | Secret name includes tenant_id. Each tenant's API key separate. No cross-tenant key leakage. |
| **Idempotency** | Fetch is idempotent. Same secret_id fetched multiple times returns same value (or newer version if rotated). |
| **Redaction** | API key never logged. Only secret_arn and version_id logged. Egress masks key in all traces. |
| **Traceability** | KMS fetch logged once at startup with timestamp. On key rotation, new fetch logged. No per-request logging of key usage. |

---

### ICD-045: KMS → PostgreSQL (DB Credentials)

| Field | Value |
|---|---|
| **From** | Secrets Manager (KMS) |
| **To** | PostgreSQL (connection string: user, password) |
| **Direction** | Unidirectional (fetch on startup) |
| **Protocol** | In-process or HTTPS (to Secrets Manager) |
| **Transport** | Private VPC subnet, TLS if external |
| **SIL** | 3 |
| **Auth** | IAM role (ECS task). |
| **Schema** | Request: GET /secret/holly/postgres_creds_{env}. Response: { user: "holly_core_tenant_a", password: "...", host: "postgres.internal", port: 5432 }. Core caches in memory with TTL 15 min (periodically re-fetch for password rotation). |
| **Error Contract** | Same as ICD-044. |
| **Latency Budget** | Fetch: p99 < 100ms. Connection pool: reuses authenticated connections. |
| **Backpressure** | Startup + periodic refresh. No per-query fetch. |
| **Tenant Isolation** | PostgreSQL role per tenant (user: holly_core_{tenant_id}). KMS secret fetch returns per-tenant credentials. |
| **Idempotency** | Fetch idempotent. Password rotation triggers new fetch (KMS version changes). |
| **Redaction** | Password never logged. Only username and host logged. |
| **Traceability** | KMS fetch logged at startup and on rotation. Correlation to deployment version. |

---

### ICD-046: KMS → MCP Registry (Tool Credentials)

| Field | Value |
|---|---|
| **From** | Secrets Manager (KMS) |
| **To** | MCP Tool Registry (per-tool credentials) |
| **Direction** | Unidirectional (fetch on tool registration) |
| **Protocol** | In-process or HTTPS |
| **Transport** | Private VPC subnet, TLS if external |
| **SIL** | 3 |
| **Auth** | IAM role (ECS task). |
| **Schema** | Request: GET /secret/holly/tool_{tool_name}_{tenant_id}. Response: { api_key, auth_header, etc. (tool-specific) }. MCP Registry caches per tool with TTL 24h. |
| **Error Contract** | Same as ICD-044. ToolCredentialNotFound: tool has no registered credentials → return empty credentials (tool runs without auth). |
| **Latency Budget** | Fetch (on tool registration): p99 < 100ms. Lookup (during invocation): p99 < 0.01ms. |
| **Backpressure** | Lazy fetch (on tool first use). Caching avoids repeated calls. |
| **Tenant Isolation** | Secret name includes tenant_id. Per-tenant tool credentials. |
| **Idempotency** | Fetch idempotent. |
| **Redaction** | Credentials never logged. Only tool_name and fetch timestamp logged. Registry masks credentials in all spans. |
| **Traceability** | Tool credential fetch logged on registration. |

---

### ICD-047: Authentik → JWT Middleware (HTTPS JWKS Endpoint)

| Field | Value |
|---|---|
| **From** | Authentik (OIDC provider) |
| **To** | JWT Middleware (JWKS public key endpoint) |
| **Direction** | Unidirectional (fetch) |
| **Protocol** | HTTPS |
| **Transport** | TLS 1.3, public JWKS endpoint (typically /.well-known/openid-configuration + /jwks) |
| **SIL** | 2 |
| **Auth** | No authentication (public JWKS endpoint). |
| **Schema** | Request: GET /.well-known/openid-configuration → Response: { issuer: "https://auth.holly.io", jwks_uri: "https://auth.holly.io/.well-known/jwks.json", ... }. Request: GET /.well-known/jwks.json → Response: { keys: [ { kty: "RSA", kid: "...", use: "sig", n: "...", e: "AQ", alg: "RS256" } ] }. |
| **Error Contract** | ConnectionError: Authentik unavailable → JWT Middleware uses cached JWKS (from Redis, see ICD-049). Timeout: 5s. ServerError (5xx): Authentik backend failure → use cached JWKS. InvalidResponse: JWKS malformed → log error, continue with cached keys. |
| **Latency Budget** | Fetch JWKS: p99 < 1s (done at startup and refresh). Token validation (using cached keys): p99 < 5ms. |
| **Backpressure** | Not applicable; JWKS fetch is periodic (1h interval) + on-demand (if kid not in cache). |
| **Tenant Isolation** | Single Authentik instance serves all tenants. JWKS keys are shared. Tenant identity embedded in JWT claim (org or tenant_id claim). |
| **Idempotency** | JWKS fetch idempotent. Same endpoint always returns same public keys (until rotation). |
| **Redaction** | JWKS is public key material; no secrets. No redaction. |
| **Traceability** | JWKS fetch logged at startup. Key rotation logged when new kid appears. |

---

### ICD-048: KMS → Authentik (Client Secret)

| Field | Value |
|---|---|
| **From** | Secrets Manager (KMS) |
| **To** | Authentik (in-process config) |
| **Direction** | Unidirectional (fetch on startup) |
| **Protocol** | In-process or HTTPS (to Secrets Manager) |
| **Transport** | Private VPC subnet, TLS if external |
| **SIL** | 3 |
| **Auth** | IAM role (ECS task). |
| **Schema** | Request: GET /secret/holly/authentik_client_secret. Response: { client_id: "holly", client_secret: "...", issuer_url: "https://auth.holly.io" }. Authentik loads in memory at startup. Secret passed to authorization code token exchange (ICD-005). |
| **Error Contract** | Same as ICD-044. |
| **Latency Budget** | Fetch: p99 < 100ms. |
| **Backpressure** | Startup only. No per-request fetch. |
| **Tenant Isolation** | Single Authentik instance for all tenants. Client secret is global. |
| **Idempotency** | Fetch idempotent. |
| **Redaction** | client_secret never logged. Only client_id logged. |
| **Traceability** | KMS fetch logged at startup. |

---

### ICD-049: JWT Middleware ↔ Redis (Revocation Cache Lookup)

| Field | Value |
|---|---|
| **From** | JWT Middleware (token validation) |
| **To** | Redis (token revocation list cache) |
| **Direction** | Unidirectional (lookup) |
| **Protocol** | Async TCP (aioredis) |
| **Transport** | Private VPC subnet, no TLS |
| **SIL** | 2 |
| **Auth** | Redis AUTH via KMS. |
| **Schema** | Key: revoked_token:{token_jti} (TTL = token.exp - now). Value: null (existence indicates revocation). Operation: EXISTS revoked_token:{jti}. If key exists, token is revoked. If Redis unavailable, fail open (allow token if signature valid). |
| **Error Contract** | ConnectionError: Redis unavailable → JWT Middleware allows token (fail open for availability). Timeout: 100ms → fail open. |
| **Latency Budget** | Revocation lookup: p99 < 1ms. |
| **Backpressure** | Not applicable; lookup is O(1). No backpressure. |
| **Tenant Isolation** | Revocation keys include tenant_id (optional, for logging). Logically scoped per tenant. |
| **Idempotency** | Revocation is idempotent. Same token revoked twice = same revocation state. |
| **Redaction** | Key is hash of JTI; no secrets. No redaction. |
| **Traceability** | Revocation lookup logged: REVOCATION_HIT or REVOCATION_MISS. Correlated via trace_id (optional). |

---

## Cross-Reference Matrix: ICD ↔ SAD Arrows

This matrix maps each SAD connection arrow to the corresponding ICD entry (or entries).


| SAD Arrow | ICD Entry | Description |
|---|---|---|
| UI → ALB | ICD-001 | User browser requests to load balancer |
| ALB → JWT Middleware | ICD-002 | ALB forwards request to middleware for token validation |
| JWT Middleware → Core | ICD-003 | Validated claims forwarded to Core handlers |
| Authentik ↔ UI | ICD-004 | OIDC login flow (redirect chains) |
| ALB → Authentik | ICD-005 | /auth/* path routed to Authentik; token exchange |
| Core ↔ Kernel | ICD-006 | Core calls KernelContext for invariant enforcement |
| Engine ↔ Kernel | ICD-007 | Engine calls KernelContext for task safety |
| Conversation → Intent | ICD-008 | Message input classified by Intent Classifier |
| Intent → Goals | ICD-009 | Intent decomposed into 7-level goal hierarchy |
| Goals → APS | ICD-010 | Goal hierarchy routed through APS tier classifier |
| APS → Topology | ICD-011 | Tier assignment triggers Topology Manager spawn/steer |
| Topology → Engine | ICD-012 | Topology bound agents dispatched to Engine lanes |
| Core → Main Lane | ICD-013 | User-initiated tasks dispatched to Main Lane queue |
| Core → Cron Lane | ICD-014 | Scheduled tasks registered with Cron Lane |
| Topology → Subagent Lane | ICD-015 | Team agents spawned into Subagent Lane |
| Lane Policy ↔ Main | ICD-016 | Policy governs Main Lane concurrency and rate limits |
| Lane Policy ↔ Cron | ICD-017 | Policy governs Cron Lane scheduling and limits |
| Lane Policy ↔ Subagent | ICD-018 | Policy governs Subagent Lane concurrency |
| Main Lane → MCP | ICD-019 | Main Lane dequeues tasks, invokes tools via MCP |
| Subagent Lane → MCP | ICD-020 | Subagent tasks invoked through MCP Registry |
| MCP ↔ Workflow | ICD-021 | MCP coordinates task execution with Workflow Engine checkpoints |
| MCP → Sandbox | ICD-022 | Code execution tool invokes Sandbox via gRPC (SIL-3 boundary) |
| Engine → Event Bus | ICD-023 | Engine emits task, lane, and execution events |
| Core → Event Bus | ICD-024 | Core emits intent, goal, topology events |
| Event Bus → WebSocket | ICD-025 | Events fanout to 9 per-tenant WebSocket channels |
| Event Bus → Logging | ICD-026 | Events persisted as structured JSON logs |
| Observability → UI | ICD-027 | WebSocket stream delivery to Console (9 channels) |
| Core → Egress | ICD-028 | Core LLM calls routed through Egress proxy |
| Subagent → Egress | ICD-029 | Subagent LLM calls routed through Egress proxy |
| Egress → Claude API | ICD-030 | Egress makes allowlisted calls to Claude API (SIL-3 boundary) |
| Core → Ollama | ICD-031 | Local inference for cost-sensitive tasks |
| Core ↔ PostgreSQL | ICD-032 | Core reads/writes state, history, audit |
| Core ↔ Redis | ICD-033 | Core caches goal hierarchies, conversations, checkpoints |
| Core ↔ ChromaDB | ICD-034 | Core semantic search for long-term memory |
| Engine ↔ Redis | ICD-035 | Engine task queues, metrics streams in Redis |
| Observability ↔ PostgreSQL | ICD-036 | Logs written to partitioned time-series table |
| Observability ↔ Redis | ICD-037 | Real-time metrics streamed to Redis |
| Kernel ↔ PostgreSQL | ICD-038 | Kernel audit WAL persisted to append-only audit table |
| Workflow ↔ PostgreSQL | ICD-039 | Workflow checkpoints (source of truth for recovery) |
| Engine ↔ PostgreSQL | ICD-040 | Task state queryable projection for monitoring |
| Memory System ↔ Redis | ICD-041 | Memory Layer 2 cache (short-term) |
| Memory System ↔ PostgreSQL | ICD-042 | Memory Layer 1.5 (medium-term, retention policy) |
| Memory System ↔ ChromaDB | ICD-043 | Memory Layer 0 (long-term vectors for semantic search) |
| KMS → Egress | ICD-044 | API key provisioning for Claude API access |
| KMS → PostgreSQL | ICD-045 | Database credential provisioning |
| KMS → MCP | ICD-046 | Per-tool credential provisioning |
| Authentik → JWT Middleware | ICD-047 | JWKS public key endpoint for token verification |
| KMS → Authentik | ICD-048 | Authentik client secret provisioning |
| JWT Middleware ↔ Redis | ICD-049 | Token revocation cache for fast invalidation |

---

## Glossary of Terms

- **SIL:** Safety Integrity Level (ISO 26262). SIL-1 = standard components. SIL-2 = safety-critical (core logic, storage). SIL-3 = highest rigor (Kernel, Sandbox, Egress, crypto).
- **Kernel:** Layer 1 in-process enforcer. Wraps every boundary with schema validation (K1), permissions (K2), bounds checking (K3), trace injection (K4), idempotency (K5), WAL (K6), HITL gates (K7), eval gates (K8).
- **KernelContext:** Python async context manager (async with KernelContext(...)) that enforces Kernel discipline. Entry point for all boundary crossings.
- **KernelViolation:** Exception raised by Kernel when contract is breached (schema mismatch, permission denied, bounds exceeded).
- **Tenant Isolation:** Multi-tenancy enforced at every boundary. tenant_id immutable within a request/operation. No cross-tenant data exposure.
- **Redaction:** Removal of PII/secrets from logs, events, and audit trails before persistence or transmission.
- **Trace ID / Span ID:** Correlation IDs injected at entry point (JWT Middleware) and propagated end-to-end through all hops (X-Trace-ID header, trace_id field in logs/events).
- **Backpressure:** How overload is handled. Queues have max depths. Rate limits applied per-tenant. Timeouts enforced. Excess requests dropped or delayed.
- **Idempotency Key:** RFC 8785 canonical form. Same key within 24h window returns cached result. Prevents duplicate LLM calls, duplicate task executions.
- **RLS (Row-Level Security):** PostgreSQL feature to enforce tenant scoping at the database layer. Queries automatically filtered by tenant_id.
- **mTLS (Mutual TLS):** Client and server authenticate via certificates. Used for Sandbox ↔ MCP Registry boundary (gRPC, SIL-3).

---

## Compliance Notes

1. **Every boundary crossing is subject to this ICD.** Code that implements a boundary outside this contract is out of spec.
2. **SIL inheritance:** Higher-SIL endpoint determines the boundary's SIL. Sandbox is SIL-3 (gRPC call is SIL-3). Claude API is SIL-3 (HTTPS call is SIL-3).
3. **Error contracts are binding.** Callers must handle specified error codes and respect retry_after headers.
4. **Latency budgets are targets.** p99 latency must be monitored; sustained violations trigger scaling or optimization.
5. **Tenant isolation is non-negotiable.** Any cross-tenant data leakage is a security incident.
6. **Redaction is mandatory.** Secrets and PII must be stripped before logs/events leave the system.
7. **Traceability is continuous.** Every request must carry trace_id end-to-end for debuggability.

---

## Appendix A: Kernel Boundary Wrapping Pattern

All in-process boundaries in Holly Core and Engine use the KernelContext pattern:

```python
async with KernelContext(
    boundary_id="ICD-006",  # e.g., "Core ↔ Kernel"
    tenant_id=user_request.tenant_id,
    user_id=user_request.user_id,
    operation="goals_decompose",
    schema_definition=GoalDecomposerRequest,
    permission_mask=["read:goals", "write:goals"],
) as ctx:
    # User code runs here
    result = await goal_decomposer.decompose(request)
    # Kernel validates request schema, checks permissions, injects trace_id
    # Kernel audits result (input_hash, output_hash)
    # On exit: K1-K8 checks complete, audit logged
    return result
```

Every boundary crossing is wrapped. Violations raise KernelViolation with HTTP status code and detail.

---

## Appendix B: Tenant Isolation Enforcement Checklist

For every interface, verify:

- [ ] tenant_id parameter present (input)
- [ ] tenant_id validated against JWT claim (input validation)
- [ ] All queries filtered by tenant_id (SQL: WHERE tenant_id = %s)
- [ ] No tenant_id override or bypass possible
- [ ] Cross-tenant JOIN operations impossible (schema enforces isolation)
- [ ] Error messages do not leak tenant data
- [ ] Logs redacted for PII (user names, conversation text)

---

## Appendix C: Latency Budget Monitoring

Set up alerting for sustained violations:

- **p99 latency > budget:** Page on-call
- **Error rate > 5%:** Page on-call
- **Queue depth > 80% max:** Warning
- **Rate limit hits > 10/min per tenant:** Warning

Latency budgets should be monitored per-interface per-tenant. Use distributed tracing (trace_id spans) to identify bottleneck hops.

---

## Document History

| Version | Date | Author | Changes |
|---|---|---|---|
| 0.1 | 2026-02-17 | Claude Code | Initial ICD document covering all 49 boundary crossings from SAD v0.1.0.5 |

---

**End of Interface Control Document v0.1**

