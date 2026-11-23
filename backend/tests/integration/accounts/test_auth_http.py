from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from municipal_assistant.accounts.router import router

PASSWORD = "correct horse battery staple"


def create_active_account(service, mailer, email="agent@municipal.tn", *, password=PASSWORD):
    account = service.create_account(uuid4(), email)
    service.activate(mailer.last_token(), password)
    return service.get_account(account.id)


def bootstrap_active_admin(service, mailer, email="admin@municipal.tn"):
    assert service.bootstrap_initial_admin() is True
    service.activate(mailer.last_token(), PASSWORD)
    return service.list_accounts()[0]


def make_client(service):
    app = FastAPI()
    app.state.account_service = service
    app.state.catalog_service = None
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_login_me_logout_round_trip(build_service, mailer):
    service = build_service()
    create_active_account(service, mailer)
    client = make_client(service)

    login = client.post("/api/v1/auth/login",
                        json={"email": "agent@municipal.tn", "password": PASSWORD})

    assert login.status_code == 200
    csrf_token = login.json()["csrf_token"]
    assert client.get("/api/v1/auth/me").json()["email"] == "agent@municipal.tn"

    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})

    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_with_a_wrong_password_returns_401(build_service, mailer):
    service = build_service()
    create_active_account(service, mailer)
    client = make_client(service)

    response = client.post("/api/v1/auth/login",
                           json={"email": "agent@municipal.tn", "password": "wrong password value"})

    assert response.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_without_csrf_header_is_forbidden(build_service, mailer):
    service = build_service()
    create_active_account(service, mailer)
    client = make_client(service)
    client.post("/api/v1/auth/login",
                json={"email": "agent@municipal.tn", "password": PASSWORD})

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_admin_creates_an_account_which_activates_and_logs_in(build_service, mailer):
    service = build_service(initial_admin_email="admin@municipal.tn")
    bootstrap_active_admin(service, mailer)
    client = make_client(service)
    login = client.post("/api/v1/auth/login",
                        json={"email": "admin@municipal.tn", "password": PASSWORD})
    csrf_token = login.json()["csrf_token"]

    created = client.post("/api/v1/admin/accounts", json={"email": "new.agent@municipal.tn"},
                          headers={"X-CSRF-Token": csrf_token})

    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    activation_token = mailer.last_token()
    activated = client.post("/api/v1/auth/activate",
                            data={"token": activation_token, "password": PASSWORD})
    assert activated.status_code == 200

    new_login = client.post("/api/v1/auth/login",
                            json={"email": "new.agent@municipal.tn", "password": PASSWORD})
    assert new_login.status_code == 200


def test_admin_account_creation_requires_csrf(build_service, mailer):
    service = build_service(initial_admin_email="admin@municipal.tn")
    bootstrap_active_admin(service, mailer)
    client = make_client(service)
    client.post("/api/v1/auth/login",
                json={"email": "admin@municipal.tn", "password": PASSWORD})

    response = client.post("/api/v1/admin/accounts", json={"email": "new.agent@municipal.tn"})

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_admin_endpoints_reject_a_non_admin_session(build_service, mailer):
    service = build_service()
    create_active_account(service, mailer)
    client = make_client(service)
    client.post("/api/v1/auth/login",
                json={"email": "agent@municipal.tn", "password": PASSWORD})

    assert client.get("/api/v1/admin/accounts").status_code == 403
