"""Тесты для проверки собственного MCP сервера (успешные вызовы и обработка ошибок)."""

import pytest
from mcp_server import validate_race_entry, simulate_race


def test_validate_race_entry_success():
    """Успешная валидация корректной машины и цвета."""
    res = validate_race_entry("racer", "purple")
    assert res["status"] == "ok"
    assert "допущен к заезду" in res["message"]
    assert "specs" in res


def test_validate_race_entry_invalid_model():
    """Ошибка: несуществующая модель машины."""
    res = validate_race_entry("batmobile", "purple")
    assert res["status"] == "error"
    assert "Неизвестная модель машинки" in res["reason"]


def test_validate_race_entry_invalid_color():
    """Ошибка: недопустимый цвет."""
    res = validate_race_entry("racer", "black")
    assert res["status"] == "error"
    assert "Недопустимый цвет" in res["reason"]


def test_simulate_race_success():
    """Успешный запуск симуляции гонки между двумя болидами."""
    res = simulate_race("racer", "tank", 400)
    assert res["status"] == "ok"
    assert "winner" in res
    assert res["winner"] in ["Player 1", "Player 2", "Ничья"]


def test_simulate_race_invalid_input():
    """Ошибка: неверная длина трека."""
    res = simulate_race("racer", "tank", -100)
    assert res["status"] == "error"
    assert "Длина трассы должна быть от 1 до 5000" in res["reason"]
