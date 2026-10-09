"""Load the Skillz package from SharePoint with caching and level applicability."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.skillz.package import (
    SkillzPackage,
    parse_skillz_zip,
)

if TYPE_CHECKING:
    from app.core.config import SkillzSettings

logger = get_logger(__name__)


class SkillzSource(Protocol):
    """Anything that can fetch the raw Skillz package bytes and its web URL."""

    def download_drive_file(self, path: str) -> tuple[bytes, str | None]: ...


@dataclass(frozen=True)
class SkillzLoadResult:
    """A loaded package, or the reason no package is available."""

    package: SkillzPackage | None
    error: str = ""


class SkillzService:
    """
    Provides the authoritative Skillz package for requirement levels it governs.

    A successfully parsed package is cached for ``cache_ttl_seconds``. When a
    refresh fails, the last good package is served rather than silently dropping
    the authoritative rules; its revision and content hash remain on every
    recommendation built from it. A failed refresh is not retried for
    ``FAILURE_RETRY_SECONDS``, so an outage does not make every review wait on
    SharePoint again.

    Refreshes are single-flight: one caller downloads while concurrent callers
    that already have a package are served the stale copy without blocking.
    """

    FAILURE_RETRY_SECONDS = 60.0

    def __init__(self, settings: SkillzSettings, source: SkillzSource | None) -> None:
        self._settings = settings
        self._source = source
        self._state_lock = threading.Lock()
        self._refresh_lock = threading.Lock()
        self._package: SkillzPackage | None = None
        self._error = ""
        self._expires_at = 0.0

    def applies_to(self, requirement_level: str | None) -> bool:
        """True when this Skillz package governs requirements at *requirement_level*."""
        if not self._settings.enabled or not requirement_level:
            return False
        level = requirement_level.strip().lower()
        return level in {
            configured.strip().lower() for configured in self._settings.applicable_levels
        }

    def load(self) -> SkillzLoadResult:
        """Return the current package, refreshing it when the cache has expired."""
        cached = self._cached()
        if cached is not None:
            return cached

        # Callers that already hold a package never wait on a refresh in progress.
        if not self._refresh_lock.acquire(blocking=self._package is None):
            return SkillzLoadResult(package=self._package)
        try:
            cached = self._cached()
            if cached is not None:
                return cached
            return self._refresh()
        finally:
            self._refresh_lock.release()

    def _cached(self) -> SkillzLoadResult | None:
        """The current result while it is fresh or within the failure back-off window."""
        with self._state_lock:
            if time.monotonic() < self._expires_at:
                return SkillzLoadResult(
                    package=self._package, error="" if self._package else self._error
                )
        return None

    def _refresh(self) -> SkillzLoadResult:
        if self._source is None:
            return self._record_failure("SharePoint is not configured for Skillz.")

        try:
            data, web_url = self._source.download_drive_file(self._settings.zip_path)
            package = parse_skillz_zip(data, source_url=web_url)
        except Exception as exc:
            logger.exception("skillz_package_load_failed", path=self._settings.zip_path)
            return self._record_failure(f"Skillz rules could not be loaded ({type(exc).__name__}).")

        with self._state_lock:
            self._package = package
            self._error = ""
            self._expires_at = time.monotonic() + self._settings.cache_ttl_seconds
        logger.info(
            "skillz_package_loaded",
            name=package.name,
            revision=package.revision,
            content_hash=package.content_hash,
            rule_count=len(package.rules),
        )
        return SkillzLoadResult(package=package)

    def _record_failure(self, error: str) -> SkillzLoadResult:
        retry_after = min(float(self._settings.cache_ttl_seconds), self.FAILURE_RETRY_SECONDS)
        with self._state_lock:
            self._error = error
            self._expires_at = time.monotonic() + retry_after
            package = self._package
        if package is not None:
            logger.warning("skillz_package_serving_stale_copy", revision=package.revision)
            return SkillzLoadResult(package=package)
        return SkillzLoadResult(package=None, error=error)
