# Holly Grace — Component Behavior Specifications (SIL-3)

**Generated:** 17 February 2026 | **Source:** SAD v0.1.0.5 | **SIL Level:** 3

---

## Overview

This document specifies the formal behavior of all SIL-3 components in the Holly Grace platform. SIL-3 (Safety Integrity Level 3) requires:

1. **Formal specification** — Every component must have a mathematical or logical specification of its state machine, invariants, and failure modes
2. **Property-based testing** — Generative test suites that exercise the specification across a wide input domain
3. **Independent verification** — A dissimilar verification channel that checks safety properties without relying on the component's implementation
4. **Formal proof or model-checking** — TLA+ or similar model-based verification that the specification satisfies key safety properties

The three SIL-3 component groups are:

- **Kernel (Layer 1):** KernelContext + K1–K8 (eight invariant-enforcement gates)
- **Sandbox:** Code Executor + Security Boundary (isolated code execution with network/filesystem/process isolation)
- **Egress Control:** L7 Application-Layer + L3 NAT (network egress enforcement)

This document follows the structure of an ISO 26262 / IEC 61508 functional safety specification: each component defines its purpose, state machine, invariants, decision logic, error behavior, failure predicates, and acceptance criteria. The state machines enumerate ALL states and ALL transitions with explicit guard conditions. Invariants are stated as formal predicates where possible. Failure predicates are exhaustive — they name every way the component can fail.

---

## 1. Kernel (Layer 1)

### 1.1 KernelContext

**Purpose:** Async context manager that wraps every boundary crossing, ensuring atomic entry/exit and preventing re-entrancy, cancellation-related violations, and untraced operations.

**Ownership:** Every boundary crossing in Holly (Conversation → Intent, Intent → Goals, Goals → APS, APS → Engine, Engine → MCP, MCP → Sandbox, Core/Engine → Egress, Egress → External) is wrapped in a `KernelContext` instance. The context is the unit of atomicity for kernel invariant enforcement.

**State Machine:**

| State | Entry Guard | Meaning | Transitions |
|-------|-------------|---------|-------------|
| **IDLE** | N/A | No active context; boundary crossing blocked | → ENTERING (on context manager `__aenter__`) |
| **ENTERING** | Called from sync or async task | KernelContext.__aenter__ executing; k1–k8 gates not yet run | → ACTIVE (on successful gate passage) \| → FAULTED (on gate failure) |
| **ACTIVE** | All k1–k8 gates passed | Boundary crossing in flight; operation executing inside boundary | → EXITING (on operation completion) \| → FAULTED (on async cancellation or eval gate failure) |
| **EXITING** | Operation complete, exit guards running | KernelContext.__aexit__ executing; cleanup (WAL finalize, trace injection, metrics emit) running | → IDLE (on successful exit) \| → FAULTED (on exit gate failure) |
| **FAULTED** | Any gate or boundary operation failed | Boundary crossing aborted; exception raised to caller | → IDLE (after exception handler consumes exception) |

**Formal State Machine Diagram (Mermaid):**

```
IDLE --> ENTERING: __aenter__()
ENTERING --> ACTIVE: all k1-k8 gates pass ✓
ENTERING --> FAULTED: gate k[n] fails
ACTIVE --> EXITING: operation completes
ACTIVE --> FAULTED: async cancel() or eval gate fails
EXITING --> IDLE: __aexit__() completes
EXITING --> FAULTED: exit gate fails (e.g., WAL write failure)
FAULTED --> IDLE: exception consumed by caller
```

**Guard Conditions:**

- **Entry:** Caller must have active event loop (synchronous callers blocked with `RuntimeError`)
- **Active→Exiting:** No async cancellation tokens pending, or cancellation deferred until after exit
- **Exit:** Trace must be complete; WAL entry must be written; all metrics flushed
- **Faulted→Idle:** Exception must propagate (no silent swallowing)

**Invariants:**

1. **∀ boundary_crossing ∈ BoundaryCrossings: crossing.context ≠ null**
   - No operation crosses a boundary without an active KernelContext.

2. **∀ context ∈ KernelContexts: count(active(context)) ≤ 1 per task**
   - A single async task cannot hold multiple active contexts simultaneously (re-entrancy prevention).

3. **∀ context ∈ KernelContexts: context.state ∈ {IDLE, ENTERING, ACTIVE, EXITING, FAULTED}**
   - Context can be in one of exactly five states; no undefined state.

4. **∀ transition: guard_condition(transition) must evaluate deterministically**
   - Guards are pure functions; no side effects on evaluation.

5. **∀ context.ACTIVE: k1.schema_validation ✓ ∧ k2.permissions ✓ ∧ k3.bounds ✓ ∧ k4.trace ✓ ∧ k5.idempotency ✓ ∧ k6.wal ✓ ∧ k7.hitl ✓ ∧ k8.eval ✓**
   - No context can be ACTIVE unless all eight gates have evaluated successfully.

6. **∀ WAL_entry: WAL_entry.written ⟹ (correlation_id ≠ null ∧ tenant_id ≠ null ∧ timestamp ≠ null)**
   - Every WAL entry carries correlation ID, tenant ID, and timestamp; no partial entries.

7. **∀ context.EXITING: ¬∃ pending_async_task(context)**
   - Exit cannot proceed while spawned async tasks are still running (structured concurrency).

**Failure Predicates:**

A KernelContext fails when:

- **Missing Event Loop:** Synchronous code path attempted entry → RuntimeError
- **Re-entrant Entry:** Same task tried to enter nested KernelContext → RuntimeError
- **Gate Failure:** Any k1–k8 gate raised an exception → exception propagates, context→FAULTED
- **Cancellation During Active:** AsyncCancellationError raised while ACTIVE → defer cancellation until EXITING, then re-raise
- **WAL Write Failure:** Postgres write failed during EXITING → context→FAULTED, exception propagates
- **Trace Injection Failure:** Correlation ID generation failed → context→FAULTED
- **Eval Gate Failure:** K8 predicate evaluated to False → context→HALTED (special FAULTED substate), exception propagates with details
- **Timeout During Entering/Exiting:** Gate execution exceeded timeout → context→FAULTED, TimeoutError raised
- **State Violation:** Transition attempted from invalid state (e.g., FAULTED→ACTIVE) → AssertionError in debug mode, silent noop in production (gates re-run on retry)

**Acceptance Criteria:**

1. **Entry Atomicity:** Test that concurrent tasks entering KernelContext are serialized or each gets its own context instance (no leakage).
   - Assert: Two concurrent tasks each hold independent context objects with distinct correlation IDs.

2. **Exit Guarantees:** Test that exiting always completes, even under cancellation.
   - Assert: No cancellation can bypass __aexit__; WAL entry always written before context freed.

3. **State Invariants:** Test that context never violates the state machine.
   - Property-based test: For any sequence of operations (enter, gate passes, cancel, exit), context state always matches expected state in diagram.

4. **Nested Context Detection:** Test that attempting to re-enter from same task raises error.
   - Assert: task.context.enter() raises RuntimeError if task.context.state != IDLE.

5. **Exception Propagation:** Test that gate failures always raise exceptions to caller, never silent failures.
   - Assert: For each gate k1–k8, a failing gate raises exception; exception.context is FAULTED; exception propagates to caller.

6. **WAL Finality:** Test that every successful boundary crossing produces exactly one WAL entry.
   - Assert: Count of WAL entries created = count of boundary crossings where context.state == IDLE (after exit).

---

### 1.2 K1 — Schema Validation

**Purpose:** Validates incoming payload against an Interface Control Document (ICD) schema at the boundary. Prevents malformed, incomplete, or type-mismatched payloads from crossing into the system.

**Input Domain:**

- **Payload:** Any JSON object, with type annotations (OpenAPI 3.1 schema)
- **Schema:** Referenced by boundary identifier (e.g., "core/intent_classifier/input_v1.0")
- **Resolution:** Schemas loaded from `architecture.yaml` or a schema registry service

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **WAITING** | K1 gate not yet invoked | → RESOLVING (on __enter__) |
| **RESOLVING** | Schema lookup in progress | → RESOLVED (schema found) \| → NOT_FOUND (schema not found) |
| **RESOLVED** | Schema loaded and parsed | → VALIDATING (on payload receipt) |
| **VALIDATING** | Payload validation in progress | → VALID (payload matches schema) \| → INVALID (payload violates schema) |
| **VALID** | Payload conforms to schema | → IDLE (exit gate, proceed) |
| **INVALID** | Payload rejected | → FAULTED (raise ValidationError) |
| **NOT_FOUND** | Schema not found or unreadable | → FAULTED (raise SchemaNotFoundError) |

**Decision Logic (in pseudocode):**

```
function k1_validate(payload, schema_id, context):
  // 1. Resolve schema
  schema = schema_registry.get(schema_id)
  if schema is null:
    context.state = NOT_FOUND
    raise SchemaNotFoundError(f"Schema {schema_id} not found")
  context.state = RESOLVED

  // 2. Validate payload against schema
  result = jsonschema.validate(payload, schema)
  if result.valid:
    context.state = VALID
    return payload
  else:
    context.state = INVALID
    raise ValidationError(
      schema_id=schema_id,
      payload=payload,
      errors=result.errors,
      trace_id=context.correlation_id
    )
```

**Invariants:**

1. **No unvalidated payload crosses a boundary:**
   - ∀ crossing ∈ BoundaryCrossings: crossing.payload.validated ∧ crossing.schema ≠ null

2. **Schema resolution is deterministic:**
   - ∀ schema_id: schema_registry.get(schema_id) returns same object on every call (idempotent)

3. **Validation errors are immutable:**
   - ∀ error ∈ ValidationErrors: error.timestamp, error.schema_id, error.payload_hash are fixed at error creation time

4. **Payload is not mutated during validation:**
   - ∀ payload: validate(payload) ⟹ payload === payload_before_validation (deep equality)

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|-----------------|---|---|---|---|
| Schema not found | `SchemaNotFoundError` | Yes (ERROR level) | Yes (trace.k1_schema_missing) | Context → FAULTED |
| Schema parse failure | `SchemaParseError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Payload validation failure | `ValidationError` | Yes (WARN level, PII redacted) | Yes (trace.k1_invalid_payload) | Context → FAULTED |
| Schema resolve timeout | `TimeoutError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Payload too large | `PayloadTooLargeError` | Yes (WARN level) | Yes | Context → FAULTED |

**Failure Predicates:**

K1 fails when:

1. **Schema Not Found:** Schema registry doesn't contain schema_id → raise SchemaNotFoundError
2. **Schema Malformed:** Schema syntax invalid (e.g., circular reference, invalid type) → raise SchemaParseError
3. **Payload Type Mismatch:** Field type doesn't match schema (e.g., string where int expected) → raise ValidationError
4. **Required Field Missing:** Schema requires field, payload omits it → raise ValidationError
5. **Additional Properties Disallowed:** Schema disallows additional fields, payload contains them → raise ValidationError
6. **Constraint Violation:** Field value violates constraint (e.g., string length, numeric range) → raise ValidationError
7. **Resolution Timeout:** Schema registry not responding within 5 seconds → raise TimeoutError
8. **Payload Size Exceeded:** Payload > 10 MB → raise PayloadTooLargeError
9. **Nested Depth Exceeded:** Payload nesting depth > 20 → raise PayloadTooLargeError

