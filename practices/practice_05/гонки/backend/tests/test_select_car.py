"""Тесты фичи A — входная валидация выбора машинки.

Соответствуют "способу проверки" из AGENTS.md:
- валидный выбор -> гонка стартует
- несуществующая модель -> отказ, гонка не стартует
- цвет не из палитры -> отказ
- слишком большой/мусорный запрос -> отказ без запуска гонки
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_valid_selection_starts_race():
    response = client.post(
        "/select-car",
        json={"model_id": "racer", "color": "purple"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_model_id_is_rejected():
    response = client.post(
        "/select-car",
        json={"model_id": "unknown-model", "color": "purple"},
    )
    assert response.status_code == 422


def test_unknown_color_is_rejected():
    response = client.post(
        "/select-car",
        json={"model_id": "racer", "color": "green"},
    )
    assert response.status_code == 422


def test_unexpected_extra_field_is_rejected():
    response = client.post(
        "/select-car",
        json={"model_id": "racer", "color": "purple", "hack": True},
    )
    assert response.status_code == 422


def test_oversized_request_is_rejected_without_starting_race():
    huge_payload = {
        "model_id": "racer",
        "color": "purple",
        "junk": "x" * 5000,
    }
    response = client.post("/select-car", json=huge_payload)
    # Либо отклонён middleware'ом по размеру (413), либо Pydantic'ом из-за
    # лишнего поля (422) — в обоих случаях гонка НЕ стартует.
    assert response.status_code in (413, 422)
