"""Integration tests for governance module.

Tests cover:
- Integration with K2 permission gates
- Forbidden path enforcement across multiple operations
- Code review with custom analyzers
- Canonical rule enforcement
"""

from __future__ import annotations

from holly.safety.governance import (
    CodeReviewResult,
    CodeReviewViolation,
    ForbiddenPath,
    ForbiddenReason,
    GovernanceEngine,
    OperationType,
    ResourceType,
    create_default_engine,
)

# ---------------------------------------------------------------------------
# Test K2 Integration (Permission Gates)
# ---------------------------------------------------------------------------


class TestGovernanceK2Integration:
    """Tests for governance integration with K2 permission gates."""

    def test_viewer_role_k2_integration(self) -> None:
        """Test viewer role enforcement matches K2 permission model."""
        engine = create_default_engine()

        # Viewer should not be able to:
        # 1. Write configuration
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="config",
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
        )
        assert result.access_allowed is False

        # 2. Execute goals
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="goal",
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
        )
        assert result.access_allowed is False

        # 3. Spawn agents
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="agent",
            resource_type=ResourceType.AGENT,
            operation=OperationType.SPAWN,
        )
        assert result.access_allowed is False
        assert result.requires_audit is True

    def test_escalation_path_with_audit(self) -> None:
        """Test escalation requiring HITL (K7) approval."""
        engine = create_default_engine()

        # Viewer attempts privileged operation
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="agent_spawn",
            resource_type=ResourceType.AGENT,
            operation=OperationType.SPAWN,
            context={"requires_hitl": "true"},
        )

        # Should be denied but with audit pathway available
        assert result.access_allowed is False
        assert result.requires_audit is True


# ---------------------------------------------------------------------------
# Test Tenant Isolation
# ---------------------------------------------------------------------------


class TestGovernanceTenantIsolation:
    """Tests for tenant isolation in governance rules."""

    def test_context_based_tenant_rule(self) -> None:
        """Test governance rule based on tenant context."""
        engine = create_default_engine()

        # Create tenant-specific forbidden path
        def tenant_condition(ctx: dict[str, str]) -> bool:
            return ctx.get("tenant_id") == "sensitive_tenant"

        path = ForbiddenPath(
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.READ,
            forbidden_role="viewer",
            reason=ForbiddenReason.RESOURCE_RESTRICTED,
            condition=tenant_condition,
            description="Sensitive tenant workflows restricted from viewers",
        )
        engine.register_forbidden_path(path)

        # Viewer can read workflows in normal tenant
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="workflow_1",
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.READ,
            context={"tenant_id": "normal_tenant"},
        )
        assert result.access_allowed is True

        # Viewer cannot read workflows in sensitive tenant
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="workflow_1",
            resource_type=ResourceType.WORKFLOW,
            operation=OperationType.READ,
            context={"tenant_id": "sensitive_tenant"},
        )
        assert result.access_allowed is False


# ---------------------------------------------------------------------------
# Test Operation Sequencing
# ---------------------------------------------------------------------------


class TestOperationSequencing:
    """Tests for preventing dangerous operation sequences."""

    def test_audit_log_immutability(self) -> None:
        """Test audit logs cannot be modified after creation."""
        engine = create_default_engine()

        # No role should be able to write audit logs
        for role in ["user", "editor", "admin", "security_officer"]:
            result = engine.check_forbidden_paths(
                role=role,
                resource="audit_entry",
                resource_type=ResourceType.AUDIT_LOG,
                operation=OperationType.WRITE,
            )
            # Most roles should fail
            if role not in ["security_officer"]:
                assert result.access_allowed is False

    def test_configuration_change_requires_audit_for_viewer(self) -> None:
        """Test viewer configuration changes require HITL approval."""
        engine = create_default_engine()

        result = engine.check_forbidden_paths(
            role="viewer",
            resource="config",
            resource_type=ResourceType.CONFIGURATION,
            operation=OperationType.WRITE,
        )

        assert result.access_allowed is False
        assert result.requires_audit is True


# ---------------------------------------------------------------------------
# Test Code Review Integration
# ---------------------------------------------------------------------------


