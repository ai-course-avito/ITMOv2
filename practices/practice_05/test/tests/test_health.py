from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_ok():
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json().get("ready") is True


def test_api_namespace_no_5xx():
    r = client.get("/api")
    assert r.status_code in (200, 404)
