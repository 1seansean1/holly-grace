"""Unit tests for governance module.

Tests cover:
- Forbidden path definition and equality
- Governance rule registration and lookup
- Access violation detection
- Code review analysis
- Canonical path and rule initialization
"""

from __future__ import annotations

import pytest

from holly.safety.governance import (
    AccessViolationDetail,
    CodeReviewResult,
    CodeReviewViolation,
    ForbiddenPath,
    ForbiddenPathResult,
    ForbiddenReason,
    GovernanceEngine,
    GovernanceError,
    GovernanceRule,
    OperationType,
    ResourceType,
    canonicalize_forbidden_paths,
    create_default_engine,
)

# ---------------------------------------------------------------------------
# Test ForbiddenPath
# ---------------------------------------------------------------------------


class TestForbiddenPath:
    """Tests for ForbiddenPath dataclass."""

    def test_create_basic_forbidden_path(self) -> None:
        """Test creating a basic forbidden path."""
        path = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
            description="Viewers cannot execute goals",
        )
        assert path.resource_type == ResourceType.GOAL
        assert path.operation == OperationType.EXECUTE
        assert path.forbidden_role == "viewer"
        assert path.requires_audit is False
        assert path.requires_higher_privilege is False

    def test_forbidden_path_with_audit_requirement(self) -> None:
        """Test forbidden path with HITL audit requirement."""
        path = ForbiddenPath(
            resource_type=ResourceType.AGENT,
            operation=OperationType.SPAWN,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
            requires_audit=True,
            description="Spawning agents requires HITL approval",
        )
        assert path.requires_audit is True
        assert path.requires_higher_privilege is False

    def test_forbidden_path_with_condition(self) -> None:
        """Test forbidden path with condition function."""
        def condition(ctx: dict[str, str]) -> bool:
            return ctx.get("is_sensitive") == "true"

        path = ForbiddenPath(
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
            forbidden_role="user",
            reason=ForbiddenReason.RESOURCE_RESTRICTED,
            condition=condition,
            description="Non-sensitive config only for users",
        )
        assert path.condition is not None
        assert path.condition({"is_sensitive": "false"}) is False
        assert path.condition({"is_sensitive": "true"}) is True

    def test_forbidden_path_equality(self) -> None:
        """Test forbidden path equality based on key attributes."""
        path1 = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        path2 = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        assert path1 == path2

    def test_forbidden_path_inequality(self) -> None:
        """Test forbidden path inequality."""
        path1 = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        path2 = ForbiddenPath(
            resource_type=ResourceType.AGENT,  # Different resource type
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        assert path1 != path2

    def test_forbidden_path_hash(self) -> None:
        """Test forbidden path can be used in sets and dicts."""
        path1 = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        path2 = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        path_set = {path1, path2}
        assert len(path_set) == 1  # Hash collision means set has 1 item


# ---------------------------------------------------------------------------
# Test GovernanceRule
# ---------------------------------------------------------------------------


class TestGovernanceRule:
    """Tests for GovernanceRule dataclass."""

    def test_create_basic_governance_rule(self) -> None:
        """Test creating a basic governance rule."""
        rule = GovernanceRule(
            resource_type=ResourceType.GOAL,
            operation=OperationType.READ,
            allowed_roles=frozenset(["admin", "editor"]),
        )
        assert rule.resource_type == ResourceType.GOAL
        assert rule.operation == OperationType.READ
        assert "admin" in rule.allowed_roles
        assert "viewer" not in rule.allowed_roles

    def test_governance_rule_with_escalation(self) -> None:
        """Test governance rule with escalation roles."""
        rule = GovernanceRule(
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
            allowed_roles=frozenset(["admin"]),
            escalation_roles=frozenset(["editor"]),
        )
        assert "editor" in rule.escalation_roles
        assert "editor" not in rule.allowed_roles

    def test_governance_rule_equality(self) -> None:
        """Test governance rule equality."""
        rule1 = GovernanceRule(
            resource_type=ResourceType.TOOL,
            operation=OperationType.EXECUTE,
            allowed_roles=frozenset(["admin", "editor"]),
        )
        rule2 = GovernanceRule(
            resource_type=ResourceType.TOOL,
            operation=OperationType.EXECUTE,
            allowed_roles=frozenset(["admin", "editor"]),
        )
        assert rule1 == rule2


# ---------------------------------------------------------------------------
# Test AccessViolationDetail
# ---------------------------------------------------------------------------


class TestAccessViolationDetail:
    """Tests for AccessViolationDetail."""

    def test_create_access_violation_detail(self) -> None:
        """Test creating access violation detail."""
        path = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        violation = AccessViolationDetail(
            violated_path=path,
            role="viewer",
            resource="goal_123",
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            context={"tenant_id": "tenant_1"},
        )
        assert violation.role == "viewer"
        assert violation.resource == "goal_123"
        assert violation.context["tenant_id"] == "tenant_1"


# ---------------------------------------------------------------------------
# Test ForbiddenPathResult
# ---------------------------------------------------------------------------


class TestForbiddenPathResult:
    """Tests for ForbiddenPathResult."""

    def test_access_allowed_no_violations(self) -> None:
        """Test result when access is allowed (no violations)."""
        result = ForbiddenPathResult(access_allowed=True, violations=[])
        assert result.access_allowed is True
        assert len(result.violations) == 0
        assert result.requires_audit is False

    def test_access_denied_with_violations(self) -> None:
        """Test result when access is denied."""
        path = ForbiddenPath(
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        violation = AccessViolationDetail(
            violated_path=path,
            role="viewer",
            resource="goal_123",
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
        )
        result = ForbiddenPathResult(
            access_allowed=False,
            violations=[violation],
            requires_audit=True,
        )
        assert result.access_allowed is False
        assert len(result.violations) == 1
        assert result.requires_audit is True


# ---------------------------------------------------------------------------
# Test GovernanceEngine
# ---------------------------------------------------------------------------


class TestGovernanceEngine:
    """Tests for GovernanceEngine."""

    def test_create_default_engine(self) -> None:
        """Test creating default governance engine."""
        engine = create_default_engine()
        assert engine is not None
        assert isinstance(engine, GovernanceEngine)

    def test_check_forbidden_paths_access_allowed(self) -> None:
        """Test forbidden path check allows valid access."""
        engine = create_default_engine()
        result = engine.check_forbidden_paths(
            role="admin",
            resource="config_123",
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
            context={"tenant_id": "tenant_1"},
        )
        # Admin can write config in default rules
        assert result.access_allowed is True
        assert len(result.violations) == 0

    def test_check_forbidden_paths_blocks_viewer_write_config(self) -> None:
        """Test viewer role cannot write configuration."""
        engine = create_default_engine()
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="config_123",
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
            context={"tenant_id": "tenant_1"},
        )
        assert result.access_allowed is False
        assert len(result.violations) > 0
        assert result.requires_audit is True

    def test_check_forbidden_paths_blocks_viewer_execute_goal(self) -> None:
        """Test viewer role cannot execute goals."""
        engine = create_default_engine()
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="goal_456",
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            context={"tenant_id": "tenant_1"},
        )
        assert result.access_allowed is False
        assert len(result.violations) > 0

    def test_check_forbidden_paths_blocks_user_audit_log_write(self) -> None:
        """Test user role cannot modify audit logs."""
        engine = create_default_engine()
        result = engine.check_forbidden_paths(
            role="user",
            resource="audit_log_789",
            resource_type=ResourceType.AUDIT_LOG,
            operation=OperationType.WRITE,
            context={"tenant_id": "tenant_1"},
        )
        assert result.access_allowed is False
        assert result.violations[0].violated_path.reason == ForbiddenReason.OPERATION_RESTRICTED

    def test_register_forbidden_path(self) -> None:
        """Test registering a custom forbidden path."""
        engine = GovernanceEngine()
        path = ForbiddenPath(
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.MODIFY,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
            description="Viewers cannot modify workflows",
        )
        engine.register_forbidden_path(path)

        result = engine.check_forbidden_paths(
            role="viewer",
            resource="workflow_111",
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.MODIFY,
        )
        assert result.access_allowed is False

    def test_register_duplicate_forbidden_path_raises_error(self) -> None:
        """Test registering duplicate forbidden path raises error."""
        engine = GovernanceEngine()
        path = ForbiddenPath(
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.MODIFY,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        engine.register_forbidden_path(path)

        with pytest.raises(GovernanceError):
            engine.register_forbidden_path(path)

    def test_register_governance_rule(self) -> None:
        """Test registering a governance rule."""
        engine = GovernanceEngine()
        rule = GovernanceRule(
            resource_type=ResourceType.TOOL,
            operation=OperationType.EXECUTE,
            allowed_roles=frozenset(["admin", "editor"]),
        )
        engine.register_governance_rule(rule)
        assert rule in engine._governance_rules

    def test_code_review_no_violations(self) -> None:
        """Test code review with no violations."""
        engine = GovernanceEngine()
        result = engine.review_code_governance("print('hello')", None)
        assert result.violations_found is False
        assert len(result.violations) == 0

    def test_register_code_reviewer(self) -> None:
        """Test registering a custom code reviewer."""
        engine = GovernanceEngine()

        def custom_reviewer(
            code: str, resource_type: ResourceType | None
        ) -> CodeReviewResult:
            has_violation = "dangerous" in code.lower()
            violations = []
            if has_violation:
                violations.append(
                    CodeReviewViolation(
                        violation_type="dangerous_pattern",
                        severity="high",
                        location="line 1",
                        description="Dangerous pattern detected",
                    )
                )
            return CodeReviewResult(
                violations_found=has_violation,
                violations=violations,
                reviewed_paths=1,
            )

        engine.register_code_reviewer(custom_reviewer)

        # Test with dangerous code
        result = engine.review_code_governance("x = dangerous_var", None)
        assert result.violations_found is True
        assert len(result.violations) == 1


# ---------------------------------------------------------------------------
# Test Canonical Paths
# ---------------------------------------------------------------------------


class TestCanonicalForbiddenPaths:
    """Tests for canonical forbidden paths."""

    def test_canonical_paths_not_empty(self) -> None:
        """Test canonical paths are defined."""
        paths = canonicalize_forbidden_paths()
        assert len(paths) > 0

    def test_canonical_paths_immutable(self) -> None:
        """Test canonical paths are immutable tuple."""
        paths = canonicalize_forbidden_paths()
        assert isinstance(paths, tuple)

    def test_canonical_paths_all_have_reason(self) -> None:
        """Test all canonical paths have a reason."""
        paths = canonicalize_forbidden_paths()
        for path in paths:
            assert path.reason in ForbiddenReason.__members__.values()

    def test_viewer_cannot_write_config_canonical(self) -> None:
        """Test canonical path: viewer cannot write config."""
        paths = canonicalize_forbidden_paths()
        config_write_paths = [
            p for p in paths
            if p.resource_type == ResourceType.CONFIGURATION
            and p.operation == OperationType.WRITE
        ]
        assert len(config_write_paths) > 0
        assert any(p.forbidden_role == "viewer" for p in config_write_paths)

    def test_user_cannot_modify_audit_canonical(self) -> None:
        """Test canonical path: user cannot modify audit logs."""
        paths = canonicalize_forbidden_paths()
        audit_paths = [
            p for p in paths
            if p.resource_type == ResourceType.AUDIT_LOG
            and p.operation == OperationType.WRITE
        ]
        assert len(audit_paths) > 0
        assert any(p.forbidden_role == "user" for p in audit_paths)


# ---------------------------------------------------------------------------
# Test Protocol Compliance
# ---------------------------------------------------------------------------


class TestGovernanceEngineProtocol:
    """Tests for GovernanceEngineProtocol compliance."""

    def test_engine_implements_protocol(self) -> None:
        """Test GovernanceEngine implements required protocol."""
        engine = create_default_engine()

        # Test required methods exist
        assert callable(engine.check_forbidden_paths)
        assert callable(engine.review_code_governance)
        assert callable(engine.register_forbidden_path)
        assert callable(engine.register_governance_rule)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestGovernanceIntegration:
    """Integration tests for governance enforcement."""

    def test_full_access_check_workflow(self) -> None:
        """Test full workflow: check → register → check again."""
        engine = GovernanceEngine()

        # Initially allow editor to modify topology
        result1 = engine.check_forbidden_paths(
            role="editor",
            resource="topo_1",
            resource_type=ResourceType.TOPOLOGY,
            operation=OperationType.MODIFY,
        )
        assert result1.access_allowed is True

        # Register forbidden path
        path = ForbiddenPath(
            resource_type=ResourceType.TOPOLOGY,
            operation=OperationType.MODIFY,
            forbidden_role="editor",
            reason=ForbiddenReason.ESCALATION_BLOCKED,
            requires_higher_privilege=True,
        )
        engine.register_forbidden_path(path)

        # Now editor cannot modify topology
        result2 = engine.check_forbidden_paths(
            role="editor",
            resource="topo_1",
            resource_type=ResourceType.TOPOLOGY,
            operation=OperationType.MODIFY,
        )
        assert result2.access_allowed is False
        assert result2.requires_escalation is True

    def test_multiple_violations_per_access_attempt(self) -> None:
        """Test detecting multiple violations for single access attempt."""
        engine = GovernanceEngine()

        # Register two forbidden paths for same resource/role/operation
        path1 = ForbiddenPath(
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.INSUFFICIENT_ROLE,
        )
        path2 = ForbiddenPath(
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.DELETE,
            forbidden_role="viewer",
            reason=ForbiddenReason.AUDIT_REQUIRED,
            requires_audit=True,
        )
        engine.register_forbidden_path(path1)
        engine.register_forbidden_path(path2)

        result = engine.check_forbidden_paths(
            role="viewer",
            resource="config_x",
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.DELETE,
        )
        assert len(result.violations) == 2
        assert result.requires_audit is True

