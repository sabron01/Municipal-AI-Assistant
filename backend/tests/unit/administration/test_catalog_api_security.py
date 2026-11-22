from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from municipal_assistant.accounts.security import digest_secret
from municipal_assistant.app import create_app


class FakeAccounts:
    def __init__(self, *, is_central_admin: bool):
        self.settings = SimpleNamespace(
            auth_enabled=True,
            session_cookie_name="test_session",
            csrf_cookie_name="test_csrf",
        )
        self.account = SimpleNamespace(id=uuid4(), is_central_admin=is_central_admin)
        self.session = SimpleNamespace(csrf_hash=digest_secret("csrf-token"))

    def current_session(self, token):
        return (self.account, self.session) if token == "session-token" else None


def test_catalog_api_requires_an_authenticated_central_admin():
    app = create_app()
    app.state.account_service = FakeAccounts(is_central_admin=False)

    response = TestClient(app).get("/api/v1/admin/catalog/directions",
        cookies={"test_session": "session-token"})

    assert response.status_code == 403


def test_catalog_write_requires_csrf_even_for_a_central_admin():
    app = create_app()
    app.state.account_service = FakeAccounts(is_central_admin=True)

    response = TestClient(app).post("/api/v1/admin/catalog/directions",
        cookies={"test_session": "session-token"}, json={"name": "Finance"})

    assert response.status_code == 403
    assert response.json()["status"] == 403
