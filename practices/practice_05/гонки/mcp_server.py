"""Собственный MCP-сервер для проекта «Гонки».

Предоставляет инструменты (tools) для AI-агента:
1. `validate_race_entry`: строгая валидация конфигурации заезда с проверкой модели и цвета.
2. `simulate_race`: симуляция заезда между двумя болидами с учётом их характеристик.
"""

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("racing-judge")

ALLOWED_MODELS = {
    "racer": {"speed": 4.8, "handling": 0.8},
    "drifter": {"speed": 4.4, "handling": 0.95},
    "tank": {"speed": 4.0, "handling": 0.7},
}

ALLOWED_COLORS = {"red", "yellow", "purple"}


@mcp.tool()
def validate_race_entry(model_id: str, color: str) -> dict:
    """Проверяет валидность машинки и цвета перед стартом гонки."""
    if not model_id or not isinstance(model_id, str):
        return {"status": "error", "reason": "model_id обязателен и должен быть строкой"}

    if not color or not isinstance(color, str):
        return {"status": "error", "reason": "color обязателен и должен быть строкой"}

    clean_model = model_id.strip().lower()
    clean_color = color.strip().lower()

    if clean_model not in ALLOWED_MODELS:
        return {
            "status": "error",
            "reason": f"Неизвестная модель машинки: '{model_id}'. Разрешены: {list(ALLOWED_MODELS.keys())}",
        }

    if clean_color not in ALLOWED_COLORS:
        return {
            "status": "error",
            "reason": f"Недопустимый цвет: '{color}'. Разрешены: {list(ALLOWED_COLORS)}",
        }

    return {
        "status": "ok",
        "message": f"Болид {clean_model} цвета {clean_color} допущен к заезду",
        "specs": ALLOWED_MODELS[clean_model],
    }


@mcp.tool()
def simulate_race(p1_model: str, p2_model: str, track_length_meters: int = 500) -> dict:
    """Симулирует соревнование между двумя моделями болидов."""
    if p1_model not in ALLOWED_MODELS or p2_model not in ALLOWED_MODELS:
        return {"status": "error", "reason": "Один из болидов не найден в реестре"}

    if track_length_meters <= 0 or track_length_meters > 5000:
        return {"status": "error", "reason": "Длина трассы должна быть от 1 до 5000 метров"}

    m1 = ALLOWED_MODELS[p1_model]
    m2 = ALLOWED_MODELS[p2_model]

    eff_speed1 = m1["speed"] * (0.7 + 0.3 * m1["handling"])
    eff_speed2 = m2["speed"] * (0.7 + 0.3 * m2["handling"])

    time1 = round(track_length_meters / (eff_speed1 * 10), 2)
    time2 = round(track_length_meters / (eff_speed2 * 10), 2)

    winner = "Player 1" if time1 < time2 else ("Player 2" if time2 < time1 else "Ничья")

    return {
        "status": "ok",
        "winner": winner,
        "details": {
            "player1": {"model": p1_model, "time_seconds": time1},
            "player2": {"model": p2_model, "time_seconds": time2},
        },
    }


if __name__ == "__main__":
    mcp.run()