**Acceptance Criteria:**

1. **Valid Payload Passes:** A payload conforming to schema passes K1 without raising exception.
   - Assert: k1_validate(valid_payload, schema_id) → returns payload unchanged

2. **Invalid Payload Fails:** A payload violating any schema constraint raises ValidationError.
   - Property test: For schema S and payload P where ¬valid(P, S), k1_validate(P, S) raises ValidationError

3. **Schema Caching:** Schema is resolved once per boundary crossing, not repeatedly.
   - Assert: Two calls to k1 with same schema_id result in single schema registry lookup (observable via mocking)

4. **Error Details:** ValidationError contains original payload (redacted), schema ID, and specific field errors.
   - Assert: error.schema_id == schema_id ∧ error.errors is list of field-level violations

5. **Timeout Enforcement:** If schema resolution exceeds 5 seconds, TimeoutError is raised.
   - Assert: k1_validate(..., timeout=5) with slow registry → TimeoutError after 5 seconds

6. **Large Payload Rejection:** Payload > 10 MB raises PayloadTooLargeError.
   - Assert: k1_validate(large_payload, schema) → PayloadTooLargeError if len(large_payload) > 10 MB

7. **Payload Immutability:** Original payload object is not modified by validation.
   - Assert: payload_id_before == payload_id_after (identity check), and deep equality holds

---

### 1.3 K2 — Permission Gates

**Purpose:** Checks caller permissions against required permissions for the boundary crossing. Enforces least-privilege and prevents unauthorized callers from proceeding.

**Input Domain:**

- **Caller JWT:** Signed JWT from Authentik, containing claims: sub (user ID), email, roles, org_id, tenant_id
- **Required Permissions:** Mask of permissions (e.g., "goal:read", "workflow:execute"), specified per boundary in ICD
- **Permission Resolution:** Roles → permission sets, via Authentik RBAC or Redis cache

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **AWAITING_JWT** | K2 waiting for caller claims | → EXTRACTING (on JWT provided by middleware) |
| **EXTRACTING** | Extracting claims from JWT | → CLAIMS_VALID (claims well-formed) \| → INVALID_JWT (malformed JWT) |
| **CLAIMS_VALID** | JWT claims extracted | → RESOLVING_PERMISSIONS (resolve roles → permissions) |
| **RESOLVING_PERMISSIONS** | Fetching permission set from role mapping | → PERMISSIONS_RESOLVED (mapping found) \| → REVOKED (token revoked in Redis) \| → EXPIRED (token expired) |
| **PERMISSIONS_RESOLVED** | Permission set determined | → EVALUATING (check if required ⊆ granted) |
| **EVALUATING** | Checking if required permissions granted | → AUTHORIZED (required ⊆ granted) \| → UNAUTHORIZED (required ⊄ granted) |
| **AUTHORIZED** | Caller has all required permissions | → IDLE (proceed) |
| **UNAUTHORIZED** | Caller lacks at least one required permission | → FAULTED (raise PermissionError) |
| **INVALID_JWT** | JWT syntax or signature invalid | → FAULTED (raise JWTError) |
| **EXPIRED** | JWT `exp` claim in past | → FAULTED (raise ExpiredTokenError) |
| **REVOKED** | Token present in revocation cache | → FAULTED (raise RevokedTokenError) |

**Decision Logic (pseudocode):**

```
function k2_check_permissions(jwt_token, required_permissions, context):
  // 1. Extract and validate JWT
  try:
    claims = jwt.decode(jwt_token, options={'verify_signature': True, 'verify_exp': True})
  except JWTError:
    raise JWTError("Invalid JWT signature or format")
  except ExpiredSignatureError:
    raise ExpiredTokenError(f"Token expired at {claims['exp']}")

  // 2. Check revocation cache
  if redis.exists(f"revoked_token:{claims['jti']}"):
    raise RevokedTokenError(f"Token {claims['jti']} revoked")

  // 3. Resolve permissions from roles
  roles = claims.get('roles', [])
  granted_permissions = set()
  for role in roles:
    role_perms = permission_registry.get_permissions_for_role(role)
    granted_permissions.update(role_perms)

  // 4. Check if required ⊆ granted
  required = set(required_permissions)
  if not (required <= granted_permissions):
    missing = required - granted_permissions
    raise PermissionError(
      required=required,
      granted=granted_permissions,
      missing=missing,
      user_id=claims['sub'],
      trace_id=context.correlation_id
    )

  return claims
```

**Invariants:**

1. **No unauthorized call crosses a boundary:**
   - ∀ crossing: crossing.authorized ⟹ required_permissions ⊆ caller.granted_permissions

2. **Permission resolution is deterministic per role:**
   - ∀ role: permission_registry.get_permissions_for_role(role) returns same set on every call (within cache TTL)

3. **JWT claims are immutable:**
   - ∀ jwt: decode(jwt) produces same claims dict on every call (no side effects)

4. **Revocation is monotonic:**
   - ∀ token: once revoked(token), ¬∃ time t where ¬revoked(token) at time t > revoked_time (revocation is irreversible)

5. **Token expiration is enforced:**
   - ∀ token: exp_time in past ⟹ token.valid = False

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| JWT signature invalid | `JWTError` | Yes (WARN level) | Yes (trace.k2_jwt_invalid) | Context → FAULTED |
| Token expired | `ExpiredTokenError` | Yes (INFO level) | Yes (trace.k2_token_expired) | Context → FAULTED |
| Token revoked | `RevokedTokenError` | Yes (WARN level) | Yes (trace.k2_token_revoked) | Context → FAULTED |
| Permission missing | `PermissionError` | Yes (WARN level, user/roles logged) | Yes (trace.k2_unauthorized) | Context → FAULTED |
| Role not found | `RoleNotFoundError` | Yes (ERROR level) | Yes | Context → FAULTED |
| JWT malformed | `JWTDecodeError` | Yes (ERROR level) | Yes | Context → FAULTED |

**Failure Predicates:**

K2 fails when:

1. **Missing Bearer Token:** HTTP Authorization header missing or malformed → raise JWTError
2. **Invalid Signature:** JWT signature doesn't match JWKS public key → raise JWTError
3. **Token Expired:** `exp` claim ≤ current_time → raise ExpiredTokenError
4. **Token Revoked:** `jti` (JWT ID) present in Redis revocation set → raise RevokedTokenError
5. **Missing Required Claim:** JWT missing required claim (sub, roles, tenant_id) → raise JWTError
6. **Role Not Mapped:** Role in claims has no entry in permission registry → raise RoleNotFoundError (or deny with default empty permission set)
7. **Permission Denied:** required_permissions ⊄ granted_permissions → raise PermissionError
8. **Revocation Cache Unavailable:** Redis unreachable when checking revocation → raise RevocationCacheError (fail-safe: deny access)
9. **Permission Registry Unavailable:** Authentik/permission service unavailable → raise PermissionRegistryError (fail-safe: deny access)

**Acceptance Criteria:**

1. **Valid Token Passes:** A properly signed, non-expired token with required permissions passes K2.
   - Assert: k2_check_permissions(valid_jwt, required_perms) → returns claims with matching user_id

2. **Missing Token Fails:** No bearer token raises JWTError.
   - Assert: k2_check_permissions(None, required_perms) → JWTError

3. **Expired Token Fails:** Token with exp < now raises ExpiredTokenError.
   - Assert: k2_check_permissions(expired_jwt, required_perms) → ExpiredTokenError

4. **Revoked Token Fails:** Token in revocation cache raises RevokedTokenError.
   - Assert: redis.set(f"revoked_token:{jti}") → k2_check_permissions(jwt) → RevokedTokenError

5. **Insufficient Permissions Fail:** Token with subset of required permissions raises PermissionError.
   - Assert: k2_check_permissions(jwt_with_["goal:read"], required=["goal:read", "goal:write"]) → PermissionError with missing=["goal:write"]

6. **Permission Resolution Caching:** Permission lookup per role is cached in Redis (configurable TTL).
   - Assert: Two calls to k2 with same role result in single permission registry lookup (verified via mock)

7. **Revocation Cache Failure Mode:** When revocation cache unavailable, access is denied (fail-safe).
   - Assert: Redis unavailable → k2_check_permissions() → RevocationCacheError (boundary crossing blocked)

8. **Fast Path for Revocation:** If token not in revocation cache, no revocation check blocks the path.
   - Assert: Revocation lookup is O(1) Redis GET; if key not found, no additional lookups

---

### 1.4 K3 — Bounds Checking

**Purpose:** Validates resource consumption within allocated budgets. Prevents any single boundary crossing from exhausting quotas and ensures per-workflow, per-tenant, and per-agent resource isolation.

**Input Domain:**

- **Resource Type:** CPU, memory, wall-clock time, database queries, LLM token usage, HTTP requests, file writes
- **Current Usage:** Cumulative usage counter maintained in Redis (per tenant, per workflow, per agent)
- **Budget Limits:** Configured per tenant, per workflow tier, per agent type; stored in `architecture.yaml` and Postgres

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **STARTING** | K3 gate initialized | → LOOKUP_BUDGET (on entry) |
| **LOOKUP_BUDGET** | Fetching budget from config | → BUDGET_FOUND (config hit) \| → BUDGET_NOT_FOUND (config miss) |
| **BUDGET_FOUND** | Budget limit retrieved | → QUERY_USAGE (fetch current usage) |
| **QUERY_USAGE** | Fetching current usage from Redis | → USAGE_QUERIED (usage found) \| → USAGE_UNAVAILABLE (Redis unavailable) |
| **USAGE_QUERIED** | Current usage known | → COMPARING (compare usage + requested ≤ budget) |
| **COMPARING** | Evaluating usage + request ≤ limit | → ALLOWED (passes budget check) \| → EXCEEDED (would exceed budget) |
| **ALLOWED** | Requested operation within budget | → IDLE (proceed) |
| **EXCEEDED** | Requested operation would exceed budget | → FAULTED (raise BoundsExceeded) |
| **BUDGET_NOT_FOUND** | No budget configured | → FAULTED (raise BudgetNotFoundError) |
| **USAGE_UNAVAILABLE** | Redis unavailable | → FAULTED (raise UsageTrackingError, fail-safe deny) |

**Decision Logic (pseudocode):**

```
function k3_check_bounds(resource_type, requested_amount, context):
  // 1. Resolve budget
  budget_key = f"{context.tenant_id}/{resource_type}"
  budget_limit = config.get_budget(budget_key)
  if budget_limit is null:
    raise BudgetNotFoundError(f"No budget configured for {budget_key}")

  // 2. Resolve current usage
  usage_key = f"usage:{context.tenant_id}:{resource_type}"
  try:
    current_usage = redis.get(usage_key) || 0
  except RedisError:
    raise UsageTrackingError("Cannot reach usage tracker; denying access")

  // 3. Check if request exceeds remaining budget
  if current_usage + requested_amount > budget_limit:
    raise BoundsExceeded(
      resource=resource_type,
      budget=budget_limit,
      current=current_usage,
      requested=requested_amount,
      remaining=budget_limit - current_usage,
      tenant_id=context.tenant_id,
      trace_id=context.correlation_id
    )

  // 4. Reserve (atomically increment usage)
  redis.incrby(usage_key, requested_amount)
  return True
```

**Invariants:**

1. **No operation exceeds allocated budget:**
   - ∀ crossing: crossing.usage + crossing.requested ≤ crossing.budget_limit

