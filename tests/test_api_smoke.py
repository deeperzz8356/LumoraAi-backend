from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_templates():
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_auth_sync():
    with patch("app.services.auth_service.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"uid": "test_user_123", "email": "test@example.com"}
        response = client.post("/api/v1/auth/sync", json={"id_token": "mock-token-123"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["user"]["uid"] == "test_user_123"


def test_auth_me_protected_unauthorized():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403


