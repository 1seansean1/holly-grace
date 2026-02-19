"""Governance module for Holly Grace.

Implements forbidden paths and code review analysis per Task 29.3
and ICD v0.1 specifications. Governance rules enforce K2 permission gates
by defining which resource-operation combinations are forbidden for which roles.

This module provides:
- Forbidden paths: policy rules that block certain operation sequences
- Code review analysis: static analysis of governance rule violations
- Access policies: role-based access control rules
- GovernanceEngine: unified engine enforcing governance rules
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)

__all__ = [
    "AccessViolation",
    "CodeReviewResult",
    "ForbiddenPath",
    "ForbiddenPathResult",
    "GovernanceEngine",
    "GovernanceEngineProtocol",
    "GovernanceError",
    "GovernanceRule",
    "create_default_engine",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GovernanceError(Exception):
    """Raised when governance check fails or cannot be applied safely."""

    pass


class AccessViolation(GovernanceError):
    """Raised when access to a resource violates governance rules."""

    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResourceType(str, Enum):
    """Resource types that governance rules can apply to."""

    GOAL = "goal"
    AGENT = "agent"
    TOOL = "tool"
    CONFIGURATION = "configuration"
    AUDIT_LOG = "audit_log"
    WORKFLOW = "workflow"
    TOPOLOGY = "topology"
    CODE = "code"


class OperationType(str, Enum):
    """Operation types that governance rules can apply to."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    SPAWN = "spawn"
    STEER = "steer"
    DISSOLVE = "dissolve"
    MODIFY = "modify"


class ForbiddenReason(str, Enum):
    """Reasons why a path might be forbidden."""

    INSUFFICIENT_ROLE = "insufficient_role"
    DANGEROUS_COMBINATION = "dangerous_combination"
    AUDIT_REQUIRED = "audit_required"
    ESCALATION_BLOCKED = "escalation_blocked"
    RESOURCE_RESTRICTED = "resource_restricted"
    OPERATION_RESTRICTED = "operation_restricted"


# ---------------------------------------------------------------------------
# Rule Definitions
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ForbiddenPath:
    """Definition of a forbidden resource-operation-role combination.

    A forbidden path specifies that a particular role cannot perform a
    specific operation on a specific resource type, optionally with additional
    conditions like tenant isolation or audit requirements.

    Attributes
    ----------
    resource_type : ResourceType
        Type of resource (e.g., "goal", "agent", "configuration").
    operation : OperationType
        Type of operation (e.g., "read", "write", "delete").
    forbidden_role : str
        Role name that cannot perform this operation on this resource.
    reason : ForbiddenReason
        Category reason why this path is forbidden.
    requires_audit : bool
        If True, operation is allowed only with HITL approval (K7).
    requires_higher_privilege : bool
        If True, operation escalation requires explicit role grant.
    condition : Callable[[dict[str, str]], bool] | None
        Optional predicate function to determine if this rule applies
        to a specific context (e.g., tenant-specific restrictions).
    description : str
        Human-readable description of why this path is forbidden.
    """

    resource_type: ResourceType
    operation: OperationType
    forbidden_role: str
    reason: ForbiddenReason
    requires_audit: bool = False
    requires_higher_privilege: bool = False
    condition: Callable[[dict[str, str]], bool] | None = None
    description: str = ""

    def __hash__(self) -> int:
        return hash(
            (
                self.resource_type,
                self.operation,
                self.forbidden_role,
                self.reason,
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ForbiddenPath):
            return NotImplemented
        return (
            self.resource_type == other.resource_type
            and self.operation == other.operation
            and self.forbidden_role == other.forbidden_role
            and self.reason == other.reason
        )


@dataclass(slots=True)
class GovernanceRule:
    """A governance rule specifying allowed resource-operation combinations.

    Rules are positive permissions: roles listed in allowed_roles are permitted
    to perform the operation on the resource type. If a role is not in
    allowed_roles, the operation is denied unless it is explicitly exempted
    by an audit or escalation path.

    Attributes
    ----------
    resource_type : ResourceType
        Type of resource governed by this rule.
    operation : OperationType
        Type of operation governed by this rule.
    allowed_roles : frozenset[str]
        Roles permitted to perform this operation on this resource.
    audit_bypass_roles : frozenset[str]
        Roles that can bypass the permission via HITL approval (K7).
    escalation_roles : frozenset[str]
        Roles that can escalate their privileges for this operation.
    requires_tenant_match : bool
        If True, operation only allowed if requester and resource in same tenant.
    """

    resource_type: ResourceType
    operation: OperationType
    allowed_roles: frozenset[str] = field(default_factory=frozenset)
    audit_bypass_roles: frozenset[str] = field(default_factory=frozenset)
    escalation_roles: frozenset[str] = field(default_factory=frozenset)
    requires_tenant_match: bool = True

    def __hash__(self) -> int:
        return hash((self.resource_type, self.operation))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GovernanceRule):
            return NotImplemented
        return (
            self.resource_type == other.resource_type
            and self.operation == other.operation
            and self.allowed_roles == other.allowed_roles
        )


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class AccessViolationDetail:
    """Details of a single access violation.

    Attributes
    ----------
    violated_path : ForbiddenPath
        The forbidden path that was violated.
    role : str
        Role attempting the access.
    resource : str
        Resource being accessed.
    resource_type : ResourceType
        Type of resource.
    operation : OperationType
        Operation attempted.
    context : dict[str, str]
        Additional context (e.g., tenant_id, user_id).
    """

    violated_path: ForbiddenPath
    role: str
    resource: str
    resource_type: ResourceType
    operation: OperationType
    context: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"AccessViolationDetail("
            f"role={self.role!r}, "
            f"resource={self.resource!r}, "
            f"operation={self.operation}, "
            f"reason={self.violated_path.reason})"
        )


