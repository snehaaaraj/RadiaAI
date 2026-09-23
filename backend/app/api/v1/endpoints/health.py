"""
Liveness and readiness endpoints.

GET /api/v1/health/live  - lightweight process check, never calls external services.
GET /api/v1/health/ready - dependency readiness with short, bounded per-dependency
                           timeouts and a cached aggregate result (see
                           ``_CACHE_TTL_SECONDS``) so load-balancer polling does not
                           multiply external call volume.
GET /api/v1/health       - legacy alias for /ready, kept for existing callers.

Dependency probes never surface provider error text or secrets - only a generic
reachability status, latency, and a fixed message per outcome.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import anyio
from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.health import DependencyHealth, HealthResponse, LivenessResponse, ServiceStatus

if TYPE_CHECKING:
    from starlette.datastructures import State

router = APIRouter()
logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 30.0
_PROBE_TIMEOUT_SECONDS = 3.0
_REQUIRED_DEPENDENCIES = frozenset({"azure_openai", "azure_search", "blob_storage"})


class HealthProbe(Protocol):
    """Minimal interface for a blocking dependency health probe."""

    def probe(self) -> None: ...


@dataclass(frozen=True)
class _CachedReadiness:
    response: HealthResponse
    expires_at: float


def _not_configured(name: str) -> DependencyHealth:
    return DependencyHealth(
        name=name, status=ServiceStatus.NOT_CONFIGURED, message="Not configured"
    )


def _unavailable(name: str) -> DependencyHealth:
    """The dependency is configured but its client was never wired up (e.g. startup failed)."""
    return DependencyHealth(name=name, status=ServiceStatus.DOWN, message="Client unavailable")


async def _probe_dependency(name: str, probe: HealthProbe) -> DependencyHealth:
    """Run a blocking SDK probe with a bounded request budget and safe response text."""
    started_at = time.monotonic()
    try:
        with anyio.fail_after(_PROBE_TIMEOUT_SECONDS):
            await anyio.to_thread.run_sync(probe.probe, abandon_on_cancel=True)
    except TimeoutError:
        logger.warning("health_dependency_probe_timed_out", dependency=name)
        return DependencyHealth(
            name=name,
            status=ServiceStatus.DOWN,
            latency_ms=round((time.monotonic() - started_at) * 1000, 2),
            message="Probe timed out",
        )
    except Exception as exc:
        logger.warning(
            "health_dependency_probe_failed",
            dependency=name,
            error_type=type(exc).__name__,
        )
        return DependencyHealth(
            name=name,
            status=ServiceStatus.DOWN,
            latency_ms=round((time.monotonic() - started_at) * 1000, 2),
            message="Service unreachable",
        )

    return DependencyHealth(
        name=name,
        status=ServiceStatus.OK,
        latency_ms=round((time.monotonic() - started_at) * 1000, 2),
        message="Reachable",
    )


async def _build_readiness(settings: AppSettings, app_state: State) -> HealthResponse:
    """Probe required services and configured optional integrations.

    A test (or an alternate deployment target) may install
    ``app_state.health_probe_runner`` - an ``async def(settings) -> HealthResponse``
    callable - to fully control the aggregate result without needing SDK-shaped
    probe doubles for every dependency.
    """
    overridden_runner = getattr(app_state, "health_probe_runner", None)
    if overridden_runner is not None:
        result: HealthResponse = await overridden_runner(settings)
        return result

    configured_probes: list[tuple[str, bool, HealthProbe | None]] = [
        ("azure_openai", True, getattr(app_state, "openai_client", None)),
        ("azure_search", True, getattr(app_state, "search_service", None)),
        ("blob_storage", True, getattr(app_state, "blob_client", None)),
        (
            "sharepoint",
            settings.sharepoint.is_configured,
            getattr(app_state, "sharepoint_client", None),
        ),
        ("jama", settings.jama.is_configured, getattr(app_state, "jama_client", None)),
    ]

    dependencies: list[DependencyHealth] = []
    for name, is_configured, probe in configured_probes:
        if not is_configured:
            dependencies.append(_not_configured(name))
        elif probe is None:
            logger.warning("health_dependency_client_unavailable", dependency=name)
            dependencies.append(_unavailable(name))
        else:
            dependencies.append(await _probe_dependency(name, probe))

    required_down = any(
        dependency.name in _REQUIRED_DEPENDENCIES and dependency.status != ServiceStatus.OK
        for dependency in dependencies
    )
    optional_down = any(
        dependency.name not in _REQUIRED_DEPENDENCIES and dependency.status == ServiceStatus.DOWN
        for dependency in dependencies
    )
    overall = (
        ServiceStatus.DOWN
        if required_down
        else ServiceStatus.DEGRADED
        if optional_down
        else ServiceStatus.OK
    )
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        environment=settings.environment,
        dependencies=dependencies,
    )


async def _readiness(settings: AppSettings, app_state: State) -> HealthResponse:
    """Return a cached readiness result, refreshing it once the TTL has elapsed.

    Bounded caching keeps load-balancer polling from re-probing every external
    dependency on every request.
    """
    cached: _CachedReadiness | None = getattr(app_state, "health_readiness_cache", None)
    if cached is not None and cached.expires_at > time.monotonic():
        return cached.response

    response = await _build_readiness(settings, app_state)
    app_state.health_readiness_cache = _CachedReadiness(
        response=response,
        expires_at=time.monotonic() + _CACHE_TTL_SECONDS,
    )
    return response


@router.get(
    "/live",
    response_model=APIResponse[LivenessResponse],
    summary="Process liveness check",
    description="Confirms that the API process can serve requests without probing external services.",
)
async def liveness_check(
    request: Request,
    settings: AppSettings = Depends(get_settings),
) -> APIResponse[LivenessResponse]:
    return APIResponse(
        data=LivenessResponse(
            status=ServiceStatus.OK,
            version=settings.app_version,
            environment=settings.environment,
        ),
        request_id=request.state.request_id,
    )


@router.get(
    "/ready",
    response_model=APIResponse[HealthResponse],
    summary="Dependency readiness check",
    description=(
        "Returns cached, sanitized dependency reachability for Azure OpenAI, Azure AI "
        "Search, Blob Storage, SharePoint, and Jama. Reports HTTP 503 when a required "
        "dependency (Azure OpenAI, Azure AI Search, or Blob Storage) is unreachable; "
        "an unreachable optional-but-configured dependency reports 'degraded' at HTTP 200."
    ),
)
@router.get(
    "",
    response_model=APIResponse[HealthResponse],
    summary="Dependency readiness check (legacy alias)",
    include_in_schema=False,
)
async def readiness_check(
    request: Request,
    response: Response,
    settings: AppSettings = Depends(get_settings),
) -> APIResponse[HealthResponse]:
    result = await _readiness(settings, request.app.state)
    if result.status == ServiceStatus.DOWN:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return APIResponse(data=result, request_id=request.state.request_id)
