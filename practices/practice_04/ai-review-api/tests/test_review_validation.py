import pytest
from fastapi.testclient import TestClient

from app.llm import get_llm_client
from app.main import app

MAX_DIFF_BYTES = 100000


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def review(self, diff: str) -> dict:
        self.calls.append(diff)
        return {"summary": "fake", "comments": []}


@pytest.fixture
def fake_llm():
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def make_diff(size_bytes: int) -> str:
    """Diff ровно в size_bytes байт UTF-8; кириллица делает символов вдвое меньше, чем байт."""
    header = "diff --git a/x b/x\n"
    body_bytes = size_bytes - len(header)
    diff = header + "я" * (body_bytes // 2) + "a" * (body_bytes % 2)
    assert len(diff.encode("utf-8")) == size_bytes
    return diff


@pytest.mark.parametrize("diff", ["", "   ", " \n\t\r\n "])
def test_review_with_blank_diff_returns_422_and_skips_llm(client, fake_llm, diff):
    response = client.post("/review", json={"diff": diff})

    assert response.status_code == 422
    assert fake_llm.calls == []


def test_review_with_diff_of_exactly_max_bytes_returns_200(client, fake_llm):
    diff = make_diff(MAX_DIFF_BYTES)

    response = client.post("/review", json={"diff": diff})

    assert response.status_code == 200
    assert fake_llm.calls == [diff]


def test_review_with_diff_one_byte_over_limit_returns_413_and_skips_llm(client, fake_llm):
    diff = make_diff(MAX_DIFF_BYTES + 1)

    response = client.post("/review", json={"diff": diff})

    assert response.status_code == 413
    assert fake_llm.calls == []


def test_review_with_oversized_diff_returns_diff_too_large_error(client, fake_llm):
    response = client.post("/review", json={"diff": make_diff(MAX_DIFF_BYTES + 1)})

    body = response.json()
    assert body["error"] == "diff_too_large"
    assert body["max_bytes"] == MAX_DIFF_BYTES


def test_review_counts_diff_size_in_bytes_not_characters(client, fake_llm):
    diff = make_diff(MAX_DIFF_BYTES + 1)
    assert len(diff) < MAX_DIFF_BYTES

    response = client.post("/review", json={"diff": diff})

    assert response.status_code == 413