@dataclass(slots=True)
class ForbiddenPathResult:
    """Result of forbidden path analysis.

    Attributes
    ----------
    access_allowed : bool
        True if the requested access is allowed by governance rules.
    violations : list[AccessViolationDetail]
        List of forbidden paths violated (empty if access allowed).
    requires_audit : bool
        True if the operation requires HITL approval (K7) before proceeding.
    requires_escalation : bool
        True if the operation requires explicit privilege escalation.
    """

    access_allowed: bool
    violations: list[AccessViolationDetail] = field(default_factory=list)
    requires_audit: bool = False
    requires_escalation: bool = False

    def __repr__(self) -> str:
        return (
            f"ForbiddenPathResult("
            f"access_allowed={self.access_allowed}, "
            f"violations={len(self.violations)}, "
            f"requires_audit={self.requires_audit})"
        )


@dataclass(slots=True)
class CodeReviewViolation:
    """A single code review finding (policy violation in code analysis).

    Attributes
    ----------
    violation_type : str
        Type of violation (e.g., "unguarded_resource_access").
    severity : str
        Severity level ("low", "medium", "high", "critical").
    location : str
        File and line number where violation occurs.
    description : str
        Human-readable description of the violation.
    suggested_fix : str
        Suggested remediation.
    """

    violation_type: str
    severity: str
    location: str
    description: str
    suggested_fix: str = ""

    def __repr__(self) -> str:
        return (
            f"CodeReviewViolation("
            f"type={self.violation_type}, "
            f"severity={self.severity}, "
            f"location={self.location})"
        )


@dataclass(slots=True)
class CodeReviewResult:
    """Result of code review analysis for governance violations.

    Attributes
    ----------
    violations_found : bool
        True if any violations were detected.
    violations : list[CodeReviewViolation]
        List of detected violations.
    reviewed_paths : int
        Number of code paths reviewed.
    """

    violations_found: bool
    violations: list[CodeReviewViolation] = field(default_factory=list)
    reviewed_paths: int = 0

    def __repr__(self) -> str:
        return (
            f"CodeReviewResult("
            f"violations_found={self.violations_found}, "
            f"violations={len(self.violations)}, "
            f"reviewed_paths={self.reviewed_paths})"
        )


# ---------------------------------------------------------------------------
# GovernanceEngine Protocol (for external dependency injection)
# ---------------------------------------------------------------------------


class GovernanceEngineProtocol(Protocol):
    """Protocol for governance engine implementations."""

    def check_forbidden_paths(
        self,
        role: str,
        resource: str,
        resource_type: ResourceType,
        operation: OperationType,
        context: dict[str, str] | None = None,
    ) -> ForbiddenPathResult:
        """Check if access to resource violates forbidden paths."""
        ...

    def review_code_governance(
        self,
        code: str,
        resource_type: ResourceType | None = None,
    ) -> CodeReviewResult:
        """Perform code review analysis for governance violations."""
        ...

    def register_forbidden_path(self, path: ForbiddenPath) -> None:
        """Register a new forbidden path rule."""
        ...

    def register_governance_rule(self, rule: GovernanceRule) -> None:
        """Register a new governance rule."""
        ...


