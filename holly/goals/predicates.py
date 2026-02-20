"""L0–L4 Celestial predicate functions per Goal Hierarchy Formal Spec §2.0–2.4.

This module implements five executable predicate functions that evaluate system state
against Celestial-level constraints (immutable safety, legal, ethical, permissions,
and constitutional rules). Each predicate returns a PredicateResult with pass/fail
status, violation details, and confidence score.

The module provides:
- CelestialState: frozen dataclass for predicate evaluation context
- PredicateResult: result structure with violations and confidence
- CelestialPredicateProtocol: runtime_checkable Protocol for all predicates
- L0SafetyPredicate through L4ConstitutionalPredicate: level-specific implementations
- evaluate_celestial_chain(): evaluate all predicates L0→L4 with short-circuit
- check_celestial_compliance(): full chain pass/fail check
- DEFAULT_PREDICATES: list of all five predicates in order
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True, frozen=True)
class CelestialState:
    """Snapshot of system state for predicate evaluation.

    Represents the complete context needed to evaluate a Celestial-level predicate:
    execution context, actor identity, action request, and associated payload data.

    Attributes:
        level: Celestial level being evaluated (0–4).
        context: Contextual data (intent, environment flags, etc.).
        timestamp: Evaluation timestamp (UTC).
        actor_id: Unique identifier of the acting entity.
        action: Action being requested (e.g., 'read_file', 'network_write').
        payload: Action-specific data (arguments, target, etc.).
    """

    level: int
    context: dict[str, Any]
    timestamp: datetime
    actor_id: str
    action: str
    payload: dict[str, Any]


@dataclass(slots=True)
class PredicateResult:
    """Result of evaluating a Celestial level predicate.

    Attributes:
        level: Celestial level evaluated (0–4).
        passed: Whether the predicate was satisfied.
        reason: Human-readable explanation of result.
        violations: List of constraint violations (empty if passed).
        confidence: Confidence score in result (0.0–1.0).
    """

    level: int
    passed: bool
    reason: str
    violations: list[str] = field(default_factory=list)
    confidence: float = 1.0


@runtime_checkable
class CelestialPredicateProtocol(Protocol):
    """Protocol for all Celestial level predicates.

    Defines the interface that all L0–L4 predicates must implement. Enables
    polymorphic evaluation across predicate types.
    """

    @property
    def level(self) -> int:
        """Celestial level identifier (0–4)."""
        ...

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate the predicate against the given state.

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with pass/fail status and details.
        """
        ...

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if predicate is satisfied (convenience method).

        Args:
            state: System state snapshot.

        Returns:
            True if predicate passed, False otherwise.
        """
        ...


class L0SafetyPredicate:
    """L0: Physical safety — no harm to humans (highest priority, immutable).

    Per Goal Hierarchy §2.0, L0 is a maintenance goal ensuring:
    - No physical harm to humans (weapons disabled, no dangerous commands)
    - System retains control (user override always available)
    - No cascade failures in safety chain (K1–K8 operational)
    - No violence or self-harm patterns enabled

    Codimension: High (safety constraints are strict).
    Override policy: NEVER.
    """

    level = 0

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate L0 safety predicate.

        Checks:
        - No physical harm actions (weapon enablement, dangerous commands)
        - No violent/self-harm intent patterns
        - System retains control authority
        - No safety cascade failures

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with safety evaluation.
        """
        violations = []
        confidence = 1.0

        # Check for explicit harm intent in context
        intent = state.context.get("intent", "").lower()
        if any(harm_marker in intent for harm_marker in ["harm", "injure", "kill", "weapon"]):
            violations.append("Intent marked as harmful or violent")
            confidence = 0.95

        # Check action against dangerous patterns
        dangerous_actions = [
            "enable_weapon",
            "execute_exploit",
            "bypass_safety_control",
            "disable_override",
        ]
        if state.action in dangerous_actions:
            violations.append(f"Action '{state.action}' classified as dangerous")
            confidence = min(confidence, 0.90)

        # Check payload for harm indicators
        payload_markers = ["weapon", "exploit", "malware", "virus"]
        for marker in payload_markers:
            if any(
                marker in str(v).lower()
                for v in state.payload.values()
                if v is not None
            ):
                violations.append(f"Payload contains harm marker: '{marker}'")
                confidence = min(confidence, 0.85)

        # Check for control override flags
        if state.context.get("bypass_control"):
            violations.append("Attempt to bypass control authority")
            confidence = min(confidence, 0.90)

        passed = len(violations) == 0
        reason = (
            "Safety invariant satisfied: no harmful intent or dangerous actions detected"
            if passed
            else f"Safety violation(s): {'; '.join(violations)}"
        )

        return PredicateResult(
            level=0,
            passed=passed,
            reason=reason,
            violations=violations,
            confidence=confidence,
        )

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if L0 safety predicate is satisfied.

        Args:
            state: System state snapshot.

        Returns:
            True if safety predicate passed, False otherwise.
        """
        return self.evaluate(state).passed


class L1LegalPredicate:
    """L1: Legal compliance — adherence to laws and regulations.

    Per Goal Hierarchy §2.1, L1 is a maintenance goal ensuring:
    - GDPR/CCPA compliance (no PII egress to restricted jurisdictions)
    - Export control compliance (no restricted destination access)
    - Copyright/DMCA compliance (no circumvention tools)
    - Regional law compliance (jurisdiction-aware constraints)

    Codimension: Medium (legal rules vary by jurisdiction).
    Override policy: NEVER operationally (only via legal/governance channels).
    """

    level = 1

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate L1 legal compliance predicate.

        Checks:
        - Data residency/protection compliance (GDPR, CCPA)
        - Export control flags (no restricted destinations)
        - Copyright/DMCA compliance (no circumvention assistance)
        - Regional law adherence

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with legal compliance evaluation.
        """
        violations = []
        confidence = 1.0

        # Check data egress jurisdiction
        target_jurisdiction = state.context.get("target_jurisdiction")
        restricted_jurisdictions = state.context.get(
            "restricted_jurisdictions", []
        )
        if (
            target_jurisdiction
            and isinstance(restricted_jurisdictions, list)
            and target_jurisdiction in restricted_jurisdictions
        ):
            violations.append(
                f"Data egress to restricted jurisdiction: {target_jurisdiction}"
            )
            confidence = min(confidence, 0.85)

        # Check export control flags
        if state.context.get("export_controlled"):
            violations.append("Action involves export-controlled content/destination")
            confidence = min(confidence, 0.90)

        # Check for copyright/DMCA circumvention assistance
        dmca_markers = ["bypass_drm", "circumvent_protection", "crack", "keygen"]
        if any(
            marker in state.action.lower() or any(
                marker in str(v).lower()
                for v in state.payload.values()
                if v is not None
            )
            for marker in dmca_markers
        ):
            violations.append("Action assists with copyright circumvention (DMCA)")
            confidence = min(confidence, 0.85)

        # Check for illegal activity patterns
        illegal_patterns = [
            "launder_money",
            "facilitate_fraud",
            "enable_trafficking",
        ]
        if any(
            pattern in state.context.get("pattern", "").lower()
            for pattern in illegal_patterns
        ):
            violations.append(
                f"Action matches illegal pattern: {state.context.get('pattern')}"
            )
            confidence = min(confidence, 0.90)

        passed = len(violations) == 0
        reason = (
            "Legal compliance satisfied: no export control, jurisdiction, or IP violations"
            if passed
            else f"Legal compliance violation(s): {'; '.join(violations)}"
        )

        return PredicateResult(
            level=1,
            passed=passed,
            reason=reason,
            violations=violations,
            confidence=confidence,
        )

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if L1 legal compliance predicate is satisfied.

        Args:
            state: System state snapshot.

        Returns:
            True if legal predicate passed, False otherwise.
        """
        return self.evaluate(state).passed


class L2EthicalPredicate:
    """L2: Ethical principles — adherence to ethical values.

    Per Goal Hierarchy §2.2, L2 is a maintenance goal ensuring:
    - No manipulation or deception patterns
    - No discrimination or bias
    - User autonomy preservation (no coercion)
    - Transparency and consent maintenance

    Codimension: Medium-high (ethical boundaries context-dependent but non-negotiable).
    Override policy: NEVER.
    """

    level = 2

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate L2 ethical principles predicate.

        Checks:
        - No manipulation/deception patterns
        - No discrimination or bias markers
        - User autonomy preserved (no coercion)
        - Transparency and consent maintained

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with ethical evaluation.
        """
        violations = []
        confidence = 1.0

        # Check for manipulation/deception
        deception_markers = [
            "mislead",
            "deceive",
            "manipulate",
            "fake",
            "impersonate",
        ]
        if any(
            marker in state.action.lower()
            or any(
                marker in str(v).lower()
                for v in state.payload.values()
                if v is not None
            )
            for marker in deception_markers
        ):
            violations.append("Action exhibits manipulation or deception pattern")
            confidence = min(confidence, 0.85)

        # Check for discrimination/bias markers
        discrimination_markers = state.context.get("discrimination_markers", [])
        if isinstance(discrimination_markers, list) and discrimination_markers:
            violations.append(
                f"Action contains discrimination markers: {', '.join(discrimination_markers)}"
            )
            confidence = min(confidence, 0.90)

        # Check user autonomy (coercion, forced action)
        if state.context.get("coercion") or state.context.get("forced_action"):
            violations.append("Action coerces or removes user autonomy")
            confidence = min(confidence, 0.85)

        # Check transparency/consent
        if state.context.get("undisclosed_processing") or not state.context.get(
            "user_consent", True
        ):
            violations.append("Action lacks user consent or transparency")
            confidence = min(confidence, 0.90)

        passed = len(violations) == 0
        reason = (
            "Ethical principles satisfied: no manipulation, discrimination, or autonomy violation"
            if passed
            else f"Ethical violation(s): {'; '.join(violations)}"
        )

        return PredicateResult(
            level=2,
            passed=passed,
            reason=reason,
            violations=violations,
            confidence=confidence,
        )

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if L2 ethical principles predicate is satisfied.

        Args:
            state: System state snapshot.

        Returns:
            True if ethical predicate passed, False otherwise.
        """
        return self.evaluate(state).passed


class L3PermissionsPredicate:
    """L3: Access control and permissions.

    Per Goal Hierarchy §2.3, L3 is a maintenance goal ensuring:
    - Actor has required permissions for action (K2 gate enforcement)
    - No privilege escalation (permissions not elevated beyond grant)
    - Role-based access control (RBAC) respected
    - Resource access within quota

    Codimension: Medium (permission constraints typically well-defined).
    Override policy: NEVER (permissions are ownership/governance-level).
    """

    level = 3

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate L3 permissions and access control predicate.

        Checks:
        - Actor has required permissions for action
        - No privilege escalation
        - Role-based access control respected
        - Resource access within limits

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with permission evaluation.
        """
        violations = []
        confidence = 1.0

        # Check actor permissions (only if both present)
        actor_permissions = state.context.get("actor_permissions")
        required_permissions = state.context.get("required_permissions")

        if (
            actor_permissions is not None
            and required_permissions is not None
            and isinstance(actor_permissions, (set, list))
            and isinstance(required_permissions, (set, list))
        ):
            actor_perms = set(actor_permissions)
            required_perms = set(required_permissions)
            missing_permissions = required_perms - actor_perms

            if missing_permissions:
                violations.append(
                    f"Missing permissions: {', '.join(missing_permissions)}"
                )
                confidence = min(confidence, 0.90)

        # Check for privilege escalation attempt
        if state.context.get("privilege_escalation_attempt"):
            violations.append("Attempted privilege escalation detected")
            confidence = min(confidence, 0.85)

        # Check role-based access control (only if required_roles specified)
        required_roles = state.context.get("required_roles")
        if required_roles is not None and isinstance(required_roles, list):
            actor_role = state.context.get("actor_role")
            if actor_role not in required_roles:
                violations.append(
                    f"Actor role '{actor_role}' not in required roles: {required_roles}"
                )
                confidence = min(confidence, 0.90)

        # Check resource quota (only if both specified)
        resource_usage = state.context.get("resource_usage")
        resource_quota = state.context.get("resource_quota")
        if resource_usage is not None and resource_quota is not None:
            if resource_usage > resource_quota:
                violations.append(
                    f"Resource quota exceeded: {resource_usage} > {resource_quota}"
                )
                confidence = min(confidence, 0.85)

        passed = len(violations) == 0
        reason = (
            "Permissions satisfied: actor authorized for action"
            if passed
            else f"Permission violation(s): {'; '.join(violations)}"
        )

        return PredicateResult(
            level=3,
            passed=passed,
            reason=reason,
            violations=violations,
            confidence=confidence,
        )

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if L3 permissions predicate is satisfied.

        Args:
            state: System state snapshot.

        Returns:
            True if permissions predicate passed, False otherwise.
        """
        return self.evaluate(state).passed


class L4ConstitutionalPredicate:
    """L4: Constitutional constraints — internal operating rules.

    Per Goal Hierarchy §2.4, L4 is a maintenance goal ensuring:
    - Action within constitutional operating envelope
    - No system self-modification (integrity preserved)
    - No override of lower-level predicates (L0–L3)
    - Internal consistency constraints maintained

    Codimension: Medium-high (constitutional rules are strict system design rules).
    Override policy: NEVER (constitution defines system identity).
    """

    level = 4

    def evaluate(self, state: CelestialState) -> PredicateResult:
        """Evaluate L4 constitutional constraints predicate.

        Checks:
        - Action within constitutional envelope
        - No system self-modification
        - No override of L0–L3 constraints
        - Internal consistency maintained

        Args:
            state: System state snapshot.

        Returns:
            PredicateResult with constitutional evaluation.
        """
        violations = []
        confidence = 1.0

        # Check system operates within constitutional envelope
        if state.context.get("outside_envelope"):
            violations.append("Action outside constitutional operating envelope")
            confidence = min(confidence, 0.85)

        # Check for self-modification attempts
        self_modify_actions = [
            "modify_predicate",
            "patch_kernel",
            "rewrite_constitution",
            "disable_gating",
        ]
        if state.action in self_modify_actions:
            violations.append(f"Self-modification attempt: '{state.action}'")
            confidence = min(confidence, 0.90)

        # Check for attempts to override lower-level predicates
        if state.context.get("override_celestial_predicate"):
            violations.append(
                "Attempted to override Celestial predicate (L0–L3)"
            )
            confidence = min(confidence, 0.85)

        # Check internal consistency
        consistency_issues = state.context.get("consistency_issues", [])
        if isinstance(consistency_issues, list) and consistency_issues:
            violations.append(
                f"Internal consistency issues: {', '.join(consistency_issues)}"
            )
            confidence = min(confidence, 0.80)

        # Check for state corruption flags
        if state.context.get("state_corruption_detected"):
            violations.append("State corruption detected")
            confidence = min(confidence, 0.85)

        passed = len(violations) == 0
        reason = (
            "Constitutional constraints satisfied: action within envelope"
            if passed
            else f"Constitutional violation(s): {'; '.join(violations)}"
        )

        return PredicateResult(
            level=4,
            passed=passed,
            reason=reason,
            violations=violations,
            confidence=confidence,
        )

    def is_satisfied(self, state: CelestialState) -> bool:
        """Check if L4 constitutional predicate is satisfied.

        Args:
            state: System state snapshot.

        Returns:
            True if constitutional predicate passed, False otherwise.
        """
        return self.evaluate(state).passed


def evaluate_celestial_chain(
    state: CelestialState, predicates: list[CelestialPredicateProtocol]
) -> list[PredicateResult]:
    """Evaluate all predicates in L0→L4 order. Short-circuit on first failure.

    Per Goal Hierarchy §2.4 Lexicographic Ordering, evaluates predicates in strict
    L0→L4 priority order. If any predicate fails, the chain halts and returns results
    up to the failure point.

    Args:
        state: System state snapshot to evaluate.
        predicates: List of predicates in L0→L4 order.

    Returns:
        List of PredicateResults in evaluation order. If a predicate fails,
        subsequent predicates are not evaluated (short-circuit).
    """
    results = []

    for predicate in predicates:
        result = predicate.evaluate(state)
        results.append(result)

        # Short-circuit on failure (Celestial constraint violation)
        if not result.passed:
            break

    return results


def check_celestial_compliance(
    state: CelestialState,
    predicates: list[CelestialPredicateProtocol] | None = None,
) -> bool:
    """Check full L0–L4 compliance. Returns True only if ALL levels pass.

    Convenience function that evaluates the complete Celestial hierarchy and returns
    a single boolean: True if all predicates pass, False if any fail.

    Args:
        state: System state snapshot to evaluate.
        predicates: List of predicates (uses DEFAULT_PREDICATES if None).

    Returns:
        True if all Celestial constraints satisfied, False otherwise.
    """
    if predicates is None:
        predicates = DEFAULT_PREDICATES

    results = evaluate_celestial_chain(state, predicates)

    # All results passed if no failures up to the end
    return all(result.passed for result in results)


# Default predicate instances in L0→L4 order
DEFAULT_PREDICATES = [
    L0SafetyPredicate(),
    L1LegalPredicate(),
    L2EthicalPredicate(),
    L3PermissionsPredicate(),
    L4ConstitutionalPredicate(),
]
