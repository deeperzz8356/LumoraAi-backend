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


def test_auth_guest():
    response = client.post("/api/v1/auth/guest", json={"device_id": "demo-device"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_auth_google():
    with patch("app.services.auth_service.auth.verify_id_token") as mock_verify:
        mock_verify.return_value = {"uid": "google_test_user_123"}
        response = client.post("/api/v1/auth/google", json={"id_token": "mock-token-123"})
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["user_id"] == "google_test_user_123"


def test_auth_login():
    response = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "access_token" in response.json()
