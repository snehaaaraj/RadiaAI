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
        """Return deduplicated source references (one per filename) for citation."""
        seen: set[str] = set()
        refs = []
        for chunk in self.chunks:
            filename = chunk.get("filename", "")
            if filename and filename not in seen:
                seen.add(filename)
                refs.append(
                    {
                        "filename": filename,
                        "source": chunk.get("source", ""),
                        "document_type": chunk.get("document_type", ""),
                        "section": chunk.get("section", ""),
                    }
                )
        return refs

    def chunk_references(self) -> list[dict[str, Any]]:
        """
        Return per-chunk provenance, undeduplicated, for fine-grained citation.

        Unlike ``source_references`` (one entry per document), this keeps every
        retrieved chunk so a finding can be traced back to the specific page,
        section, and excerpt that produced it, not just the document it came from.
        """
        return [
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "filename": chunk.get("filename", ""),
                "section": chunk.get("section", ""),
                "page_number": chunk.get("page_number"),
                "content": chunk.get("content", ""),
            }
            for chunk in self.chunks
        ]


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
        diversify: bool = False,
    ) -> RetrievedContext:
        """
        Retrieve relevant chunks from Azure AI Search.

        When *diversify* is True, fetches extra results and ensures chunks are
        drawn from as many distinct source documents as possible so the LLM
        can cite multiple standards rather than a single dominant document.
        """
        effective_top_k = top_k or self._settings.retrieval_top_k

        if not diversify:
            results = self._search.search(
                query=query,
                mode=mode,
                top_k=effective_top_k,
                filters=filters,
            )
            return RetrievedContext(chunks=results, query=query, mode=mode)

        # Fetch a larger pool and diversify across source documents
        pool_size = max(effective_top_k * 5, 25)
        raw_results = self._search.search(
            query=query,
            mode=mode,
            top_k=pool_size,
            filters=filters,
        )

        diversified = _diversify_by_source(raw_results, effective_top_k)
        return RetrievedContext(chunks=diversified, query=query, mode=mode)

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
            temperature=temperature
            if temperature is not None
            else self._settings.azure_openai.temperature,
        )


def _diversify_by_source(results: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    """
    Select *target_count* chunks from *results* ensuring maximum document diversity.

    Strategy — round-robin across source filenames:
      1. Group results by filename, preserving score order within each group.
      2. Round-robin pick the top-scored chunk from each document in turn.
      3. Continue until *target_count* slots are filled or all results are used.

    This guarantees that if 9 documents each have a relevant chunk, the LLM
    will see at least one chunk from each document (up to target_count).
    """
    if len(results) <= target_count:
        return results

    # Group by filename, preserving original score order
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        key = r.get("filename", "unknown")
        groups.setdefault(key, []).append(r)

    selected: list[dict[str, Any]] = []
    # Track position within each group
    group_keys = list(groups.keys())
    pointers = {k: 0 for k in group_keys}

    while len(selected) < target_count:
        added_this_round = False
        for key in group_keys:
            if len(selected) >= target_count:
                break
            idx = pointers[key]
            if idx < len(groups[key]):
                selected.append(groups[key][idx])
                pointers[key] = idx + 1
                added_this_round = True
        if not added_this_round:
            break

    return selected
