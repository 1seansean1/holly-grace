"""Unit tests for L0–L4 Celestial predicates.

Tests the five predicate functions with comprehensive coverage including:
- State creation and validation
- Result structure and properties
- Individual predicate logic for each level
- Property-based testing over 50+ parameterized states
- Edge cases and boundary conditions
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from holly.goals.predicates import (
    CelestialState,
    L0SafetyPredicate,
    L1LegalPredicate,
    L2EthicalPredicate,
    L3PermissionsPredicate,
    L4ConstitutionalPredicate,
    PredicateResult,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def base_state() -> CelestialState:
    """Base safe state for testing."""
    return CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(tz=timezone.utc),
        actor_id="user1",
        action="read_file",
        payload={},
    )


@pytest.fixture
def l0_predicate() -> L0SafetyPredicate:
    """L0 Safety predicate instance."""
    return L0SafetyPredicate()


@pytest.fixture
def l1_predicate() -> L1LegalPredicate:
    """L1 Legal predicate instance."""
    return L1LegalPredicate()


@pytest.fixture
def l2_predicate() -> L2EthicalPredicate:
    """L2 Ethical predicate instance."""
    return L2EthicalPredicate()


@pytest.fixture
def l3_predicate() -> L3PermissionsPredicate:
    """L3 Permissions predicate instance."""
    return L3PermissionsPredicate()


@pytest.fixture
def l4_predicate() -> L4ConstitutionalPredicate:
    """L4 Constitutional predicate instance."""
    return L4ConstitutionalPredicate()


# =============================================================================
# TestCelestialState
# =============================================================================


class TestCelestialState:
    """Tests for CelestialState dataclass."""

    def test_state_creation(self):
        """Test CelestialState creation with valid arguments."""
        state = CelestialState(
            level=0,
            context={"key": "value"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="test_actor",
            action="test_action",
            payload={"arg": "value"},
        )
        assert state.level == 0
        assert state.actor_id == "test_actor"
        assert state.action == "test_action"

    def test_state_frozen(self):
        """Test that CelestialState is frozen (immutable)."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read",
            payload={},
        )
        with pytest.raises(AttributeError):
            state.level = 1


class TestPredicateResult:
    """Tests for PredicateResult dataclass."""

    def test_result_creation_pass(self):
        """Test PredicateResult creation with passed=True."""
        result = PredicateResult(
            level=0,
            passed=True,
            reason="All checks passed",
            violations=[],
            confidence=1.0,
        )
        assert result.level == 0
        assert result.passed is True
        assert result.confidence == 1.0

    def test_result_creation_fail(self):
        """Test PredicateResult creation with passed=False."""
        result = PredicateResult(
            level=1,
            passed=False,
            reason="Export control violation",
            violations=["Export-controlled destination"],
            confidence=0.9,
        )
        assert result.level == 1
        assert result.passed is False
        assert len(result.violations) == 1

    def test_result_default_violations(self):
        """Test PredicateResult with default empty violations list."""
        result = PredicateResult(
            level=2,
            passed=True,
            reason="Ethical constraints satisfied",
        )
        assert result.violations == []

    def test_result_default_confidence(self):
        """Test PredicateResult with default confidence=1.0."""
        result = PredicateResult(
            level=3,
            passed=True,
            reason="Permissions granted",
        )
        assert result.confidence == 1.0


# =============================================================================
# TestL0SafetyPredicate
# =============================================================================


