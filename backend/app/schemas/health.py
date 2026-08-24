"""Health check schemas."""

from enum import StrEnum

from pydantic import BaseModel


class ServiceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class DependencyHealth(BaseModel):
    """Health status of a single external dependency."""

    name: str
    status: ServiceStatus
    latency_ms: float | None = None
    message: str = ""


class HealthResponse(BaseModel):
    """Aggregated health response returned by GET /api/v1/health."""

    status: ServiceStatus
    version: str
    environment: str
    dependencies: list[DependencyHealth] = []
