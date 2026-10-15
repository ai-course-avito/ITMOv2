import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.llm import get_llm_client
from app.main import MAX_DIFF_BYTES, app

TEST_TIMEOUT_SECONDS = 0.05
BLOCKED_LLM_SAFETY_SECONDS = 5
MAX_RESPONSE_SECONDS = BLOCKED_LLM_SAFETY_SECONDS / 2


class FailingLLM:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[str] = []

    def review(self, diff: str) -> dict:
        self.calls.append(diff)
        raise self.error


class HangingLLM:
    """Зависает, пока тест не отпустит; страховочный таймаут не дает потоку жить вечно."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls: list[str] = []

    def review(self, diff: str) -> dict:
        self.calls.append(diff)
        self.release.wait(BLOCKED_LLM_SAFETY_SECONDS)
        return {"summary": "late", "comments": []}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def failing_llm():
    fake = FailingLLM(RuntimeError("secret internal failure"))
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def hanging_llm(monkeypatch):
    monkeypatch.setattr("app.main.LLM_TIMEOUT_SECONDS", TEST_TIMEOUT_SECONDS)
    fake = HangingLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    fake.release.set()
    app.dependency_overrides.clear()


def test_review_when_llm_raises_returns_502_llm_unavailable(client, failing_llm):
    response = client.post("/review", json={"diff": "diff --git a/x b/x"})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "llm_unavailable"
    assert "detail" in body
    assert failing_llm.calls == ["diff --git a/x b/x"]


def test_review_when_llm_raises_does_not_leak_stacktrace(client, failing_llm):
    response = client.post("/review", json={"diff": "diff --git a/x b/x"})

    assert "Traceback" not in response.text
    assert "secret internal failure" not in response.text


def test_review_when_llm_times_out_returns_502_llm_unavailable(client, hanging_llm):
    response = client.post("/review", json={"diff": "diff --git a/x b/x"})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "llm_unavailable"
    assert "detail" in body
    assert hanging_llm.calls == ["diff --git a/x b/x"]


def test_review_when_llm_times_out_responds_without_waiting_for_llm(client, hanging_llm):
    started_at = time.monotonic()
    response = client.post("/review", json={"diff": "diff --git a/x b/x"})
    elapsed = time.monotonic() - started_at

    assert response.status_code == 502
    assert elapsed < MAX_RESPONSE_SECONDS


def test_review_with_empty_diff_when_llm_fails_returns_422_without_calling_llm(client, failing_llm):
    response = client.post("/review", json={"diff": ""})

    assert response.status_code == 422
    assert failing_llm.calls == []


def test_review_with_oversized_diff_when_llm_fails_returns_413_without_calling_llm(client, failing_llm):
    response = client.post("/review", json={"diff": "a" * (MAX_DIFF_BYTES + 1)})

    assert response.status_code == 413
    assert response.json()["error"] == "diff_too_large"
    assert failing_llm.calls == []