2. **Budget limits are non-negative:**
   - ∀ budget: budget.limit ≥ 0

3. **Usage counters are monotonically increasing:**
   - ∀ resource, time t1 < t2: usage(resource, t1) ≤ usage(resource, t2)

4. **Budget enforcement is per-tenant:**
   - ∀ tenants T1, T2 (T1 ≠ T2): usage(T1, resource) + requested(T1) ≤ budget(T1) ∧ usage(T2, resource) + requested(T2) ≤ budget(T2) (independent)

5. **Budget limits are immutable during crossing:**
   - ∀ crossing: budget_limit(crossing) is fixed at crossing entry time (read-only)

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Budget not found | `BudgetNotFoundError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Budget exceeded | `BoundsExceeded` | Yes (WARN level, resource and amounts logged) | Yes (trace.k3_bounds_exceeded) | Context → FAULTED |
| Usage tracker unavailable | `UsageTrackingError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Budget limit negative | `InvalidBudgetError` | Yes (ERROR level) | Yes | Context → FAULTED |

**Failure Predicates:**

K3 fails when:

1. **Budget Not Found:** No budget configured for (tenant, resource_type) pair → raise BudgetNotFoundError
2. **Usage + Request > Budget:** current_usage + requested_amount > budget_limit → raise BoundsExceeded
3. **Negative Budget:** Budget limit < 0 (config error) → raise InvalidBudgetError
4. **Redis Unavailable:** Cannot fetch current usage from Redis → raise UsageTrackingError
5. **Negative Current Usage:** Current usage counter is negative (data corruption) → raise UsageTrackingError
6. **Requested Amount Negative:** Requested amount < 0 (invalid input) → raise ValueError
7. **Requested Amount > Budget:** Requested amount alone exceeds entire budget (even if usage=0) → raise BoundsExceeded
8. **Integer Overflow:** usage + requested overflows integer type → raise OverflowError

**Acceptance Criteria:**

1. **Budget Check Passes:** Operation within budget passes K3.
   - Assert: k3_check_bounds(resource, 10, {budget: 100, usage: 50}) → True (50 + 10 ≤ 100)

2. **Budget Exceeded:** Operation exceeding budget raises BoundsExceeded.
   - Assert: k3_check_bounds(resource, 60, {budget: 100, usage: 50}) → BoundsExceeded (50 + 60 > 100)

3. **Usage Atomicity:** Usage increment is atomic (no race conditions with concurrent requests).
   - Property test: N concurrent requests, each within remaining budget, all succeed; final usage = sum of all requests

4. **Tenant Isolation:** Budgets for different tenants are independent.
   - Assert: tenant_a uses X of budget, tenant_b uses Y of budget; usage(a) + usage(b) ≤ budget(a) + budget(b)

5. **Budget Immutability:** Budget limit doesn't change during a crossing.
   - Assert: k3_check_bounds() reads budget once; subsequent config change doesn't affect ongoing crossing

6. **Fail-Safe Deny:** When Redis unavailable, access denied (not allowed through).
   - Assert: Redis unavailable → k3_check_bounds() → UsageTrackingError, boundary crossing blocked

7. **Usage Reset:** Budget counters reset on configurable period (e.g., daily) or per-workflow lifetime.
   - Assert: redis.set_with_expiry(usage_key, 0, ttl=86400) ensures daily reset

---

### 1.5 K4 — Trace Injection

**Purpose:** Injects correlation ID and tenant ID into every boundary crossing, enabling distributed tracing and tenant isolation auditing.

**Input Domain:**

- **Correlation ID:** UUID v4, either provided by caller or generated; uniquely identifies a logical request flow across boundaries
- **Tenant ID:** Extracted from JWT claims; identifies the tenant/organization; immutable for a crossing

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **INIT** | K4 starting | → EXTRACT_TENANT (on context entry) |
| **EXTRACT_TENANT** | Extracting tenant_id from JWT claims | → TENANT_FOUND (claims have tenant_id) \| → TENANT_MISSING (claims lack tenant_id) |
| **TENANT_FOUND** | Tenant ID extracted | → RESOLVE_CORRELATION (get or generate correlation_id) |
| **RESOLVE_CORRELATION** | Resolving correlation ID | → CORRELATION_PROVIDED (caller provided id) \| → CORRELATION_GENERATED (generated new id) |
| **CORRELATION_PROVIDED** | Using caller-provided correlation ID | → INJECTING (inject into context) |
| **CORRELATION_GENERATED** | Generated new correlation ID | → INJECTING |
| **INJECTING** | Attaching IDs to context | → INJECTED (IDs attached to context) |
| **INJECTED** | Correlation and tenant IDs set in context | → IDLE (proceed) |
| **TENANT_MISSING** | JWT claims missing tenant_id | → FAULTED (raise TenantContextError) |

**Decision Logic (pseudocode):**

```
function k4_inject_trace(claims, provided_correlation_id, context):
  // 1. Extract tenant ID from claims
  tenant_id = claims.get('tenant_id')
  if tenant_id is null:
    raise TenantContextError("JWT missing tenant_id claim")

  // 2. Resolve or generate correlation ID
  if provided_correlation_id is not null:
    correlation_id = provided_correlation_id
  else:
    correlation_id = uuid.uuid4()

  // 3. Validate correlation ID format
  if not is_valid_uuid(correlation_id):
    raise ValueError(f"Invalid correlation ID format: {correlation_id}")

  // 4. Inject into context
  context.correlation_id = correlation_id
  context.tenant_id = tenant_id
  context.trace_started_at = time.time()

  return (correlation_id, tenant_id)
```

**Invariants:**

1. **Every boundary crossing carries correlation and tenant IDs:**
   - ∀ crossing: crossing.context.correlation_id ≠ null ∧ crossing.context.tenant_id ≠ null

2. **Correlation ID is globally unique per logical flow:**
   - ∀ correlation_id: count(crossings with this id) ≥ 1; id generated or provided exactly once at flow start

3. **Tenant ID is immutable within a crossing:**
   - ∀ crossing: tenant_id is read-only after K4 injection; no operation can change it

4. **Correlation ID propagates through child crossings:**
   - ∀ crossing C1 → C2 (C2 child of C1): correlation_id(C1) = correlation_id(C2)

5. **Trace timestamps are monotonically increasing:**
   - ∀ crossings C1, C2: if C1 starts before C2, then timestamp(C1) < timestamp(C2)

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Missing tenant_id | `TenantContextError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Invalid correlation ID | `ValueError` | Yes (WARN level) | Yes | Context → FAULTED |

**Failure Predicates:**

K4 fails when:

1. **Missing Tenant Context:** JWT claims lack tenant_id → raise TenantContextError
2. **Invalid Correlation ID Format:** Provided correlation_id is not a valid UUID → raise ValueError
3. **Null Correlation ID:** Both provided and generated correlation ID are null → raise ValueError (generation failed)

**Acceptance Criteria:**

1. **Tenant Extraction:** Valid JWT with tenant_id is extracted correctly.
   - Assert: claims['tenant_id'] == "org_123" → k4_inject_trace() → context.tenant_id == "org_123"

2. **Correlation ID Propagation:** Correlation ID from first crossing propagates to child crossings.
   - Assert: parent_context.correlation_id == child_context.correlation_id

3. **New Correlation ID Generation:** If caller doesn't provide correlation_id, K4 generates one.
   - Assert: k4_inject_trace(claims, provided_correlation_id=None) → context.correlation_id is UUID v4 (non-null, valid format)

4. **Caller-Provided Correlation ID:** If caller provides correlation_id, it's used as-is.
   - Assert: k4_inject_trace(claims, provided_correlation_id=uuid_x) → context.correlation_id == uuid_x

5. **Tenant Isolation:** Two crossings with different tenant_ids have independent traces.
   - Assert: crossing_a.context.tenant_id != crossing_b.context.tenant_id ⟹ traces are isolated

6. **Missing Tenant Error:** JWT without tenant_id raises TenantContextError.
   - Assert: k4_inject_trace(claims={no tenant_id}) → TenantContextError

7. **Timestamp Ordering:** Trace timestamps are monotonically increasing.
   - Property test: For any sequence of crossings, timestamp(C_i) ≤ timestamp(C_{i+1})

---

### 1.6 K5 — Idempotency Key Generation

**Purpose:** Generates deterministic RFC 8785 (JSON Canonicalization Scheme) keys from operation payloads, enabling idempotency checks and deduplication across retries.

**Algorithm:**

1. **Canonicalize Payload:** Convert incoming JSON to RFC 8785 canonical form (sorted keys, no whitespace, UTF-8 encoding)
2. **Hash:** SHA-256 hash of canonical JSON
3. **Return Key:** Hex-encoded hash as idempotency key

**RFC 8785 Rules Applied:**

- Object members ordered lexicographically by key (UTF-8 codepoint order)
- Whitespace (spaces, newlines, tabs) removed
- All strings use double quotes; Unicode escapes normalized
- Numbers in decimal form (no scientific notation)
- Arrays preserve order
- Null, true, false rendered as-is

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **INPUT** | Received JSON input | → CANONICALIZING (apply RFC 8785) |
| **CANONICALIZING** | Converting to canonical form | → CANONICAL (success) \| → NOT_CANONICAL (non-canonical input) |
| **CANONICAL** | Input in canonical form | → HASHING |
| **HASHING** | Computing SHA-256 | → HASHED |
| **HASHED** | Hash computed | → IDLE (return key) |
| **NOT_CANONICAL** | Input already non-canonical | → FAULTED (raise ValueError) |

**Decision Logic (pseudocode):**

```
function k5_generate_idempotency_key(payload):
  // 1. Validate payload is JSON
  if not is_json(payload):
    raise ValueError("Payload must be valid JSON")

  // 2. Canonicalize using RFC 8785
  canonical_json = rfc8785.canonicalize(payload)

  // 3. Hash
  hash_digest = sha256(canonical_json.encode('utf-8'))

  // 4. Return hex key
  idempotency_key = hash_digest.hexdigest()
  return idempotency_key
