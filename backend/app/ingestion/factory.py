"""Build the Azure-backed ingestion pipeline for API and worker processes."""

from __future__ import annotations

from app.core.azure_clients import BlobStorageClient, OpenAIClient, SearchService
from app.core.config import AppSettings
from app.documents.repository import DocumentCatalogRepository
from app.ingestion.service import IngestionService
from radia_ai.features.jama_requirement_reviewer.connectors.sharepoint_client import (
    SharePointStandardsClient,
)


def build_ingestion_service(settings: AppSettings) -> IngestionService:
    """Construct ingestion dependencies for an independently deployed worker."""
    openai_client = OpenAIClient(settings.azure_openai)
    search_service = SearchService(settings.azure_search, openai_client, settings)
    search_service.ensure_index()
    blob_client = BlobStorageClient(settings.azure_blob)
    catalog = DocumentCatalogRepository(settings.azure_search)
    catalog.ensure_index()
    if catalog.is_empty():
        catalog.backfill(search_service.iter_indexed_document_chunks())
    return IngestionService(
        settings=settings,
        openai_client=openai_client,
        search_service=search_service,
        blob_client=blob_client,
        sharepoint_client=SharePointStandardsClient(settings.sharepoint),
        document_catalog=catalog,
    )
