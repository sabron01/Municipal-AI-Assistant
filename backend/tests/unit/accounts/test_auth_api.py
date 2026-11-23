from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from municipal_assistant.accounts.security import digest_secret
from municipal_assistant.app import create_app

EMAIL = "admin@municipal.tn"
PASSWORD = "correct horse battery staple"
SESSION_TOKEN = "session-token"
CSRF_TOKEN = "csrf-token"


class FakeAccounts:
    def __init__(self, *, auth_enabled=True, is_central_admin=True):
        self.settings = SimpleNamespace(
            auth_enabled=auth_enabled,
            session_cookie_name="maa_session",
            csrf_cookie_name="maa_csrf",
            cookie_secure=False,
            session_ttl_hours=8,
        )
        self.account = SimpleNamespace(
            id=uuid4(),
            email=EMAIL,
            status="active",
            is_central_admin=is_central_admin,
            created_at=datetime.now(timezone.utc),
        )
        self.session = SimpleNamespace(csrf_hash=digest_secret(CSRF_TOKEN))
        self.logged_out = []

    def authenticate(self, email, password, source_ip):
        if email == EMAIL and password == PASSWORD:
            return self.account, SESSION_TOKEN, CSRF_TOKEN
        return None

    def current_session(self, token):
        return (self.account, self.session) if token == SESSION_TOKEN else None

    def logout(self, token):
        self.logged_out.append(token)

    def list_accounts(self):
        return [self.account]

    def create_account(self, actor_id, email):
        return self.account


def make_client(*, auth_enabled=True, is_central_admin=True):
    app = create_app()
    fake = FakeAccounts(auth_enabled=auth_enabled, is_central_admin=is_central_admin)
    app.state.account_service = fake
    app.state.catalog_service = None
    return TestClient(app), fake


def login(client):
    return client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})


def cookie_header(response, name):
    headers = [value for value in response.headers.get_list("set-cookie")
               if value.startswith(f"{name}=")]
    assert headers, f"Cookie {name} was not set"
    return headers[0].lower()


def test_login_sets_httponly_session_cookie_and_readable_csrf_cookie():
    client, _ = make_client()

    response = login(client)

    assert response.status_code == 200
    assert response.json()["csrf_token"] == CSRF_TOKEN
    session_cookie = cookie_header(response, "maa_session")
    csrf_cookie = cookie_header(response, "maa_csrf")
    assert "httponly" in session_cookie
    assert "httponly" not in csrf_cookie
    assert "samesite=strict" in session_cookie
    assert "samesite=strict" in csrf_cookie
    assert "path=/" in session_cookie


def test_login_response_is_not_cacheable():
    client, _ = make_client()

    response = login(client)

    assert response.headers["cache-control"] == "no-store"


def test_login_rejects_invalid_credentials_without_setting_cookies():
    client, _ = make_client()

    response = client.post("/api/v1/auth/login",
                           json={"email": EMAIL, "password": "wrong password value"})

    assert response.status_code == 401
    assert response.headers.get_list("set-cookie") == []


def test_me_requires_an_authenticated_session():
    client, _ = make_client()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_me_returns_the_current_account_and_is_not_cacheable():
    client, fake = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == fake.account.email
    assert response.json()["is_central_admin"] is True
    assert response.headers["cache-control"] == "no-store"


def test_logout_requires_a_csrf_token():
    client, _ = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)
    client.cookies.set("maa_csrf", CSRF_TOKEN)

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_logout_rejects_a_mismatched_csrf_token():
    client, _ = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)
    client.cookies.set("maa_csrf", CSRF_TOKEN)

    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "other-token"})

    assert response.status_code == 403


def test_logout_with_valid_csrf_revokes_the_session_and_clears_cookies():
    client, fake = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)
    client.cookies.set("maa_csrf", CSRF_TOKEN)

    response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": CSRF_TOKEN})

    assert response.status_code == 204
    assert fake.logged_out == [SESSION_TOKEN]
    cleared = [value for value in response.headers.get_list("set-cookie")
               if value.startswith(("maa_session=", "maa_csrf="))]
    assert len(cleared) == 2
    assert all("max-age=0" in value.lower() for value in cleared)


def test_admin_endpoints_require_a_central_administrator():
    client, _ = make_client(is_central_admin=False)
    client.cookies.set("maa_session", SESSION_TOKEN)

    response = client.get("/api/v1/admin/accounts")

    assert response.status_code == 403
    assert response.json()["detail"] == "Central administrator permission required"


def test_admin_list_returns_accounts_for_a_central_administrator():
    client, fake = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)

    response = client.get("/api/v1/admin/accounts")

    assert response.status_code == 200
    assert response.json()[0]["email"] == fake.account.email


def test_admin_mutation_requires_csrf_even_for_a_central_administrator():
    client, _ = make_client()
    client.cookies.set("maa_session", SESSION_TOKEN)
    client.cookies.set("maa_csrf", CSRF_TOKEN)

    response = client.post("/api/v1/admin/accounts", json={"email": "agent@municipal.tn"})

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_account_routes_fail_closed_when_authentication_is_disabled():
    client, _ = make_client(auth_enabled=False)

    response = login(client)

    assert response.status_code == 503
    assert response.json()["detail"] == "Account services are not configured"


def test_activation_form_escapes_the_token():
    client, _ = make_client()

    response = client.get("/api/v1/auth/activate",
                          params={"token": "<script>alert(1)</script>"})

    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize("path", ["/api/v1/auth/activate", "/api/v1/auth/reset-password"])
def test_activation_and_reset_forms_are_not_cacheable(path):
    client, _ = make_client()

    response = client.get(path, params={"token": "a" * 43})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
