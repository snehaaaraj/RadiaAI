"""
API v1 router - aggregates all versioned endpoint routers.

Authentication is applied here, at mount time, so every endpoint is protected by
default and a new endpoint cannot accidentally ship unauthenticated:

  - public:              health probes, Microsoft Graph webhook receiver
                         (authenticated by its subscription clientState instead)
  - Radia.User:          everything else
  - Radia.DocumentAdmin: ingestion management and indexed-document deletion
                         (the latter is enforced on the endpoint itself)

Adding a new feature means creating a new module under endpoints/ and
registering it below with the appropriate dependency list.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    auth,
    chat,
    documents,
    health,
    ingest,
    jama,
    review,
    search,
    standards,
)
from app.core.security import require_document_admin, require_user

# Master router for /api/v1
router = APIRouter()

_user = [Depends(require_user)]
_document_admin = [Depends(require_document_admin)]

# Public
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(ingest.webhook_router, prefix="/ingest", tags=["Ingestion"])

# Signed-in Radia users
router.include_router(auth.router, prefix="/auth", tags=["Auth"], dependencies=_user)
router.include_router(chat.router, prefix="/chat", tags=["Chat"], dependencies=_user)
router.include_router(search.router, prefix="/search", tags=["Search"], dependencies=_user)
router.include_router(
    ingest.status_router, prefix="/ingest", tags=["Ingestion"], dependencies=_user
)
router.include_router(documents.router, prefix="/documents", tags=["Documents"], dependencies=_user)
router.include_router(review.router, prefix="/review", tags=["Review"], dependencies=_user)
router.include_router(standards.router, prefix="/standards", tags=["Standards"], dependencies=_user)
router.include_router(jama.router, prefix="/jama", tags=["Jama"], dependencies=_user)

# Document administrators
router.include_router(
    ingest.router, prefix="/ingest", tags=["Ingestion"], dependencies=_document_admin
)
