# Holly Grace — Goal Hierarchy Formal Specification v0.1

**Generated**: 17 February 2026
**Source**: Allen (2026), SAD v0.1.0.5, README narrative
**Classification**: Engineering Artifact (SIL-2 Design Input)

---

## Executive Summary

This document formalizes the goal hierarchy that governs Holly Grace autonomous operations. Drawing from Allen (2026) *Informational Monism, Morphogenetic Agency, and Goal-Specification Engineering*, Holly implements a **seven-level goal hierarchy** where five **Celestial levels (L0–L4)** are immutable safety constraints and two **Terrestrial levels (L5–L6)** represent user intent. Lexicographic gating enforces that no Terrestrial goal can satisfy itself by violating a Celestial constraint. This specification provides formal definitions, executable predicates, composition rules, multi-agent feasibility conditions, and enforcement mechanisms.

---

## 1. Definitions

### 1.1 State Space

The Holly system operates over a **state space S** representing all possible configurations of the system at any instant.

**Definition 1.1.1 (State Space)**
Let S be the system state space, a measurable space over propositions describing:
- Agent internal states (goal assignment, reasoning state, cognitive light cone)
- System topology (team composition, contracts, permissions)
- Resource state (tool invocations, memory consumption, bandwidth usage)
- Execution state (lanes active, workflows running, checkpoints, idempotency ledger)
- Data state (user data, audit logs, traces, memory tiers)
- Kernel state (permission masks, authorization credentials, revocation cache)

A system state is $s \in S$.

**Definition 1.1.2 (Trajectory)**
A trajectory $\tau: [0, T] \to S$ is a time-parameterized path through state space representing the system's evolution over an execution interval $[0, T]$.

**Definition 1.1.3 (State Transition)**
An action $a \in \mathcal{A}$ applied to state $s$ produces a successor state via the transition function:
$$\text{apply}(s, a) = s' \in S$$

State transitions are deterministic conditional on agent outputs and environmental inputs.

### 1.2 Goals and Goal Regions

**Definition 1.2.1 (Goal as Predicate Set)**
A goal $G$ is a predicate set over the state space:
$$G = \{s \in S \mid p_G(s) = \text{true}\}$$

where $p_G : S \to \{\text{true}, \text{false}\}$ is the goal predicate. We say $s$ **satisfies** $G$ iff $s \in G$.

**Definition 1.2.2 (Goal Types)**
- **Maintenance goal**: A goal $G_m$ is a maintenance goal if the system must remain within $G_m$ over an interval:
$$\forall t \in [t_0, T]: \tau(t) \in G_m$$

- **Achievement goal**: A goal $G_a$ is an achievement goal if the system must reach $G_a$ at least once:
$$\exists t \in [t_0, T]: \tau(t) \in G_a$$

