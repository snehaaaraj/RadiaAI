"""
Azure service client wrappers.

Thin wrappers around the Azure SDKs providing typed interfaces for:
  - Azure OpenAI (chat completions + embeddings)
  - Azure AI Search (index management, document upload, vector/hybrid search)
  - Azure Blob Storage (upload/download blobs)

Each client is designed to be instantiated once at startup (via the DI container)
and reused for the lifetime of the application.
"""

from __future__ import annotations

import contextlib
import hashlib
from typing import Any, cast

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from azure.storage.blob import BlobServiceClient, ContentSettings
from openai import AzureOpenAI

from app.core.config import AppSettings, AzureBlobSettings, AzureOpenAISettings, AzureSearchSettings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------


class OpenAIClient:
    """Wraps Azure OpenAI for chat completions and embedding generation."""

    def __init__(self, settings: AzureOpenAISettings) -> None:
        self._settings = settings
        self._client = AzureOpenAI(
            azure_endpoint=str(settings.endpoint),
            api_key=settings.api_key,
            api_version=settings.api_version,
        )

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts."""
        if not texts:
            return []
        # Truncate to stay within the 8192 token limit
        truncated = [t[:30000] for t in texts]
        response = self._client.embeddings.create(
            input=truncated,
            model=self._settings.embedding_deployment,
            dimensions=self._settings.embedding_dimensions,
        )
        return [item.embedding for item in response.data]

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run a chat completion and return the assistant message content."""
        kwargs: dict[str, Any] = {
            "model": self._settings.chat_deployment,
            "messages": messages,
            "max_completion_tokens": max_tokens or self._settings.max_tokens,
        }
        # Some models (e.g. GPT-5, o-series) only support temperature=1.
        # Only pass temperature if explicitly requested and non-default.
        temp = temperature if temperature is not None else self._settings.temperature
        if temp > 0.0:
            kwargs["temperature"] = temp

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Azure AI Search client
# ---------------------------------------------------------------------------


