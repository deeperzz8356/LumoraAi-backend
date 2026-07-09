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