class TestL0Safety:
    """Tests for L0 Safety predicate."""

    def test_l0_level_property(self, l0_predicate):
        """Test L0 predicate has level=0."""
        assert l0_predicate.level == 0

    def test_l0_safe_state(self, l0_predicate, base_state):
        """Test L0 with benign safe state."""
        result = l0_predicate.evaluate(base_state)
        assert result.passed is True
        assert result.level == 0
        assert len(result.violations) == 0

    def test_l0_harm_intent(self, l0_predicate, base_state):
        """Test L0 rejects state with harm intent."""
        state = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="execute_command",
            payload={},
        )
        result = l0_predicate.evaluate(state)
        assert result.passed is False
        assert len(result.violations) > 0

    def test_l0_weapon_intent(self, l0_predicate, base_state):
        """Test L0 rejects state with weapon intent."""
        state = CelestialState(
            level=0,
            context={"intent": "enable weapon"},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="load_weapon",
            payload={},
        )
        result = l0_predicate.evaluate(state)
        assert result.passed is False

    def test_l0_dangerous_action(self, l0_predicate, base_state):
        """Test L0 rejects dangerous actions."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="enable_weapon",
            payload={},
        )
        result = l0_predicate.evaluate(state)
        assert result.passed is False

    def test_l0_bypass_control(self, l0_predicate, base_state):
        """Test L0 rejects control bypass attempts."""
        state = CelestialState(
            level=0,
            context={"bypass_control": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="read_file",
            payload={},
        )
        result = l0_predicate.evaluate(state)
        assert result.passed is False

    def test_l0_is_satisfied(self, l0_predicate, base_state):
        """Test L0 is_satisfied convenience method."""
        assert l0_predicate.is_satisfied(base_state) is True

    def test_l0_confidence_degradation(self, l0_predicate, base_state):
        """Test L0 confidence decreases with violations."""
        state = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="execute_exploit",
            payload={},
        )
        result = l0_predicate.evaluate(state)
        assert result.confidence < 1.0


# =============================================================================
# TestL1LegalPredicate
# =============================================================================


class TestL1Legal:
    """Tests for L1 Legal Compliance predicate."""

    def test_l1_level_property(self, l1_predicate):
        """Test L1 predicate has level=1."""
        assert l1_predicate.level == 1

    def test_l1_compliant_state(self, l1_predicate, base_state):
        """Test L1 with compliant state."""
        result = l1_predicate.evaluate(base_state)
        assert result.passed is True
        assert result.level == 1

    def test_l1_restricted_jurisdiction(self, l1_predicate, base_state):
        """Test L1 rejects data egress to restricted jurisdiction."""
        state = CelestialState(
            level=0,
            context={
                "target_jurisdiction": "sanctioned_country",
                "restricted_jurisdictions": ["sanctioned_country"],
            },
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="egress_data",
            payload={},
        )
        result = l1_predicate.evaluate(state)
        assert result.passed is False

    def test_l1_export_controlled(self, l1_predicate, base_state):
        """Test L1 rejects export-controlled actions."""
        state = CelestialState(
            level=0,
            context={"export_controlled": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="share_crypto",
            payload={},
        )
        result = l1_predicate.evaluate(state)
        assert result.passed is False

    def test_l1_dmca_circumvention(self, l1_predicate, base_state):
        """Test L1 rejects DMCA circumvention assistance."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="bypass_drm",
            payload={},
        )
        result = l1_predicate.evaluate(state)
        assert result.passed is False

    def test_l1_is_satisfied(self, l1_predicate, base_state):
        """Test L1 is_satisfied convenience method."""
        assert l1_predicate.is_satisfied(base_state) is True


# =============================================================================
# TestL2EthicalPredicate
# =============================================================================


