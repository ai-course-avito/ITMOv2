"""Тесты кнопки "Сообщить об ошибке" (/report-error).

Та же идея валидации, что и в Фиче A: мусорный/пустой/слишком большой вход
отклоняется ещё до записи в лог.
"""

import json

from fastapi.testclient import TestClient

from app.main import ERROR_LOG_PATH, app

client = TestClient(app)


def _read_last_log_line() -> dict:
    with ERROR_LOG_PATH.open(encoding="utf-8") as f:
        lines = f.readlines()
    return json.loads(lines[-1])


def test_valid_report_is_accepted_and_logged():
    response = client.post(
        "/report-error",
        json={"message": "Машинка зависла на втором круге", "model_id": "racer", "color": "purple"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ok"

    logged = _read_last_log_line()
    assert logged["message"] == "Машинка зависла на втором круге"
    assert logged["model_id"] == "racer"


def test_report_without_context_is_accepted():
    response = client.post("/report-error", json={"message": "Кнопки не реагируют"})
    assert response.status_code == 201


def test_empty_message_is_rejected():
    response = client.post("/report-error", json={"message": ""})
    assert response.status_code == 422


def test_blank_message_is_rejected():
    response = client.post("/report-error", json={"message": "    "})
    assert response.status_code == 422


def test_too_long_message_is_rejected():
    response = client.post("/report-error", json={"message": "x" * 501})
    assert response.status_code == 422


def test_unexpected_field_is_rejected():
    response = client.post("/report-error", json={"message": "ок", "hack": True})
    assert response.status_code == 422