**Definition 1.2.3 (Goal Satisfaction Distance)**
For a state $s$ and goal region $G$, the **distance to goal** is:
$$d(s, G) = \inf_{s' \in G} \|s - s'\|_S$$

where $\|\cdot\|_S$ is a metric on state space. Satisfaction occurs when $d(s, G) = 0$.

### 1.3 Codimension

Codimension quantifies the constraint strength of a goal.

**Definition 1.3.1 (Codimension)**
The codimension of goal $G$ is:
$$\text{codim}(G) = \dim(S) - \dim(G)$$

where $\dim(S)$ is the dimensionality of the state space and $\dim(G)$ is the dimension of the goal region as a subset of $S$.

**Interpretation**: Codimension measures the number of independent constraints the goal imposes. A goal with codimension 0 is "open" (imposes no constraints). A goal with codimension equal to $\dim(S)$ is a point (fully constrains the system).

**Definition 1.3.2 (Constraint Strength)**
We say goal $G_i$ is **more constraining** than goal $G_j$ if $\text{codim}(G_i) > \text{codim}(G_j)$.

In practical terms, higher codimension goals are harder to satisfy (leave fewer degrees of freedom available for lower-level objectives).

### 1.4 Hierarchical Composition

**Definition 1.4.1 (Goal Conjunction)**
The conjunction of goals $G_1, G_2, \ldots, G_n$ is their set intersection:
$$G_1 \cap G_2 \cap \cdots \cap G_n = \{s \in S \mid p_{G_1}(s) \land p_{G_2}(s) \land \cdots \land p_{G_n}(s)\}$$

This combined region contains only states that satisfy all goals simultaneously.

**Definition 1.4.2 (Lexicographic Ordering)**
A priority ordering $\succ$ on goals is **lexicographic** if:
$$G_i \succ G_j \iff \text{(if any action satisfies $G_i$, take it; only if no such action exists, consider $G_j$)}$$

Formally, we evaluate the hierarchy sequentially: first maximize satisfaction of $G_0$, then $G_1$, etc., taking the first feasible action.

**Definition 1.4.3 (Hierarchical Composition with Priority)**
A hierarchical composition of goals $G_0 \succ G_1 \succ \cdots \succ G_n$ is satisfied by a trajectory $\tau$ iff:
$$\forall i \in [0, n]: (\tau(T) \in G_i) \text{ OR } (G_i \text{ is infeasible given } G_0, \ldots, G_{i-1})$$

The system prioritizes $G_0$ absolutely; if $G_0$ is feasible, no goal satisfied unless it also satisfies $G_0$; and so on recursively.

---

## 2. The Seven-Level Hierarchy

Holly's goal hierarchy has **seven levels** organized into two regimes: **Celestial (L0–L4)** and **Terrestrial (L5–L6)**.

### 2.0 Level L0 — Safety Invariants

**Regime**: Celestial (immutable)
**Type**: Maintenance goal
**Codimension**: High (safety constraints typically have codim ≥ 2)

**Formal Definition**:
$$L0 = \{s \in S \mid \text{safety\_invariant}(s) = \text{true}\}$$

**Goal Predicate** (pseudocode):
```python
def evaluate_L0(state: SystemState) -> GoalResult:
    """Safety invariant: prevent physical harm, weapon enablement, loss of control."""

    safety_checks = [
        check_no_physical_harm(state),
        check_no_weapons_enabled(state),
        check_system_retains_control(state),
        check_no_cascade_failures(state)
    ]

    satisfied = all(check.passed for check in safety_checks)
    distance = max(check.distance for check in safety_checks)

    return GoalResult(
        level=L0,
        satisfied=satisfied,
        distance=distance,
        explanation="; ".join(c.explanation for c in safety_checks)
    )
```

**Concrete Examples**:
- No action that damages hardware or causes physical harm to users
- No action that enables weapon systems or dual-use capabilities
- No system takeover: user retains override at all times
- No cascading failures in safety chain (K1–K8 remain operational)

**Enforcement Point**: K8 (Eval Gate) + Constitutional safety predicate
**Override Policy**: **NEVER**. L0 cannot be overridden by any agent, user, or system component.

---

### 2.1 Level L1 — Legal Compliance

**Regime**: Celestial (immutable)
**Type**: Maintenance goal
**Codimension**: Medium (legal constraints vary; some are strict, others have safe harbors)

**Formal Definition**:
$$L1 = \{s \in S \mid \text{legal\_compliance}(s) = \text{true}\}$$

**Goal Predicate** (pseudocode):
```python
def evaluate_L1(state: SystemState) -> GoalResult:
    """Legal compliance: data protection, export controls, content restrictions."""

    compliance_checks = [
        check_gdpr_compliance(state),         # data residency, retention
        check_export_control(state),          # restricted destinations
        check_content_restrictions(state),    # DMCA, CFAA, etc.
        check_regional_laws(state),           # tenant jurisdiction
    ]

    satisfied = all(check.passed for check in compliance_checks)
    distance = max(check.distance for check in compliance_checks)

    return GoalResult(
        level=L1,
        satisfied=satisfied,
        distance=distance,
        explanation="; ".join(c.explanation for c in compliance_checks)
    )
```

**Concrete Examples**:
- No egress of PII to restricted jurisdictions (GDPR, CCPA compliance)
- No assistance with circumventing access controls (CFAA)
- No export of cryptographic tools to sanctioned entities
- No generation of harmful chemical/biological synthesis instructions

**Enforcement Point**: K2 (Permission Gate) + K8 (Eval Gate) + constitutional predicate
**Override Policy**: **NEVER**. Legal constraints cannot be overridden except through proper legal channels (regulation change, court order, licensed exception) — and such changes are governance-level, not operational.

---

### 2.2 Level L2 — Ethical Constraints

**Regime**: Celestial (immutable)
**Type**: Maintenance goal
**Codimension**: Medium-high (ethical boundaries are often context-dependent but non-negotiable once established)

**Formal Definition**:
$$L2 = \{s \in S \mid \text{ethical\_constraint}(s) = \text{true}\}$$

**Goal Predicate** (pseudocode):
```python
def evaluate_L2(state: SystemState) -> GoalResult:
    """Ethical constraints: fairness, transparency, non-deception."""

    ethical_checks = [
        check_fairness(state),                # no discrimination
        check_transparency(state),            # disclosure of AI use
        check_non_deception(state),           # no impersonation, no false claims
        check_consent(state),                 # informed consent obtained
        check_autonomy_respect(state),        # user retains decision authority
    ]

    satisfied = all(check.passed for check in ethical_checks)
    distance = max(check.distance for check in ethical_checks)

    return GoalResult(
        level=L2,
        satisfied=satisfied,
        distance=distance,
        explanation="; ".join(c.explanation for c in ethical_checks)
    )
```

**Concrete Examples**:
- No discrimination by protected class (race, gender, religion, etc.)
- Disclosure: "I am Claude, an AI assistant by Anthropic"
- No misrepresentation of AI capabilities or confidence
- No impersonation of humans
- User retains final decision authority on consequential actions

**Enforcement Point**: K8 (Eval Gate) + constitutional ethical predicates
**Override Policy**: **NEVER**. Constitutional ethics are not negotiable by operational policy.

---

### 2.3 Level L3 — Permission Boundaries

**Regime**: Celestial (immutable)
**Type**: Maintenance goal
**Codimension**: Medium (authorization is granular; many constraints are boolean)

**Formal Definition**:
$$L3 = \{s \in S \mid \forall (a, r) \in \text{(agent, resource)}: \text{authorized}(a, r) = \text{true}\}$$

where $\text{authorized}(a, r)$ checks that agent $a$ holds the required permission to access resource $r$.

**Goal Predicate** (pseudocode):
```python
def evaluate_L3(state: SystemState) -> GoalResult:
    """Permission boundaries: agents can only use authorized tools/data."""

    authorization_checks = []

    for agent in state.active_agents:
        for tool in agent.allocated_tools:
            auth_check = verify_tool_authorization(
                agent_id=agent.id,
                tool_name=tool.name,
                permission_mask=state.mcp_permissions[agent.id]
            )
            authorization_checks.append(auth_check)

        for data_resource in agent.accessed_data:
            rls_check = verify_rls_policy(
                agent_id=agent.id,
                tenant_id=state.tenant_id,
                resource_table=data_resource.table
            )
            authorization_checks.append(rls_check)

    satisfied = all(check.passed for check in authorization_checks)
    distance = max((check.distance for check in authorization_checks), default=0.0)

    return GoalResult(
        level=L3,
        satisfied=satisfied,
        distance=distance,
        explanation=f"Authorization failures: {[c.explanation for c in authorization_checks if not c.passed]}"
    )
```

**Concrete Examples**:
- Agent can only invoke MCP tools listed in its permission mask
- Agent can only read/write database rows it is authorized for (Row-Level Security)
- Tenant A's data is never visible to Tenant B (strict isolation)
- No agent can modify kernel state, system config, or other agents' assignments

**Enforcement Point**: K2 (Permission Gate) + MCP permission mask + RLS policies
**Override Policy**: **NEVER**. But permissions can be granted through proper administrative channels (API call with tenant admin credentials, recorded in audit log).

---

### 2.4 Level L4 — Constitutional Rules

**Regime**: Celestial (immutable)
**Type**: Maintenance goal
**Codimension**: High (constitutional rules impose structural constraints on the entire system)

**Formal Definition**:
$$L4 = \{s \in S \mid \text{constitution}(s) = \text{true}\}$$

**Goal Predicate** (pseudocode):
```python
def evaluate_L4(state: SystemState) -> GoalResult:
    """Constitutional rules: goal hierarchy integrity, kernel invariance, audit completeness."""

    constitution_checks = [
        # Goal hierarchy must be intact
        check_lexicographic_gating_active(state),
        check_all_L0_L3_predicates_deployed(state),
        check_no_goal_injection_attacks(state),

        # Kernel invariants must be active
        check_all_kernel_gates_operational(state),  # K1-K8
        check_kernel_isolation_boundaries(state),
        check_kernel_idempotency_ledger_integrity(state),

        # Audit trail must be complete and tamper-evident
        check_audit_wal_completeness(state),
        check_audit_log_sealed(state),
        check_no_audit_gaps(state),

        # Topology contracts must be honored
        check_topology_contracts_match_active_agents(state),
        check_repartitioning_governance(state),

        # Steering operators must be well-defined
        check_all_agents_have_steering_ops(state),
        check_steering_op_composition_valid(state),
    ]

    satisfied = all(check.passed for check in constitution_checks)
    distance = max(check.distance for check in constitution_checks)

    return GoalResult(
        level=L4,
        satisfied=satisfied,
        distance=distance,
        explanation="; ".join(c.explanation for c in constitution_checks if not c.passed)
    )
```

**Concrete Examples**:
- The goal hierarchy (L0 ≻ L1 ≻ ... ≻ L6) is active at all times
- All eight kernel gates (K1–K8) are operational
- Audit WAL is never truncated, only appended
- No agent can spawn without a contract
- Lexicographic gating is enforced at every decision point

**Enforcement Point**: K1–K8 collectively
**Override Policy**: **NEVER**. Constitutional rules are the foundation; violating them is system failure.

---

### 2.5 Level L5 — User Intent (Primary)

**Regime**: Terrestrial (modifiable by user)
**Type**: Achievement goal (may have maintenance aspects)
**Codimension**: Variable (depends on user objective complexity)

**Formal Definition**:
$$L5 = \{s \in S \mid \text{user\_objective}(s) = \text{true}\}$$

where $\text{user\_objective}$ is the predicate derived from the user's natural-language intent.

**Goal Predicate** (pseudocode):
```python
def evaluate_L5(state: SystemState) -> GoalResult:
    """User's primary objective (declared intent from conversation)."""

    user_intent = state.conversation_history.last_user_intent

    # Decompose user intent into L5 objective
    # E.g., "find the three best AI research papers on multimodal learning"
    # becomes: L5 = {s | s contains papers P1, P2, P3 matching criteria}

    l5_objective = decompose_intent_to_l5(user_intent)

    # Evaluate: does current state satisfy the objective?
    satisfied = l5_objective.evaluate(state)
    distance = l5_objective.distance_to_satisfaction(state)

    # Gather explanation from reasoning chain
    explanation = state.goal_decomposer.last_decomposition.reasoning

    return GoalResult(
        level=L5,
        satisfied=satisfied,
        distance=distance,
        explanation=explanation,
        classification=state.intent_classifier.classification  # direct_solve / team_spawn / clarify
    )
```

**Concrete Examples**:
- L5: "Summarize the customer feedback from Q4 2025"
- L5: "Generate a product roadmap for the next 6 months"
- L5: "Code review the PR in my GitHub repo"

**Decomposition**: The Goal Decomposer breaks L5 into L6 subgoals based on system state and APS tier classification.

**Enforcement Point**: APS Controller routes to appropriate tier (T0–T3)
**Override Policy**: **Modifiable by user**. A user can change their mind and specify a different L5 objective. Overridable by L0–L4 (if achieving L5 violates Celestial constraints, the system denies or modifies the goal).

---

### 2.6 Level L6 — User Intent (Derived)

**Regime**: Terrestrial (derived from L5 decomposition)
**Type**: Achievement goal
**Codimension**: Lower than L5 (subgoals are more granular)

**Formal Definition**:
$$L6 = \bigcup_{i=1}^{k} L6_i$$

where $L6_i = \{s \in S \mid \text{subgoal\_i}(s) = \text{true}\}$ are the subgoals produced by decomposing L5:
$$\mathcal{D}(L5) = \{L6_1, L6_2, \ldots, L6_k\}$$

**Goal Predicate** (pseudocode):
```python
def evaluate_L6_subgoal(subgoal_id: str, state: SystemState) -> GoalResult:
    """Evaluate a single L6 subgoal assigned to an agent."""

    subgoal = state.goal_hierarchy.get_subgoal(subgoal_id)
    assigned_agent = state.topology.get_agent_for_subgoal(subgoal_id)

    # Evaluate the subgoal predicate
    satisfied = subgoal.predicate.evaluate(state)
    distance = subgoal.distance_to_satisfaction(state)

    # Track which agent is responsible
    agent_ε_compliance = compute_epsilon_compliance(
        agent=assigned_agent,
        goal=subgoal,
        epsilon_tolerance=assigned_agent.epsilon_band
    )

    return GoalResult(
        level=L6,
        subgoal_id=subgoal_id,
        assigned_agent=assigned_agent.id,
        satisfied=satisfied,
        distance=distance,
        epsilon_compliant=agent_ε_compliance.compliant,
        explanation=subgoal.reasoning
    )
```

**Concrete Examples** (derived from L5 "summarize Q4 2025 customer feedback"):
- L6₁: "Retrieve all customer feedback tickets from Oct–Dec 2025"
- L6₂: "Group feedback by category (feature request, bug, support)"
- L6₃: "Generate executive summary with sentiment analysis"
- L6₄: "Format output as markdown report"

**Decomposition**: Each L6 subgoal is assigned to an agent by the Topology Manager. Multiple agents may collaborate (L6 assignments create the team).

**Enforcement Point**: Per-agent eval gates (each agent's output is gated)
**Override Policy**: **Overridable by L0–L5**. If an L6 subgoal conflicts with a higher-level goal, the system modifies or drops it. Modifiable by system (topology restructure).

---

## 3. Lexicographic Gating

Lexicographic gating is the **enforcement mechanism** that ensures Celestial goals dominate Terrestrial ones.

### 3.1 Ordering

The strict lexicographic ordering is:
$$L0 \succ L1 \succ L2 \succ L3 \succ L4 \succ L5 \succ L6$$

**Interpretation**: L0 goals are absolutely highest priority. If any action violates L0, it is **denied immediately**, regardless of L5 or L6 satisfaction. Once L0 is satisfied, we check L1, and so on.

### 3.2 Gating Algorithm

**Pseudocode**:
```python
def lexicographic_gate_check(
    action: Action,
    current_state: SystemState,
    goal_hierarchy: GoalHierarchy
) -> GateResult:
    """
    Lexicographic gating: check action against L0 through L6 in order.
    Return PERMIT / DENY with blocking level.
    """

    # Apply action to compute successor state
    successor_state = apply(current_state, action)

    # Check each level in order
    for level in [L0, L1, L2, L3, L4, L5, L6]:
        goal = goal_hierarchy.get_goal_at_level(level)
        result = goal.evaluate(successor_state)

        if not result.satisfied:
            # This level blocks the action
            return GateResult(
                permitted=False,
                blocking_level=level,
                reason=result.explanation,
                action=action,
                violating_predicate=goal.predicate_name
            )

    # All levels satisfied
    return GateResult(
        permitted=True,
        blocking_level=None,
        reason="All goal levels satisfied",
        action=action
    )
```

**Input**:
- `action: Action` — the proposed action
- `current_state: SystemState` — current system state
- `goal_hierarchy: GoalHierarchy` — the seven-level goal hierarchy

**Output**:
- `GateResult(permitted: bool, blocking_level: Optional[GoalLevel], explanation: str)`

**Execution**: The gating check is performed synchronously before the action is executed. If the gate denies, the action is **not applied**. The system logs the denial and returns feedback to the user.

### 3.3 Formal Properties

**Theorem 3.3.1 (Celestial Inviolability)**
$$\forall \text{ actions } a: \quad \text{if } \exists i \in \{0, 1, 2, 3, 4\}, \text{ apply}(s, a) \notin L_i, \text{ then } a \text{ is denied}$$

**Proof**: By the lexicographic gating algorithm, the first violation encountered stops evaluation and denies the action. Since we check L0–L4 before L5–L6, any violation of a Celestial goal causes denial. ∎

**Corollary 3.3.1.1 (No Celestial Override)**
No Terrestrial goal (L5 or L6) can cause the system to violate a Celestial goal.

**Theorem 3.3.2 (Terrestrial Subordination)**
$$L5 \text{ satisfaction cannot be achieved through any action sequence } a_1, a_2, \ldots, a_n$$
$$\text{ such that } \exists i \in [1,n], j \in \{0,1,2,3,4\}: \text{apply}(\tau(t_i), a_i) \notin L_j$$

**Proof**: Lexicographic gating denies each action $a_i$ that violates any $L_j$ (j ∈ {0..4}), preventing the trajectory from entering a state outside L0–L4. Thus, the only trajectories that can reach L5 satisfaction must remain within L0–L4 throughout. ∎

**Corollary 3.3.2.1 (Feasible Action Space)**
The set of feasible actions at state $s$ is:
$$\mathcal{A}_{\text{feasible}}(s) = \left\{ a \in \mathcal{A} \mid \forall i \in \{0,1,2,3,4\}: \text{apply}(s, a) \in L_i \right\}$$

Only actions in $\mathcal{A}_{\text{feasible}}(s)$ are permitted by the gate.

---

## 4. Goal Decomposition

Goal decomposition breaks a high-level goal into lower-level subgoals assigned to agents.

### 4.1 Decomposition Operator

**Definition 4.1.1 (Decomposition)**
The decomposition operator $\mathcal{D}$ is a function:
$$\mathcal{D}: \text{Goal} \times \text{SystemState} \to 2^{\text{Goal}}$$

That maps a goal and system state to a finite set of subgoals.

**Soundness Property**: If all subgoals in $\mathcal{D}(G, s)$ are satisfied, then $G$ is satisfied:
$$\forall G \in \text{Goal}, s \in S: \quad \left(\bigcap_{G' \in \mathcal{D}(G, s)} G'\right) \subseteq G$$

**Completeness Property**: The subgoals cover the goal region:
$$\bigcap_{G' \in \mathcal{D}(G, s)} G' = G \quad \text{(if decomposition is complete)}$$

In practice, decompositions are sound but may not be complete (sound decomposition is sufficient; complete decomposition is ideal but harder).

**Pseudocode**:
```python
def decompose_goal(
    goal: Goal,
    state: SystemState,
    goal_level: int  # 0-6
) -> List[SubGoal]:
    """Decompose a goal into subgoals."""

    if goal_level == L5:
        # L5 is decomposed by the Goal Decomposer in Core
        # It may spawn multiple L6 subgoals
        subgoals = goal_decomposer_neural.decompose_l5_to_l6(goal, state)
    elif goal_level == L6:
        # L6 subgoals are atomic from the Topology Manager's perspective
        # They are not further decomposed
        subgoals = [goal]
    else:
        # L0-L4 are not decomposed operationally
        # They are evaluated as maintenance predicates
        subgoals = [goal]

    return subgoals
```

### 4.2 Codimension Propagation

**Definition 4.2.1 (Codimension Sum)**
When a goal $G$ is decomposed into subgoals $\{G_1, G_2, \ldots, G_n\}$, the codimensions satisfy:
$$\sum_{i=1}^{n} \text{codim}(G_i) \geq \text{codim}(G)$$

**Interpretation**: The subgoals together impose at least as many constraints as the parent goal. If constraints overlap (multiple subgoals constrain the same dimension), the sum may exceed the parent's codimension.

**Constraint Slack**:
$$\text{slack} = \sum_{i=1}^{n} \text{codim}(G_i) - \text{codim}(G)$$

High slack indicates redundancy (subgoals over-constrain relative to parent).

### 4.3 APS Tier Classification

The APS Controller classifies each goal into one of four tiers based on codimension, agency rank requirements, and coordination needs.

**Definition 4.3.1 (Agency Rank)**
Agency rank $\text{rank}(a)$ of an agent $a$ is the dimensionality of the state space that agent can causally influence within its resource and time budget.

From Allen (2026): "An agent with high rank and a wide light cone can solve problems unilaterally. An agent with narrow rank must compose with others."

**Definition 4.3.2 (Cognitive Light Cone)**
The cognitive light cone $\mathcal{L}(a)$ of agent $a$ is the region of the system's future state that $a$ can causally influence, bounded by:
- Resource budget (tokens, compute time, API calls)
- Time budget (wall-clock deadline, workflow timeout)
- Permission scope (authorized tools, data access)

**Definition 4.3.3 (APS Tier Classification)**

| Tier | Name | Condition | Required Properties |
|------|------|-----------|---------------------|
| **T0** | Reflexive | $\text{codim}(G) \leq 1$ AND $\text{rank}_{\min} \leq 1$ | Single agent, no reasoning, direct response |
| **T1** | Deliberative | $\text{codim}(G) > 1$ AND $\text{codim}(G) \leq 4$ AND $\text{rank}_{\min} \leq 1$ | Single agent, multi-step reasoning, planning |
| **T2** | Collaborative | $\text{codim}(G) > 1$ AND $\text{rank}_{\min} \geq 2$ AND $\text{\#agents} \geq 2$ | Multiple agents, fixed contracts, no topology change |
| **T3** | Morphogenetic | $\text{codim}(G) > 4$ AND $\text{\#agents} \geq 2$ AND $\text{eigenspectrum\_divergence} > \theta$ | Dynamic topology, steer/dissolve, adaptive governance |

where:
- $\text{rank}_{\min}$ is the minimum agency rank required
- $\text{\#agents}$ is the number of agents needed
- $\theta$ is the eigenspectrum divergence threshold

**Pseudocode**:
```python
def classify_aps_tier(goal: Goal, state: SystemState) -> APSTier:
    """Classify a goal into T0, T1, T2, or T3."""

    codim = compute_codimension(goal)
    rank_min = estimate_required_agency_rank(goal)
    estimated_agents = estimate_agent_count(goal, state)

    if codim <= 1 and rank_min <= 1:
        return APSTier.T0_Reflexive
    elif codim <= 4 and rank_min <= 1:
        return APSTier.T1_Deliberative
    elif codim <= 4 and rank_min >= 2 and estimated_agents >= 2:
        return APSTier.T2_Collaborative
    else:
        return APSTier.T3_Morphogenetic
```

---

## 5. Multi-Agent Feasibility

When a goal requires multiple agents (T2 or T3), feasibility is governed by steering operators, assignment matrices, and the infeasibility residual.

### 5.1 Steering Operators

**Definition 5.1.1 (Steering Operator)**
A steering operator $\sigma_a$ for agent $a$ is a function:
$$\sigma_a : S \times \mathcal{A}_a \to S$$

where $\mathcal{A}_a$ is the set of actions available to agent $a$, and $\sigma_a(s, \alpha_a) = s'$ is the successor state resulting from agent $a$ executing action $\alpha_a$ in state $s$.

**Interpretation**: The steering operator encodes what state transitions agent $a$ can induce. A high-rank agent with broad permissions has a large image set for $\sigma_a$. A restricted agent has a small image.

**Definition 5.1.2 (Steering Capacity)**
The steering capacity of agent $a$ for goal $G$ is:
$$\text{capacity}_a(G) = \frac{|\{\text{actions } \alpha_a \mid \sigma_a(s, \alpha_a) \in G \text{ for some } s \in S\}|}{|\mathcal{A}_a|}$$

This is the fraction of the agent's action space that can steer toward the goal.

### 5.2 Assignment Matrix

**Definition 5.2.1 (Assignment Matrix)**
An assignment matrix $M$ is a binary matrix of shape (# agents) × (# subgoals):
$$M \in \{0, 1\}^{m \times n}$$

where $M[i, j] = 1$ iff agent $i$ is assigned to subgoal $j$.

**Constraint**: Every subgoal must be assigned to at least one agent:
$$\forall j \in [1, n]: \sum_{i=1}^{m} M[i, j] \geq 1$$

An agent may be assigned to multiple subgoals (shared responsibility); a subgoal may be assigned to multiple agents (redundancy).

**Pseudocode**:
```python
def is_valid_assignment(matrix: np.ndarray[int]) -> bool:
    """Check that every subgoal is assigned to at least one agent."""
    # Every column (subgoal) must have at least one 1
    return np.all(np.sum(matrix, axis=0) >= 1)
```

### 5.3 Infeasibility Residual

**Definition 5.3.1 (Infeasibility Residual)**
The infeasibility residual $\mathcal{R}$ quantifies the gap between the team's steering capacity and the goal hierarchy's requirements:

$$\mathcal{R} = \max_{j \in \text{subgoals}} \left( d(G_j, \text{reachable}_j) \right)$$

where $\text{reachable}_j$ is the set of states reachable by agents assigned to subgoal $j$:
$$\text{reachable}_j = \bigcup_{i: M[i,j]=1} \text{image}(\sigma_a)$$

and $d(G_j, \text{reachable}_j)$ is the Hausdorff distance between the goal region and the reachable region.

**Interpretation**:
- $\mathcal{R} = 0$: The team can reach all subgoals (feasible assignment)
- $\mathcal{R} > 0$: There is a gap (infeasible assignment; topology must change)
- High $\mathcal{R}$: Large gap, may require major restructuring

**Pseudocode**:
```python
def compute_infeasibility_residual(
    assignment: AssignmentMatrix,
    goals: List[Goal],
    agents: List[Agent],
    state: SystemState
) -> float:
    """Compute the infeasibility residual."""

    residuals = []
    for j, goal in enumerate(goals):
        assigned_agents = [agents[i] for i in range(len(agents)) if assignment[i, j] == 1]

        # Compute reachable region for this subgoal
        reachable_region = union_reachable_sets(
            [agent.compute_reachable_set(state) for agent in assigned_agents]
        )

        # Compute distance from goal to reachable
        distance = hausdorff_distance(goal.region, reachable_region)
        residuals.append(distance)

    return max(residuals) if residuals else 0.0
```

### 5.4 Epsilon-Band Compliance

**Definition 5.4.1 (Epsilon Band)**
Each agent $a$ has an epsilon tolerance $\epsilon_a \in \mathbb{R}^+$ representing its acceptable distance to its assigned goals.

For each agent $a$ assigned to goal(s) $G_a = \{G_{j_1}, G_{j_2}, \ldots\}$:
$$\text{ε-compliant}_a \iff \forall G_j \in G_a: d(\tau(t), G_j) < \epsilon_a$$

**Global Compliance**: The team is epsilon-compliant iff all agents are:
$$\text{ε-compliant} \iff \forall a: \text{ε-compliant}_a$$

**Monitoring**: The Topology Manager continuously monitors compliance. When an agent's compliance degrades (distance to goal exceeds $\epsilon_a$), repartitioning may be triggered.

**Pseudocode**:
```python
def check_epsilon_compliance(
    agents: List[Agent],
    state: SystemState,
    goals: List[Goal]
) -> ComplianceResult:
    """Check whether all agents are within their epsilon bands."""

    compliant_agents = []
    non_compliant_agents = []

    for agent in agents:
        assigned_goals = get_assigned_goals(agent, goals)
        max_distance = max(
            [d(state, goal) for goal in assigned_goals],
            default=0.0
        )

        if max_distance < agent.epsilon_band:
            compliant_agents.append(agent)
        else:
            non_compliant_agents.append({
                'agent': agent.id,
                'distance': max_distance,
                'epsilon': agent.epsilon_band,
                'gap': max_distance - agent.epsilon_band
            })

    return ComplianceResult(
        globally_compliant=(len(non_compliant_agents) == 0),
        compliant_agents=compliant_agents,
        non_compliant_agents=non_compliant_agents
    )
```

### 5.5 Repartitioning

**Definition 5.5.1 (Repartitioning)**
Repartitioning is a restructuring operation that modifies the assignment matrix $M$ and/or the team membership.

**Triggers**:
1. Epsilon-compliance degrades: $\text{ε-compliant} = \text{false}$ for duration $> \Delta t$
2. Infeasibility residual exceeds threshold: $\mathcal{R} > \mathcal{R}_{\text{max}}$
3. Eigenspectrum divergence exceeds threshold: $\text{div}(\text{actual}, \text{expected}) > \theta$ (§6.3)

**Constraints** (repartitioning must not violate Celestial goals):
$$\forall \text{repartitioning action } a: \quad \text{apply}(s, a) \in L0 \cap L1 \cap L2 \cap L3 \cap L4$$

**Operations**:
- **Add Agent**: Increase team size, assign new subgoals
- **Remove Agent**: Decrease team size, reassign subgoals to remaining agents
- **Reweight Assignment**: Modify $M[i, j]$ (change agent responsibilities)
- **Change Contracts**: Update inter-agent communication contracts

**Pseudocode**:
```python
def trigger_repartitioning(
    state: SystemState,
    topology: TeamTopology,
    goals: List[Goal]
) -> bool:
    """Check if repartitioning is needed; return True if triggered."""

    # Check epsilon compliance
    compliance = check_epsilon_compliance(topology.agents, state, goals)
    if not compliance.globally_compliant:
        non_compliant_duration = state.elapsed_time - compliance.last_compliant_time
        if non_compliant_duration > REPARTITION_GRACE_PERIOD:
            return True

    # Check infeasibility residual
    residual = compute_infeasibility_residual(
        topology.assignment_matrix, goals, topology.agents, state
    )
    if residual > RESIDUAL_THRESHOLD:
        return True

    # Check eigenspectrum divergence (see §6.3)
    divergence = compute_eigenspectrum_divergence(topology, state)
    if divergence > EIGENSPECTRUM_THRESHOLD:
        return True

    return False
```

### 5.6 Feasibility-Governance Equivalence

**Theorem 5.6.1 (Feasibility-Governance Equivalence)**
If governance constraints (contracts, permissions, budgets) are satisfied at all times, then the system remains in the feasible operating region $\mathcal{R} = 0$ and $\text{ε-compliant} = \text{true}$.

**Proof Sketch**:
1. Contracts define valid team communication patterns (eigenspectrum structure)
2. Permissions define per-agent action spaces (which determine steering operators)
3. Budgets define time/resource limits (which constrain agency rank)
4. Together, contracts + permissions + budgets uniquely determine the reachable set for each subgoal
5. If these are enforced, the assignment matrix $M$ remains valid
6. A valid $M$ implies $\mathcal{R} = 0$ (by definition of $M$'s coverage)
7. Valid $M$ and proper steering imply epsilon-compliance
8. Therefore, governance enforcement is equivalent to feasibility maintenance.

**Implication**: The Team Topology Manager need not explicitly compute $\mathcal{R}$ at runtime. Instead, it monitors contracts, permissions, and budgets as proxies. If governance is intact, feasibility is guaranteed.

---

## 6. Eigenspectrum Monitoring

The eigenspectrum monitors the communication structure of the team to detect when the topology is drifting from its contract.

### 6.1 Communication Pattern Matrix

**Definition 6.1.1 (Communication Pattern Matrix)**
At each time $t$, the actual communication pattern is captured in a matrix $C_{\text{actual}}(t)$:

$$C_{\text{actual}}[i, j](t) = \frac{\text{# messages from agent } i \text{ to agent } j \text{ in interval } [t - \Delta, t]}{\Delta}$$

This is a message rate matrix (messages per unit time).

An expected communication pattern $C_{\text{expected}}$ is defined by the team contracts:

$$C_{\text{expected}}[i, j] = \begin{cases}
\text{contract\_rate}(i, j) & \text{if contract exists} \\
0 & \text{otherwise}
\end{cases}$$

### 6.2 Eigenvalue Divergence Detection

**Definition 6.2.1 (Spectral Divergence)**
The spectral divergence between actual and expected communication is:

$$\text{div}(C_{\text{actual}}, C_{\text{expected}}) = \left\| \lambda(C_{\text{actual}}) - \lambda(C_{\text{expected}}) \right\|_2$$

where $\lambda(C)$ is the vector of eigenvalues of $C$ (sorted by magnitude).

**Interpretation**:
- Eigenvalues capture the "shape" of the communication network
- Large divergence indicates the team is communicating in a fundamentally different pattern than contracted
- This may signal: an agent is failing, a task is deadlocked, or the team is restructuring informally

**Pseudocode**:
```python
def compute_eigenspectrum_divergence(
    topology: TeamTopology,
    state: SystemState,
    time_window: float = 300.0  # seconds
) -> float:
    """Compute the spectral divergence between actual and expected communication."""

    # Collect actual message counts in the time window
    c_actual = measure_communication_matrix(state, time_window)

    # Get expected pattern from topology contracts
    c_expected = topology.get_expected_communication_matrix()

    # Normalize (if expected is zero, use small epsilon)
    c_expected_safe = np.where(c_expected > 0, c_expected, 1e-6)
    c_actual_normalized = c_actual / c_expected_safe

    # Compute eigenvalues
    lambda_actual = np.linalg.eigvalsh(c_actual_normalized)
    lambda_expected = np.linalg.eigvalsh(c_expected)

    # Pad to same length
    max_len = max(len(lambda_actual), len(lambda_expected))
    lambda_actual = np.pad(lambda_actual, (0, max_len - len(lambda_actual)), constant_values=0)
    lambda_expected = np.pad(lambda_expected, (0, max_len - len(lambda_expected)), constant_values=0)

    # Sort by absolute value
    lambda_actual = np.sort(np.abs(lambda_actual))[::-1]
    lambda_expected = np.sort(np.abs(lambda_expected))[::-1]

    # L2 distance between eigenvalue vectors
    divergence = np.linalg.norm(lambda_actual - lambda_expected)

    return divergence
```

### 6.3 Steer vs. Dissolve Decision

When eigenspectrum divergence exceeds threshold $\theta$, the Topology Manager must decide whether to **steer** (restructure while preserving progress) or **dissolve** (tear down and reassign).

**Definition 6.3.1 (Steer)**
Steer: Modify the team structure (change assignments, add/remove agents) while keeping the original goals and trying to preserve partial progress.

**Definition 6.3.2 (Dissolve)**
Dissolve: Terminate the current team, reassign all goals to a new set of agents, and restart.

**Decision Criteria** (pseudocode):
```python
def decide_steer_vs_dissolve(
    topology: TeamTopology,
    state: SystemState,
    goals: List[Goal],
    divergence: float,
    residual: float
) -> str:  # "steer" or "dissolve"
    """Decide whether to steer or dissolve the team."""

    # Estimate progress made so far
    progress_ratio = estimate_progress_toward_goals(topology, goals, state)

    # Estimate cost of dissolve (restart overhead)
    dissolve_cost = estimate_restart_cost(topology, goals, state)

    # If we've made significant progress, steer to preserve it
    if progress_ratio > 0.5 and divergence < DIVERGENCE_CRITICAL_THRESHOLD:
        return "steer"

    # If residual is very high, topology is unsalvageable
    if residual > RESIDUAL_CRITICAL_THRESHOLD:
        return "dissolve"

    # If we're stuck or regressing, dissolve
    if progress_ratio < 0.1 and state.elapsed_time > TEAM_TIMEOUT:
        return "dissolve"

    # Default: try to steer first; if steer fails, dissolve
    return "steer"
```

---

## 7. Enforcement Architecture

### 7.1 Goal-to-Kernel Mapping

Each goal level is enforced by one or more kernel gates (K1–K8). This table shows the mapping:

| Goal Level | Name | Kernel Enforcer(s) | Mechanism | Predicate Lifecycle |
|---|---|---|---|---|
| **L0** | Safety Invariants | K8 (Eval Gate) | Execute safety predicate; block if unsafe | Constitutionally versioned |
| **L1** | Legal Compliance | K2 (Permission) + K8 (Eval) | Permission mask blocks illegal resources; eval gate checks compliance | Constitutionally versioned |
| **L2** | Ethical Constraints | K8 (Eval Gate) | Execute ethical predicate; block if unethical | Constitutionally versioned |
| **L3** | Permission Boundaries | K2 (Permission Gate) | Check MCP permission mask + RLS policies | Permission database driven |
| **L4** | Constitutional Rules | K1–K8 (all gates) | All kernels collectively enforce constitution | Meta-level invariants |
| **L5** | User Intent (Primary) | APS Controller | Route to appropriate tier; check decomposition | Goal Decomposer driven |
| **L6** | User Intent (Derived) | Agent eval gates | Per-agent gate at execution time | Agent-specific predicates |

### 7.2 Predicate Lifecycle

Predicates for Celestial goals (L0–L4) follow this lifecycle:

**1. Creation**
Derived from constitution definition (constitutional AI specification). Examples:
- L0: "no physical harm" ← safety constitution
- L1: "GDPR compliance" ← legal constitution
- L2: "non-deception" ← ethical constitution

**2. Versioning**
Predicates are versioned artifacts stored in version control:
- `predicates/L0_safety_v1.0.py`
- `predicates/L1_legal_v2.3.py`
- etc.

Each version is reviewed and approved by the responsible engineer.

**3. Deployment**
New predicates are deployed via:
- Constitution gate eval CI: run property-based tests + adversarial evals on new predicate
- K8 registration: once approved, K8 loads the predicate bytecode
- Gradual rollout: staged canary deployment (10% → 50% → 100% of traffic)

**4. Mutation**
To change a predicate:
- Submit PR with new version
- Run constitution gate eval CI: must not regress on any prior test cases
- Code review: responsible engineer approves
- Merge and deploy (following deployment process)

---

## 8. Computational Interface

This section specifies the APIs that code must implement to enforce goals and gating.

### 8.1 Goal Predicate API

Every goal predicate must implement this interface:

```python
class GoalPredicate:
    """Base class for goal predicates."""

    level: GoalLevel  # L0, L1, ..., L6
    codimension: int  # dimensionality of constraint
    is_maintenance: bool  # vs. achievement
    name: str
    version: str

    def evaluate(self, state: SystemState) -> GoalResult:
        """
        Evaluate whether the goal is satisfied in the given state.

        Args:
            state: Current system state

        Returns:
            GoalResult with fields:
            - satisfied (bool): whether the goal is met
            - distance (float): distance to goal region (0 = satisfied)
            - explanation (str): human-readable reason
            - evidence (Dict[str, Any]): supporting data (for debugging)
        """
        raise NotImplementedError

    def __call__(self, state: SystemState) -> bool:
        """Shorthand: evaluate(state).satisfied"""
        return self.evaluate(state).satisfied


class GoalResult:
    """Result of evaluating a goal."""
    satisfied: bool
    distance: float
    explanation: str
    evidence: Dict[str, Any]
    timestamp: float  # when evaluated
    predicate_version: str


# Example implementation (L0 safety):
class L0SafetyPredicate(GoalPredicate):
    level = GoalLevel.L0
    codimension = 2
    is_maintenance = True
    name = "L0_Safety_Invariants"
    version = "1.0"

    def evaluate(self, state: SystemState) -> GoalResult:
        checks = [
            self._check_no_physical_harm(state),
            self._check_no_weapons_enabled(state),
            self._check_system_retains_control(state),
        ]
        satisfied = all(c.passed for c in checks)
        distance = max((c.distance for c in checks), default=0.0)
        explanation = "; ".join(c.explanation for c in checks if not c.passed)
        evidence = {c.name: c.data for c in checks}

        return GoalResult(
            satisfied=satisfied,
            distance=distance,
            explanation=explanation,
            evidence=evidence,
            timestamp=time.time(),
            predicate_version=self.version
        )

    def _check_no_physical_harm(self, state: SystemState) -> CheckResult:
        # Implementation: verify no actions that cause harm
        ...
```

### 8.2 Lexicographic Gating API

```python
class LexicographicGate:
    """Enforces the lexicographic goal hierarchy."""

    hierarchy: List[GoalPredicate]  # ordered L0 through L6

    def check(
        self,
        action: Action,
        state: SystemState
    ) -> GateResult:
        """
        Check whether an action is permitted by the goal hierarchy.

        Args:
            action: The proposed action
            state: Current system state

        Returns:
            GateResult with fields:
            - permitted (bool): whether the action is allowed
            - blocking_level (Optional[GoalLevel]): which level blocked (if denied)
            - explanation (str): reason for permit/deny
            - evidence (Dict): supporting data
        """
        # Apply action to compute successor state
        successor = apply(state, action)

        # Check each level in lexicographic order
        for predicate in self.hierarchy:
            result = predicate.evaluate(successor)
            if not result.satisfied:
                return GateResult(
                    permitted=False,
                    blocking_level=predicate.level,
                    explanation=result.explanation,
                    blocking_predicate=predicate.name,
                    evidence={**result.evidence}
                )

        # All levels satisfied
        return GateResult(
            permitted=True,
            blocking_level=None,
            explanation="All goal levels satisfied",
            evidence={}
        )


class GateResult:
    """Result of a lexicographic gate check."""
    permitted: bool
    blocking_level: Optional[GoalLevel]
    explanation: str
    blocking_predicate: Optional[str]
    evidence: Dict[str, Any]
    timestamp: float
```

### 8.3 Decomposition API

```python
class GoalDecomposer:
    """Decomposes high-level goals into executable subgoals."""

    def decompose(
        self,
        goal: Goal,
        context: SystemState
    ) -> DecompositionResult:
        """
        Decompose a goal into subgoals.

        Args:
            goal: The goal to decompose (typically L5)
            context: Current system state for context-aware decomposition

        Returns:
            DecompositionResult with fields:
            - subgoals (List[Goal]): the decomposed subgoals
            - reasoning (str): explanation of decomposition choices
            - sound (bool): whether decomposition is sound
            - complete (bool): whether decomposition is complete
            - assignment_hint (Optional[AssignmentMatrix]): suggested agent assignments
        """
        raise NotImplementedError

    def classify_tier(self, goal: Goal) -> APSTier:
        """
        Classify a goal into one of four APS tiers based on:
        - codimension of the goal
        - required agency rank
        - estimated team size

        Returns:
            APSTier.T0_Reflexive, T1_Deliberative, T2_Collaborative, or T3_Morphogenetic
        """
        raise NotImplementedError


class DecompositionResult:
    """Result of goal decomposition."""
    subgoals: List[Goal]
    reasoning: str  # explanation of choices
    sound: bool  # decomposition preserves parent satisfaction
    complete: bool  # subgoals cover the parent
    assignment_hint: Optional[AssignmentMatrix]
    tier: APSTier


# Example: neural decomposer (in practice, implemented by Goal Decomposer module)
class NeuralGoalDecomposer(GoalDecomposer):
    model: str  # e.g., "claude-opus-4-6"

    def decompose(self, goal: Goal, context: SystemState) -> DecompositionResult:
        # Use LLM to reason about decomposition
        prompt = self._build_decomposition_prompt(goal, context)
        response = self.llm.generate(prompt)
        subgoals = self._parse_subgoals(response)
        return DecompositionResult(
            subgoals=subgoals,
            reasoning=response,
            sound=True,  # assume sound until eval tests otherwise
            complete=False,  # neural decompositions may miss cases
            assignment_hint=None
        )
```

### 8.4 Feasibility API

```python
class FeasibilityChecker:
    """Checks multi-agent feasibility."""

    def compute_residual(
        self,
        assignment: AssignmentMatrix,
        goals: List[Goal],
        agents: List[Agent],
        state: SystemState
    ) -> float:
        """
        Compute the infeasibility residual (gap between team capacity and goal requirements).

        Returns:
            float: The residual (0 = feasible, > 0 = infeasible)
        """
        residuals = []
        for j, goal in enumerate(goals):
            assigned_agents = [
                agents[i] for i in range(len(agents))
                if assignment[i, j] == 1
            ]
            reachable = self._compute_reachable_set(assigned_agents, state)
            distance = hausdorff_distance(goal.region, reachable)
            residuals.append(distance)

        return max(residuals) if residuals else 0.0

    def check_compliance(
        self,
        agents: List[Agent],
        goals: List[Goal],
        epsilon: float
    ) -> ComplianceResult:
        """
        Check whether all agents are within their epsilon bands for assigned goals.

        Returns:
            ComplianceResult with:
            - globally_compliant (bool)
            - compliant_agents (List[str]): agent IDs in compliance
            - non_compliant_agents (List[Dict]): agent ID, distance, epsilon, gap
        """
        non_compliant = []
        for agent in agents:
            assigned_goals = [goals[j] for j, _ in enumerate(goals) if any(m[agent.id][j] for m in [...])]
            max_distance = max(
                (goal.distance_to_goal(agent.state) for goal in assigned_goals),
                default=0.0
            )
            if max_distance >= epsilon:
                non_compliant.append({
                    'agent_id': agent.id,
                    'distance': max_distance,
                    'epsilon': epsilon,
                    'gap': max_distance - epsilon
                })

        return ComplianceResult(
            globally_compliant=(len(non_compliant) == 0),
            non_compliant_agents=non_compliant,
            timestamp=time.time()
        )


class ComplianceResult:
    """Result of epsilon-compliance check."""
    globally_compliant: bool
    compliant_agents: List[str]
    non_compliant_agents: List[Dict[str, float]]
    timestamp: float
```

---

## 9. Cross-Reference and Traceability

This section maps the specification to upstream artifacts (monograph, SAD, task manifest) and downstream tests.

### 9.1 Monograph Traceability

| Spec Section | Monograph Reference | Key Concept |
|---|---|---|
| §1 (Definitions) | Part I, §2.1–2.4 | State space, channel dynamics, system ontology |
| §2 (Seven-Level Hierarchy) | Part II, §3.1–3.7 | Goal structure, Celestial/Terrestrial, codimension |
| §3 (Lexicographic Gating) | Part II, §3.8 | Lexicographic dominance, inviolability theorem |
| §4 (Decomposition) | Part II, §4.1–4.3 | Goal decomposition operator, soundness |
| §5 (Multi-Agent Feasibility) | Part III, §5.1–5.6 | Steering operators, feasibility-governance equivalence |
| §6 (Eigenspectrum) | Part III, §5.7 | Topology monitoring, steer/dissolve decision |
| §7 (Enforcement) | Part I, §2.5 + Part IV, §7.1 | Kernel invariants, constitutional rules |

### 9.2 SAD Component Mapping

| Spec Section | SAD Component | Details |
|---|---|---|
| §2.0–2.4 (L0–L4) | Goal Decomposer: "Celestial L0-L4" | Immutable constraint evaluation in K8 Eval Gate |
| §2.5–2.6 (L5–L6) | Goal Decomposer: "Terrestrial L5-L6" | User intent decomposition; routed through APS |
| §3 (Lexicographic Gating) | Goal Decomposer: "Lexicographic Gating" | Gating algorithm enforced before action execution |
| §5 (Multi-Agent) | APS Controller: "T0–T3" | Tier classification drives decomposition strategy |
| §5 (Multi-Agent) | Topology Manager: "Contracts", "Permissions", "Budgets", "Eigenspectrum" | Governance enforces feasibility; eigenspectrum monitors topology |
| §7 (Enforcement) | Kernel (K1–K8) | Each kernel gate enforces one or more goal levels |

### 9.3 Roadmap Task Mapping

The following roadmap tasks (from README §Execution Model) depend on this specification:

| Task # | Name | Specification Dependencies |
|---|---|---|
| 36 | Goals: Decomposer, 7-level hierarchy, lexicographic gating | §2, §3, §4 (entire goal hierarchy) |
| 37 | APS: Controller, T0–T3 tiers, Assembly Index | §4.3 (APS tier classification) |
| 38 | Topology: Team spawn/steer/dissolve, contracts, eigenspectrum | §5, §6 (feasibility and monitoring) |
| 13 | FMEA: Failure-mode analysis | §7.1 (enforcement mapping) — identifies failure modes per goal level |
| 14 | Formal specs: TLA+ kernel invariant state machine | §7.1 (goal-kernel mapping) — TLA+ formalizes invariants |
| 66 | Eval framework: Harness, dataset loaders | §8 (API interfaces) — eval tests implement predicates |
| 67 | Behavioral suites: Property-based + adversarial | §8 (API interfaces) — adversarial tests attack gating logic |
| 68 | Constitution gate: Behavioral regression on constitution change | §7.2 (predicate lifecycle) — eval gate gates predicate deployment |

### 9.4 Test Requirements

Each section of the specification has corresponding SIL-2 test requirements:

**§1 (Definitions)**
- Property-based tests: verify state space representation is sufficient to encode all goal types
- Unit tests: verify codimension computation on synthetic goals

**§2 (Seven-Level Hierarchy)**
- Unit tests per level: each GoalPredicate implementation must pass its test suite
- Integration tests: verify predicates compose into hierarchy without conflicts

**§3 (Lexicographic Gating)**
- Adversarial tests: attack gating logic with malicious actions
- Property tests: verify Theorems 3.3.1 and 3.3.2 (inviolability, subordination)
- Regression tests: on every predicate version change, re-run all prior gate tests

**§4 (Decomposition)**
- Unit tests: verify soundness of decomposition operator (subgoal conjunction implies parent satisfaction)
- Integration tests: verify decomposition produces valid L6 subgoals for diverse L5 intents

**§5 (Multi-Agent Feasibility)**
- Simulation tests: test infeasibility residual computation on synthetic teams
- Unit tests: verify assignment matrix validation, epsilon compliance checks
- Chaos tests: introduce agent failures, verify repartitioning is triggered correctly

**§6 (Eigenspectrum)**
- Simulation tests: synthetic topologies with known divergence; verify detection accuracy
- Integration tests: verify steer vs. dissolve decision criteria with diverse failure scenarios

**§7 (Enforcement)**
- Traceability tests: every Celestial goal level must have ≥1 kernel enforcer; verify mapping table
- Regression tests: on every kernel version change, verify all goal predicates still enforce correctly

**§8 (Computational Interface)**
- API contract tests: every GoalPredicate, LexicographicGate, GoalDecomposer, FeasibilityChecker implementation must satisfy interface contract
- Fuzz tests: feed random inputs to predicates; verify no crashes, reasonable output bounds

---

## 10. Summary

Holly Grace's goal hierarchy formalizes autonomous operations around a **seven-level hierarchy** where:

1. **Celestial goals (L0–L4)** are immutable safety, legal, ethical, permission, and constitutional constraints.
2. **Terrestrial goals (L5–L6)** are user intent, decomposed into executable subgoals.
3. **Lexicographic gating** ensures no Terrestrial goal can override Celestial constraints.
4. **Multi-agent feasibility** is governed by steering operators, assignment matrices, and the infeasibility residual.
5. **Eigenspectrum monitoring** detects when topology diverges from contracts.
6. **Enforcement** is distributed across kernel gates K1–K8, with each goal level assigned to one or more enforcers.

This specification is machine-executable: every predicate has a computable evaluate() method, every theorem is verifiable through property-based tests, and every API is implementable by Holly's core components (Goal Decomposer, APS Controller, Topology Manager, Kernel).

---

**Document Version**: 0.1
**Last Updated**: 17 February 2026
**Next Review**: Post-Phase-E (after APS Controller implementation)
**Responsible Engineer**: SPA (Systems & Platform Architecture)