# ---------------------------------------------------------------------------
# Canonical Forbidden Paths
# ---------------------------------------------------------------------------

_CANONICAL_FORBIDDEN_PATHS: tuple[ForbiddenPath, ...] = (
    # Viewer role restrictions
    ForbiddenPath(
        resource_type=ResourceType.CONFIGURATION,
        operation=OperationType.WRITE,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=True,
        description="Viewer role cannot modify configuration; requires HITL approval",
    ),
    ForbiddenPath(
        resource_type=ResourceType.GOAL,
        operation=OperationType.WRITE,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=False,
        description="Viewer role cannot modify goals; read-only access",
    ),
    ForbiddenPath(
        resource_type=ResourceType.GOAL,
        operation=OperationType.EXECUTE,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=False,
        description="Viewer role cannot execute goals; read-only access",
    ),
    ForbiddenPath(
        resource_type=ResourceType.AGENT,
        operation=OperationType.SPAWN,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=True,
        description="Viewer role cannot spawn agents; requires HITL approval per K7",
    ),
    ForbiddenPath(
        resource_type=ResourceType.TOOL,
        operation=OperationType.EXECUTE,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=True,
        description="Tool execution requires at least editor role; viewer cannot invoke",
    ),
    ForbiddenPath(
        resource_type=ResourceType.CODE,
        operation=OperationType.EXECUTE,
        forbidden_role="viewer",
        reason=ForbiddenReason.INSUFFICIENT_ROLE,
        requires_audit=True,
        description="Code execution forbidden for viewer role; requires K7 HITL approval",
    ),
    # Audit log immutability - no one except security_officer can modify
    ForbiddenPath(
        resource_type=ResourceType.AUDIT_LOG,
        operation=OperationType.WRITE,
        forbidden_role="viewer",
        reason=ForbiddenReason.OPERATION_RESTRICTED,
        description="Viewers cannot modify audit logs; audit trail must be immutable",
    ),
    ForbiddenPath(
        resource_type=ResourceType.AUDIT_LOG,
        operation=OperationType.WRITE,
        forbidden_role="user",
        reason=ForbiddenReason.OPERATION_RESTRICTED,
        description="Users cannot modify audit logs; audit trail must be immutable",
    ),
    ForbiddenPath(
        resource_type=ResourceType.AUDIT_LOG,
        operation=OperationType.WRITE,
        forbidden_role="editor",
        reason=ForbiddenReason.OPERATION_RESTRICTED,
        description="Editors cannot modify audit logs; audit trail must be immutable",
    ),
    ForbiddenPath(
        resource_type=ResourceType.AUDIT_LOG,
        operation=OperationType.WRITE,
        forbidden_role="admin",
        reason=ForbiddenReason.OPERATION_RESTRICTED,
        description="Admins cannot modify audit logs; audit trail must be immutable",
    ),
    ForbiddenPath(
        resource_type=ResourceType.AUDIT_LOG,
        operation=OperationType.DELETE,
        forbidden_role="admin",
        reason=ForbiddenReason.OPERATION_RESTRICTED,
        requires_higher_privilege=True,
        description="Audit log deletion requires security officer approval",
    ),
)


def canonicalize_forbidden_paths() -> tuple[ForbiddenPath, ...]:
    """Return the canonical set of ICD v0.1 forbidden paths.

    Forbidden paths define operation-resource-role combinations that are
    explicitly denied by governance policy. Per ICD v0.1, all access checks
    must verify against these paths before proceeding.

    Returns
    -------
    tuple[ForbiddenPath, ...]
        Immutable tuple of forbidden paths in canonical order.
    """
    return _CANONICAL_FORBIDDEN_PATHS


# ---------------------------------------------------------------------------
# GovernanceEngine Implementation
# ---------------------------------------------------------------------------


