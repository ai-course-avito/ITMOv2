"""Эталонный пример теста: так должны выглядеть новые тесты в проекте.

Паттерн: Arrange - Act - Assert, один сценарий на тест,
имя теста описывает проверяемое поведение, а не реализацию.
Тестируем через публичный HTTP-интерфейс, не через внутренние структуры.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_task_rejects_empty_title():
    payload = {"title": "", "tags": ["demo"]}

    response = client.post("/tasks", json=payload)

    assert response.status_code == 422


def test_create_task_accepts_valid_input():
    payload = {"title": "Buy milk", "tags": ["errands", "shopping"]}

    response = client.post("/tasks", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Buy milk"
    assert body["tags"] == ["errands", "shopping"]
