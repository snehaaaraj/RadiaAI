"""
Ingestion service — end-to-end document processing pipeline.

Orchestrates: download → extract text → chunk → embed → index into Azure AI Search.
Supports both SharePoint auto-sync and manual blob upload ingestion.
Tracks file hashes to skip re-processing unchanged documents.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.azure_clients import BlobStorageClient, OpenAIClient, SearchService, compute_file_hash
from app.core.config import AppSettings
from app.core.logging import get_logger
from app.ingestion.chunker import Chunk, chunk_text
from app.ingestion.extractor import extract_text
from radia_ai.features.jama_requirement_reviewer.connectors.sharepoint_client import SharePointStandardsClient

logger = get_logger(__name__)

# Max texts per embedding API call
_EMBEDDING_BATCH_SIZE = 16


class IngestionService:
    """Ingests documents into the Azure AI Search index."""

    def __init__(
        self,
        settings: AppSettings,
        openai_client: OpenAIClient,
        search_service: SearchService,
        blob_client: BlobStorageClient | None = None,
        sharepoint_client: SharePointStandardsClient | None = None,
    ) -> None:
        self._settings = settings
        self._openai = openai_client
        self._search = search_service
        self._blob = blob_client
        self._sharepoint = sharepoint_client

    def ingest_from_blob(self, document_ids: list[str] | None = None) -> dict[str, Any]:
        """Ingest documents from Azure Blob Storage into the search index."""
        if self._blob is None:
            return {"status": "error", "message": "Blob storage client not configured"}

        blobs = self._blob.list_blobs()
        if document_ids:
            blobs = [b for b in blobs if b["name"] in document_ids]

        indexed_hashes = self._search.get_indexed_file_hashes()
        results = {"processed": 0, "skipped": 0, "failed": 0, "details": []}

        for blob_info in blobs:
            try:
                data = self._blob.download_blob(blob_info["name"])
                file_hash = compute_file_hash(data)

                if file_hash in indexed_hashes:
                    results["skipped"] += 1
                    results["details"].append({"filename": blob_info["name"], "status": "skipped", "reason": "unchanged"})
                    continue

                self._process_document(
                    data=data,
                    filename=blob_info["name"],
                    source="blob",
                    file_hash=file_hash,
                )
                results["processed"] += 1
                results["details"].append({"filename": blob_info["name"], "status": "indexed"})

            except Exception as e:
                logger.exception("blob_ingest_failed", filename=blob_info["name"])
                results["failed"] += 1
                results["details"].append({"filename": blob_info["name"], "status": "failed", "error": str(e)})

        return results

    def ingest_from_sharepoint(self) -> dict[str, Any]:
        """Sync standards documents from SharePoint into the search index."""
        if self._sharepoint is None or not self._sharepoint._settings.is_configured:
            return {"status": "skipped", "message": "SharePoint not configured"}

        files = self._sharepoint.fetch_file_contents()
        if not files:
            return {"status": "skipped", "message": "No files retrieved from SharePoint"}

        indexed_hashes = self._search.get_indexed_file_hashes()
        results = {"processed": 0, "skipped": 0, "failed": 0, "details": []}

        for file_info in files:
            try:
                data = file_info["content"]
                file_hash = compute_file_hash(data)

                if file_hash in indexed_hashes:
                    results["skipped"] += 1
                    results["details"].append({"filename": file_info["name"], "status": "skipped"})
                    continue

                # Delete old chunks for this file if re-indexing
                old_hash = file_info.get("previous_hash")
                if old_hash:
                    self._search.delete_documents_by_file_hash(old_hash)

                self._process_document(
                    data=data,
                    filename=file_info["name"],
                    source="sharepoint",
                    document_type=file_info.get("document_type", ""),
                    file_hash=file_hash,
                    sharepoint_url=file_info.get("url", ""),
                )
                results["processed"] += 1
                results["details"].append({"filename": file_info["name"], "status": "indexed"})

            except Exception as e:
                logger.exception("sharepoint_ingest_failed", filename=file_info.get("name", "unknown"))
                results["failed"] += 1
                results["details"].append({"filename": file_info.get("name", "unknown"), "status": "failed", "error": str(e)})

        return results

    def ingest_raw_document(self, data: bytes, filename: str, source: str = "upload") -> dict[str, Any]:
        """Ingest a single raw document (e.g. from a manual upload endpoint)."""
        file_hash = compute_file_hash(data)
        indexed_hashes = self._search.get_indexed_file_hashes()

        if file_hash in indexed_hashes:
            return {"status": "skipped", "filename": filename, "reason": "unchanged"}

        try:
            self._process_document(data=data, filename=filename, source=source, file_hash=file_hash)
            return {"status": "indexed", "filename": filename}
        except Exception as e:
            logger.exception("raw_ingest_failed", filename=filename)
            return {"status": "failed", "filename": filename, "error": str(e)}

    def _process_document(
        self,
        *,
        data: bytes,
        filename: str,
        source: str,
        document_type: str = "",
        file_hash: str = "",
        sharepoint_url: str = "",
    ) -> None:
        """Core pipeline: extract → chunk → embed → index."""
        text = extract_text(data, filename)
        if not text.strip():
            logger.warning("empty_document_skipped", filename=filename)
            return

        chunks = chunk_text(
            text,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
            source=source,
            filename=filename,
            document_type=document_type,
            file_hash=file_hash,
        )

        if not chunks:
            return

        # Generate embeddings in batches
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), _EMBEDDING_BATCH_SIZE):
            batch = chunks[i : i + _EMBEDDING_BATCH_SIZE]
            texts = [c.content for c in batch]
            embeddings = self._openai.generate_embeddings(texts)
            all_embeddings.extend(embeddings)

        # Build search documents
        search_docs = []
        for chunk, embedding in zip(chunks, all_embeddings):
            search_docs.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "content_vector": embedding,
                "source": chunk.source,
                "filename": chunk.filename,
                "document_type": chunk.document_type or document_type,
                "section": chunk.section,
                "page_number": chunk.page_number or 0,
                "chunk_index": chunk.chunk_index,
                "file_hash": chunk.file_hash,
            })

        self._search.upload_documents(search_docs)
        logger.info("document_indexed", filename=filename, chunks=len(search_docs))