```

**Invariants:**

1. **Same logical operation always produces same key:**
   - ∀ payload P: k5(P) = k5(P) (deterministic)

2. **Different operations produce different keys (collision-resistant):**
   - ∀ payloads P1 ≠ P2: k5(P1) ≠ k5(P2) (assuming SHA-256 collision resistance; practical probability < 2^-256)

3. **Idempotency keys are immutable:**
   - ∀ payload: k5(payload) is fixed; no operation can change it

4. **Canonical form is unique per logical content:**
   - ∀ payload P and any reordering P': if P_logically_equal(P') then canonical(P) = canonical(P')

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Non-JSON input | `ValueError` | Yes (WARN level) | Yes | Context → FAULTED |
| Canonicalization failure | `CanonicalizeError` | Yes (ERROR level) | Yes | Context → FAULTED |

**Failure Predicates:**

K5 fails when:

1. **Non-JSON Input:** Payload is not valid JSON → raise ValueError
2. **Circular Reference:** JSON payload contains circular structure (impossible in valid JSON, but worth checking) → raise CanonicalizeError
3. **Non-Serializable Types:** Payload contains non-JSON types (datetime, custom objects) → raise TypeError
4. **Null Payload:** payload is None → raise ValueError

**Acceptance Criteria:**

1. **Deterministic Keys:** Same payload always generates same key.
   - Assert: k5(payload_x) == k5(payload_x) (on second call)

2. **Field-Order Independence:** Reordered JSON fields generate same key.
   - Assert: k5({'a': 1, 'b': 2}) == k5({'b': 2, 'a': 1})

3. **Whitespace Independence:** JSON with different whitespace generates same key.
   - Assert: k5(compact_json) == k5(pretty_json)

4. **Unicode Normalization:** Unicode characters are normalized to canonical form.
   - Assert: k5(json_with_unicode_x) == k5(json_with_unicode_x_canonical)

5. **Different Payloads Different Keys:** Two logically different payloads generate different keys.
   - Property test: For any two payloads P1 ≠ P2, k5(P1) ≠ k5(P2)

6. **Non-JSON Rejection:** Non-JSON input raises ValueError.
   - Assert: k5("not json") → ValueError

7. **Key Format:** Generated key is lowercase hexadecimal, 64 characters (SHA-256 output).
   - Assert: idempotency_key matches regex `^[a-f0-9]{64}$`

---

### 1.7 K6 — Durability / WAL (Write-Ahead Log)

**Purpose:** Append-only audit log recording every boundary crossing with full context (payload, claims, decision outcomes), enabling compliance auditing, incident reconstruction, and redaction of sensitive data before persistence.

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **ACCUMULATING** | Collecting trace data during crossing | → PREPARING (after operation complete) |
| **PREPARING** | Formatting trace for WAL entry | → REDACTING (redact PII/secrets) |
| **REDACTING** | Applying redaction rules to PII fields | → REDACTED (sensitive data masked) |
| **REDACTED** | Trace sanitized | → WRITING (insert into Postgres) |
| **WRITING** | PostgreSQL insert in progress | → WRITTEN (WAL entry persisted) \| → WRITE_FAILED (insert failed) |
| **WRITTEN** | WAL entry durable | → IDLE (crossing exits) |
| **WRITE_FAILED** | Postgres write failed | → FAULTED (raise WALWriteError) |

**WAL Entry Schema:**

```
table audit_wal(
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,  -- tenant isolation
  correlation_id UUID NOT NULL,  -- trace link
  timestamp TIMESTAMPTZ NOT NULL,
  boundary_crossing TEXT NOT NULL,  -- e.g., "core::intent_classifier"
  caller_user_id UUID NOT NULL,
  caller_roles TEXT[] NOT NULL,
  k1_schema_id TEXT,
  k1_valid BOOLEAN NOT NULL,
  k2_required_permissions TEXT[],
  k2_granted_permissions TEXT[],
  k2_authorized BOOLEAN NOT NULL,
  k3_resource_type TEXT,
  k3_budget_limit BIGINT,
  k3_usage_before BIGINT,
  k3_requested BIGINT,
  k3_within_budget BOOLEAN NOT NULL,
  k5_idempotency_key TEXT,
  k7_confidence_score FLOAT,
  k7_human_approved BOOLEAN,
  k8_eval_passed BOOLEAN,
  operation_result TEXT,  -- redacted payload or error
  exit_code INT NOT NULL,  -- 0 = success, >0 = error code

  -- Redaction tracking
  redaction_rules_applied TEXT[],
  contains_pii_before_redaction BOOLEAN,

  -- Indexing
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  partition_date DATE NOT NULL,  -- for time-based partitioning

  CONSTRAINT audit_wal_tenant_fk FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
CREATE INDEX audit_wal_tenant_ts ON audit_wal(tenant_id, created_at);
CREATE INDEX audit_wal_correlation ON audit_wal(correlation_id);
```

**Redaction Rules:**

- **Email addresses:** Redact to `[email hidden]`
- **API keys/tokens:** Redact to `[secret redacted]`
- **Credit card numbers:** Redact to `****-****-****-XXXX` (last 4 only)
- **Personally identifiable information (PII):** Name, phone, SSN redacted to `[pii redacted]`
- **Full JSON payloads:** Hash and store reference, not full content (privacy-preserving)

**Decision Logic (pseudocode):**

```
function k6_write_wal(context, operation_result, exit_code):
  // 1. Collect trace data
  entry = {
    id: uuid.uuid4(),
    tenant_id: context.tenant_id,
    correlation_id: context.correlation_id,
    timestamp: datetime.utcnow(),
    boundary_crossing: context.boundary_name,
    caller_user_id: context.claims['sub'],
    caller_roles: context.claims.get('roles', []),

    k1_schema_id: context.k1_schema,
    k1_valid: context.k1_passed,
    k2_required_permissions: context.k2_required,
    k2_granted_permissions: context.k2_granted,
    k2_authorized: context.k2_passed,
    k3_resource_type: context.k3_resource,
    k3_budget_limit: context.k3_budget,
    k3_usage_before: context.k3_usage_before,
    k3_requested: context.k3_requested,
    k3_within_budget: context.k3_passed,
    k5_idempotency_key: context.idempotency_key,
    k7_confidence_score: context.k7_confidence,
    k7_human_approved: context.k7_approved,
    k8_eval_passed: context.k8_passed,

    operation_result: operation_result,
    exit_code: exit_code,
  }

  // 2. Apply redaction
  redaction_applied = redact_sensitive_fields(entry)
  entry['redaction_rules_applied'] = redaction_applied
  entry['contains_pii_before_redaction'] = detect_pii(entry)

  // 3. Insert into Postgres
  try:
    pg.insert('audit_wal', entry)
    return True
  except PostgresError as e:
    raise WALWriteError(f"Failed to write WAL: {e}")
```

**Invariants:**

1. **Every boundary crossing produces a WAL entry:**
   - ∀ crossing ∈ CompletedCrossings: ∃ wal_entry where wal_entry.correlation_id = crossing.correlation_id

2. **WAL is append-only:**
   - ∀ wal_entries: entry.id is immutable; entry.created_at is immutable; no UPDATE or DELETE operations on entries

3. **Sensitive data redacted before write:**
   - ∀ wal_entry: ¬contains_pii(wal_entry.operation_result) ∧ ¬contains_secret(wal_entry.operation_result)

4. **WAL entries are ordered by timestamp:**
   - ∀ entries e1, e2: e1.created_at < e2.created_at ⟹ e1.id precedes e2.id in insertion order

5. **Tenant isolation in WAL:**
   - ∀ wal_entries: queries filtered by tenant_id; no cross-tenant visibility

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Postgres write failure | `WALWriteError` | Yes (ERROR level) | Yes (trace.k6_wal_write_failed) | Context → FAULTED |
| Redaction failure | `RedactionError` | Yes (ERROR level) | Yes | Context → FAULTED |
| Invalid WAL entry format | `WALFormatError` | Yes (ERROR level) | Yes | Context → FAULTED |

**Failure Predicates:**

K6 fails when:

1. **Postgres Unavailable:** Database connection failed → raise WALWriteError
2. **WAL Table Missing:** Table `audit_wal` doesn't exist → raise WALFormatError
3. **Tenant ID Mismatch:** Tenant ID in entry doesn't match context → raise ValueError
4. **Redaction Failure:** Redaction function threw exception → raise RedactionError
5. **Entry Serialization Failure:** Entry cannot be serialized to database format → raise WALFormatError

**Acceptance Criteria:**

1. **WAL Entry Created:** Every boundary crossing creates one WAL entry.
   - Assert: After crossing completes, count(WAL entries with correlation_id) == 1

2. **Append-Only:** Once written, WAL entry cannot be modified.
   - Assert: Postgres constraint: no UPDATE on audit_wal; no DELETE on audit_wal

3. **Redaction Applied:** Sensitive fields are redacted before write.
   - Assert: wal_entry.operation_result does not contain plaintext email, API key, or credit card

4. **Tenant Isolation:** WAL entries only visible to same tenant.
   - Assert: postgres query "SELECT * FROM audit_wal WHERE tenant_id = 'org_a'" returns no rows with tenant_id = 'org_b'

5. **Timestamp Ordering:** WAL entries ordered by timestamp.
   - Assert: For entries e1, e2 with e1.created_at < e2.created_at, e1 appears before e2 in query results

6. **Correlation ID Link:** WAL entry's correlation_id matches context.
   - Assert: wal_entry.correlation_id == context.correlation_id

7. **Failure Handling:** If Postgres unavailable, context → FAULTED.
   - Assert: k6_write_wal with Postgres down → WALWriteError, context transitions to FAULTED

---

### 1.8 K7 — HITL (Human-in-the-Loop) Gates

**Purpose:** Blocks execution on low-confidence operations, escalates to human reviewer for approval, and enforces that high-risk operations never proceed without explicit human authorization.

**Input Domain:**

- **Confidence Score:** Float [0.0, 1.0], computed by a confidence evaluator (LLM-based or rule-based)
- **Confidence Threshold:** Configurable per boundary, per operation type (e.g., "workflow:execute" = 0.85)
- **Human Approval Channel:** WebSocket event, email, or dashboard reviewer interface

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **EVALUATING** | Computing confidence score | → CONFIDENT (score ≥ threshold) \| → UNCERTAIN (score < threshold) |
| **CONFIDENT** | Confidence ≥ threshold | → PASS (proceed) |
| **UNCERTAIN** | Confidence < threshold | → BLOCKED (operation halted, awaiting human) |
| **BLOCKED** | Awaiting human review | → HUMAN_APPROVED (human clicked "approve") \| → HUMAN_REJECTED (human clicked "reject") \| → APPROVAL_TIMEOUT (timeout after 24h) |
| **HUMAN_APPROVED** | Human approved operation | → PASS |
| **HUMAN_REJECTED** | Human rejected operation | → FAULTED (raise OperationRejected) |
| **APPROVAL_TIMEOUT** | No human response within TTL | → FAULTED (raise ApprovalTimeout) |
| **PASS** | Operation allowed | → IDLE (proceed to next gate) |
| **FAULTED** | Confidence check failed | → context.state=FAULTED |

**Decision Logic (pseudocode):**

```
function k7_evaluate_confidence(operation, context):
  // 1. Compute confidence score
  confidence_threshold = config.get_confidence_threshold(operation.type)
  confidence_score = evaluate_confidence(operation)  // LLM-based or rule-based

  if confidence_score >= confidence_threshold:
    // High confidence: proceed
    return (True, confidence_score)

  // Low confidence: require human approval
  approval_request = {
    id: uuid.uuid4(),
    correlation_id: context.correlation_id,
    operation: operation,
    confidence_score: confidence_score,
    threshold: confidence_threshold,
    created_at: datetime.utcnow(),
    expires_at: datetime.utcnow() + timedelta(hours=24),
  }

  // 2. Emit approval request to human review channel
  approval_channel.emit(approval_request)

  // 3. Wait for human decision (with timeout)
  try:
    human_decision = approval_channel.wait_for_decision(
      approval_request.id,
      timeout=86400  // 24 hours
    )
  except TimeoutError:
    raise ApprovalTimeout(f"No human decision after 24 hours for {operation.id}")

  if human_decision.action == "approve":
    return (True, confidence_score)
  elif human_decision.action == "reject":
    raise OperationRejected(
      reason=human_decision.reason,
      reviewer=human_decision.reviewer_id,
      trace_id=context.correlation_id
    )
```

**Invariants:**

1. **Low-confidence operations never proceed without human approval:**
   - ∀ operation: confidence_score < threshold ⟹ operation.approval ∈ {HUMAN_APPROVED, BLOCKED}

2. **Human approvals are durable:**
   - ∀ approval: approval.reviewed_at is recorded and immutable; no retroactive revocation

3. **Confidence scores are deterministic per operation:**
   - ∀ operation O: evaluate_confidence(O) always returns same score (within session; may change across sessions as model updates)

4. **Approval requests timeout:**
   - ∀ approval_request: if no decision after 24 hours, operation denied

5. **Human reviewer is always recorded:**
   - ∀ approval ∈ HUMAN_APPROVED ∨ HUMAN_REJECTED: approval.reviewer_id ≠ null

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Confidence evaluator failure | `ConfidenceError` | Yes (ERROR level) | Yes | Context → FAULTED (fail-safe: deny) |
| Approval timeout | `ApprovalTimeout` | Yes (WARN level) | Yes (trace.k7_approval_timeout) | Context → FAULTED |
| Human rejection | `OperationRejected` | Yes (INFO level, reason logged) | Yes (trace.k7_human_rejected) | Context → FAULTED |
| Approval channel unavailable | `ApprovalChannelError` | Yes (ERROR level) | Yes | Context → FAULTED |

**Failure Predicates:**

K7 fails when:

1. **Confidence Evaluator Failure:** Confidence computation threw exception → raise ConfidenceError (fail-safe: deny)
2. **Approval Timeout:** No human decision after 24 hours → raise ApprovalTimeout
3. **Human Rejection:** Reviewer clicked "reject" → raise OperationRejected
4. **Approval Channel Unavailable:** WebSocket or review service unreachable → raise ApprovalChannelError (fail-safe: deny)
5. **Invalid Confidence Score:** Returned score not in [0.0, 1.0] → raise ValueError
6. **Missing Operation Context:** Cannot determine operation type or threshold → raise ValueError

**Acceptance Criteria:**

1. **High-Confidence Pass:** Operation with confidence ≥ threshold passes K7.
   - Assert: k7_evaluate_confidence(op_with_confidence=0.95, threshold=0.85) → (True, 0.95)

2. **Low-Confidence Blocks:** Operation with confidence < threshold blocks and requires approval.
   - Assert: k7_evaluate_confidence(op_with_confidence=0.70, threshold=0.85) → blocks, emits approval request

3. **Human Approval Passes:** After human approves, operation proceeds.
   - Assert: blocked_operation → human clicks "approve" → k7_evaluate_confidence() → (True, ...)

4. **Human Rejection Fails:** Human rejection raises OperationRejected.
   - Assert: blocked_operation → human clicks "reject" → k7_evaluate_confidence() → OperationRejected

5. **Approval Timeout:** After 24 hours with no human decision, operation fails.
   - Assert: time.advance(25 hours) with no decision → k7_evaluate_confidence() → ApprovalTimeout

6. **Reviewer Recorded:** Human approvals/rejections record the reviewer's user ID.
   - Assert: approval.reviewer_id == human_user_id

7. **Fail-Safe Deny:** Confidence evaluator failure denies access.
   - Assert: confidence evaluator throws exception → k7_evaluate_confidence() → ConfidenceError, operation blocked

8. **Threshold Configuration:** Different operation types have different thresholds.
   - Assert: config.get_confidence_threshold("goal:modify") ≠ config.get_confidence_threshold("goal:read")

---

### 1.9 K8 — Eval Gates

**Purpose:** Runs a behavioral predicate on the operation's output before allowing it to proceed, halting execution if the output violates expected properties.

**Input Domain:**

- **Output:** Result of the boundary crossing operation (e.g., generated goal tree, API response, code execution result)
- **Eval Predicate:** Function that takes output and returns Boolean; may be LLM-based or rule-based
- **Predicate ID:** References a specific eval spec (e.g., "goals/celestial_constraint_check_v1.2")

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **READY** | Output available for evaluation | → LOADING_PREDICATE (fetch eval spec) |
| **LOADING_PREDICATE** | Fetching predicate from registry | → PREDICATE_LOADED (spec found) \| → PREDICATE_NOT_FOUND (spec missing) |
| **PREDICATE_LOADED** | Predicate loaded and parsed | → EVALUATING |
| **EVALUATING** | Running predicate against output | → PASS (predicate returned True) \| → FAIL (predicate returned False) \| → EVAL_ERROR (predicate raised exception) |
| **PASS** | Output satisfies predicate | → IDLE (proceed) |
| **FAIL** | Output violates predicate | → HALTED (raise EvalGateFailure) |
| **EVAL_ERROR** | Predicate evaluation raised exception | → HALTED (raise EvalError) |
| **PREDICATE_NOT_FOUND** | Predicate spec not found | → HALTED (raise PredicateNotFoundError) |
| **HALTED** | Eval gate triggered halt | → context.state=FAULTED |

**Decision Logic (pseudocode):**

```
function k8_evaluate_output(output, predicate_id, context):
  // 1. Load predicate
  predicate_spec = predicate_registry.get(predicate_id)
  if predicate_spec is null:
    raise PredicateNotFoundError(f"Predicate {predicate_id} not found")

  // 2. Evaluate predicate
  try:
    result = predicate_spec.evaluate(output)
  except Exception as e:
    raise EvalError(f"Predicate evaluation failed: {e}")

  // 3. Check result
  if not result:
    raise EvalGateFailure(
      predicate_id=predicate_id,
      output_hash=hash(output),  // redacted
      reason="Output violated eval gate",
      trace_id=context.correlation_id
    )

  return True
```

**Example Predicates:**

1. **Celestial L0–L4 Constraint Check:** Output goals must not violate Celestial constraints.
   ```
   predicate: celestial_constraint_check
   input: goal_tree
   checks:
     - no goal violates L0 (authorization boundary)
     - no goal violates L1 (system integrity)
     - no goal violates L2 (privacy boundary)
     - no goal violates L3 (failure recovery)
     - no goal violates L4 (agent autonomy limit)
   output: Boolean (True if all checks pass)
   ```

2. **Goal Coherence Check:** Output goal decomposition is logically coherent.
   ```
   predicate: goal_coherence_check
   input: goal_tree
   checks:
     - parent goal ⇒ child goals (child subgoals should logically decompose parent)
     - no cycles (goal tree is DAG)
     - all leaves are primitive operations (can be executed)
   output: Boolean
   ```

3. **Schema Conformance:** Output conforms to expected output schema.
   ```
   predicate: output_schema_conformance
   input: operation_result
   checks:
     - result.type == expected_type
     - all required fields present
     - all field types match schema
   output: Boolean
   ```

**Invariants:**

1. **No output proceeds without eval gate pass:**
   - ∀ output: output.eval_passed = True ⟹ predicate(output) = True

2. **Eval gate failure halts execution:**
   - ∀ crossing: eval_gate_failed(crossing) ⟹ output.blocked = True

3. **Predicates are deterministic:**
   - ∀ output O: predicate(O) always returns same Boolean value (within same predicate version)

4. **Predicate versions are immutable:**
   - ∀ predicate P: once created, P.version is immutable; changes create new version

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace Emitted | Action |
|---|---|---|---|---|
| Predicate not found | `PredicateNotFoundError` | Yes (ERROR level) | Yes | Context → HALTED → FAULTED |
| Predicate evaluation error | `EvalError` | Yes (ERROR level) | Yes (trace.k8_eval_error) | Context → HALTED → FAULTED |
| Output violates predicate | `EvalGateFailure` | Yes (INFO level) | Yes (trace.k8_eval_gate_failure) | Context → HALTED → FAULTED |
| Timeout during evaluation | `TimeoutError` | Yes (WARN level) | Yes | Context → HALTED → FAULTED |

**Failure Predicates:**

K8 fails when:

1. **Predicate Not Found:** Predicate registry doesn't contain predicate_id → raise PredicateNotFoundError
2. **Predicate Parse Error:** Predicate spec is malformed → raise PredicateParseError
3. **Predicate Evaluation Error:** Predicate raised unhandled exception → raise EvalError
4. **Output Violates Predicate:** predicate(output) returns False → raise EvalGateFailure
5. **Evaluation Timeout:** Predicate evaluation exceeded timeout (5 seconds) → raise TimeoutError
6. **Output Serialization Failure:** Output cannot be passed to predicate → raise TypeError

**Acceptance Criteria:**

1. **Pass on Valid Output:** Output satisfying predicate passes K8.
   - Assert: k8_evaluate_output(valid_output, predicate_id) → True (no exception)

2. **Fail on Invalid Output:** Output violating predicate raises EvalGateFailure.
   - Assert: k8_evaluate_output(invalid_output, predicate_id) → EvalGateFailure

3. **Predicate Loading:** Predicate spec is loaded from registry.
   - Assert: predicate_registry.get(predicate_id) called exactly once per k8_evaluate_output

4. **Timeout Enforcement:** Predicate evaluation times out after 5 seconds.
   - Assert: slow_predicate (sleeps 10s) → k8_evaluate_output() → TimeoutError after 5s

5. **Missing Predicate Error:** Predicate not in registry raises PredicateNotFoundError.
   - Assert: k8_evaluate_output(output, nonexistent_predicate_id) → PredicateNotFoundError

6. **Deterministic Evaluation:** Same output always produces same predicate result.
   - Assert: k8_evaluate_output(output_x, pred) → result_x, k8_evaluate_output(output_x, pred) → result_x (identical)

7. **Failure Blocks Output:** When K8 fails, output is not returned to caller.
   - Assert: If k8_evaluate_output() raises EvalGateFailure, operation result is blocked

---

## 2. Sandbox

### 2.1 Code Executor

**Purpose:** Execute untrusted code in an isolated, containerized environment via gRPC, with resource limits (CPU, memory, wall-clock time, disk I/O) and namespace-based isolation to prevent escape attempts.

**Protocol:** gRPC service with `ExecutionRequest` and `ExecutionResult` messages

```protobuf
message ExecutionRequest {
  string request_id = 1;  // Unique execution ID (UUID)
  string code = 2;  // Source code (Python, JavaScript, etc.)
  string language = 3;  // Language identifier ("python3.11", "node18", etc.)
  map<string, string> environment = 4;  // Environment variables (no secrets)
  map<string, bytes> files = 5;  // Input files (sandboxed tmpfs only)
  google.protobuf.Duration timeout = 6;  // Wall-clock timeout (max 30 seconds)
  int64 memory_limit_mb = 7;  // Memory limit in MB (default 256)
  int64 cpu_period_ms = 8;  // CPU throttle period (cgroup v2)
  int64 cpu_quota_ms = 9;  // CPU quota per period
}

message ExecutionResult {
  string request_id = 1;
  string stdout = 2;  // Standard output (max 1 MB)
  string stderr = 3;  // Standard error (max 1 MB)
  map<string, bytes> output_files = 4;  // Generated files
  int32 exit_code = 5;  // Process exit code (0 = success)
  google.protobuf.Duration wall_time = 6;  // Actual wall-clock time
  google.protobuf.Duration user_time = 7;  // User CPU time
  google.protobuf.Duration system_time = 8;  // System CPU time
  int64 memory_peak_mb = 9;  // Peak memory usage
  int64 page_faults = 10;  // Major page faults (OOM indicator)
  string error_message = 11;  // Error description if exit_code != 0
  google.protobuf.Timestamp start_time = 12;
  google.protobuf.Timestamp end_time = 13;
}
```

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **IDLE** | Executor ready for request | → RECEIVING |
| **RECEIVING** | Reading ExecutionRequest from gRPC | → REQUEST_PARSED (parsed successfully) \| → PROTOCOL_ERROR (malformed request) |
| **REQUEST_PARSED** | Request received and validated | → SPAWNING |
| **SPAWNING** | Creating container and launching process | → EXECUTING (process running) \| → SPAWN_ERROR (container creation failed) |
| **EXECUTING** | Code running inside sandbox | → COMPLETED (process exited) \| → TIMEOUT (wall-clock limit exceeded) \| → OOM (memory limit hit) \| → SYSCALL_BLOCKED (seccomp violation) |
| **COMPLETED** | Process exited normally | → COLLECTING_METRICS (gathering resource stats) |
| **COLLECTING_METRICS** | Reading CPU/memory/IO stats | → RETURNING |
| **RETURNING** | Sending ExecutionResult over gRPC | → IDLE |
| **TIMEOUT** | Execution exceeded wall-clock limit | → CLEANUP → IDLE |
| **OOM** | Memory limit exceeded | → CLEANUP → IDLE |
| **SYSCALL_BLOCKED** | Disallowed syscall attempted | → CLEANUP → IDLE |
| **SPAWN_ERROR** | Container creation failed | → FAULTED |
| **PROTOCOL_ERROR** | Malformed gRPC message | → FAULTED |
| **FAULTED** | Executor error (not code error) | → IDLE |

**Resource Limits:**

| Resource | Default | Maximum | Unit | Enforcement |
|---|---|---|---|---|
| Wall-clock time | 10s | 30s | seconds | SIGKILL after timeout |
| Memory | 256 | 512 | MB | cgroup v2 limit; OOM killer |
| CPU cores | 1.0 (soft) | 2.0 (hard) | cores | cpu.max cgroup limit |
| Disk I/O | 100 | 500 | MB/s | io.max throttle (optional) |
| Output (stdout+stderr) | 1 | 1 | MB | truncated beyond limit |
| Open file descriptors | 256 | 256 | count | resource.RLIMIT_NOFILE |
| Processes (PIDs) | 1 | 1 | count | single process in namespace |

**Invariants:**

1. **Code executes only inside namespace-isolated container:**
   - ∀ execution: process.pid_namespace ≠ host.pid_namespace ∧ process.net_namespace ≠ host.net_namespace

2. **No state persists between executions:**
   - ∀ executions E1, E2: E1.tmpfs ≠ E2.tmpfs (each execution gets fresh tmpfs)

3. **Execution cannot exceed resource limits:**
   - ∀ execution: wall_time ≤ timeout ∧ memory_peak ≤ memory_limit ∧ cpu_time ≤ cpu_quota

4. **Network isolation enforced:**
   - ∀ execution: process.net_namespace.routes = empty (no network egress possible)

5. **Filesystem isolation enforced:**
   - ∀ execution: accessible_paths ⊆ {rootfs_readonly, tmpfs_scratch}

**Error Behavior:**

| Error Condition | Exit Code | stderr | Result | Trace |
|---|---|---|---|---|
| Wall-clock timeout | 137 | `Timeout: wall-clock limit exceeded` | TIMEOUT state | trace.sandbox_timeout |
| Memory limit exceeded | 137 | `OOM: memory limit exceeded` | OOM state | trace.sandbox_oom |
| Disallowed syscall | 159 | `Seccomp violation: syscall X blocked` | SYSCALL_BLOCKED state | trace.sandbox_seccomp |
| Container creation failed | 1 | `Spawn failed: {error}` | SPAWN_ERROR state | trace.sandbox_spawn_error |
| gRPC protocol error | N/A | N/A | PROTOCOL_ERROR state | trace.sandbox_protocol_error |
| Code exits with error | (exit_code from process) | (from stderr) | COMPLETED state | trace.sandbox_code_error |

**Failure Predicates:**

Code Executor fails (returns error, not code-execution error) when:

1. **Malformed Request:** ExecutionRequest missing required fields → raise ProtocolError
2. **Unsupported Language:** Language not in supported list → raise UnsupportedLanguageError
3. **Code Size Too Large:** Code > 10 MB → raise CodeSizeError
4. **Invalid Resource Limits:** memory_limit > 512 MB or timeout > 30s → raise InvalidLimitError
5. **Container Creation Failure:** Docker/cri-o/containerd unable to spawn container → raise SpawnError
6. **Namespace Setup Failure:** PID/NET/MNT namespace isolation failed → raise NamespaceError
7. **Seccomp Profile Load Failure:** Unable to load seccomp profile → raise SeccompError
8. **Cgroup Limit Setup Failure:** cgroup v2 limit failed to apply → raise CgroupError

**Acceptance Criteria:**

1. **Successful Execution:** Valid code executes and returns output.
   - Assert: k8_execute(code="print('hello')", language="python3.11") → exit_code=0, stdout="hello\n"

2. **Timeout Enforcement:** Code exceeding wall-clock limit is killed.
   - Assert: k8_execute(code="while True: pass", timeout=5) → exit_code=137 after ~5s

3. **Memory Limit Enforcement:** Code exceeding memory limit is OOM-killed.
   - Assert: k8_execute(code="x=[1]*999999999", memory_limit=256) → exit_code=137 (OOM)

4. **Network Isolation:** Code cannot establish outbound connections.
   - Assert: k8_execute(code="import socket; socket.create_connection(('8.8.8.8', 53))") → socket.error (connection refused)

5. **Filesystem Isolation:** Code cannot read/write outside tmpfs.
   - Assert: k8_execute(code="open('/etc/passwd')") → FileNotFoundError or PermissionError

6. **Seccomp Enforcement:** Disallowed syscall is blocked.
   - Assert: k8_execute(code="import os; os.execve(...)) → seccomp violation, exit code 159

7. **No State Leakage:** File created in E1 not visible in E2.
   - Assert: E1 creates /tmp/file; E2 reads /tmp → file not found

8. **Resource Stats Collected:** Peak memory and CPU time accurately measured.
   - Assert: memory_peak_mb in [expected_min, expected_max]; cpu_time ≈ actual computation time

---

### 2.2 Security Boundary

**Purpose:** Enforce complete isolation between sandbox and host via namespace isolation, seccomp syscall filtering, and cgroup resource limits.

**Isolation Layers:**

1. **PID Namespace Isolation**
   - Container sees only its own process (init, pid=1) and spawned children
   - Host process tree invisible
   - Process signals scoped to namespace (kill from host doesn't reach container)

2. **NET Namespace Isolation**
   - Container has empty network namespace (no loopback, no eth0, no routes)
   - All network syscalls (socket, bind, connect) return ENODEV or EACCES
   - No egress possible; no DNS resolution possible

3. **MNT (Mount) Namespace Isolation**
   - Container sees read-only rootfs (squashfs or overlay)
   - Tmpfs scratch mounted at /tmp (read-write, tmpfs-backed, max 100 MB)
   - No /dev (or /dev/null, /dev/urandom only via whiteout)
   - No /proc, /sys (or minimal /proc/self read-only)

4. **UTS (Hostname) Namespace Isolation**
   - Container hostname set to sandbox_<request_id> (not host hostname)

5. **IPC Namespace Isolation**
   - Container IPC resources isolated from host and other containers

6. **Seccomp Filtering**
   - Allowlist-based syscall filtering (default deny, whitelist specific syscalls)
   - Allowed syscalls:
     - **Process control:** brk, arch_prctl, prctl, exit, exit_group
     - **Memory:** mmap, mprotect, madvise, mremap, munmap, msync
     - **File I/O:** open, openat, read, write, pread64, pwrite64, readv, writev, preadv, pwritev, fstat, fstatfs, faccessat, fcntl, dup, dup2, dup3, close
     - **Directory:** getdents64, getcwd
     - **Time:** clock_gettime, clock_nanosleep, nanosleep, gettimeofday
     - **Signals:** rt_sigaction, rt_sigprocmask, rt_sigpending
     - **Sched:** sched_getaffinity, sched_yield
     - **Other:** sigaltstack, ioctl (limited), prlimit64, getrandom
   - **Blocked syscalls:** execve, ptrace, clone (new namespace), socket, connect, bind, sendto, recvfrom, ioctl (most forms), chroot, mount, umount2, seccomp (recursive sandboxing blocked)

7. **Cgroup v2 Resource Limits**
   - Memory: memory.max
   - CPU: cpu.max (hard limit), cpu.weight (soft proportional share)
   - I/O: io.max (optional bandwidth throttle)
   - Pids: pids.max = 1 (single process only)

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **INITIALIZING** | Setting up isolation layers | → READY (all layers initialized) \| → INIT_ERROR (setup failed) |
| **READY** | Sandbox configured and ready for execution | → ACTIVE (on code execution start) |
| **ACTIVE** | Code executing inside sandbox | → TEARDOWN (on process exit) |
| **TEARDOWN** | Cleaning up namespaces, cgroups, tmpfs | → DESTROYED (cleanup complete) |
| **DESTROYED** | Sandbox destroyed; resources freed | → (new sandbox for next request) |
| **INIT_ERROR** | Initialization failed | → FAULTED |
| **FAULTED** | Isolation layer failure detected at runtime | → TEARDOWN |

**Violation Detection & Response:**

| Violation | Detection | Response |
|---|---|---|
| Syscall outside allowlist | Seccomp filter blocks | Process receives SIGKILL, exit code 159 |
| Network connection attempt | NET namespace has no routes | socket() returns ENODEV, connect() returns EACCES |
| Filesystem access outside tmpfs | MNT namespace rootfs is read-only | open() returns EACCES or ENOENT |
| Process creation (fork, clone) | seccomp blocks clone with CLONE_* | clone() blocked, EPERM |
| Device access | No /dev in namespace | open(/dev/...) returns ENODEV or EACCES |
| Namespace escape attempt (ptrace, setns) | Seccomp blocks ptrace, setns | Blocked, EPERM |

**Invariants:**

1. **No network egress from sandbox:**
   - ∀ process ∈ sandbox: network_operations = {} (empty set; no connections possible)

2. **No filesystem access outside tmpfs:**
   - ∀ path accessed by process ∈ sandbox: path ∈ {tmpfs_mount, rootfs_readonly}

3. **No process visibility outside namespace:**
   - ∀ process ∈ sandbox: visible_processes ⊆ {self, children}

4. **No syscall outside allowlist:**
   - ∀ syscall attempted by process ∈ sandbox: syscall ∈ allowlist ∨ seccomp_filter blocks

5. **No resource sharing with host:**
   - ∀ resource ∈ {memory, cpu, disk, pids}: resource.sandbox_usage ≤ resource.limit

**Error Behavior:**

| Error Condition | Detection | Logged | Trace | Response |
|---|---|---|---|---|
| Namespace creation failure | ns_create() returns error | Yes (ERROR) | trace.sandbox_ns_error | Context → FAULTED |
| Seccomp profile load failure | seccomp_load() returns error | Yes (ERROR) | trace.sandbox_seccomp_error | Context → FAULTED |
| Cgroup limit setup failure | cgroup_write() fails | Yes (ERROR) | trace.sandbox_cgroup_error | Context → FAULTED |
| Rootfs mount failure | mount() returns error | Yes (ERROR) | trace.sandbox_mount_error | Context → FAULTED |
| Tmpfs mount failure | tmpfs mount fails | Yes (ERROR) | trace.sandbox_tmpfs_error | Context → FAULTED |
| Namespace escape detected (runtime) | Anomalous syscall pattern | Yes (CRITICAL) | trace.sandbox_escape_attempt | Process SIGKILL, audit alert |

**Failure Predicates:**

Security Boundary fails when:

1. **PID Namespace Creation Fails:** unshare(CLONE_NEWPID) returns error → raise NamespaceError
2. **NET Namespace Creation Fails:** unshare(CLONE_NEWNET) returns error → raise NamespaceError
3. **MNT Namespace Creation Fails:** unshare(CLONE_NEWNS) returns error → raise NamespaceError
4. **Seccomp Profile Invalid:** seccomp filter rule syntax invalid → raise SeccompError
5. **Seccomp Load Fails:** prctl(PR_SET_SECCOMP) returns error → raise SeccompError
6. **Cgroup v2 Not Available:** /sys/fs/cgroup/cgroup.controllers missing → raise CgroupError
7. **Cgroup Memory Limit Fails:** write to memory.max fails → raise CgroupError
8. **Cgroup CPU Limit Fails:** write to cpu.max fails → raise CgroupError
9. **Rootfs Mount Fails:** mount(squashfs, /root) fails → raise MountError
10. **Tmpfs Mount Fails:** mount(tmpfs, /tmp) fails → raise MountError
11. **Syscall Escape Detected:** Process attempts blocked syscall at runtime → SIGKILL (exit 159)

**Acceptance Criteria:**

1. **Namespace Isolation Active:** Process in sandbox cannot see host processes.
   - Assert: ps inside sandbox shows only init + child process; ps on host shows normal process tree

2. **Network Isolation Verified:** Network connect fails inside sandbox.
   - Assert: Code attempting socket.connect() receives EACCES or connection timeout (no actual connection)

3. **Filesystem Isolation Verified:** Read-only rootfs blocks writes outside tmpfs.
   - Assert: Code attempting open('/etc/passwd', 'w') fails with EACCES

4. **Seccomp Allowlist Enforced:** Blocked syscalls trigger SIGKILL.
   - Assert: Code calling ptrace() or execve() dies with exit code 159

5. **Cgroup Memory Limit Enforced:** OOM killer activates at limit.
   - Assert: Allocation loop with memory_limit=256 hits OOM, process killed with exit 137

6. **Cgroup CPU Limit Enforced:** CPU usage throttled to quota.
   - Assert: Busy loop CPU usage ≤ cpu.quota over measurement period

7. **Tmpfs Writable:** Code can write to /tmp.
   - Assert: Code writing to /tmp/test.txt succeeds; file readable within same process

8. **State Cleanup:** Tmpfs cleared between executions.
   - Assert: After execution E1 completes, /tmp is empty for execution E2

9. **Isolation Layer Failure Detection:** If namespace setup fails, execution rejected.
   - Assert: unshare() failure → ExecutionResult.error_message set, exit_code=1

10. **Escape Audit Trail:** Anomalous pattern (e.g., unexpected syscalls) logged.
    - Assert: Attempted ptrace or setns logged as CRITICAL event with request_id, timestamp, user_id

---

## 3. Egress Control

### 3.1 L7 Application-Layer Enforcement

**Purpose:** Enforce domain allowlist, redact sensitive payloads, apply rate limits, enforce budget constraints, and log all outbound requests before allowing them to transit to external services (LLM APIs, HTTP endpoints, etc.).

**Pipeline:**

```
Request → Domain Check → Payload Redaction → Rate Limit Check → Budget Check → Logging → Forward (or Reject)
```

**State Machine:**

| State | Meaning | Transitions |
|-------|---------|-------------|
| **RECEIVING** | Received outbound request | → CHECKING_DOMAIN |
| **CHECKING_DOMAIN** | Verifying domain in allowlist | → DOMAIN_ALLOWED (domain ✓) \| → DOMAIN_BLOCKED (not in allowlist) |
| **DOMAIN_ALLOWED** | Domain permitted | → REDACTING |
| **REDACTING** | Applying PII/secret redaction to request/response | → REDACTED (redaction complete) \| → REDACTION_ERROR (redaction failed) |
| **REDACTED** | Payload sanitized | → RATE_CHECKING |
| **RATE_CHECKING** | Evaluating rate limit (requests/minute per tenant) | → RATE_ALLOWED (under limit) \| → RATE_EXCEEDED (over limit) |
| **RATE_ALLOWED** | Rate limit not exceeded | → BUDGET_CHECKING |
| **BUDGET_CHECKING** | Evaluating budget (LLM tokens, API calls per workflow) | → BUDGET_ALLOWED (within budget) \| → BUDGET_EXCEEDED (over budget) |
| **BUDGET_ALLOWED** | Budget not exceeded | → LOGGING |
| **LOGGING** | Recording request details for audit | → LOGGED (record written) \| → LOG_ERROR (write failed) |
| **LOGGED** | Request logged | → FORWARDING |
| **FORWARDING** | Sending request to external service | → RESPONSE_RECEIVED (response arrived) \| → FORWARD_ERROR (request failed) |
| **RESPONSE_RECEIVED** | External service responded | → RESPONSE_REDACTING (sanitize response) |
| **RESPONSE_REDACTING** | Redacting sensitive data from response | → RESPONSE_REDACTED (response sanitized) |
| **RESPONSE_REDACTED** | Response cleaned | → IDLE (return to caller) |
| **DOMAIN_BLOCKED** | Domain not in allowlist | → FAULTED (raise DomainBlockedError) |
| **RATE_EXCEEDED** | Rate limit hit | → FAULTED (raise RateLimitError) |
| **BUDGET_EXCEEDED** | Budget exhausted | → FAULTED (raise BudgetExceededError) |
| **REDACTION_ERROR** | Redaction failed | → FAULTED (raise RedactionError) |
| **LOG_ERROR** | Logging failed | → FAULTED (raise LoggingError) |
| **FORWARD_ERROR** | Request failed or timed out | → FAULTED (raise ForwardError) |

**Domain Allowlist:**

```
ALLOWED_DOMAINS = {
  "api.openai.com": {"type": "llm", "rate_limit": 100_per_min, "budget": "token_count"},
  "api.anthropic.com": {"type": "llm", "rate_limit": 100_per_min, "budget": "token_count"},
  "api.gmail.com": {"type": "email", "rate_limit": 10_per_min, "budget": "messages"},
  "api.slack.com": {"type": "messaging", "rate_limit": 50_per_min, "budget": "messages"},
  ...
}
```

**Redaction Rules (Request & Response):**

- **API Keys/Tokens:** Redact to `[secret]`
- **Email Addresses:** Redact to `[email]`
- **Phone Numbers:** Redact to `[phone]`
- **Credit Card Numbers:** Redact to `****-****-****-XXXX`
- **PII (Names, SSN, DOB):** Redact to `[pii]`
- **Database Connection Strings:** Redact to `[db_string]`

**Rate Limiting:**

```
Per-tenant rate limits (enforced via Redis counter):
  rate_limit_key = f"egress:rate:{tenant_id}:{domain}"
  current_count = redis.get(rate_limit_key) || 0
  if current_count >= rate_limit_threshold:
    raise RateLimitError()
  redis.incr(rate_limit_key)
  redis.expire(rate_limit_key, 60)  // Reset every minute
```

**Budget Tracking:**

```
Per-workflow budgets (stored in Postgres, updated per request):
  budget_key = f"workflow:{workflow_id}:tokens_used"
  tokens_used = pg.query(SELECT tokens_used FROM workflow_budgets WHERE id=workflow_id)
  tokens_in_request = estimate_tokens(request)
  if tokens_used + tokens_in_request > budget_limit:
    raise BudgetExceededError()
  pg.update(workflow_budgets, tokens_used += tokens_in_request)
```

**Decision Logic (pseudocode):**

```
function l7_enforce_egress(request, caller_context):
  // 1. Check domain allowlist
  domain = extract_domain(request.url)
  if domain not in ALLOWED_DOMAINS:
    raise DomainBlockedError(f"Domain {domain} not in allowlist")

  // 2. Redact request payload
  redacted_request = redact_sensitive_fields(request)

  // 3. Check rate limit
  rate_limit = ALLOWED_DOMAINS[domain].rate_limit
  rate_key = f"egress:rate:{caller_context.tenant_id}:{domain}"
  if redis.get(rate_key) >= rate_limit:
    raise RateLimitError(f"Rate limit {rate_limit} exceeded for {domain}")
  redis.incr(rate_key)
  redis.expire(rate_key, 60)

  // 4. Check budget
  budget = get_workflow_budget(caller_context.workflow_id)
  tokens_estimated = estimate_tokens(redacted_request)
  workflow_tokens = pg.query("SELECT tokens_used FROM workflow_budgets WHERE id=?",
                              caller_context.workflow_id)
  if workflow_tokens + tokens_estimated > budget.limit:
    raise BudgetExceededError()

  // 5. Log request
  log_request({
    tenant_id: caller_context.tenant_id,
    workflow_id: caller_context.workflow_id,
    domain: domain,
    timestamp: now(),
    redacted_request: redacted_request,
  })

  // 6. Forward request
  response = http_client.send(redacted_request)

  // 7. Redact response
  redacted_response = redact_sensitive_fields(response)

  // 8. Update budget
  pg.query("UPDATE workflow_budgets SET tokens_used = tokens_used + ? WHERE id = ?",
           tokens_estimated, caller_context.workflow_id)

  return redacted_response
```

**Invariants:**

1. **No request to non-allowlisted domain:**
   - ∀ egress_request: domain(request.url) ∈ ALLOWED_DOMAINS

2. **All PII/secrets redacted before egress:**
   - ∀ request: ¬contains_pii(redacted_request) ∧ ¬contains_secret(redacted_request)

3. **Rate limits enforced per tenant:**
   - ∀ tenant, domain: requests_per_minute(tenant, domain) ≤ rate_limit(domain)

4. **Budget enforced per workflow:**
   - ∀ workflow: cumulative_tokens_used(workflow) ≤ budget_limit(workflow)

5. **All egress logged:**
   - ∀ request: request.url ∈ ALLOWED_DOMAINS ⟹ ∃ log_entry where log_entry.domain = domain(request.url)

**Error Behavior:**

| Error Condition | Exception Type | Logged | Trace | Response |
|---|---|---|---|---|
| Domain not allowed | `DomainBlockedError` | Yes (WARN) | Yes (trace.egress_domain_blocked) | HTTP 403 Forbidden |
| Rate limit exceeded | `RateLimitError` | Yes (INFO) | Yes (trace.egress_rate_limited) | HTTP 429 Too Many Requests |
| Budget exceeded | `BudgetExceededError` | Yes (WARN) | Yes (trace.egress_budget_exceeded) | HTTP 402 Payment Required |
| Redaction failed | `RedactionError` | Yes (ERROR) | Yes | HTTP 500 Internal Error |
| Logging failed | `LoggingError` | Yes (ERROR) | Yes | HTTP 500 Internal Error (fail-safe: block request) |
| Forward failed | `ForwardError` | Yes (WARN) | Yes (trace.egress_forward_error) | HTTP 502 Bad Gateway |
| Request timeout | `TimeoutError` | Yes (WARN) | Yes | HTTP 504 Gateway Timeout |

**Failure Predicates:**

L7 fails when:

1. **Domain Not in Allowlist:** domain not in ALLOWED_DOMAINS → raise DomainBlockedError
2. **Rate Limit Exceeded:** requests_in_window ≥ rate_limit → raise RateLimitError
3. **Budget Exceeded:** cumulative_tokens > budget_limit → raise BudgetExceededError
4. **Redaction Error:** redaction function threw exception → raise RedactionError
5. **Logging Error:** log write to Postgres failed → raise LoggingError (fail-safe: block request)
6. **Forward Timeout:** HTTP request exceeded timeout (30s) → raise TimeoutError
7. **Forward Error:** HTTP request failed (connection error, 5xx response) → raise ForwardError

**Acceptance Criteria:**

1. **Allowlisted Domain Passes:** Domain in allowlist proceeds through pipeline.
   - Assert: l7_enforce_egress(request_to_api.openai.com) → request forwarded (no DomainBlockedError)

2. **Non-Allowlisted Domain Blocked:** Domain not in allowlist raises DomainBlockedError.
   - Assert: l7_enforce_egress(request_to_random.example.com) → DomainBlockedError

3. **Request Redaction:** PII in request is redacted before forward.
   - Assert: request contains email@example.com → l7_enforce_egress() → forwarded request contains `[email]`, not plaintext

4. **Response Redaction:** PII in response is redacted before return.
   - Assert: response contains API key → l7_enforce_egress() → returned response contains `[secret]`, not plaintext

5. **Rate Limit Enforcement:** Requests exceeding per-minute limit are blocked.
   - Assert: Send 100 requests in 1 minute (rate_limit=100) → 101st request → RateLimitError

6. **Budget Enforcement:** Requests exceeding workflow budget are blocked.
   - Assert: workflow.budget = 1000 tokens, 900 used, request needs 200 → BudgetExceededError

7. **Logging Coverage:** All forwarded requests logged.
   - Assert: After forwarding N requests, count(egress_logs) == N

8. **Timeout Enforcement:** Requests exceeding 30s timeout are aborted.
   - Assert: Slow upstream (doesn't respond for 60s) → l7_enforce_egress() → TimeoutError after 30s

9. **Tenant Isolation:** Rate limits and budgets per tenant are independent.
   - Assert: tenant_a uses X requests, tenant_b uses Y requests; no interference

10. **Fail-Safe Deny on Logging Error:** If logging fails, request is blocked.
    - Assert: Postgres unavailable → l7_enforce_egress() → LoggingError, request not forwarded

---

### 3.2 L3 NAT Gateway

**Purpose:** Provide network-layer egress-only routing and prevent inbound connections from internet to Holly Grace infrastructure.

**Architecture:**

```
Holly Grace VPC (private subnet)
  ↓
  NAT Gateway (AWS NAT or OCI equivalent)
    ↓
    Elastic IP (static outbound address)
      ↓
      Internet Gateway
        ↓
        External Internet
```

**Network Configuration:**

```
Holly Private Subnet Route Table:
  0.0.0.0/0 → NAT Gateway (nat-xyz)
  10.0.0.0/8 → Local (VPC CIDR)

NAT Gateway:
  - In public subnet (has route to IGW)
  - Elastic IP: 203.0.113.45 (static)
  - Handles outbound TCP/UDP from private subnet
  - Drops inbound traffic from internet (no inbound rules)

Security Group (egress):
  Egress: 0.0.0.0/0 (allow all outbound)
  Ingress: 10.0.0.0/8 only (internal only)

Network ACL (outbound only):
  Outbound: 0.0.0.0/0 allowed
  Inbound: 10.0.0.0/8 allowed (internal); 0.0.0.0/0 denied (internet blocked)
```

**Invariants:**

1. **NAT provides egress-only routing:**
   - ∀ outbound_packet from private subnet: routed through NAT; return packets translated by NAT; source IP becomes NAT's Elastic IP

2. **No inbound connections from internet:**
   - ∀ inbound_packet from internet (source IP not in VPC CIDR): dropped by NAT (no inbound rule exists)

3. **Elastic IP is static:**
   - NAT Gateway's Elastic IP remains constant; domain allowlist in L7 can whitelist this static IP

**Routing Table Entries:**

| Destination | Target | Status |
|---|---|---|
| 0.0.0.0/0 | nat-12345 | Active |
| 10.0.0.0/8 | Local | Active |

**Security Group Rules:**

| Direction | Protocol | Port Range | CIDR | Action |
|---|---|---|---|---|
| Egress | All | All | 0.0.0.0/0 | Allow |
| Ingress | TCP | 443 | 10.0.0.0/8 | Allow |
| Ingress | TCP | 22 | 10.0.0.0/8 | Allow |
| Ingress | All | All | 0.0.0.0/0 | Deny |

**Network ACL Rules:**

| Rule # | Type | Protocol | Port | CIDR | Action |
|---|---|---|---|---|---|
| 100 | Inbound | All | All | 10.0.0.0/8 | Allow |
| 110 | Inbound | TCP | 1024-65535 | 0.0.0.0/0 | Allow (return traffic) |
| 120 | Inbound | All | All | 0.0.0.0/0 | Deny |
| 100 | Outbound | All | All | 0.0.0.0/0 | Allow |

**Failure Predicates:**

L3 NAT fails when:

1. **NAT Gateway Unavailable:** NAT instance/service down → all outbound traffic blocked (fail-safe)
2. **Elastic IP Unassociated:** EIP not attached to NAT → outbound traffic fails
3. **Routing Table Corrupt:** Route to NAT missing or pointing elsewhere → traffic misrouted
4. **Security Group Missing Egress Rule:** Egress rule to 0.0.0.0/0 removed → outbound traffic blocked
5. **Network ACL Denies Outbound:** ACL rule removes outbound allow → traffic blocked
6. **VPC Flow Logs Show Inbound Accepted:** If ACCEPT action logged for inbound from internet, ACL/SG misconfigured

**Acceptance Criteria:**

1. **Outbound Routing Works:** Packet from Holly private subnet routed through NAT.
   - Assert: traceroute from container → shows NAT Gateway as hop

2. **Static Elastic IP:** NAT Elastic IP is stable across instance restarts.
   - Assert: ping NAT Elastic IP before/after restart → same IP

3. **Inbound Blocked:** Internet packet to Holly private subnet is dropped.
   - Assert: nmap from external host to Holly private subnet → no open ports; all filtered

4. **Return Traffic Allowed:** Established connections receive return traffic.
   - Assert: Outbound connection established → inbound response packets are NATted and delivered

5. **Security Group Enforced:** Ingress from internet denied at SG level.
   - Assert: Security group has no ingress rules from 0.0.0.0/0

6. **Network ACL Enforced:** Inbound ACL rule denies internet traffic.
   - Assert: NACL inbound rule 120 "DENY all from 0.0.0.0/0"

---

## Cross-Reference: Component Mapping

| Component | SAD Node | SIL Level | Formal Spec | FMEA | Tests | Acceptance Gate |
|---|---|---|---|---|---|---|
| **KernelContext** | Layer 1 / KERNEL | 3 | State machine (§1.1) | FMEA-K001 | Property-based, state machine fuzzing | All transitions covered |
| **K1 Schema Validation** | Layer 1 / K1 | 3 | Decision logic (§1.2) | FMEA-K102 | Schema fuzzing, invalid payload suites | All input domains covered |
| **K2 Permission Gates** | Layer 1 / K2 | 3 | Decision logic (§1.3) | FMEA-K103 | JWT fuzzing, role matrix | All permission combos |
| **K3 Bounds Checking** | Layer 1 / K3 | 3 | Decision logic (§1.4) | FMEA-K104 | Budget exhaustion, overflow tests | Budget ceiling tests |
| **K4 Trace Injection** | Layer 1 / K4 | 3 | Decision logic (§1.5) | FMEA-K105 | Trace propagation, correlation ID leakage | Correlation preserved end-to-end |
| **K5 Idempotency Key Gen** | Layer 1 / K5 | 3 | RFC 8785 algorithm (§1.6) | FMEA-K106 | RFC 8785 vectors, collision test | Zero collisions in test suite |
| **K6 Audit WAL** | Layer 1 / K6 | 3 | Append-only schema (§1.7) | FMEA-K107 | Redaction coverage, WAL ordering | All PII redacted, no updates |
| **K7 HITL Gates** | Layer 1 / K7 | 3 | State machine (§1.8) | FMEA-K108 | Confidence eval, approval workflow | Timeout enforced, human approval required |
| **K8 Eval Gates** | Layer 1 / K8 | 3 | State machine (§1.9) | FMEA-K109 | Predicate loading, eval failure | All predicates tested, timeout enforced |
| **Code Executor** | Sandbox / SEXEC | 3 | Protocol + limits (§2.1) | FMEA-SAND201 | Execution fuzzing, timeout/OOM/seccomp | All limits enforced, metrics accurate |
| **Security Boundary** | Sandbox / SSEC | 3 | Isolation layers (§2.2) | FMEA-SAND202 | Namespace escape, syscall blocking | All namespaces active, seccomp enforced |
| **L7 App-Layer** | Egress / EGRESS | 3 | Decision logic (§3.1) | FMEA-EGR301 | Domain whitelist, redaction, rate limits | All redaction rules covered |
| **L3 NAT Gateway** | Egress / EGRESS | 3 | NAT config (§3.2) | FMEA-EGR302 | Inbound block, outbound routing | Inbound blocked, outbound works |

---

## Verification & Testing Strategy

### SIL-3 Verification Levels

For each component, verification uses:

1. **Unit Tests** (fast, deterministic)
   - State transitions
   - Decision logic edge cases
   - Error conditions

2. **Property-Based Tests** (Hypothesis, generative)
   - Invariants hold across random input domain
   - State machine never reaches invalid state
   - Idempotency properties (K5)

3. **Integration Tests** (thin slice)
   - Kernel gates in sequence
   - Sandbox with L7 egress
   - End-to-end boundary crossing

4. **Formal Model-Checking** (TLA+)
   - KernelContext state machine (deadlock-free, liveness)
   - Sandbox isolation (no escape conditions)
   - Egress pipeline (no domain bypass)

5. **Independent Verification** (dissimilar channel)
   - Sandbox escape attempts by external security team
   - Cryptographic validation of K5 (RFC 8785) by standard library
   - WAL integrity checks via database constraints (no UPDATE allowed)

6. **Adversarial / Red Team**
   - Prompt injection to bypass eval gates
   - Resource exhaustion (budgets)
   - Timing attacks on rate limiters

### Traceability

Every acceptance criterion is linked to:
- A specific test case in the SIL-3 test suite
- A specific requirement in the design document (README or SAD)
- A specific design decision (Architecture Decision Record)

---

## Conclusion

This specification formalizes Holly Grace's three SIL-3 component groups to the level required for independent verification, model-checking, and formal proof. Each component:

- Defines its state machine exhaustively
- States its invariants as formal predicates
- Enumerates all failure modes
- Specifies acceptance criteria that are testable
- Includes decision logic precise enough for TLA+ specification

The specification is the source of truth for:
- Test case design (property-based and unit)
- Formal model-checking (TLA+)
- Architecture fitness functions (CI gates)
- Dissimilar verification channel validation
- Safety case evidence (claims → evidence → context)

