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
from app.reviewers.certification.reviewer import CertificationReviewer
from app.reviewers.language.reviewer import LanguageReviewer
from app.reviewers.orchestrator import ReviewOrchestrator
from app.reviewers.requirement_set.reviewer import RequirementSetReviewer
from app.reviewers.structure.reviewer import StructureReviewer
from app.reviewers.traceability.reviewer import TraceabilityReviewer
from app.reviewers.verifiability.reviewer import VerifiabilityReviewer
from app.services.requirement_review_service import RequirementReviewService
from app.services.review_version_service import ReviewVersionService

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lifespan — startup and shutdown hooks
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
    settings = get_settings()
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    app.state.review_orchestrator = _build_review_orchestrator(settings)
    app.state.review_version_service = ReviewVersionService(app.state.review_orchestrator)
    app.state.requirement_review_service = RequirementReviewService(app.state.review_orchestrator)

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


def _build_review_orchestrator(settings: AppSettings) -> ReviewOrchestrator:
    """Construct the deterministic review orchestrator with registered reviewers."""
    return ReviewOrchestrator(
        settings=settings,
        reviewers=[
            LanguageReviewer(),
            StructureReviewer(),
            VerifiabilityReviewer(),
            TraceabilityReviewer(),
            CertificationReviewer(),
            RequirementSetReviewer(),
        ],
        reviewer_bundle_version="1.0.0",
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
        settings = get_settings()
        orchestrator = _build_review_orchestrator(settings)
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
