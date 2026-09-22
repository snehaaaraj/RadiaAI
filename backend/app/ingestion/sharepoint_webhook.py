"""
SharePoint change-notification webhook - auto-triggers ingestion when documents change.

Manages the lifecycle of a Microsoft Graph subscription on the SharePoint standards
folder so that document changes trigger `IngestionService.ingest_from_sharepoint()`
automatically, instead of relying solely on the manual "Ingest Documents" button.

Subscription state (id, expiration, clientState secret) is persisted as a small JSON
blob in Azure Blob Storage so it survives across stateless serverless invocations.

Renewal strategy:
  - Lazy: every incoming webhook notification opportunistically renews the
    subscription if it is close to expiring.
  - Fallback: `ensure_subscription_throttled()` is called from the /standards
    endpoint (which the frontend already polls on page load) so a quiet SharePoint
    period doesn't silently let the subscription expire forever.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
from azure.core.exceptions import ResourceNotFoundError

from app.core.azure_clients import BlobStorageClient
from app.core.config import SharePointSettings
from app.core.logging import get_logger
from app.ingestion.service import IngestionService
from app.ingestion.status_store import IngestionStatusStore
from radia_ai.features.jama_requirement_reviewer.connectors.sharepoint_client import (
    SharePointStandardsClient,
)

logger = get_logger(__name__)

_GRAPH_SUBSCRIPTIONS_URL = "https://graph.microsoft.com/v1.0/subscriptions"

# Graph subscription lifetimes vary by resource type (some cap as low as ~3 days).
# Requesting a conservative 3-day window keeps us well within limits for driveItem
# resources regardless of exact per-resource caps.
_SUBSCRIPTION_LIFETIME = timedelta(days=3)
# Renew once less than this much time remains before expiry.
_RENEWAL_WINDOW = timedelta(hours=24)
# Minimum time between fallback checks triggered from the /standards endpoint, to
# avoid a Blob Storage + Graph round-trip on every single page load.
_FALLBACK_CHECK_INTERVAL_SECONDS = 900  # 15 minutes

_STATE_BLOB_NAME = "system/sharepoint-webhook-subscription.json"

# Graph supports change notifications on the drive root, but not on an
# arbitrary folder driveItem. The handler rescans the configured folder after
# any change in the document library.
_CHANGE_TYPE = "updated"


def _graph_timestamp(value: datetime) -> str:
    """Format a UTC timestamp in the Graph API's required ``Z`` form."""
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class SharePointWebhookService:
    """Creates, renews, and validates the Graph change-notification subscription."""

    def __init__(
        self,
        settings: SharePointSettings,
        sharepoint_client: SharePointStandardsClient,
        blob_client: BlobStorageClient,
        ingestion_service: IngestionService,
        status_store: IngestionStatusStore | None = None,
    ) -> None:
        self._settings = settings
        self._sharepoint = sharepoint_client
        self._blob = blob_client
        self._ingestion = ingestion_service
        self._status_store = status_store
        self._last_fallback_check: float = 0.0

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> dict[str, Any] | None:
        try:
            data = self._blob.download_blob(_STATE_BLOB_NAME)
            return cast(dict[str, Any], json.loads(data))
        except ResourceNotFoundError:
            return None
        except Exception:
            logger.exception("sharepoint_webhook_state_load_failed")
            return None

    def _save_state(self, state: dict[str, Any]) -> None:
        self._blob.upload_blob(
            _STATE_BLOB_NAME,
            json.dumps(state).encode("utf-8"),
            content_type="application/json",
        )

    # ------------------------------------------------------------------
    # Subscription lifecycle
    # ------------------------------------------------------------------

    def ensure_subscription(self, *, force: bool = False) -> None:
        """
        Ensure a valid, non-expiring-soon Graph subscription exists.

        Creates a new subscription if none exists (or the stored one is gone/expired),
        renews it if it is close to expiring, and otherwise does nothing.
        """
        if not self._settings.is_webhook_configured:
            return

        state = self._load_state()
        now = datetime.now(UTC)

        if state and not force:
            expires_at = datetime.fromisoformat(state["expiration"])
            if expires_at - now > _RENEWAL_WINDOW:
                return  # still fresh, nothing to do
            try:
                self._renew(state, now)
                return
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.warning("sharepoint_webhook_subscription_missing_recreating")
                else:
                    logger.exception("sharepoint_webhook_renew_failed")
                    return  # keep using the stale state rather than losing it

        if state and force:
            self._delete_best_effort(state["subscription_id"])

        try:
            self._create(now)
        except Exception:
            logger.exception("sharepoint_webhook_subscription_create_failed")

    def ensure_subscription_throttled(self) -> None:
        """Fallback check invoked from request paths (e.g. GET /standards)."""
        if not self._settings.is_webhook_configured:
            return
        now = time.monotonic()
        if now - self._last_fallback_check < _FALLBACK_CHECK_INTERVAL_SECONDS:
            return
        self._last_fallback_check = now
        self.ensure_subscription()

    def _create(self, now: datetime) -> None:
        drive_id, _folder_item_id = self._sharepoint.resolve_folder_context()
        client_state = secrets.token_urlsafe(32)
        expiration = now + _SUBSCRIPTION_LIFETIME
        notification_url = self._notification_url()

        body = {
            "changeType": _CHANGE_TYPE,
            "notificationUrl": notification_url,
            "resource": f"/drives/{drive_id}/root",
            "expirationDateTime": _graph_timestamp(expiration),
            "clientState": client_state,
        }
        with httpx.Client() as client:
            resp = client.post(
                _GRAPH_SUBSCRIPTIONS_URL,
                headers={**self._sharepoint.auth_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            if resp.is_error:
                logger.error(
                    "sharepoint_webhook_graph_subscription_rejected",
                    status_code=resp.status_code,
                    response_body=resp.text[:2000],
                    notification_url=notification_url,
                    resource=body["resource"],
                    expiration=body["expirationDateTime"],
                )
            resp.raise_for_status()
            subscription = resp.json()

        self._save_state(
            {
                "subscription_id": subscription["id"],
                "expiration": subscription["expirationDateTime"],
                "client_state": client_state,
                "resource": body["resource"],
                "notification_url": notification_url,
            }
        )
        logger.info(
            "sharepoint_webhook_subscription_created",
            subscription_id=subscription["id"],
            expiration=subscription["expirationDateTime"],
        )

    def _renew(self, state: dict[str, Any], now: datetime) -> None:
        subscription_id = state["subscription_id"]
        expiration = now + _SUBSCRIPTION_LIFETIME

        with httpx.Client() as client:
            resp = client.patch(
                f"{_GRAPH_SUBSCRIPTIONS_URL}/{subscription_id}",
                headers={**self._sharepoint.auth_headers(), "Content-Type": "application/json"},
                json={"expirationDateTime": _graph_timestamp(expiration)},
                timeout=30,
            )
            resp.raise_for_status()
            subscription = resp.json()

        state["expiration"] = subscription["expirationDateTime"]
        self._save_state(state)
        logger.info(
            "sharepoint_webhook_subscription_renewed",
            subscription_id=subscription_id,
            expiration=state["expiration"],
        )

    def _delete_best_effort(self, subscription_id: str) -> None:
        """Best-effort delete of a stale subscription before creating a replacement."""
        try:
            with httpx.Client() as client:
                resp = client.delete(
                    f"{_GRAPH_SUBSCRIPTIONS_URL}/{subscription_id}",
                    headers=self._sharepoint.auth_headers(),
                    timeout=15,
                )
                if resp.status_code not in (200, 202, 204, 404):
                    resp.raise_for_status()
        except Exception:
            logger.warning("sharepoint_webhook_subscription_delete_failed", exc_info=True)

    def _notification_url(self) -> str:
        base = self._settings.webhook_public_base_url.rstrip("/")
        return f"{base}/api/v1/ingest/webhook"

    # ------------------------------------------------------------------
    # Notification handling
    # ------------------------------------------------------------------

    def handle_notification(self, notifications: list[dict[str, Any]]) -> bool:
        """
        Validate incoming change notifications and trigger re-ingestion.

        Returns True if at least one notification carried a valid clientState and
        ingestion was triggered; False otherwise (e.g. no stored subscription state,
        or every notification failed clientState verification).
        """
        state = self._load_state()
        if state is None:
            logger.warning("sharepoint_webhook_notification_without_subscription_state")
            return False

        expected_client_state = state.get("client_state")
        valid = any(n.get("clientState") == expected_client_state for n in notifications)

        if not valid:
            logger.warning("sharepoint_webhook_notification_client_state_mismatch")
            return False

        logger.info("sharepoint_webhook_notification_received", count=len(notifications))

        try:
            result = self._ingestion.ingest_from_sharepoint()
            self._record_status(result)
        except Exception as exc:
            logger.exception("sharepoint_webhook_triggered_ingestion_failed")
            self._record_status({"status": "error", "message": str(exc)})

        # Opportunistically renew if we're getting close to expiry.
        self.ensure_subscription()
        return True

    def _record_status(self, result: dict[str, Any]) -> None:
        """Persist the ingestion outcome so the frontend can poll for it."""
        if self._status_store is None:
            return
        processed = result.get("processed", 0)
        skipped = result.get("skipped", 0)
        failed = result.get("failed", 0)
        outcome = self._status_store.outcome_from_result(result)
        message = result.get(
            "message",
            f"Processed: {processed}, Skipped (unchanged): {skipped}, Failed: {failed}",
        )
        self._status_store.record(
            source="sharepoint",
            trigger="webhook",
            outcome=outcome,
            processed=processed,
            skipped=skipped,
            failed=failed,
            message=message,
        )
