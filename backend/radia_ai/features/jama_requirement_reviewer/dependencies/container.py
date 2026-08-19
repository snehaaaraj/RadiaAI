"""
Dependency injection container.

This module is the single place where concrete implementations are wired to
abstract interfaces. Endpoint handlers declare what they need via type annotations
and Depends(); this module provides the actual instances.

Phase 1: Only settings and auth are wired.
Phase 2+: Azure service wrappers will be registered here as singletons
          using FastAPI's lifespan context manager pattern.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import ReviewHistoryRepository
from radia_ai.features.jama_requirement_reviewer.reviewers.certification.reviewer import CertificationReviewer
from radia_ai.features.jama_requirement_reviewer.reviewers.language.reviewer import LanguageReviewer
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator
from radia_ai.features.jama_requirement_reviewer.reviewers.structure.reviewer import StructureReviewer
from radia_ai.features.jama_requirement_reviewer.reviewers.traceability.reviewer import TraceabilityReviewer
from radia_ai.features.jama_requirement_reviewer.reviewers.verifiability.reviewer import VerifiabilityReviewer
from radia_ai.features.jama_requirement_reviewer.connectors.sharepoint_client import SharePointStandardsClient
from radia_ai.features.jama_requirement_reviewer.services.requirement_review_service import RequirementReviewService
from radia_ai.features.jama_requirement_reviewer.services.requirement_delta_review_service import RequirementDeltaReviewService
from radia_ai.features.jama_requirement_reviewer.services.review_history_service import ReviewHistoryService
from radia_ai.features.jama_requirement_reviewer.services.review_version_service import ReviewVersionService
from radia_ai.features.jama_requirement_reviewer.services.standards_service import StandardsService

from radia_ai.features.jama_requirement_reviewer.standards.registry import StandardsRegistry

logger = get_logger(__name__)


def _resolve_settings(app: FastAPI) -> AppSettings:
    """Use explicit app-scoped settings when present, else load the default settings."""
    return getattr(app.state, "settings", None) or get_settings()

# ---------------------------------------------------------------------------
# Lifespan â€” startup and shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup: initialise shared resources (Azure clients, connection pools).
    Shutdown: gracefully close connections and flush logs.

    Phase 2 will instantiate Azure service wrappers here and attach them to
    app.state so they can be injected into request handlers.
    """
    settings = _resolve_settings(app)
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    sharepoint_client = SharePointStandardsClient(settings.sharepoint)
    app.state.standards_service = StandardsService(StandardsRegistry(), sharepoint_client)
    app.state.review_orchestrator = _build_review_orchestrator(
        settings,
        app.state.standards_service,
    )
    app.state.review_version_service = ReviewVersionService(app.state.review_orchestrator)
    app.state.sharepoint_client = sharepoint_client
    app.state.requirement_review_service = RequirementReviewService(app.state.review_orchestrator)
    app.state.review_history_repository = ReviewHistoryRepository()
    app.state.review_history_service = ReviewHistoryService(app.state.review_history_repository)
    app.state.requirement_delta_review_service = RequirementDeltaReviewService(
        app.state.requirement_review_service,
        app.state.review_version_service,
    )

    # Phase 2: initialise Azure clients here, e.g.:
    # app.state.search_service = AzureSearchService(settings.azure_search)
    # app.state.openai_service = AzureOpenAIService(settings.azure_openai)
    # app.state.blob_service = BlobStorageService(settings.azure_blob)

    yield  # application runs

    logger.info("application_shutdown")


# ---------------------------------------------------------------------------
# Common injectable dependencies
# ---------------------------------------------------------------------------

SettingsDep = Annotated[AppSettings, Depends(get_settings)]


def _build_review_orchestrator(
    settings: AppSettings, standards_service: StandardsService | None = None
) -> ReviewOrchestrator:
    """Construct the deterministic review orchestrator with registered reviewers."""
    return ReviewOrchestrator(
        settings=settings,
        reviewers=[
            LanguageReviewer(),
            StructureReviewer(),
            VerifiabilityReviewer(),
            TraceabilityReviewer(),
            CertificationReviewer(),
        ],
        standards_service=standards_service,
        reviewer_bundle_version="1.1.0",
    )


def get_review_version_service(request: Request) -> ReviewVersionService:
    """Resolve review version service from application state."""
    service = getattr(request.app.state, "review_version_service", None)
    if service is None:
        orchestrator = get_review_orchestrator(request)
        service = ReviewVersionService(orchestrator)
        request.app.state.review_version_service = service
    return service


ReviewVersionServiceDep = Annotated[ReviewVersionService, Depends(get_review_version_service)]


def get_review_orchestrator(request: Request) -> ReviewOrchestrator:
    """Resolve review orchestrator from application state."""
    orchestrator = getattr(request.app.state, "review_orchestrator", None)
    if orchestrator is None:
        settings = _resolve_settings(request.app)
        standards_service = get_standards_service(request)
        orchestrator = _build_review_orchestrator(settings, standards_service)
        request.app.state.review_orchestrator = orchestrator
    return orchestrator


def get_requirement_review_service(request: Request) -> RequirementReviewService:
    """Resolve requirement review service from application state."""
    service = getattr(request.app.state, "requirement_review_service", None)
    if service is None:
        orchestrator = get_review_orchestrator(request)
        service = RequirementReviewService(orchestrator)
        request.app.state.requirement_review_service = service
    return service


RequirementReviewServiceDep = Annotated[
    RequirementReviewService, Depends(get_requirement_review_service)
]


def get_requirement_delta_review_service(request: Request) -> RequirementDeltaReviewService:
    """Resolve requirement delta review service from application state."""
    service = getattr(request.app.state, "requirement_delta_review_service", None)
    if service is None:
        requirement_service = get_requirement_review_service(request)
        version_service = get_review_version_service(request)
        service = RequirementDeltaReviewService(
            requirement_review_service=requirement_service,
            review_version_service=version_service,
        )
        request.app.state.requirement_delta_review_service = service
    return service


RequirementDeltaReviewServiceDep = Annotated[
    RequirementDeltaReviewService, Depends(get_requirement_delta_review_service)
]


def get_review_history_service(request: Request) -> ReviewHistoryService:
    """Resolve review history service from application state."""
    service = getattr(request.app.state, "review_history_service", None)
    if service is None:
        repository = getattr(request.app.state, "review_history_repository", None)
        if repository is None:
            repository = ReviewHistoryRepository()
            request.app.state.review_history_repository = repository
        service = ReviewHistoryService(repository)
        request.app.state.review_history_service = service
    return service


ReviewHistoryServiceDep = Annotated[ReviewHistoryService, Depends(get_review_history_service)]


def get_standards_service(request: Request) -> StandardsService:
    """Resolve standards service from application state."""
    service = getattr(request.app.state, "standards_service", None)
    if service is None:
        settings = _resolve_settings(request.app)
        sharepoint_client = SharePointStandardsClient(settings.sharepoint)
        service = StandardsService(StandardsRegistry(), sharepoint_client)
        request.app.state.standards_service = service
    return service


StandardsServiceDep = Annotated[StandardsService, Depends(get_standards_service)]
