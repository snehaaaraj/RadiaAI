"""Cross-system linking, queried live against each connector.

There is deliberately **no datastore here**. Every call reads the source
systems directly, so the answer is always current and nothing has to be kept in
sync. The cost is that this is a read amplifier: one call fans out to several
API requests, and there is no way to ask "what points *at* this item" in
systems that do not index inbound links.

A persisted link graph is the obvious next step and is explicitly out of scope
for this pass - see the README.

Two sources of relationship:

  - **Native** (always on): links the source system records as first-class
    data. Jira ``issuelinks`` and parent, Jama upstream/downstream
    relationships, Confluence page links in the body.
  - **Text** (opt-in): identifiers found in prose and then resolved against
    Jira and Jama. Heuristic, hence off by default.
"""

import asyncio

from mcp_radia.connectors.confluence import ConfluenceClient
from mcp_radia.connectors.errors import ConnectorError, ItemNotFoundError
from mcp_radia.connectors.genesys import GenesysClient
from mcp_radia.connectors.jama import JamaClient
from mcp_radia.connectors.jira import JiraClient
from mcp_radia.linking.models import RelatedItem, RelatedItemsResult
from mcp_radia.linking.references import extract_candidate_keys, texts_from_mapping
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Cap on how many text-found keys we try to resolve. Each one costs at least
#: one API call, so an unbounded scan of a long page could fire hundreds.
MAX_TEXT_LOOKUPS = 10


