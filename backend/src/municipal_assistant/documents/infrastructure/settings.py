"""Configuration d'exposition du module Documents, lue depuis l'environnement.

Aucune valeur métier n'est fournie par défaut : sans liste MIME, taille maximale
et approbation explicite des décisions métier, les routes restent fermées.
"""
import os
import re
from dataclasses import dataclass


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _media_types(name: str) -> frozenset[str]:
    raw = os.getenv(name, "")
    return frozenset(part.lower() for part in re.split(r"[,;\s]+", raw) if part)


@dataclass(frozen=True, slots=True)
class DocumentSettings:
    database_url: str | None
    object_storage_endpoint: str | None
    object_storage_access_key: str | None
    object_storage_secret_key: str | None
    object_storage_bucket: str | None
    verify_tls: bool
    max_upload_bytes: int | None
    allowed_media_types: frozenset[str]
    policy_approved: bool

    @property
    def requested(self) -> bool:
        """True dès qu'un réglage Documents est présent dans l'environnement."""
        return bool(self.max_upload_bytes or self.allowed_media_types or self.policy_approved)

    @property
    def missing(self) -> tuple[str, ...]:
        missing = []
        if self.max_upload_bytes is None:
            missing.append("DOCUMENT_MAX_UPLOAD_BYTES")
        if not self.allowed_media_types:
            missing.append("DOCUMENT_ALLOWED_MEDIA_TYPES")
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not self.object_storage_endpoint:
            missing.append("OBJECT_STORAGE_ENDPOINT")
        if not self.object_storage_access_key:
            missing.append("RUSTFS_ACCESS_KEY")
        if not self.object_storage_secret_key:
            missing.append("RUSTFS_SECRET_KEY")
        if not self.object_storage_bucket:
            missing.append("OBJECT_STORAGE_BUCKET")
        return tuple(missing)

    def require_complete(self) -> None:
        if self.missing:
            raise ValueError("Documents configuration is incomplete: " + ", ".join(self.missing))

    @classmethod
    def from_environment(cls) -> "DocumentSettings":
        return cls(
            database_url=os.getenv("DATABASE_URL") or None,
            object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT") or None,
            object_storage_access_key=os.getenv("RUSTFS_ACCESS_KEY") or None,
            object_storage_secret_key=os.getenv("RUSTFS_SECRET_KEY") or None,
            object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET")
            or os.getenv("RUSTFS_BUCKET_DOCUMENTS") or None,
            verify_tls=_boolean("OBJECT_STORAGE_VERIFY_TLS", True),
            max_upload_bytes=_positive_int("DOCUMENT_MAX_UPLOAD_BYTES"),
            allowed_media_types=_media_types("DOCUMENT_ALLOWED_MEDIA_TYPES"),
            policy_approved=_boolean("DOCUMENT_POLICY_APPROVED", False),
        )
