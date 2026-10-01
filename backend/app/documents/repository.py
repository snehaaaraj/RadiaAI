"""Azure AI Search-backed repository for document-level catalog records."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal, cast

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

from app.core.config import AzureSearchSettings
from app.schemas.documents import DocumentMetadata, DocumentStatus, DocumentSummary

DocumentSortField = Literal["filename", "source", "chunk_count", "ingested_at"]

_CATALOG_SUFFIX = "-catalog"


class DocumentCatalogRepository:
    """Stores one searchable catalog record per indexed source document."""

    def __init__(self, settings: AzureSearchSettings) -> None:
        index_name = f"{settings.index_name}{_CATALOG_SUFFIX}"
        credential = AzureKeyCredential(settings.api_key)
        self._index_name = index_name
        self._index_client = SearchIndexClient(
            endpoint=str(settings.endpoint), credential=credential
        )
        self._search_client = SearchClient(
            endpoint=str(settings.endpoint), index_name=index_name, credential=credential
        )

    def ensure_index(self) -> None:
        """Create or update the catalog schema without deleting existing data."""
        index = SearchIndex(
            name=self._index_name,
            fields=[
                SimpleField(
                    name="document_id",
                    type=SearchFieldDataType.String,
                    key=True,
                    filterable=True,
                ),
                SearchableField(
                    name="filename",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    sortable=True,
                ),
                SimpleField(
                    name="source",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    facetable=True,
                    sortable=True,
                ),
                SimpleField(
                    name="status",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    facetable=True,
                ),
                SimpleField(
                    name="chunk_count",
                    type=SearchFieldDataType.Int32,
                    sortable=True,
                ),
                SimpleField(name="document_type", type=SearchFieldDataType.String),
                SimpleField(name="author", type=SearchFieldDataType.String),
                SimpleField(name="version", type=SearchFieldDataType.String),
                SimpleField(
                    name="modified_date",
                    type=SearchFieldDataType.DateTimeOffset,
                    filterable=True,
                    sortable=True,
                ),
                SimpleField(
                    name="ingested_at",
                    type=SearchFieldDataType.DateTimeOffset,
                    filterable=True,
                    sortable=True,
                ),
            ],
        )
        try:
            self._index_client.get_index(self._index_name)
        except ResourceNotFoundError:
            self._index_client.create_or_update_index(index)
            return
        self._index_client.create_or_update_index(index)

    def upsert(
        self,
        *,
        document_id: str,
        filename: str,
        source: str,
        document_type: str,
        chunk_count: int,
        author: str = "",
        version: str = "",
        modified_date: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> None:
        """Create or replace the catalog record for one successfully indexed file."""
        record = self._record(
            document_id=document_id,
            filename=filename,
            source=source,
            document_type=document_type,
            chunk_count=chunk_count,
            author=author,
            version=version,
            modified_date=modified_date,
            ingested_at=ingested_at,
        )
        result = self._search_client.upload_documents(documents=[record])
        if not result or not result[0].succeeded:
            raise RuntimeError(f"Could not save document catalog record for {document_id}")

    def backfill(self, chunks: Iterable[dict[str, Any]]) -> None:
        """Create catalog rows for documents indexed before the catalog existed."""
        by_document: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            document_id = chunk.get("file_hash")
            if not document_id:
                continue
            entry = by_document.setdefault(
                str(document_id),
                {
                    "document_id": str(document_id),
                    "filename": str(chunk.get("filename") or ""),
                    "source": str(chunk.get("source") or ""),
                    "document_type": str(chunk.get("document_type") or ""),
                    "chunk_count": 0,
                },
            )
            entry["chunk_count"] += 1

        records = [
            self._record(
                document_id=entry["document_id"],
                filename=entry["filename"],
                source=entry["source"],
                document_type=entry["document_type"],
                chunk_count=entry["chunk_count"],
            )
            for entry in by_document.values()
        ]
        for offset in range(0, len(records), 100):
            batch = records[offset : offset + 100]
            results = self._search_client.upload_documents(documents=batch)
            failed = [result.key for result in results if not result.succeeded]
            if failed:
                raise RuntimeError(f"Could not backfill document catalog records: {failed}")

    def is_empty(self) -> bool:
        """Check whether the catalog has any records."""
        results = self._search_client.search(
            search_text="*",
            top=1,
            include_total_count=True,
        )
        return not results.get_count()

    @staticmethod
    def _record(
        *,
        document_id: str,
        filename: str,
        source: str,
        document_type: str,
        chunk_count: int,
        author: str = "",
        version: str = "",
        modified_date: datetime | None = None,
        ingested_at: datetime | None = None,
    ) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "filename": filename,
            "source": source,
            "status": DocumentStatus.INDEXED.value,
            "chunk_count": chunk_count,
            "document_type": document_type,
            "author": author,
            "version": version,
            "modified_date": modified_date.isoformat() if modified_date else None,
            "ingested_at": ingested_at.isoformat() if ingested_at else None,
        }

    def get(self, document_id: str) -> DocumentSummary | None:
        """Retrieve one catalog record, returning None only when it does not exist."""
        try:
            record = self._search_client.get_document(key=document_id)
        except ResourceNotFoundError:
            return None
        return self._to_summary(record)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        source: str | None = None,
        query: str | None = None,
        sort_by: DocumentSortField = "filename",
        sort_order: Literal["asc", "desc"] = "asc",
    ) -> tuple[list[DocumentSummary], int]:
        """Return one page of catalog records and the total matching count."""
        filter_expression = None
        if source:
            escaped_source = source.replace("'", "''")
            filter_expression = f"source eq '{escaped_source}'"

        results = self._search_client.search(
            search_text=query or "*",
            filter=filter_expression,
            order_by=[f"{sort_by} {sort_order}"],
            skip=(page - 1) * page_size,
            top=page_size,
            include_total_count=True,
            select=[
                "document_id",
                "filename",
                "source",
                "status",
                "chunk_count",
                "document_type",
                "author",
                "version",
                "modified_date",
                "ingested_at",
            ],
        )
        rows = [self._to_summary(row) for row in results]
        return rows, int(results.get_count() or 0)

    def delete(self, document_id: str) -> None:
        """Remove the catalog record for one document."""
        self._search_client.delete_documents(documents=[{"document_id": document_id}])

    @staticmethod
    def _to_summary(record: dict[str, Any]) -> DocumentSummary:
        metadata = DocumentMetadata(
            source=str(record.get("source") or ""),
            filename=str(record.get("filename") or ""),
            document_type=str(record.get("document_type") or ""),
            author=str(record.get("author") or ""),
            version=str(record.get("version") or ""),
            modified_date=record.get("modified_date"),
        )
        return DocumentSummary(
            document_id=str(record["document_id"]),
            filename=metadata.filename,
            status=cast(DocumentStatus, record.get("status", DocumentStatus.INDEXED.value)),
            chunk_count=int(record.get("chunk_count") or 0),
            metadata=metadata,
            ingested_at=record.get("ingested_at"),
        )
