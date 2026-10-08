"""Encrypted, per-user storage of linked Jama API credentials.

Each Entra user's Jama client ID / secret is encrypted with Fernet (AES-128-CBC +
HMAC-SHA256) and stored as one blob named by a SHA-256 hash of the user's
tenant-qualified object id, in a container dedicated to user secrets.

The encrypted payload also embeds the owner's subject key and is checked on
decrypt, so a blob copied onto another user's name cannot be used by them.
Several comma-separated keys may be configured for rotation: the first key
encrypts and every key decrypts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Protocol

from azure.core.exceptions import ResourceNotFoundError
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import BaseModel

from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import JamaApiCredentials
from radia_ai.features.jama_requirement_reviewer.models.jama_models import JamaUserProfile

logger = get_logger(__name__)

_BLOB_PREFIX = "jama-links/"
_SCHEMA_VERSION = 1


class _BlobStore(Protocol):
    def upload_blob(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str: ...

    def download_blob(self, blob_name: str) -> bytes: ...

    def delete_blob(self, blob_name: str) -> None: ...


class JamaAccountLink(BaseModel):
    """Non-secret metadata about a user's linked Jama account."""

    jama_user_id: int
    jama_username: str = ""
    jama_email: str = ""
    jama_display_name: str = ""
    linked_at: str


class _StoredLink(JamaAccountLink):
    version: int = _SCHEMA_VERSION
    ciphertext: str


def _build_cipher(encryption_keys: str) -> MultiFernet:
    keys = [key.strip() for key in encryption_keys.split(",") if key.strip()]
    if not keys:
        raise ConfigurationError("JAMA_CREDENTIAL_ENCRYPTION_KEY is not configured.")
    try:
        return MultiFernet([Fernet(key.encode()) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ConfigurationError(
            "JAMA_CREDENTIAL_ENCRYPTION_KEY must be one or more comma-separated Fernet keys."
        ) from exc


class JamaCredentialRepository:
    """Blob-backed store for each user's encrypted Jama API credentials."""

    def __init__(self, blob_store: _BlobStore, encryption_keys: str) -> None:
        self._blob = blob_store
        self._cipher = _build_cipher(encryption_keys)

    @staticmethod
    def _blob_name(subject_key: str) -> str:
        digest = hashlib.sha256(subject_key.encode()).hexdigest()
        return f"{_BLOB_PREFIX}{digest}.json"

    def _read(self, subject_key: str) -> _StoredLink | None:
        # Only a missing blob means "not linked"; storage outages must surface as errors
        # rather than silently asking the user to re-link.
        try:
            data = self._blob.download_blob(self._blob_name(subject_key))
        except (ResourceNotFoundError, KeyError):
            return None
        try:
            return _StoredLink.model_validate_json(data)
        except ValueError:
            logger.warning("jama_link_record_corrupt")
            return None

    def save(
        self,
        subject_key: str,
        credentials: JamaApiCredentials,
        profile: JamaUserProfile,
    ) -> JamaAccountLink:
        secret = json.dumps(
            {
                "sub": subject_key,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            }
        ).encode()
        record = _StoredLink(
            jama_user_id=profile.id,
            jama_username=profile.username,
            jama_email=profile.email,
            jama_display_name=profile.display_name,
            linked_at=datetime.now(UTC).isoformat(),
            ciphertext=self._cipher.encrypt(secret).decode(),
        )
        self._blob.upload_blob(
            self._blob_name(subject_key),
            record.model_dump_json().encode(),
            content_type="application/json",
        )
        return JamaAccountLink.model_validate(record.model_dump(exclude={"ciphertext", "version"}))

    def get_link(self, subject_key: str) -> JamaAccountLink | None:
        record = self._read(subject_key)
        if record is None:
            return None
        return JamaAccountLink.model_validate(record.model_dump(exclude={"ciphertext", "version"}))

    def get_credentials(self, subject_key: str) -> JamaApiCredentials | None:
        """Decrypt the user's credentials, or None when absent or undecryptable."""
        record = self._read(subject_key)
        if record is None:
            return None
        try:
            payload = json.loads(self._cipher.decrypt(record.ciphertext.encode()))
        except (InvalidToken, ValueError):
            # Typically the encryption key was rotated out; the user must re-link.
            logger.error("jama_link_decrypt_failed")
            return None
        if payload.get("sub") != subject_key:
            logger.error("jama_link_subject_mismatch")
            return None
        return JamaApiCredentials(
            client_id=str(payload["client_id"]), client_secret=str(payload["client_secret"])
        )

    def delete(self, subject_key: str) -> bool:
        if self._read(subject_key) is None:
            return False
        self._blob.delete_blob(self._blob_name(subject_key))
        return True
