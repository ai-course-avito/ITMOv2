# Demo: Subscription Service (Python/FastAPI)

Простой HTTP-сервис подписки.

Эндпоинты:
- GET /health -> {"status":"ok"}
- GET /version -> {"version":"0.1.0"}
- POST /subscribe -> body: {"email":"string", "name":"string?"} -> 201, {"email":"...","status":"subscribed"}
- GET /subscribers -> [{"email":"...","name":"..."}]
- DELETE /subscribers/{email} -> 204

Хранение: файл JSON `data/subscribers.json` в этой директории.

Запуск:

1. Установите зависимости (нужен pip). Если pip не установлен:

Ubuntu/Debian:

```bash
sudo apt-get update && sudo apt-get install -y python3-pip
```

Затем поставьте зависимости:

```bash
python3 -m pip install -r requirements.txt
```

2. Запустите сервис:

```bash
make run
```

Сервис слушает `http://localhost:8000`.

Smoke-проверка:
- Используйте локальный конфиг `.opencode/skills/api-contract-smoke/config/local_example.json`
- Проверяются `/health` и `/version`
