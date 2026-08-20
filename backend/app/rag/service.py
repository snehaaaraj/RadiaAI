"""
RAG (Retrieval-Augmented Generation) service.

Provides the bridge between Azure AI Search retrieval and Azure OpenAI
chat completions. Used by the reviewer modules to ground their analysis
in the actual indexed standards documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.azure_clients import OpenAIClient, SearchService
from app.core.config import AppSettings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedContext:
    """Bundle of retrieved chunks from the search index."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    mode: str = "hybrid"

    @property
    def has_context(self) -> bool:
        return len(self.chunks) > 0

    def format_for_prompt(self) -> str:
        """Format retrieved chunks as numbered context blocks for an LLM prompt."""
        if not self.chunks:
            return "No relevant standards documents were found in the knowledge base."

        parts = []
        for i, chunk in enumerate(self.chunks, 1):
            source = chunk.get("filename", chunk.get("source", "unknown"))
            section = chunk.get("section", "")
            content = chunk.get("content", "")
            header = f"[Source {i}: {source}"
            if section:
                header += f" — {section}"
            header += "]"
            parts.append(f"{header}\n{content}")

        return "\n\n---\n\n".join(parts)

    def source_references(self) -> list[dict[str, str]]:
        """Return deduplicated source references for citation."""
        seen: set[str] = set()
        refs = []
        for chunk in self.chunks:
            filename = chunk.get("filename", "")
            if filename and filename not in seen:
                seen.add(filename)
                refs.append({
                    "filename": filename,
                    "source": chunk.get("source", ""),
                    "document_type": chunk.get("document_type", ""),
                    "section": chunk.get("section", ""),
                })
        return refs


class RAGService:
    """Retrieves relevant context from the search index and optionally generates completions."""

    def __init__(
        self,
        settings: AppSettings,
        openai_client: OpenAIClient,
        search_service: SearchService,
    ) -> None:
        self._settings = settings
        self._openai = openai_client
        self._search = search_service

    def retrieve(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> RetrievedContext:
        """Retrieve relevant chunks from Azure AI Search."""
        results = self._search.search(
            query=query,
            mode=mode,
            top_k=top_k or self._settings.retrieval_top_k,
            filters=filters,
        )
        return RetrievedContext(chunks=results, query=query, mode=mode)

    def generate_with_context(
        self,
        system_prompt: str,
        user_message: str,
        context: RetrievedContext,
        *,
        temperature: float | None = None,
    ) -> str:
        """
        Run a chat completion grounded in retrieved context.

        Injects the retrieved standards chunks into the system prompt so the
        LLM's response is grounded in actual indexed documents rather than
        parametric knowledge.
        """
        context_text = context.format_for_prompt()
        full_system = (
            f"{system_prompt}\n\n"
            f"## Retrieved Standards Context\n\n"
            f"Use ONLY the following excerpts from indexed standards documents to "
            f"support your analysis. Cite specific sources when making recommendations.\n\n"
            f"{context_text}"
        )

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_message},
        ]

        return self._openai.chat_completion(
            messages,
            temperature=temperature if temperature is not None else self._settings.azure_openai.temperature,
        )
