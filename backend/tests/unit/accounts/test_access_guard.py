from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from municipal_assistant.accounts.security import digest_secret
from municipal_assistant.app import create_app

CSRF = "csrf-token"


class FakeAccounts:
    def __init__(self, *, is_central_admin: bool):
        self.settings = SimpleNamespace(
            auth_enabled=True,
            session_cookie_name="test_session",
            csrf_cookie_name="test_csrf",
        )
        self.account = SimpleNamespace(id=uuid4(), is_central_admin=is_central_admin)
        self.session = SimpleNamespace(csrf_hash=digest_secret(CSRF))

    def current_session(self, token):
        return (self.account, self.session) if token == "session-token" else None


def make_client(*, is_central_admin: bool, authenticated: bool = True) -> TestClient:
    app = create_app()
    app.state.account_service = FakeAccounts(is_central_admin=is_central_admin)
    client = TestClient(app)
    if authenticated:
        client.cookies.set("test_session", "session-token")
        client.cookies.set("test_csrf", CSRF)
    return client


def test_api_responses_are_not_cacheable():
    client = make_client(is_central_admin=True, authenticated=False)

    response = client.get("/api/v1/admin/catalog/directions")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_health_endpoint_is_not_marked_no_store():
    client = make_client(is_central_admin=True, authenticated=False)

    response = client.get("/health")

    assert response.status_code == 200
    assert "cache-control" not in response.headers


def test_write_checks_csrf_before_the_role():
    client = make_client(is_central_admin=False)

    response = client.post("/api/v1/admin/catalog/directions", json={"name": "Urbanisme"})

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_non_admin_with_a_valid_csrf_token_is_refused():
    client = make_client(is_central_admin=False)

    response = client.post("/api/v1/admin/catalog/directions", json={"name": "Urbanisme"},
                           headers={"X-CSRF-Token": CSRF})

    assert response.status_code == 403
    assert response.json()["detail"] == "Central administrator permission required"


def test_accounts_and_catalog_routers_share_the_same_guard():
    client = make_client(is_central_admin=False)

    accounts = client.get("/api/v1/admin/accounts")
    catalog = client.get("/api/v1/admin/catalog/directions")

    assert accounts.status_code == catalog.status_code == 403
    assert accounts.json()["detail"] == catalog.json()["detail"]