class LinkingService:
    """Answers "what is related to this item" by querying connectors live."""

    def __init__(
        self,
        *,
        jama: JamaClient,
        jira: JiraClient,
        confluence: ConfluenceClient,
        genesys: GenesysClient | None = None,
    ) -> None:
        self._jama = jama
        self._jira = jira
        self._confluence = confluence
        self._genesys = genesys

    async def list_related_items(
        self,
        system: str,
        item_id: str,
        *,
        include_text_references: bool = False,
    ) -> RelatedItemsResult:
        """Return everything related to ``item_id`` in ``system``."""
        normalized = system.strip().lower()
        if normalized == "jira":
            return await self._from_jira(item_id, include_text_references)
        if normalized == "jama":
            return await self._from_jama(item_id, include_text_references)
        if normalized == "confluence":
            return await self._from_confluence(item_id, include_text_references)
        if normalized == "genesys":
            return RelatedItemsResult(
                system="genesys",
                item_id=item_id,
                notes=[
                    "The GENESYS connector is a placeholder with no implementation yet, so "
                    "its relationships cannot be read. Nothing was queried."
                ],
            )
        raise ValueError(
            f"Unknown system {system!r}. Expected one of: jama, jira, confluence, genesys."
        )

    # -- per-system native links --------------------------------------------

    async def _from_jira(self, issue_key: str, include_text: bool) -> RelatedItemsResult:
        issue = await self._jira.get_issue(issue_key)
        related = [
            RelatedItem(
                system="jira",
                id=None,
                key=link.key,
                title=link.summary,
                relation=link.type,
                discovered_via="native",
                web_url=self._jira_url(link.key),
            )
            for link in issue.links
        ]
        if issue.parent_key:
            related.append(
                RelatedItem(
                    system="jira",
                    key=issue.parent_key,
                    title="",
                    relation="parent",
                    discovered_via="native",
                    web_url=self._jira_url(issue.parent_key),
                )
            )

        result = RelatedItemsResult(
            system="jira",
            item_id=issue.key,
            item_title=issue.summary,
            related=related,
        )
        if include_text:
            await self._add_text_references(
                result,
                texts=[issue.summary, issue.description],
                own_key=issue.key,
            )
        return result

    async def _from_jama(self, item_id: str, include_text: bool) -> RelatedItemsResult:
        try:
            numeric_id = int(item_id.strip())
        except ValueError as exc:
            raise ValueError(
                f"Jama item ids are numeric; got {item_id!r}. "
                "Use the numeric id, not the document key."
            ) from exc

        item = await self._jama.get_item(numeric_id)
        links = await self._jama.get_related_items(numeric_id)
        related = [
            RelatedItem(
                system="jama",
                id=str(link.item.id),
                key=link.item.document_key,
                title=link.item.name,
                relation=link.direction,
                discovered_via="native",
                web_url=link.item.web_url,
            )
            for link in links
        ]

        result = RelatedItemsResult(
            system="jama",
            item_id=str(item.id),
            item_title=item.name,
            related=related,
        )
        if include_text:
            # Custom fields are where Jama cross-references usually hide.
            await self._add_text_references(
                result,
                texts=[item.name, item.description, *texts_from_mapping(item.fields)],
                own_key=item.document_key,
            )
        return result

    async def _from_confluence(self, page_id: str, include_text: bool) -> RelatedItemsResult:
        page = await self._confluence.get_page(page_id)
        related = [
            RelatedItem(
                system="confluence",
                id=None,
                key=None,
                title=link.title,
                relation="links-to",
                discovered_via="native",
                web_url=link.url,
            )
            for link in page.outbound_links
        ]

        result = RelatedItemsResult(
            system="confluence",
            item_id=page.id,
            item_title=page.title,
            related=related,
            notes=[
                "Confluence has no supported way to query inbound links, so these are "
                "outbound references from this page only."
            ],
        )
        if include_text:
            await self._add_text_references(result, texts=[page.title, page.body], own_key=None)
        return result

    # -- text references -----------------------------------------------------

    async def _add_text_references(
        self,
        result: RelatedItemsResult,
        *,
        texts: list[str | None],
        own_key: str | None,
    ) -> None:
        """Find identifiers in prose, resolve them, and append what matched."""
        already_linked = {item.key for item in result.related if item.key}
        candidates = [
            key
            for key in extract_candidate_keys(*texts, exclude=own_key)
            if key not in already_linked
        ]
        if not candidates:
            return

        if len(candidates) > MAX_TEXT_LOOKUPS:
            result.notes.append(
                f"Found {len(candidates)} identifiers in text but only resolved the first "
                f"{MAX_TEXT_LOOKUPS}."
            )
            candidates = candidates[:MAX_TEXT_LOOKUPS]

        resolved = await asyncio.gather(
            *(self._resolve_key(key) for key in candidates), return_exceptions=True
        )

        problems: set[str] = set()
        for key, outcome in zip(candidates, resolved, strict=True):
            if isinstance(outcome, RelatedItem):
                result.related.append(outcome)
            elif isinstance(outcome, ConnectorError):
                # Do not let one unconfigured system look like "no match".
                problems.add(f"{outcome.system}: {outcome.message}")
            elif isinstance(outcome, BaseException):
                problems.add(str(outcome))
            else:
                result.related.append(
                    RelatedItem(
                        system="unresolved",
                        key=key,
                        title="",
                        relation="text-reference",
                        discovered_via="text",
                    )
                )
        result.notes.extend(
            f"Text reference lookup was incomplete - {problem}" for problem in sorted(problems)
        )

    async def _resolve_key(self, key: str) -> RelatedItem | None:
        """Resolve a key-shaped string to a real item, or ``None`` if nothing matches.

        Tries Jira first because a key maps directly to an issue there, then
        Jama, where the same shape is a document key and needs a search. A
        genuine 404 means "not this system"; anything else is a real problem
        and is raised so the caller can report it rather than silently
        downgrading it to "no match".
        """
        try:
            issue = await self._jira.get_issue(key)
        except ItemNotFoundError:
            pass
        except ConnectorError:
            raise
        else:
            return RelatedItem(
                system="jira",
                key=issue.key,
                title=issue.summary,
                relation="text-reference",
                discovered_via="text",
                web_url=issue.web_url,
            )

        try:
            found = await self._jama.search(query=key, max_results=5)
        except ItemNotFoundError:
            return None
        except ConnectorError:
            raise

        for candidate in found.results:
            if (candidate.document_key or "").upper() == key.upper():
                return RelatedItem(
                    system="jama",
                    id=str(candidate.id),
                    key=candidate.document_key,
                    title=candidate.name,
                    relation="text-reference",
                    discovered_via="text",
                    web_url=candidate.web_url,
                )
        return None

    # -- helpers -------------------------------------------------------------

    def _jira_url(self, key: str) -> str | None:
        base = self._jira.settings.base
        return f"{base}/browse/{key}" if base and key else None
