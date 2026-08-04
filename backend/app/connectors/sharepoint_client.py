"""
SharePoint document library client using Microsoft Graph API.

Fetches the list of standard reference documents from the configured SharePoint
folder. Authentication uses the client-credentials (app-only) OAuth 2.0 flow via
azure-identity — no user login required.

The file listing is cached in-memory for `cache_ttl_seconds` to avoid hammering
the Graph API on every request to GET /standards.
"""

import time
from urllib.parse import quote

import httpx
from azure.identity import ClientSecretCredential

from app.core.config import SharePointSettings
from app.core.logging import get_logger
from app.models.standards_models import StandardReference

logger = get_logger(__name__)

# Graph API base URL
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Maps file extension → requirement review category tags
_EXT_CATEGORY_MAP: dict[str, list[str]] = {
    ".pdf":  ["reference"],
    ".docx": ["reference"],
    ".doc":  ["reference"],
    ".xlsx": ["reference"],
    ".xls":  ["reference"],
    ".pptx": ["reference"],
    ".txt":  ["reference"],
    ".md":   ["reference"],
}

# Category hints derived from filename keywords
_KEYWORD_CATEGORY_MAP: list[tuple[str, list[str]]] = [
    ("incose",       ["language", "verifiability", "structure"]),
    ("ears",         ["language", "structure"]),
    ("style guide",  ["language", "structure", "naming"]),
    ("style_guide",  ["language", "structure", "naming"]),
    ("cert",         ["certification", "traceability", "verification"]),
    ("do-178",       ["certification"]),
    ("do-254",       ["certification"]),
    ("arp4754",      ["certification"]),
    ("trace",        ["traceability"]),
    ("verif",        ["verifiability"]),
    ("structure",    ["structure"]),
    ("language",     ["language"]),
    ("naming",       ["naming"]),
    ("safety",       ["certification"]),
]


def _categories_from_name(name: str) -> list[str]:
    lower = name.lower()
    for keyword, cats in _KEYWORD_CATEGORY_MAP:
        if keyword in lower:
            return cats
    return ["reference"]


def _slug(name: str) -> str:
    """Create a stable key from a filename."""
    return name.lower().replace(" ", "-").replace("_", "-").split(".")[0]


class SharePointStandardsClient:
    """
    Lists documents from a SharePoint document library folder via Graph API.

    Caches results for `settings.cache_ttl_seconds` to avoid repeated calls.
    Falls back gracefully to an empty list on any error.
    """

    def __init__(self, settings: SharePointSettings) -> None:
        self._settings = settings
        self._credential: ClientSecretCredential | None = None
        self._cached_standards: list[StandardReference] = []
        self._cache_expires_at: float = 0.0
        self._site_id: str | None = None
        self._drive_id: str | None = None

        if settings.is_configured:
            self._credential = ClientSecretCredential(
                tenant_id=settings.tenant_id,
                client_id=settings.client_id,
                client_secret=settings.client_secret,
            )

    def _get_token(self) -> str:
        assert self._credential is not None
        token = self._credential.get_token("https://graph.microsoft.com/.default")
        return token.token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

    def _resolve_site_id(self, client: httpx.Client) -> str:
        """Resolve the Graph site ID for the configured SharePoint site URL."""
        # Extract hostname and path from site_url
        # e.g. https://radia99.sharepoint.com/sites/sysengint
        url = self._settings.site_url.rstrip("/")
        # Strip scheme
        without_scheme = url.split("://", 1)[-1]
        parts = without_scheme.split("/", 1)
        hostname = parts[0]
        site_path = parts[1] if len(parts) > 1 else ""

        graph_url = f"{_GRAPH_BASE}/sites/{hostname}:/{site_path}"
        resp = client.get(graph_url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()["id"]

    def _resolve_drive_id(self, client: httpx.Client, site_id: str) -> str:
        """Resolve the drive (document library) ID by name."""
        resp = client.get(
            f"{_GRAPH_BASE}/sites/{site_id}/drives",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        drives: list[dict] = resp.json().get("value", [])
        target = self._settings.drive_name.lower()
        for drive in drives:
            if drive.get("name", "").lower() == target:
                return drive["id"]
        # If exact match fails, log available drives and use first one
        names = [d.get("name") for d in drives]
        logger.warning(
            "sharepoint_drive_not_found",
            target=self._settings.drive_name,
            available=names,
        )
        if drives:
            return drives[0]["id"]
        raise ValueError(f"No drives found on site {site_id}")

    def _list_folder_children(self, client: httpx.Client, drive_id: str) -> list[dict]:
        """Return the Graph API items from the configured standards folder."""
        folder = self._settings.standards_folder
        # URL-encode the path segments but keep slashes
        encoded_folder = "/".join(quote(segment) for segment in folder.split("/"))
        url = f"{_GRAPH_BASE}/drives/{drive_id}/root:/{encoded_folder}:/children"
        resp = client.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def _item_to_standard(self, item: dict) -> StandardReference | None:
        """Convert a Graph API driveItem to a StandardReference. Returns None for folders."""
        if "folder" in item:
            return None  # skip subfolders
        name: str = item.get("name", "")
        ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        web_url: str = item.get("webUrl", "")
        last_modified: str = item.get("lastModifiedDateTime", "")
        size: int = item.get("size", 0)

        # Strip extension for display name
        display_name = name.rsplit(".", 1)[0] if "." in name else name

        return StandardReference(
            key=_slug(name),
            name=display_name,
            version="1.0.0",
            source="SharePoint",
            categories=_categories_from_name(name),
            description=f"{ext.upper().lstrip('.')} document from SharePoint standards library.",
            sharepoint_url=web_url,
            file_type=ext.lstrip(".").upper() if ext else None,
            last_modified=last_modified[:10] if last_modified else None,  # date only
            file_size_bytes=size,
        )

    def fetch_standards(self) -> list[StandardReference]:
        """
        Return standards from SharePoint, using the in-memory cache if still fresh.
        Returns an empty list (and logs) if SharePoint is not configured or fails.
        """
        if not self._settings.is_configured:
            logger.info("sharepoint_not_configured", reason="credentials missing")
            return []

        now = time.monotonic()
        if self._cached_standards and now < self._cache_expires_at:
            logger.debug("sharepoint_standards_cache_hit")
            return self._cached_standards

        try:
            with httpx.Client() as client:
                if self._site_id is None:
                    self._site_id = self._resolve_site_id(client)
                    logger.info("sharepoint_site_resolved", site_id=self._site_id)
                if self._drive_id is None:
                    self._drive_id = self._resolve_drive_id(client, self._site_id)
                    logger.info("sharepoint_drive_resolved", drive_id=self._drive_id)

                items = self._list_folder_children(client, self._drive_id)

            standards = [s for item in items if (s := self._item_to_standard(item)) is not None]
            standards.sort(key=lambda s: s.name.lower())

            self._cached_standards = standards
            self._cache_expires_at = now + self._settings.cache_ttl_seconds

            logger.info("sharepoint_standards_fetched", count=len(standards))
            return standards

        except Exception:
            logger.exception("sharepoint_fetch_failed")
            # Return stale cache if available, otherwise empty list
            return self._cached_standards
