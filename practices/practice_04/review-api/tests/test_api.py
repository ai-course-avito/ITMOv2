from fastapi.testclient import TestClient

from app.api import app
from app.dependencies import llm

client = TestClient(app)


def setup_function() -> None:
    llm.calls.clear()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_review_returns_llm_answer() -> None:
    response = client.post("/api/reviews", json={"diff": "diff --git a/x.py b/x.py\n+print(1)\n"})
    assert response.status_code == 200
    assert response.json() == {"comment": "stub review: no problems found"}
    assert len(llm.calls) == 1


def test_api1_no_diff_field() -> None:
    response = client.post("/api/reviews", json={})
    assert response.status_code == 422
    assert len(llm.calls) == 0


def test_api1_diff_not_string() -> None:
    response = client.post("/api/reviews", json={"diff": 123})
    assert response.status_code == 422
    assert len(llm.calls) == 0


def test_api1_empty_diff_after_strip() -> None:
    response = client.post("/api/reviews", json={"diff": "   "})
    assert response.status_code == 422
    assert len(llm.calls) == 0


def test_api1_diff_too_large() -> None:
    diff = "a" * 20001
    response = client.post("/api/reviews", json={"diff": diff})
    assert response.status_code == 413
    assert response.json() == {"detail": "diff too large"}
    assert len(llm.calls) == 0


def test_api1_diff_exactly_20000() -> None:
    diff = "a" * 20000
    response = client.post("/api/reviews", json={"diff": diff})
    assert response.status_code == 200
    assert response.json() == {"comment": "stub review: no problems found"}
    assert len(llm.calls) == 1
