"""Пример теста в духе проекта.

Правила стиля:
- клиент приложения создаем через TestClient;
- LLM подменяем через app.dependency_overrides, сеть и реальный клиент не нужны;
- фейк детерминированный, запоминает вызовы, чтобы проверять "LLM не вызывался";
- после теста overrides чистим (фикстура), имя теста описывает поведение.
"""
import pytest
from fastapi.testclient import TestClient

from app.llm import get_llm_client
from app.main import app


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


def test_review_passes_diff_to_llm_and_returns_its_answer(client, fake_llm):
    response = client.post("/review", json={"diff": "diff --git a/x b/x"})

    assert response.status_code == 200
    assert response.json() == {"summary": "fake", "comments": []}
    assert fake_llm.calls == ["diff --git a/x b/x"]
