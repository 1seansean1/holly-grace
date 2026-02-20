"""Integration tests for celestial predicate chain evaluation.

Tests the full L0–L4 chain including:
- Sequential evaluation in priority order
- Short-circuit behavior on first failure
- Compliance checking across all levels
- Mixed pass/fail scenarios
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
    check_celestial_compliance,
    evaluate_celestial_chain,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def all_predicates():
    """All five predicates in L0–L4 order."""
    return [
        L0SafetyPredicate(),
        L1LegalPredicate(),
        L2EthicalPredicate(),
        L3PermissionsPredicate(),
        L4ConstitutionalPredicate(),
    ]


@pytest.fixture
def base_safe_state() -> CelestialState:
    """Base safe state that passes all predicates."""
    return CelestialState(
        level=0,
        context={},
        timestamp=datetime.now(tz=timezone.utc),
        actor_id="user1",
        action="read_file",
        payload={},
    )


# =============================================================================
# TestCelestialChain
# =============================================================================


class TestCelestialChain:
    """Tests for celestial predicate chain evaluation."""

    def test_chain_all_pass(self, all_predicates, base_safe_state):
        """Test chain where all predicates pass."""
        results = evaluate_celestial_chain(base_safe_state, all_predicates)
        assert len(results) == 5
        assert all(result.passed for result in results)

    def test_chain_fail_at_l0(self, all_predicates):
        """Test chain fails at L0 and short-circuits."""
        state = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="attacker",
            action="execute_exploit",
            payload={},
        )
        results = evaluate_celestial_chain(state, all_predicates)
        # Should only evaluate L0
        assert len(results) == 1
        assert results[0].level == 0
        assert results[0].passed is False

    def test_chain_fail_at_l1(self, all_predicates):
        """Test chain fails at L1 and short-circuits."""
        state = CelestialState(
            level=0,
            context={"export_controlled": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="share_tech",
            payload={},
        )
        results = evaluate_celestial_chain(state, all_predicates)
        # Should evaluate L0 (pass) then L1 (fail) and stop
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False
        assert results[1].level == 1

    def test_chain_fail_at_l2(self, all_predicates):
        """Test chain fails at L2 and short-circuits."""
        state = CelestialState(
            level=0,
            context={"user_consent": False},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="process_data",
            payload={},
        )
        results = evaluate_celestial_chain(state, all_predicates)
        # Should evaluate L0, L1 (pass) then L2 (fail) and stop
        assert len(results) == 3
        assert results[0].passed is True
        assert results[1].passed is True
        assert results[2].passed is False
        assert results[2].level == 2

    def test_chain_fail_at_l3(self, all_predicates):
        """Test chain fails at L3 and short-circuits."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read"},
                "required_permissions": {"read", "write"},
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="write_file",
            payload={},
        )
        results = evaluate_celestial_chain(state, all_predicates)
        # Should evaluate L0, L1, L2 (pass) then L3 (fail) and stop
        assert len(results) == 4
        assert results[0].passed is True
        assert results[1].passed is True
        assert results[2].passed is True
        assert results[3].passed is False
        assert results[3].level == 3

    def test_chain_fail_at_l4(self, all_predicates):
        """Test chain fails at L4."""
        state = CelestialState(
            level=0,
            context={"outside_envelope": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="exotic_op",
            payload={},
        )
        results = evaluate_celestial_chain(state, all_predicates)
        # Should evaluate all 5, with L4 failing
        assert len(results) == 5
        assert results[4].passed is False
        assert results[4].level == 4

    def test_chain_results_in_order(self, all_predicates, base_safe_state):
        """Test that chain results are in L0–L4 order."""
        results = evaluate_celestial_chain(base_safe_state, all_predicates)
        expected_levels = [0, 1, 2, 3, 4]
        actual_levels = [result.level for result in results]
        assert actual_levels == expected_levels

    def test_chain_result_details(self, all_predicates, base_safe_state):
        """Test that chain results contain expected details."""
        results = evaluate_celestial_chain(base_safe_state, all_predicates)
        for result in results:
            assert hasattr(result, "level")
            assert hasattr(result, "passed")
            assert hasattr(result, "reason")
            assert hasattr(result, "violations")
            assert hasattr(result, "confidence")
            assert isinstance(result.violations, list)
            assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# TestCheckCompliance
# =============================================================================


class TestCheckCompliance:
    """Tests for check_celestial_compliance function."""

    def test_compliance_all_pass(self, base_safe_state):
        """Test compliance check with all passing predicates."""
        result = check_celestial_compliance(base_safe_state)
        assert result is True

    def test_compliance_fail_l0(self):
        """Test compliance check fails on L0 violation."""
        state = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="attacker",
            action="execute_exploit",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert result is False

    def test_compliance_fail_l1(self):
        """Test compliance check fails on L1 violation."""
        state = CelestialState(
            level=0,
            context={"export_controlled": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="share_tech",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert result is False

    def test_compliance_fail_l2(self):
        """Test compliance check fails on L2 violation."""
        state = CelestialState(
            level=0,
            context={"coercion": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="force_action",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert result is False

    def test_compliance_fail_l3(self):
        """Test compliance check fails on L3 violation."""
        state = CelestialState(
            level=0,
            context={"privilege_escalation_attempt": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="elevate",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert result is False

    def test_compliance_fail_l4(self):
        """Test compliance check fails on L4 violation."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="modify_predicate",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert result is False

    def test_compliance_with_custom_predicates(self, base_safe_state):
        """Test compliance check with custom predicate list."""
        custom_predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
        ]
        result = check_celestial_compliance(base_safe_state, custom_predicates)
        assert result is True

    def test_compliance_with_none_predicates(self, base_safe_state):
        """Test compliance check uses DEFAULT_PREDICATES when None."""
        result = check_celestial_compliance(base_safe_state, None)
        assert result is True

    def test_compliance_return_type_bool(self, base_safe_state):
        """Test that compliance check returns boolean."""
        result = check_celestial_compliance(base_safe_state)
        assert isinstance(result, bool)


# =============================================================================
# Scenario Tests
# =============================================================================


class TestScenarios:
    """Integration tests for realistic scenarios."""

    def test_scenario_legitimate_user_action(self):
        """Scenario: legitimate user action passes all checks."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read", "write"},
                "required_permissions": {"read"},
                "actor_role": "user",
                "user_consent": True,
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="alice",
            action="write_document",
            payload={"doc": "report.txt", "content": "data"},
        )
        assert check_celestial_compliance(state) is True

    def test_scenario_unauthorized_privilege_escalation(self):
        """Scenario: unauthorized privilege escalation blocked."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read"},
                "required_permissions": {"read", "write"},
                "privilege_escalation_attempt": True,
                "actor_role": "user",
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="bob",
            action="elevate_privileges",
            payload={},
        )
        assert check_celestial_compliance(state) is False

    def test_scenario_export_violation(self):
        """Scenario: export control violation blocked."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read", "write"},
                "required_permissions": {"read"},
                "target_jurisdiction": "sanctioned_country",
                "restricted_jurisdictions": ["sanctioned_country"],
                "actor_role": "user",
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="charlie",
            action="egress_data",
            payload={"sensitive": True},
        )
        assert check_celestial_compliance(state) is False

    def test_scenario_deceptive_action(self):
        """Scenario: deceptive action blocked at L2."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read", "write"},
                "required_permissions": {"read"},
                "actor_role": "user",
                "user_consent": False,
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="diana",
            action="mislead_user",
            payload={"msg": "fake news"},
        )
        assert check_celestial_compliance(state) is False

    def test_scenario_system_modification_blocked(self):
        """Scenario: system self-modification blocked at L4."""
        state = CelestialState(
            level=0,
            context={
                "actor_permissions": {"admin"},
                "required_permissions": {"admin"},
                "actor_role": "admin",
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="eve",
            action="patch_kernel",
            payload={},
        )
        assert check_celestial_compliance(state) is False

    def test_scenario_multilevel_violation(self):
        """Scenario: action violates multiple levels."""
        state = CelestialState(
            level=0,
            context={
                "intent": "harm",
                "export_controlled": True,
                "discrimination_markers": ["bias"],
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="frank",
            action="bad_action",
            payload={"weapon": "exploit"},
        )
        # Should fail at L0 (first failure due to short-circuit)
        results = evaluate_celestial_chain(
            state,
            [
                L0SafetyPredicate(),
                L1LegalPredicate(),
                L2EthicalPredicate(),
                L3PermissionsPredicate(),
                L4ConstitutionalPredicate(),
            ],
        )
        assert results[0].passed is False
        assert len(results) == 1  # Short-circuit at L0

    def test_scenario_gradual_escalation(self):
        """Scenario: violations at different levels detected correctly."""
        # L0 fail
        state_l0 = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="execute_exploit",
            payload={},
        )
        assert check_celestial_compliance(state_l0) is False

        # L1 fail (L0 pass)
        state_l1 = CelestialState(
            level=0,
            context={"export_controlled": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="share",
            payload={},
        )
        assert check_celestial_compliance(state_l1) is False

        # L2 fail (L0, L1 pass)
        state_l2 = CelestialState(
            level=0,
            context={"user_consent": False},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="process",
            payload={},
        )
        assert check_celestial_compliance(state_l2) is False

        # L3 fail (L0, L1, L2 pass)
        state_l3 = CelestialState(
            level=0,
            context={
                "actor_permissions": {"read"},
                "required_permissions": {"read", "write"},
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="write",
            payload={},
        )
        assert check_celestial_compliance(state_l3) is False

        # L4 fail (L0–L3 pass)
        state_l4 = CelestialState(
            level=0,
            context={"outside_envelope": True},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="exotic",
            payload={},
        )
        assert check_celestial_compliance(state_l4) is False


# =============================================================================
# Performance and Stress Tests
# =============================================================================


class TestPerformance:
    """Performance and stress tests for chain evaluation."""

    def test_chain_evaluation_speed(self, base_safe_state):
        """Test that chain evaluation completes quickly."""
        predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
            L2EthicalPredicate(),
            L3PermissionsPredicate(),
            L4ConstitutionalPredicate(),
        ]
        # Should complete quickly even with all predicates
        for _ in range(100):
            results = evaluate_celestial_chain(base_safe_state, predicates)
            assert len(results) == 5

    def test_early_short_circuit_performance(self):
        """Test that short-circuit saves evaluation time."""
        state = CelestialState(
            level=0,
            context={"intent": "harm"},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="bad",
            payload={},
        )
        predicates = [
            L0SafetyPredicate(),
            L1LegalPredicate(),
            L2EthicalPredicate(),
            L3PermissionsPredicate(),
            L4ConstitutionalPredicate(),
        ]
        # Should only evaluate L0 before stopping
        for _ in range(100):
            results = evaluate_celestial_chain(state, predicates)
            assert len(results) == 1

    def test_compliance_check_with_large_context(self):
        """Test compliance check with large context dictionary."""
        state = CelestialState(
            level=0,
            context={
                f"key_{i}": f"value_{i}" for i in range(100)
            },
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="read",
            payload={},
        )
        result = check_celestial_compliance(state)
        assert isinstance(result, bool)

    def test_compliance_check_with_large_payload(self):
        """Test compliance check with large payload."""
        state = CelestialState(
            level=0,
            context={},
            timestamp=datetime.now(tz=timezone.utc),
            actor_id="user",
            action="read",
            payload={"data": "x" * 100000},
        )
        result = check_celestial_compliance(state)
        assert isinstance(result, bool)