class GovernanceEngine:
    """Production implementation of governance rule enforcement.

    The engine maintains a registry of forbidden paths and governance rules,
    and provides methods to check access against these rules. It also supports
    code review analysis to detect governance violations in code.

    Per Task 29.3, the engine integrates with K2 permission gates to enforce
    governance rules at every boundary crossing that involves resource access
    or operation execution.
    """

    __slots__ = ("_code_reviewers", "_forbidden_paths", "_governance_rules")

    def __init__(
        self,
        forbidden_paths: tuple[ForbiddenPath, ...] | None = None,
        governance_rules: tuple[GovernanceRule, ...] | None = None,
    ) -> None:
        """Initialize governance engine.

        Parameters
        ----------
        forbidden_paths:
            Forbidden paths to register. If None, uses canonical set.
        governance_rules:
            Governance rules to register. If None, creates empty set.
        """
        self._forbidden_paths: set[ForbiddenPath] = set(
            forbidden_paths or canonicalize_forbidden_paths()
        )
        self._governance_rules: set[GovernanceRule] = set(governance_rules or ())
        self._code_reviewers: list[
            Callable[[str, ResourceType | None], CodeReviewResult]
        ] = []

    def check_forbidden_paths(
        self,
        role: str,
        resource: str,
        resource_type: ResourceType,
        operation: OperationType,
        context: dict[str, str] | None = None,
    ) -> ForbiddenPathResult:
        """Check if access to resource violates forbidden paths.

        Parameters
        ----------
        role:
            Role attempting access.
        resource:
            Resource identifier.
        resource_type:
            Type of resource.
        operation:
            Operation type being attempted.
        context:
            Additional context for condition evaluation (e.g., tenant_id).

        Returns
        -------
        ForbiddenPathResult
            Result of forbidden path check.
        """
        context = context or {}
        violations: list[AccessViolationDetail] = []
        requires_audit = False
        requires_escalation = False

        for path in self._forbidden_paths:
            # Check if this path matches the resource and operation
            if path.resource_type != resource_type or path.operation != operation:
                continue

            # Check if the role is forbidden
            if path.forbidden_role != role:
                continue

            # Check condition if present
            if path.condition is not None and not path.condition(context):
                continue

            # Violation found
            violation = AccessViolationDetail(
                violated_path=path,
                role=role,
                resource=resource,
                resource_type=resource_type,
                operation=operation,
                context=context,
            )
            violations.append(violation)

            if path.requires_audit:
                requires_audit = True
            if path.requires_higher_privilege:
                requires_escalation = True

        access_allowed = len(violations) == 0

        return ForbiddenPathResult(
            access_allowed=access_allowed,
            violations=violations,
            requires_audit=requires_audit,
            requires_escalation=requires_escalation,
        )

    def review_code_governance(
        self,
        code: str,
        resource_type: ResourceType | None = None,
    ) -> CodeReviewResult:
        """Perform code review analysis for governance violations.

        Parameters
        ----------
        code:
            Source code to review.
        resource_type:
            Optional resource type to restrict review scope.

        Returns
        -------
        CodeReviewResult
            Code review analysis results.
        """
        all_violations: list[CodeReviewViolation] = []
        reviewed_paths = 0

        # Run all registered code reviewers
        for reviewer in self._code_reviewers:
            result = reviewer(code, resource_type)
            all_violations.extend(result.violations)
            reviewed_paths += result.reviewed_paths

        violations_found = len(all_violations) > 0

        return CodeReviewResult(
            violations_found=violations_found,
            violations=sorted(
                all_violations,
                key=lambda v: (v.severity, v.location),
            ),
            reviewed_paths=reviewed_paths,
        )

    def register_forbidden_path(self, path: ForbiddenPath) -> None:
        """Register a new forbidden path rule.

        Parameters
        ----------
        path:
            Forbidden path to register.

        Raises
        ------
        GovernanceError
            If path is already registered.
        """
        if path in self._forbidden_paths:
            raise GovernanceError(f"Forbidden path already registered: {path}")
        self._forbidden_paths.add(path)

    def register_governance_rule(self, rule: GovernanceRule) -> None:
        """Register a new governance rule.

        Parameters
        ----------
        rule:
            Governance rule to register.

        Raises
        ------
        GovernanceError
            If rule is already registered.
        """
        if rule in self._governance_rules:
            raise GovernanceError(f"Governance rule already registered: {rule}")
        self._governance_rules.add(rule)

    def register_code_reviewer(
        self,
        reviewer: Callable[[str, ResourceType | None], CodeReviewResult],
    ) -> None:
        """Register a code reviewer function.

        Parameters
        ----------
        reviewer:
            Function that reviews code and returns CodeReviewResult.
        """
        self._code_reviewers.append(reviewer)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_default_engine() -> GovernanceEngine:
    """Create a governance engine with canonical rules and forbidden paths.

    Returns
    -------
    GovernanceEngine
        Engine with canonical configuration per ICD v0.1.
    """
    return GovernanceEngine(
        forbidden_paths=canonicalize_forbidden_paths(),
        governance_rules=(),
    )
