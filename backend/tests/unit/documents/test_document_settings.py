from types import SimpleNamespace

import pytest

from municipal_assistant.accounts.service import DatabaseDocumentAccessPolicy
from municipal_assistant.app import create_app
from municipal_assistant.documents.infrastructure import activation
from municipal_assistant.documents.infrastructure.settings import DocumentSettings

DOCUMENT_ENV = (
    "DOCUMENT_MAX_UPLOAD_BYTES", "DOCUMENT_ALLOWED_MEDIA_TYPES", "DOCUMENT_POLICY_APPROVED",
    "OBJECT_STORAGE_ENDPOINT", "OBJECT_STORAGE_BUCKET", "RUSTFS_BUCKET_DOCUMENTS",
    "RUSTFS_ACCESS_KEY", "RUSTFS_SECRET_KEY", "OBJECT_STORAGE_VERIFY_TLS",
)


def clear_document_environment(monkeypatch):
    for name in DOCUMENT_ENV:
        monkeypatch.delenv(name, raising=False)


def complete_environment(monkeypatch, *, approved=True):
    clear_document_environment(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("DOCUMENT_MAX_UPLOAD_BYTES", "4096")
    monkeypatch.setenv("DOCUMENT_ALLOWED_MEDIA_TYPES", "application/pdf,image/png")
    monkeypatch.setenv("DOCUMENT_POLICY_APPROVED", "true" if approved else "false")
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT", "http://127.0.0.1:9000")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "municipal-documents")
    monkeypatch.setenv("RUSTFS_ACCESS_KEY", "test-access")
    monkeypatch.setenv("RUSTFS_SECRET_KEY", "test-secret")


def test_documents_stay_closed_without_configuration(monkeypatch):
    clear_document_environment(monkeypatch)

    assert DocumentSettings.from_environment().requested is False
    assert create_app().state.document_service is None


def test_media_types_are_normalized(monkeypatch):
    clear_document_environment(monkeypatch)
    monkeypatch.setenv("DOCUMENT_ALLOWED_MEDIA_TYPES", " Application/PDF ; image/PNG ,")

    settings = DocumentSettings.from_environment()

    assert settings.allowed_media_types == frozenset({"application/pdf", "image/png"})


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_invalid_upload_size_is_rejected(monkeypatch, value):
    clear_document_environment(monkeypatch)
    monkeypatch.setenv("DOCUMENT_MAX_UPLOAD_BYTES", value)

    with pytest.raises(ValueError):
        DocumentSettings.from_environment()


def test_approval_without_upload_policy_is_rejected(monkeypatch):
    clear_document_environment(monkeypatch)
    monkeypatch.setenv("DOCUMENT_POLICY_APPROVED", "true")
    monkeypatch.setenv("DOCUMENT_MAX_UPLOAD_BYTES", "1024")

    with pytest.raises(ValueError, match="DOCUMENT_ALLOWED_MEDIA_TYPES"):
        activation.build_configured_document_service(DocumentSettings.from_environment())


def test_builder_receives_parsed_settings(monkeypatch):
    complete_environment(monkeypatch)
    recorded = {}

    def fake_builder(**kwargs):
        recorded.update(kwargs)
        return "document-service"

    monkeypatch.setattr(activation, "build_document_service", fake_builder)

    service = activation.build_configured_document_service(DocumentSettings.from_environment())

    assert service == "document-service"
    assert recorded["max_upload_bytes"] == 4096
    assert recorded["allowed_media_types"] == frozenset({"application/pdf", "image/png"})
    assert recorded["object_storage_endpoint"] == "http://127.0.0.1:9000"
    assert recorded["verify_tls"] is True


def test_create_app_activates_documents_when_policy_is_approved(monkeypatch):
    complete_environment(monkeypatch)
    fake_service = SimpleNamespace(
        validator=SimpleNamespace(max_bytes=4096,
                                  allowed_media_types=frozenset({"application/pdf"})),
        access=DatabaseDocumentAccessPolicy(lambda: None),
    )
    monkeypatch.setattr("municipal_assistant.app.build_configured_document_service",
                        lambda settings: fake_service)

    app = create_app()

    assert app.state.document_service is fake_service
    assert app.state.max_upload_bytes == 4096


def test_create_app_keeps_documents_closed_without_approval(monkeypatch):
    complete_environment(monkeypatch, approved=False)

    def fail_builder(settings):
        raise AssertionError("Documents must not be built before business approval")

    monkeypatch.setattr("municipal_assistant.app.build_configured_document_service", fail_builder)

    assert create_app().state.document_service is None


def test_create_app_rejects_approval_without_upload_policy(monkeypatch):
    complete_environment(monkeypatch)
    monkeypatch.delenv("DOCUMENT_ALLOWED_MEDIA_TYPES")

    with pytest.raises(ValueError, match="DOCUMENT_ALLOWED_MEDIA_TYPES"):
        create_app()
