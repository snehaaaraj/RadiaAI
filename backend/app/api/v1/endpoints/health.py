"""
Health check endpoint.

GET /api/v1/health — Returns the application status and the health of
each external dependency (Azure OpenAI, Azure AI Search, Blob Storage).
"""

import time

from fastapi import APIRouter, Depends, Request

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.health import DependencyHealth, HealthResponse, ServiceStatus

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=APIResponse[HealthResponse],
    summary="Application health check",
    description="Returns application status and external dependency health.",
)
async def health_check(
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> APIResponse[HealthResponse]:
    """
    Lightweight health probe.

    Returns 200 even when dependencies are degraded so that load balancers
    and orchestrators don't take the pod out of rotation on transient issues.
    The caller should inspect the 'status' field of the response body.
    """
    start = time.monotonic()

    # TODO: Implement real connectivity probes for each dependency
    # Stub dependency checks - to be replaced with real connectivity probes
    dependencies = [
        DependencyHealth(name="azure_openai", status=ServiceStatus.OK, message="stub"),
        DependencyHealth(name="azure_search", status=ServiceStatus.OK, message="stub"),
        DependencyHealth(name="blob_storage", status=ServiceStatus.OK, message="stub"),
    ]

    overall = (
        ServiceStatus.OK
        if all(d.status == ServiceStatus.OK for d in dependencies)
        else ServiceStatus.DEGRADED
    )

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("health_check", status=overall, elapsed_ms=round(elapsed_ms, 2))

    return APIResponse(
        data=HealthResponse(
            status=overall,
            version=settings.app_version,
            environment=settings.environment,
            dependencies=dependencies,
        ),
        request_id=request.state.request_id,
    )
