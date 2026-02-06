"""Circuit breaker for external service protection.

States:
- CLOSED: Healthy, requests pass through
- OPEN: Failing, requests short-circuited (fail fast)
- HALF_OPEN: Testing recovery, limited requests allowed

Config: 5 failures → OPEN, 60s cooldown → HALF_OPEN, 1 success → CLOSED
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker for external service calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit %s → HALF_OPEN", self.name)
            return self._state

    def allow_request(self) -> bool:
        """Check if the circuit allows a request through."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit %s → CLOSED (recovered)", self.name)
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit %s → OPEN (half-open test failed)", self.name)
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit %s → OPEN (%d failures)", self.name, self._failure_count
                )

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0


# Pre-configured circuit breakers for each external service
_breakers: dict[str, CircuitBreaker] = {}

SERVICE_NAMES = ["ollama", "stripe", "shopify", "printful", "instagram", "chromadb", "redis"]


def get_breaker(service: str) -> CircuitBreaker:
    """Get or create a circuit breaker for a service."""
    if service not in _breakers:
        _breakers[service] = CircuitBreaker(name=service)
    return _breakers[service]


def get_all_states() -> dict[str, str]:
    """Get the state of all circuit breakers."""
    return {name: get_breaker(name).state.value for name in SERVICE_NAMES}