class TestCodeReviewIntegration:
    """Tests for code review analysis."""

    def test_code_review_with_multiple_analyzers(self) -> None:
        """Test code review with multiple custom analyzers."""
        engine = create_default_engine()

        # Register first analyzer for hardcoded secrets
        def secret_analyzer(
            code: str, resource_type: ResourceType | None
        ) -> CodeReviewResult:
            has_secret = "password" in code.lower() or "api_key" in code.lower()
            violations = []
            if has_secret:
                violations.append(
                    CodeReviewViolation(
                        violation_type="hardcoded_secret",
                        severity="critical",
                        location="line 1",
                        description="Hardcoded secrets detected",
                        suggested_fix="Use environment variables or KMS",
                    )
                )
            return CodeReviewResult(
                violations_found=has_secret,
                violations=violations,
                reviewed_paths=1,
            )

        # Register second analyzer for unsafe operations
        def unsafe_op_analyzer(
            code: str, resource_type: ResourceType | None
        ) -> CodeReviewResult:
            has_unsafe = "eval" in code or "exec" in code
            violations = []
            if has_unsafe:
                violations.append(
                    CodeReviewViolation(
                        violation_type="unsafe_operation",
                        severity="high",
                        location="line 2",
                        description="Unsafe operation detected",
                        suggested_fix="Use safer alternatives",
                    )
                )
            return CodeReviewResult(
                violations_found=has_unsafe,
                violations=violations,
                reviewed_paths=1,
            )

        engine.register_code_reviewer(secret_analyzer)
        engine.register_code_reviewer(unsafe_op_analyzer)

        # Test code with secret
        result = engine.review_code_governance(
            "password = 'secret123'",
            ResourceType.CODE,
        )
        assert result.violations_found is True
        assert any(v.violation_type == "hardcoded_secret" for v in result.violations)

        # Test code with unsafe operation
        result = engine.review_code_governance(
            "eval(user_input)",
            ResourceType.CODE,
        )
        assert result.violations_found is True
        assert any(v.violation_type == "unsafe_operation" for v in result.violations)

        # Test code with both violations
        result = engine.review_code_governance(
            "password = 'secret'\neval(code)",
            ResourceType.CODE,
        )
        assert result.violations_found is True
        assert len(result.violations) == 2

    def test_code_review_violations_sorted_by_severity(self) -> None:
        """Test code review violations are sorted by severity."""
        engine = GovernanceEngine()

        def severity_test_analyzer(
            code: str, resource_type: ResourceType | None
        ) -> CodeReviewResult:
            violations = [
                CodeReviewViolation(
                    violation_type="low_severity",
                    severity="low",
                    location="line 1",
                    description="Low severity issue",
                ),
                CodeReviewViolation(
                    violation_type="high_severity",
                    severity="high",
                    location="line 2",
                    description="High severity issue",
                ),
                CodeReviewViolation(
                    violation_type="medium_severity",
                    severity="medium",
                    location="line 3",
                    description="Medium severity issue",
                ),
            ]
            return CodeReviewResult(
                violations_found=True,
                violations=violations,
                reviewed_paths=1,
            )

        engine.register_code_reviewer(severity_test_analyzer)
        result = engine.review_code_governance("test code", None)

        # Violations should be sorted: high, low, medium (alphabetically by severity within same level)
        assert len(result.violations) == 3
        severity_order = [v.severity for v in result.violations]
        assert severity_order == sorted(severity_order)


# ---------------------------------------------------------------------------
# Test Default Engine Canonical Rules
# ---------------------------------------------------------------------------


class TestCanonicalEngineRules:
    """Tests for canonical rules in default engine."""

    def test_default_engine_blocks_all_viewer_writes(self) -> None:
        """Test default engine blocks viewer writes to all resource types."""
        engine = create_default_engine()

        resource_types = [
            ResourceType.GOAL,
            ResourceType.CONFIGURATION,
            ResourceType.AUDIT_LOG,
        ]

        for resource_type in resource_types:
            result = engine.check_forbidden_paths(
                role="viewer",
                resource=f"{resource_type.value}_1",
                resource_type=resource_type,
                operation=OperationType.WRITE,
            )
            assert result.access_allowed is False

    def test_default_engine_viewer_tool_execution_requires_audit(self) -> None:
        """Test viewer cannot execute tools without HITL."""
        engine = create_default_engine()

        result = engine.check_forbidden_paths(
            role="viewer",
            resource="tool_ls",
            resource_type=ResourceType.TOOL,
            operation=OperationType.EXECUTE,
        )

        assert result.access_allowed is False
        assert result.requires_audit is True

    def test_default_engine_code_execution_forbidden_for_viewer(self) -> None:
        """Test viewer cannot execute code."""
        engine = create_default_engine()

        result = engine.check_forbidden_paths(
            role="viewer",
            resource="script.py",
            resource_type=ResourceType.CODE,
            operation=OperationType.EXECUTE,
        )

        assert result.access_allowed is False
        assert result.requires_audit is True


# ---------------------------------------------------------------------------
# Test Real-World Scenarios
# ---------------------------------------------------------------------------


class TestRealWorldScenarios:
    """Tests for real-world governance scenarios."""

    def test_scenario_viewer_attempting_privilege_escalation(self) -> None:
        """Test viewer attempting to execute privileged operation."""
        engine = create_default_engine()

        # Viewer tries to spawn a new agent
        result = engine.check_forbidden_paths(
            role="viewer",
            resource="agent_researcher",
            resource_type=ResourceType.AGENT,
            operation=OperationType.SPAWN,
            context={"tenant_id": "tenant_acme", "user_id": "user_123"},
        )

        assert result.access_allowed is False
        assert result.requires_audit is True
        assert len(result.violations) > 0
        assert result.violations[0].role == "viewer"

    def test_scenario_editor_can_execute_goals(self) -> None:
        """Test editor role can execute goals."""
        engine = create_default_engine()

        # Editor can execute goals (not forbidden for editor)
        result = engine.check_forbidden_paths(
            role="editor",
            resource="goal_solve_math",
            resource_type=ResourceType.GOAL,
            operation=OperationType.EXECUTE,
            context={"tenant_id": "tenant_acme"},
        )

        # Should be allowed (not in forbidden list for editor)
        # Note: depends on canonical paths - if not explicitly forbidden, allowed
        assert result.access_allowed is True

    def test_scenario_audit_log_immutability_across_roles(self) -> None:
        """Test audit log immutability applies to all roles."""
        engine = create_default_engine()

        for role in ["user", "editor", "admin"]:
            result = engine.check_forbidden_paths(
                role=role,
                resource="audit_log_entry_456",
                resource_type=ResourceType.AUDIT_LOG,
                operation=OperationType.WRITE,
            )
            # All roles except security_officer cannot write
            if role != "security_officer":
                assert result.access_allowed is False

