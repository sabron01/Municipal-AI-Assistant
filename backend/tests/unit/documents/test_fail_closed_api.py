from types import SimpleNamespace
from fastapi.testclient import TestClient
from uuid import uuid4

import pytest

from municipal_assistant.accounts.security import digest_secret
from municipal_assistant.app import create_app


@pytest.fixture(autouse=True)
def documents_unconfigured(monkeypatch):
    for name in ("DOCUMENT_MAX_UPLOAD_BYTES", "DOCUMENT_ALLOWED_MEDIA_TYPES",
                 "DOCUMENT_POLICY_APPROVED"):
        monkeypatch.delenv(name, raising=False)


def test_document_routes_fail_closed_without_identity_and_access_wiring():
    response = TestClient(create_app()).get("/api/v1/documents")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


def test_upload_route_fails_before_accepting_multipart_when_policy_is_missing():
    response = TestClient(create_app()).post("/api/v1/documents", files={
        "file": ("report.pdf", b"%PDF-1.7")
    }, data={"title": "Report", "service_id": "00000000-0000-0000-0000-000000000001",
             "category_id": "00000000-0000-0000-0000-000000000002"})
    assert response.status_code == 503


def test_metadata_request_body_is_bounded_before_json_parsing():
    app = create_app()
    app.state.actor_resolver = lambda request: uuid4()
    response = TestClient(app).patch(f"/api/v1/documents/{uuid4()}",
        headers={"If-Match": '"1"', "Content-Type": "application/json"},
        content=b"{" + b" " * 20_000 + b"}")
    assert response.status_code == 413


def test_document_mutation_requires_the_active_session_csrf_token():
    app = create_app()
    account = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(csrf_hash=digest_secret("expected-csrf"))

    class Accounts:
        settings = SimpleNamespace(auth_enabled=True, session_cookie_name="test-session",
                                   csrf_cookie_name="test-csrf")

        def current_session(self, token):
            return (account, session) if token == "valid-session" else None

    app.state.account_service = Accounts()
    client = TestClient(app)
    client.cookies.set("test-session", "valid-session")

    rejected = client.delete(f"/api/v1/documents/{uuid4()}")
    assert rejected.status_code == 403

    client.cookies.set("test-csrf", "expected-csrf")
    accepted_csrf = client.delete(f"/api/v1/documents/{uuid4()}",
        headers={"X-CSRF-Token": "expected-csrf"})
    assert accepted_csrf.status_code == 503  # CSRF passed; Documents remains unconfigured.
