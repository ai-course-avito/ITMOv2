import pytest
from fastapi.testclient import TestClient

from app.llm import LLMClient, get_llm_client
from app.main import app


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


def test_review_returns_summary_and_comments_with_default_stub():
    diff = "diff --git a/a.py b/a.py\n+x\ndiff --git a/b.py b/b.py\n+y\n"

    response = TestClient(app).post("/review", json={"diff": diff})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Файлов в diff: 2"
    assert len(body["comments"]) == 1


def test_stub_is_deterministic():
    diff = "diff --git a/a.py b/a.py\n+x\n"

    assert LLMClient().review(diff) == LLMClient().review(diff)


def test_review_without_diff_field_is_rejected_by_schema():
    response = TestClient(app).post("/review", json={})

    assert response.status_code == 422
