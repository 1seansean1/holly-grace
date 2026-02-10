"""Health and service status models."""

from __future__ import annotations

from pydantic import BaseModel


class ServiceHealth(BaseModel):
    name: str
    healthy: bool
    circuit_breaker_state: str = "closed"
    failure_count: int = 0


class SystemHealth(BaseModel):
    overall: str  # "healthy", "degraded", "down"
    services: list[ServiceHealth]
    ecom_agents_reachable: bool
