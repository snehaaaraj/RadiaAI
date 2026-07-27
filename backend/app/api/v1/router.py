"""
API v1 router — aggregates all versioned endpoint routers.

Adding a new feature means creating a new module under endpoints/
and registering it here. No changes needed elsewhere in the app.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import chat, documents, health, ingest, review, search, standards

# Master router for /api/v1
router = APIRouter()

router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(search.router, prefix="/search", tags=["Search"])
router.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(review.router, prefix="/review", tags=["Review"])
router.include_router(standards.router, prefix="/standards", tags=["Standards"])
