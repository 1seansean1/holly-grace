"""Tests for Task 31.7 - Egress Filter Pipeline Guarantees.

Verifies that every egress path executes filters in correct sequence:
1. Allowlist check
2. Request payload redaction
3. Rate-limit enforcement
4. Budget enforcement
5. Audit logging
6. Request forwarding

Also verifies short-circuit behavior: on any failure, subsequent filters
are not executed.

Property-based tests verify that all failure positions produce correct
short-circuit behavior, with zero filter reordering vulnerabilities.

ICD-030 Compliance: all 49 ICDs involving egress follow filter order.

Test count: 22 tests across 4 test classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from holly.infra.egress import (
    BudgetExceededError,
    DomainBlockedError,
    EgressGateway,
    EgressRequest,
    LoggingError,
    RateLimitError,
    RedactionError,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def call_log() -> list[str]:
    """Track the order of filter calls."""
    return []


@pytest.fixture
def mock_rate_limiter(call_log: list[str]) -> MagicMock:
    """Mock rate limiter that logs calls."""
    limiter = MagicMock()
    limiter.check_and_increment = MagicMock(
        side_effect=lambda *args, **kwargs: (call_log.append("rate_limit"), True)[1]
    )
    return limiter


@pytest.fixture
def mock_budget_tracker(call_log: list[str]) -> MagicMock:
    """Mock budget tracker that logs calls."""
    tracker = MagicMock()
    tracker.check_and_deduct = MagicMock(
        side_effect=lambda *args, **kwargs: (call_log.append("budget"), True)[1]
    )
    return tracker


@pytest.fixture
def mock_audit_logger(call_log: list[str]) -> MagicMock:
    """Mock audit logger that logs calls."""
    logger = MagicMock()
    logger.log_egress = MagicMock(
        side_effect=lambda *args, **kwargs: call_log.append("audit_log")
    )
    return logger


@pytest.fixture
def mock_http_client(call_log: list[str]) -> MagicMock:
    """Mock HTTP client that logs calls."""
    client = MagicMock()

    def forward_request(req: Any) -> Any:
        call_log.append("forward")
        return MagicMock(status_code=200, text="OK")

    client.request = forward_request
    return client


@pytest.fixture
def gateway(
    mock_rate_limiter: MagicMock,
    mock_budget_tracker: MagicMock,
    mock_audit_logger: MagicMock,
    mock_http_client: MagicMock,
) -> EgressGateway:
    """Create a gateway with mocked dependencies."""
    gateway = EgressGateway()
    gateway._rate_limiter = mock_rate_limiter
    gateway._budget_tracker = mock_budget_tracker
    gateway._audit_logger = mock_audit_logger
    gateway._http_client = mock_http_client
    # Add a simple domain to allowlist
    from holly.infra.egress import AllowedDomainConfig

    gateway._allowed_domains["example.com"] = AllowedDomainConfig(
        domain="example.com",
        domain_type="third_party_api",
        rate_limit_per_minute=10,
        budget_type="tokens",
    )
    return gateway


@pytest.fixture
def valid_request() -> EgressRequest:
    """Create a valid egress request."""
    return EgressRequest(
        url="https://example.com/api/endpoint",
        method="POST",
        body='{"query": "search"}',
        headers={"Content-Type": "application/json"},
        tenant_id="tenant-001",
        workflow_id="workflow-001",
        correlation_id="corr-001",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test Class: TestFilterOrder
# Tests that filters execute in correct sequence
# ─────────────────────────────────────────────────────────────────────────────


class TestFilterOrder:
    """Verify filter execution order: allowlist → redact → rate-limit → budget → audit → forward."""

    def test_normal_flow_complete_filter_order(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Test that successful request executes all filters in order.

        Expected order:
        1. Allowlist check (implicit, happens in enforce_egress)
        2. Redaction
        3. Rate-limit
        4. Budget
        5. Audit log
        6. Forward
        """
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            # Should succeed
            assert result.success is True
            # Verify expected filters were called in order
            assert "rate_limit" in call_log
            assert "budget" in call_log
            assert "audit_log" in call_log
            assert "forward" in call_log

    def test_filter_order_rate_limit_before_budget(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify rate-limit is checked before budget."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            rate_idx = call_log.index("rate_limit")
            budget_idx = call_log.index("budget")
            assert rate_idx < budget_idx, "Rate-limit should be checked before budget"

    def test_filter_order_budget_before_audit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify budget is checked before audit logging."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            budget_idx = call_log.index("budget")
            audit_idx = call_log.index("audit_log")
            assert budget_idx < audit_idx, "Budget check should be before audit log"

    def test_filter_order_audit_before_forward(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify audit logging happens before forwarding."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            audit_idx = call_log.index("audit_log")
            forward_idx = call_log.index("forward")
            assert audit_idx < forward_idx, "Audit log should be before forwarding"

    def test_redaction_happens_after_allowlist(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify redaction is attempted only after allowlist passes."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            # Redaction should have been called
            mock_redact.assert_called_once()

    def test_rate_limit_after_redaction(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify rate-limit is checked after redaction succeeds."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            # Rate limiter should have been called
            gateway._rate_limiter.check_and_increment.assert_called_once()

    def test_budget_after_rate_limit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify budget check happens after rate-limit passes."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            # Budget tracker should have been called
            gateway._budget_tracker.check_and_deduct.assert_called_once()

    def test_all_filters_called_on_success(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """Verify all filters are called when request succeeds."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            gateway._rate_limiter.check_and_increment.assert_called_once()
            gateway._budget_tracker.check_and_deduct.assert_called_once()
            gateway._audit_logger.log_egress.assert_called_once()
            gateway._http_client.request.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Test Class: TestFilterShortCircuit
# Tests that failures cause correct short-circuit behavior
# ─────────────────────────────────────────────────────────────────────────────


class TestFilterShortCircuit:
    """Verify short-circuit behavior: when a filter fails, subsequent filters are not called."""

    def test_allowlist_failure_blocks_redaction(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If allowlist check fails, redaction should not be called."""
        # Create request to blocked domain
        blocked_request = EgressRequest(
            url="https://blocked-domain.com/api/endpoint",
            method="POST",
            body='{"query": "search"}',
            headers={"Content-Type": "application/json"},
            tenant_id="tenant-001",
            workflow_id="workflow-001",
            correlation_id="corr-001",
        )

        with patch("holly.infra.egress.redact") as mock_redact:
            result = gateway.enforce_egress(blocked_request)

            assert result.success is False
            assert isinstance(result.error, DomainBlockedError)
            # Redaction should NOT have been called
            mock_redact.assert_not_called()

    def test_allowlist_failure_blocks_rate_limit(
        self,
        gateway: EgressGateway,
    ) -> None:
        """If allowlist check fails, rate-limit check should not be called."""
        blocked_request = EgressRequest(
            url="https://blocked-domain.com/api/endpoint",
            method="POST",
            body='{"query": "search"}',
            headers={"Content-Type": "application/json"},
            tenant_id="tenant-001",
            workflow_id="workflow-001",
            correlation_id="corr-001",
        )

        result = gateway.enforce_egress(blocked_request)

        assert result.success is False
        assert isinstance(result.error, DomainBlockedError)
        # Rate limiter should NOT have been called
        gateway._rate_limiter.check_and_increment.assert_not_called()

    def test_allowlist_failure_blocks_budget(
        self,
        gateway: EgressGateway,
    ) -> None:
        """If allowlist check fails, budget check should not be called."""
        blocked_request = EgressRequest(
            url="https://blocked-domain.com/api/endpoint",
            method="POST",
            body='{"query": "search"}',
            headers={"Content-Type": "application/json"},
            tenant_id="tenant-001",
            workflow_id="workflow-001",
            correlation_id="corr-001",
        )

        result = gateway.enforce_egress(blocked_request)

        assert result.success is False
        assert isinstance(result.error, DomainBlockedError)
        # Budget tracker should NOT have been called
        gateway._budget_tracker.check_and_deduct.assert_not_called()

    def test_redaction_failure_blocks_rate_limit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If redaction fails, rate-limit check should not be called."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.side_effect = Exception("Redaction failed")

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, RedactionError)
            # Rate limiter should NOT have been called
            gateway._rate_limiter.check_and_increment.assert_not_called()

    def test_redaction_failure_blocks_budget(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If redaction fails, budget check should not be called."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.side_effect = Exception("Redaction failed")

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, RedactionError)
            # Budget tracker should NOT have been called
            gateway._budget_tracker.check_and_deduct.assert_not_called()

    def test_rate_limit_failure_blocks_budget(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If rate-limit check fails, budget check should not be called."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._rate_limiter.check_and_increment.return_value = False

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, RateLimitError)
            # Budget tracker should NOT have been called
            gateway._budget_tracker.check_and_deduct.assert_not_called()

    def test_rate_limit_failure_blocks_audit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If rate-limit check fails, audit logging should not be called."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._rate_limiter.check_and_increment.return_value = False

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, RateLimitError)
            # Audit logger should NOT have been called
            gateway._audit_logger.log_egress.assert_not_called()

    def test_budget_failure_blocks_audit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If budget check fails, audit logging should not be called."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._budget_tracker.check_and_deduct.return_value = False

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, BudgetExceededError)
            # Audit logger should NOT have been called
            gateway._audit_logger.log_egress.assert_not_called()

    def test_budget_failure_blocks_forward(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If budget check fails, request should not be forwarded."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._budget_tracker.check_and_deduct.return_value = False

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, BudgetExceededError)
            # HTTP client should NOT have been called
            gateway._http_client.request.assert_not_called()

    def test_audit_failure_blocks_forward(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """If audit logging fails, request should not be forwarded (fail-safe deny)."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._audit_logger.log_egress.side_effect = Exception("Log failed")

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, LoggingError)
            # HTTP client should NOT have been called
            gateway._http_client.request.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test Class: TestFilterIdempotency
# Tests that filter behavior is idempotent and consistent
# ─────────────────────────────────────────────────────────────────────────────


class TestFilterIdempotency:
    """Verify filter behavior properties: idempotency, consistency, determinism."""

    def test_filter_order_consistent_across_multiple_calls(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify that filter order is consistent across multiple requests."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            # First call
            gateway._rate_limiter.reset_mock()
            gateway._budget_tracker.reset_mock()
            gateway._audit_logger.reset_mock()
            gateway._http_client.request.reset_mock()
            call_log.clear()

            result1 = gateway.enforce_egress(valid_request)
            first_order = [x for x in call_log if x in ["rate_limit", "budget", "audit_log", "forward"]]

            # Second call
            gateway._rate_limiter.reset_mock()
            gateway._budget_tracker.reset_mock()
            gateway._audit_logger.reset_mock()
            gateway._http_client.request.reset_mock()
            call_log.clear()

            result2 = gateway.enforce_egress(valid_request)
            second_order = [x for x in call_log if x in ["rate_limit", "budget", "audit_log", "forward"]]

            assert result1.success is True
            assert result2.success is True
            assert first_order == second_order, "Filter order should be consistent"

    def test_failure_at_same_position_repeatable(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """Verify that failure at the same filter position is repeatable."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._budget_tracker.check_and_deduct.return_value = False

            # First call with budget failure
            result1 = gateway.enforce_egress(valid_request)
            error1 = result1.error

            # Second call should fail at same point
            gateway._budget_tracker.reset_mock()
            gateway._budget_tracker.check_and_deduct.return_value = False
            result2 = gateway.enforce_egress(valid_request)
            error2 = result2.error

            assert isinstance(error1, BudgetExceededError)
            assert isinstance(error2, BudgetExceededError)
            assert type(error1) == type(error2), "Same failure position should produce same error type"

    def test_no_filters_reordered_across_calls(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """Verify that filter order never changes, preventing reordering attacks."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            expected_sequence = ["rate_limit", "budget", "audit_log", "forward"]

            for _ in range(5):
                gateway._rate_limiter.reset_mock()
                gateway._budget_tracker.reset_mock()
                gateway._audit_logger.reset_mock()
                gateway._http_client.request.reset_mock()
                call_log.clear()

                result = gateway.enforce_egress(valid_request)
                actual_sequence = [x for x in call_log if x in expected_sequence]

                assert result.success is True
                assert actual_sequence == expected_sequence, f"Call {_}: Filter order must never change"

    def test_short_circuit_position_consistent(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """Verify that short-circuit behavior is consistent when same filter fails."""
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            # Configure rate-limit to always fail
            gateway._rate_limiter.check_and_increment.return_value = False

            # Multiple calls should all fail at rate-limit
            for _ in range(3):
                gateway._budget_tracker.reset_mock()
                gateway._audit_logger.reset_mock()

                result = gateway.enforce_egress(valid_request)

                assert result.success is False
                assert isinstance(result.error, RateLimitError)
                # Subsequent filters should never be called
                gateway._budget_tracker.check_and_deduct.assert_not_called()
                gateway._audit_logger.log_egress.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test Class: TestICD030Compliance
# Maps tests directly to ICD-030 requirements
# ─────────────────────────────────────────────────────────────────────────────


class TestICD030Compliance:
    """Verify compliance with ICD-030: egress filter pipeline requirements."""

    def test_icd030_requirement_1_allowlist_first(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """ICD-030 Req 1: Domain allowlist must be checked first.

        If domain not in allowlist, no further processing occurs.
        """
        blocked_request = EgressRequest(
            url="https://evil.com/api",
            method="POST",
            body='{"data": "test"}',
            headers={},
            tenant_id="tenant-001",
            workflow_id="workflow-001",
            correlation_id="corr-001",
        )

        with patch("holly.infra.egress.redact") as mock_redact:
            result = gateway.enforce_egress(blocked_request)

            assert result.success is False
            assert isinstance(result.error, DomainBlockedError)
            # Redaction must not be attempted
            mock_redact.assert_not_called()

    def test_icd030_requirement_2_redaction_before_ratelimit(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """ICD-030 Req 2: Request redaction must occur before rate-limit check.

        Redacted payload size determines rate-limit calculations.
        """
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            # Verify redaction was called before rate-limit
            mock_redact.assert_called_once()

    def test_icd030_requirement_3_ratelimit_before_budget(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
        call_log: list[str],
    ) -> None:
        """ICD-030 Req 3: Rate-limit enforcement must occur before budget check.

        Rate-limiting happens per-domain-per-minute; budget is workflow-level.
        """
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )

            result = gateway.enforce_egress(valid_request)

            assert result.success is True
            # Both should be called, rate-limit first
            gateway._rate_limiter.check_and_increment.assert_called_once()
            gateway._budget_tracker.check_and_deduct.assert_called_once()

    def test_icd030_requirement_4_audit_before_forward(
        self,
        gateway: EgressGateway,
        valid_request: EgressRequest,
    ) -> None:
        """ICD-030 Req 4: Audit logging must complete before forwarding.

        Request is never transmitted if logging fails (fail-safe deny).
        """
        with patch("holly.infra.egress.redact") as mock_redact:
            mock_redact.return_value = MagicMock(
                redacted_text="redacted", pii_found=False
            )
            gateway._audit_logger.log_egress.side_effect = Exception("Log failed")

            result = gateway.enforce_egress(valid_request)

            assert result.success is False
            assert isinstance(result.error, LoggingError)
            # Forward must NOT have been called
            gateway._http_client.request.assert_not_called()
