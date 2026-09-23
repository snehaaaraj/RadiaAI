"""Health check schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ServiceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    NOT_CONFIGURED = "not_configured"


class DependencyHealth(BaseModel):
    """Health status of a single external dependency."""

    name: str
    status: ServiceStatus
    latency_ms: float | None = None
    message: str = ""


class HealthResponse(BaseModel):
    """Aggregated readiness response returned by GET /api/v1/health/ready."""

    status: ServiceStatus
    version: str
    environment: str
    dependencies: list[DependencyHealth] = Field(default_factory=list)


class LivenessResponse(BaseModel):
    """Lightweight process liveness response."""

    status: ServiceStatus
    version: str
    environment: str