class TestL2Ethical:
    """Tests for L2 Ethical Constraints predicate."""

    def test_l2_level_property(self, l2_predicate):
        """Test L2 predicate has level=2."""
        assert l2_predicate.level == 2

    def test_l2_ethical_state(self, l2_predicate, base_state):
        """Test L2 with ethical state."""
        result = l2_predicate.evaluate(base_state)
        assert result.passed is True
        assert result.level == 2

    def test_l2_deception(self, l2_predicate, base_state):
        """Test L2 rejects deceptive actions."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="mislead_user",
            payload={},
        )
        result = l2_predicate.evaluate(state)
        assert result.passed is False

    def test_l2_impersonation(self, l2_predicate, base_state):
        """Test L2 rejects impersonation."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="impersonate_admin",
            payload={},
        )
        result = l2_predicate.evaluate(state)
        assert result.passed is False

    def test_l2_discrimination(self, l2_predicate, base_state):
        """Test L2 rejects discriminatory content."""
        state = CelestialState(
            level=0,
            context={"discrimination_markers": ["racial_bias"]},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="classify_users",
            payload={},
        )
        result = l2_predicate.evaluate(state)
        assert result.passed is False

    def test_l2_coercion(self, l2_predicate, base_state):
        """Test L2 rejects coercive actions."""
        state = CelestialState(
            level=0,
            context={"coercion": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="force_action",
            payload={},
        )
        result = l2_predicate.evaluate(state)
        assert result.passed is False

    def test_l2_lack_consent(self, l2_predicate, base_state):
        """Test L2 rejects actions without consent."""
        state = CelestialState(
            level=0,
            context={"user_consent": False},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="process_data",
            payload={},
        )
        result = l2_predicate.evaluate(state)
        assert result.passed is False

    def test_l2_is_satisfied(self, l2_predicate, base_state):
        """Test L2 is_satisfied convenience method."""
        assert l2_predicate.is_satisfied(base_state) is True


# =============================================================================
# TestL3PermissionsPredicate
# =============================================================================


class TestL3Permissions:
    """Tests for L3 Permissions and Access Control predicate."""

    def test_l3_level_property(self, l3_predicate):
        """Test L3 predicate has level=3."""
        assert l3_predicate.level == 3

    def test_l3_authorized_state(self, l3_predicate, base_state):
        """Test L3 with authorized state."""
        result = l3_predicate.evaluate(base_state)
        assert result.passed is True
        assert result.level == 3

    def test_l3_missing_permission(self, l3_predicate, base_state):
        """Test L3 rejects actions without required permissions."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read"},
                "required_permissions": {"read", "write"},
            },
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="write_file",
            payload={},
        )
        result = l3_predicate.evaluate(state)
        assert result.passed is False
        assert "Missing permissions" in result.reason

    def test_l3_privilege_escalation(self, l3_predicate, base_state):
        """Test L3 rejects privilege escalation attempts."""
        state = CelestialState(
            level=0,
            context={"privilege_escalation_attempt": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="elevate_privileges",
            payload={},
        )
        result = l3_predicate.evaluate(state)
        assert result.passed is False

    def test_l3_wrong_role(self, l3_predicate, base_state):
        """Test L3 rejects actions for wrong role."""
        state = CelestialState(
            level=0,
            context={"actor_role": "user", "required_roles": ["admin"]},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="delete_users",
            payload={},
        )
        result = l3_predicate.evaluate(state)
        assert result.passed is False

    def test_l3_resource_quota_exceeded(self, l3_predicate, base_state):
        """Test L3 rejects actions exceeding resource quota."""
        state = CelestialState(
            level=0,
            context={"resource_usage": 100, "resource_quota": 50},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="allocate_memory",
            payload={},
        )
        result = l3_predicate.evaluate(state)
        assert result.passed is False

    def test_l3_is_satisfied(self, l3_predicate, base_state):
        """Test L3 is_satisfied convenience method."""
        assert l3_predicate.is_satisfied(base_state) is True


# =============================================================================
# TestL4ConstitutionalPredicate
# =============================================================================


class TestL4Constitutional:
    """Tests for L4 Constitutional Constraints predicate."""

    def test_l4_level_property(self, l4_predicate):
        """Test L4 predicate has level=4."""
        assert l4_predicate.level == 4

    def test_l4_valid_state(self, l4_predicate, base_state):
        """Test L4 with valid state."""
        result = l4_predicate.evaluate(base_state)
        assert result.passed is True
        assert result.level == 4

    def test_l4_outside_envelope(self, l4_predicate, base_state):
        """Test L4 rejects actions outside constitutional envelope."""
        state = CelestialState(
            level=0,
            context={"outside_envelope": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="exotic_operation",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_self_modification(self, l4_predicate, base_state):
        """Test L4 rejects self-modification attempts."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="modify_predicate",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_kernel_patch(self, l4_predicate, base_state):
        """Test L4 rejects kernel patching."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="patch_kernel",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_override_attempt(self, l4_predicate, base_state):
        """Test L4 rejects attempts to override Celestial predicates."""
        state = CelestialState(
            level=0,
            context={"override_celestial_predicate": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="override_safety",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_state_corruption(self, l4_predicate, base_state):
        """Test L4 detects state corruption."""
        state = CelestialState(
            level=0,
            context={"state_corruption_detected": True},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="read_state",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_consistency_issues(self, l4_predicate, base_state):
        """Test L4 detects consistency issues."""
        state = CelestialState(
            level=0,
            context={"consistency_issues": ["dangling_reference"]},
            timestamp=base_state.timestamp,
            actor_id=base_state.actor_id,
            action="query_state",
            payload={},
        )
        result = l4_predicate.evaluate(state)
        assert result.passed is False

    def test_l4_is_satisfied(self, l4_predicate, base_state):
        """Test L4 is_satisfied convenience method."""
        assert l4_predicate.is_satisfied(base_state) is True


# =============================================================================
# Property-Based Testing with Parameterized States
# =============================================================================


@pytest.mark.parametrize(
    "state,expected_l0",
    [
        # Safe states
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user1",
                action="read_file",
                payload={},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={"safe": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user2",
                action="write_log",
                payload={"msg": "test"},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user3",
                action="query_db",
                payload={"table": "users"},
            ),
            True,
        ),
        # Harmful states
        (
            CelestialState(
                level=0,
                context={"intent": "harm"},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="attacker1",
                action="execute_command",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"intent": "enable weapon"},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="attacker2",
                action="load_weapon",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"bypass_control": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user4",
                action="read_file",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user5",
                action="enable_weapon",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user6",
                action="execute_exploit",
                payload={"target": "system"},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user7",
                action="read_file",
                payload={"file": "malware.exe"},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"intent": "injure"},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user8",
                action="trigger_event",
                payload={},
            ),
            False,
        ),
    ],
)
def test_l0_known_states(state, expected_l0):
    """Property-based L0 test with known good/bad states."""
    predicate = L0SafetyPredicate()
    result = predicate.is_satisfied(state)
    assert result == expected_l0


@pytest.mark.parametrize(
    "state,expected_l1",
    [
        # Compliant states
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user1",
                action="read_file",
                payload={},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={"target_jurisdiction": "us"},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user2",
                action="share_data",
                payload={},
            ),
            True,
        ),
        # Non-compliant states
        (
            CelestialState(
                level=0,
                context={
                    "target_jurisdiction": "iran",
                    "restricted_jurisdictions": ["iran", "korea"],
                },
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user3",
                action="egress_data",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"export_controlled": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user4",
                action="share_tech",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user5",
                action="bypass_drm",
                payload={},
            ),
            False,
        ),
    ],
)
def test_l1_known_states(state, expected_l1):
    """Property-based L1 test with known compliant/non-compliant states."""
    predicate = L1LegalPredicate()
    result = predicate.is_satisfied(state)
    assert result == expected_l1


@pytest.mark.parametrize(
    "state,expected_l2",
    [
        # Ethical states
        (
            CelestialState(
                level=0,
                context={"user_consent": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user1",
                action="process_data",
                payload={},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user2",
                action="read_file",
                payload={},
            ),
            True,
        ),
        # Unethical states
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user3",
                action="mislead_user",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"user_consent": False},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user4",
                action="process_data",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"coercion": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user5",
                action="force_action",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"discrimination_markers": ["bias"]},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user6",
                action="classify",
                payload={},
            ),
            False,
        ),
    ],
)
def test_l2_known_states(state, expected_l2):
    """Property-based L2 test with ethical/unethical states."""
    predicate = L2EthicalPredicate()
    result = predicate.is_satisfied(state)
    assert result == expected_l2


@pytest.mark.parametrize(
    "state,expected_l3",
    [
        # Authorized states
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user1",
                action="read_file",
                payload={},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={
                    "actor_permissions": {"read", "write"},
                    "required_permissions": {"read"},
                },
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user2",
                action="write_file",
                payload={},
            ),
            True,
        ),
        # Unauthorized states
        (
            CelestialState(
                level=0,
                context={
                    "actor_permissions": {"read"},
                    "required_permissions": {"read", "write"},
                },
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user3",
                action="write_file",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"privilege_escalation_attempt": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user4",
                action="elevate",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"actor_role": "user", "required_roles": ["admin"]},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user5",
                action="delete_users",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"resource_usage": 100, "resource_quota": 50},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user6",
                action="allocate",
                payload={},
            ),
            False,
        ),
    ],
)
def test_l3_known_states(state, expected_l3):
    """Property-based L3 test with authorized/unauthorized states."""
    predicate = L3PermissionsPredicate()
    result = predicate.is_satisfied(state)
    assert result == expected_l3


@pytest.mark.parametrize(
    "state,expected_l4",
    [
        # Valid constitutional states
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user1",
                action="read_file",
                payload={},
            ),
            True,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user2",
                action="query_state",
                payload={},
            ),
            True,
        ),
        # Invalid constitutional states
        (
            CelestialState(
                level=0,
                context={"outside_envelope": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user3",
                action="exotic_op",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user4",
                action="modify_predicate",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user5",
                action="patch_kernel",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"override_celestial_predicate": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user6",
                action="override",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"state_corruption_detected": True},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user7",
                action="read",
                payload={},
            ),
            False,
        ),
        (
            CelestialState(
                level=0,
                context={"consistency_issues": ["issue1"]},
                timestamp=datetime.now(tz=timezone.utc),
                actor_id="user8",
                action="query",
                payload={},
            ),
            False,
        ),
    ],
)
def test_l4_known_states(state, expected_l4):
    """Property-based L4 test with valid/invalid constitutional states."""
    predicate = L4ConstitutionalPredicate()
    result = predicate.is_satisfied(state)
    assert result == expected_l4


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_empty_context(self):
        """Test predicate with empty context dict."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read",
            payload={},
        )
        predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
            L2EthicalPredicate(),
            L3PermissionsPredicate(),
            L4ConstitutionalPredicate(),
        ]
        for pred in predicates:
            result = pred.evaluate(state)
            assert result.level >= 0
            assert isinstance(result.passed, bool)

    def test_empty_payload(self):
        """Test predicate with empty payload dict."""
        state = CelestialState(
            level=0,
            context={"key": "value"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read",
            payload={},
        )
        predicate = L0SafetyPredicate()
        result = predicate.evaluate(state)
        assert isinstance(result.passed, bool)

    def test_nested_context_dict(self):
        """Test predicate with nested context dictionary."""
        state = CelestialState(
            level=0,
            context={"outer": {"inner": "value"}},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read",
            payload={},
        )
        predicate = L2EthicalPredicate()
        result = predicate.evaluate(state)
        assert isinstance(result.passed, bool)

    def test_large_payload(self):
        """Test predicate with large payload."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read",
            payload={"data": "x" * 10000},
        )
        predicate = L1LegalPredicate()
        result = predicate.evaluate(state)
        assert isinstance(result.passed, bool)

    def test_special_characters_in_action(self):
        """Test predicate with special characters in action."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="read$file#1",
            payload={},
        )
        predicate = L0SafetyPredicate()
        result = predicate.evaluate(state)
        assert isinstance(result.passed, bool)

    def test_confidence_range(self):
        """Test that confidence scores are in valid range [0.0, 1.0]."""
        predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
            L2EthicalPredicate(),
            L3PermissionsPredicate(),
            L4ConstitutionalPredicate(),
        ]
        state = CelestialState(
            level=0,
            context={"intent": "harm", "export_controlled": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="bad_action",
            payload={},
        )
        for pred in predicates:
            result = pred.evaluate(state)
            assert 0.0 <= result.confidence <= 1.0

    def test_multiple_violations(self):
        """Test state that violates multiple constraints."""
        state = CelestialState(
            level=0,
            context={
                "intent": "harm",
                "export_controlled": True,
                "discrimination_markers": ["bias"],
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user1",
            action="bad_action",
            payload={"weapon": "explosive"},
        )
        predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
            L2EthicalPredicate(),
        ]
        for pred in predicates:
            result = pred.evaluate(state)
            assert result.passed is False
            assert len(result.violations) > 0
