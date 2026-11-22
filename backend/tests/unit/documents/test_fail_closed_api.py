from fastapi.testclient import TestClient
from uuid import uuid4

from municipal_assistant.app import create_app


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
