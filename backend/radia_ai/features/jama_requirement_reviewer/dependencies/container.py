"""
Dependency injection container.

This module is the single place where concrete implementations are wired to
abstract interfaces. Endpoint handlers declare what they need via type annotations
and Depends(); this module provides the actual instances.

Initialises Azure OpenAI, Azure AI Search, and Blob Storage clients at startup.
Wires the LLM review enhancer into all reviewers for LLM-based review.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from app.core.azure_clients import BlobStorageClient, OpenAIClient, SearchService
from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from app.ingestion.service import IngestionService
from app.rag.llm_review_enhancer_v2 import LLMReviewEnhancer
from app.rag.service import RAGService
from radia_ai.features.jama_requirement_reviewer.connectors.sharepoint_client import (
    SharePointStandardsClient,
)
from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import (
    ReviewHistoryRepository,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.consolidated import (
    build_category_reviewers,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator
from radia_ai.features.jama_requirement_reviewer.services.requirement_delta_review_service import (
    RequirementDeltaReviewService,
)
from radia_ai.features.jama_requirement_reviewer.services.requirement_review_service import (
    RequirementReviewService,
)
from radia_ai.features.jama_requirement_reviewer.services.review_history_service import (
    ReviewHistoryService,
)
from radia_ai.features.jama_requirement_reviewer.services.review_version_service import (
    ReviewVersionService,
)
from radia_ai.features.jama_requirement_reviewer.services.standards_service import StandardsService
from radia_ai.features.jama_requirement_reviewer.standards.registry import StandardsRegistry

logger = get_logger(__name__)


def _resolve_settings(app: FastAPI) -> AppSettings:
    """Use explicit app-scoped settings when present, else load the default settings."""
    return getattr(app.state, "settings", None) or get_settings()


# ---------------------------------------------------------------------------
# Lifespan - startup and shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup: initialise Azure clients, RAG pipeline, ingestion service,
             and hybrid review orchestrator.
    Shutdown: gracefully close connections and flush logs.
    """
    settings = _resolve_settings(app)
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Azure clients
    openai_client = OpenAIClient(settings.azure_openai)
    search_service = SearchService(settings.azure_search, openai_client, settings)
    blob_client = BlobStorageClient(settings.azure_blob)

    # Ensure the search index exists with the correct schema
    try:
        search_service.ensure_index()
    except Exception:
        logger.exception("search_index_creation_failed")

    app.state.openai_client = openai_client
    app.state.search_service = search_service
    app.state.blob_client = blob_client

    # RAG service
    rag_service = RAGService(settings, openai_client, search_service)
    app.state.rag_service = rag_service

    # LLM review enhancer
    llm_enhancer = LLMReviewEnhancer(rag_service)
    app.state.llm_enhancer = llm_enhancer

    # SharePoint + Standards
    sharepoint_client = SharePointStandardsClient(settings.sharepoint)
    app.state.standards_service = StandardsService(StandardsRegistry(), sharepoint_client)
    app.state.sharepoint_client = sharepoint_client

    # Ingestion service
    ingestion_service = IngestionService(
        settings=settings,
        openai_client=openai_client,
        search_service=search_service,
        blob_client=blob_client,
        sharepoint_client=sharepoint_client,
    )
    app.state.ingestion_service = ingestion_service

    # Note: Auto-sync removed for Vercel serverless compatibility.
    # Use manual ingestion via POST /api/v1/ingest endpoint or UI button instead.
    logger.info("ingestion_service_ready", message="Manual ingestion available via /api/v1/ingest")

    # Review orchestrator (LLM-based review)
    app.state.review_orchestrator = _build_review_orchestrator(
        settings,
        app.state.standards_service,
        llm_enhancer,
    )
    app.state.review_version_service = ReviewVersionService(app.state.review_orchestrator)
    app.state.requirement_review_service = RequirementReviewService(app.state.review_orchestrator)
    app.state.review_history_repository = ReviewHistoryRepository(blob_client)
    app.state.review_history_service = ReviewHistoryService(app.state.review_history_repository)
    app.state.requirement_delta_review_service = RequirementDeltaReviewService(
        app.state.review_orchestrator,
        app.state.review_version_service,
    )

    yield  # application runs

    logger.info("application_shutdown")


