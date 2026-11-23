"""Construction du service Documents à partir de la configuration validée."""

from .composition import build_document_service
from .settings import DocumentSettings


def build_configured_document_service(settings: DocumentSettings):
    settings.require_complete()
    return build_document_service(
        database_url=settings.database_url,
        object_storage_endpoint=settings.object_storage_endpoint,
        object_storage_access_key=settings.object_storage_access_key,
        object_storage_secret_key=settings.object_storage_secret_key,
        object_storage_bucket=settings.object_storage_bucket,
        max_upload_bytes=settings.max_upload_bytes,
        allowed_media_types=settings.allowed_media_types,
        verify_tls=settings.verify_tls,
    )