class SearchService:
    """Wraps Azure AI Search for index management and querying."""

    def __init__(
        self, settings: AzureSearchSettings, openai_client: OpenAIClient, app_settings: AppSettings
    ) -> None:
        self._settings = settings
        self._openai = openai_client
        self._app_settings = app_settings
        credential = AzureKeyCredential(settings.api_key)
        self._index_client = SearchIndexClient(
            endpoint=str(settings.endpoint), credential=credential
        )
        self._search_client = SearchClient(
            endpoint=str(settings.endpoint),
            index_name=settings.index_name,
            credential=credential,
        )

    # -- Index management --

    def ensure_index(self) -> None:
        """Create or update the search index with the expected schema."""
        embedding_dims = self._app_settings.azure_openai.embedding_dimensions

        fields = [
            SimpleField(
                name="chunk_id", type=SearchFieldDataType.String, key=True, filterable=True
            ),
            SearchableField(
                name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
            ),
            SimpleField(
                name="source", type=SearchFieldDataType.String, filterable=True, facetable=True
            ),
            SimpleField(
                name="filename", type=SearchFieldDataType.String, filterable=True, facetable=True
            ),
            SimpleField(
                name="document_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(name="section", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="file_hash", type=SearchFieldDataType.String, filterable=True),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=embedding_dims,
                vector_search_profile_name="default-vector-profile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
            profiles=[
                VectorSearchProfile(
                    name="default-vector-profile", algorithm_configuration_name="default-hnsw"
                )
            ],
        )

        semantic_config = SemanticConfiguration(
            name=self._settings.semantic_config_name,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="filename"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="document_type")],
            ),
        )

        index = SearchIndex(
            name=self._settings.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=SemanticSearch(configurations=[semantic_config]),
        )

        try:
            self._index_client.create_or_update_index(index)
        except Exception:
            # Incompatible existing index — delete and recreate
            logger.warning(
                "index_schema_incompatible_recreating", index_name=self._settings.index_name
            )
            with contextlib.suppress(Exception):
                self._index_client.delete_index(self._settings.index_name)
            self._index_client.create_or_update_index(index)

        logger.info("search_index_ensured", index_name=self._settings.index_name)

    # -- Document operations --

    def upload_documents(self, documents: list[dict[str, Any]]) -> int:
        """Upload (merge-or-upload) documents into the search index. Returns count uploaded."""
        if not documents:
            return 0
        result = self._search_client.upload_documents(documents=documents)
        succeeded = sum(1 for r in result if r.succeeded)
        logger.info("documents_uploaded", total=len(documents), succeeded=succeeded)
        return succeeded

    def delete_documents_by_file_hash(self, file_hash: str) -> None:
        """Delete all chunks belonging to a specific file hash."""
        results = self._search_client.search(
            search_text="*",
            filter=f"file_hash eq '{file_hash}'",
            select=["chunk_id"],
            top=1000,
        )
        docs_to_delete = [{"chunk_id": r["chunk_id"]} for r in results]
        if docs_to_delete:
            self._search_client.delete_documents(documents=docs_to_delete)
            logger.info("chunks_deleted", file_hash=file_hash, count=len(docs_to_delete))

    # -- Search --

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute keyword, vector, or hybrid search."""
        top = top_k or self._app_settings.retrieval_top_k
        filter_expr = _build_filter(filters) if filters else None

        vector_query = None
        search_text: str | None = query

        if mode in ("vector", "hybrid"):
            embeddings = self._openai.generate_embeddings([query])
            if embeddings:
                vector_query = VectorizedQuery(
                    vector=embeddings[0],
                    k_nearest_neighbors=top,
                    fields="content_vector",
                )

        if mode == "vector":
            search_text = None

        results = self._search_client.search(
            search_text=search_text,
            vector_queries=[vector_query] if vector_query else None,
            filter=filter_expr,
            top=top,
            select=[
                "chunk_id",
                "content",
                "source",
                "filename",
                "document_type",
                "section",
                "page_number",
            ],
        )

        return [
            {
                "chunk_id": r["chunk_id"],
                "score": r.get("@search.score", 0.0),
                "content": r["content"],
                "source": r.get("source", ""),
                "filename": r.get("filename", ""),
                "document_type": r.get("document_type", ""),
                "section": r.get("section", ""),
                "page_number": r.get("page_number"),
                "highlights": list((r.get("@search.highlights") or {}).get("content", [])),
            }
            for r in results
        ]

    def get_indexed_file_hashes(self) -> set[str]:
        """Return all distinct file_hash values currently in the index."""
        try:
            results = self._search_client.search(
                search_text="*",
                select=["file_hash"],
                top=5000,
            )
            return {r["file_hash"] for r in results if r.get("file_hash")}
        except Exception:
            # Index may not exist yet or may not have the file_hash field
            logger.warning("get_indexed_file_hashes_failed_returning_empty")
            return set()


# ---------------------------------------------------------------------------
# Azure Blob Storage client
# ---------------------------------------------------------------------------


class BlobStorageClient:
    """Wraps Azure Blob Storage for document upload/download."""

    def __init__(self, settings: AzureBlobSettings) -> None:
        self._settings = settings
        self._service_client = BlobServiceClient.from_connection_string(settings.connection_string)
        self._container_client = self._service_client.get_container_client(settings.container_name)

    def upload_blob(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload a blob and return its URL."""
        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return cast(str, blob_client.url)

    def download_blob(self, blob_name: str) -> bytes:
        """Download blob content as bytes."""
        blob_client = self._container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()

    def list_blobs(self, prefix: str = "") -> list[dict[str, Any]]:
        """List blobs with metadata."""
        blobs = self._container_client.list_blobs(name_starts_with=prefix or None)
        return [
            {
                "name": blob.name,
                "size": blob.size,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                "content_type": blob.content_settings.content_type
                if blob.content_settings
                else None,
                "etag": blob.etag,
            }
            for blob in blobs
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_file_hash(data: bytes) -> str:
    """Compute a SHA-256 hash for file change detection."""
    return hashlib.sha256(data).hexdigest()


def _build_filter(filters: dict[str, str]) -> str:
    """Build an OData filter expression from key-value pairs."""
    parts = [f"{key} eq '{value}'" for key, value in filters.items() if value]
    return " and ".join(parts) if parts else ""