# ---------------------------------------------------------------------------
# Common injectable dependencies
# ---------------------------------------------------------------------------

SettingsDep = Annotated[AppSettings, Depends(get_settings)]


def _build_review_orchestrator(
    settings: AppSettings,
    standards_service: StandardsService | None = None,
    llm_enhancer: LLMReviewEnhancer | None = None,
) -> ReviewOrchestrator:
    """Construct the LLM-based review orchestrator with registered reviewers."""
    return ReviewOrchestrator(
        settings=settings,
        reviewers=build_category_reviewers(),
        standards_service=standards_service,
        llm_enhancer=llm_enhancer,
        reviewer_bundle_version="2.0.0",
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


def get_llm_enhancer(request: Request) -> LLMReviewEnhancer | None:
    """
    Resolve the LLM review enhancer, rebuilding the Azure chain if needed.

    Normally the enhancer is created during lifespan startup. When app state is
    missing it (a request served by a process that never ran lifespan — e.g. a
    cold serverless invocation), rebuild it from settings rather than handing the
    orchestrator a None enhancer, which would make every review silently return
    zero findings.

    Returns None only when the Azure clients cannot be constructed at all; the
    orchestrator then reports REVIEW_ENGINE_UNAVAILABLE instead of a clean review.
    """
    enhancer = getattr(request.app.state, "llm_enhancer", None)
    if enhancer is not None:
        return cast(LLMReviewEnhancer, enhancer)

    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service is None:
        settings = _resolve_settings(request.app)
        try:
            openai_client = getattr(request.app.state, "openai_client", None) or OpenAIClient(
                settings.azure_openai
            )
            search_service = getattr(request.app.state, "search_service", None) or SearchService(
                settings.azure_search, openai_client, settings
            )
        except Exception:
            logger.exception("llm_enhancer_bootstrap_failed")
            return None

        rag_service = RAGService(settings, openai_client, search_service)
        request.app.state.openai_client = openai_client
        request.app.state.search_service = search_service
        request.app.state.rag_service = rag_service
        logger.warning("llm_enhancer_rebuilt_outside_lifespan")

    enhancer = LLMReviewEnhancer(rag_service)
    request.app.state.llm_enhancer = enhancer
    return enhancer


def get_review_orchestrator(request: Request) -> ReviewOrchestrator:
    """Resolve review orchestrator from application state."""
    orchestrator = getattr(request.app.state, "review_orchestrator", None)
    if orchestrator is None:
        settings = _resolve_settings(request.app)
        standards_service = get_standards_service(request)
        orchestrator = _build_review_orchestrator(
            settings,
            standards_service,
            get_llm_enhancer(request),
        )
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
        service = RequirementDeltaReviewService(
            orchestrator=get_review_orchestrator(request),
            review_version_service=get_review_version_service(request),
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
            blob_client = getattr(request.app.state, "blob_client", None)
            if blob_client is None:
                settings = get_settings()
                from app.core.azure_clients import BlobStorageClient as _Blob

                blob_client = _Blob(settings.azure_blob)
            repository = ReviewHistoryRepository(blob_client)
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


# ---------------------------------------------------------------------------
# Azure service injectable dependencies
# ---------------------------------------------------------------------------


def get_search_service(request: Request) -> SearchService:
    """Resolve Azure AI Search service from application state."""
    return cast(SearchService, request.app.state.search_service)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_rag_service(request: Request) -> RAGService:
    """Resolve RAG service from application state."""
    return cast(RAGService, request.app.state.rag_service)


RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]


def get_ingestion_service(request: Request) -> IngestionService:
    """Resolve ingestion service from application state."""
    return cast(IngestionService, request.app.state.ingestion_service)


IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
