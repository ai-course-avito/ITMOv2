# AGENTS.md — subtracker

Трекер подписок: пользователь добавляет свои платные сервисы, приложение считает расход за месяц/год и напоминает о предстоящих списаниях. Подробное ТЗ — в `SPEC.md`.

## Стек
- **Backend:** Python 3.12, FastAPI, Pydantic v2
- **DB:** PostgreSQL + SQLAlchemy 2.x (async), миграции — Alembic
- **Frontend:** React + Vite + TypeScript, Tailwind CSS
- **Auth:** JWT (access + refresh), хеш паролей — argon2
- **Планировщик:** APScheduler (проверка предстоящих списаний) — см. примечание ниже
- **Инфра:** Docker + docker-compose (backend, frontend, postgres)
- **Пакеты:** backend — `uv`; frontend — `npm`
- **Тесты:** pytest (+ pytest-asyncio), httpx для тестового клиента
- **Качество:** ruff (линт + формат)

## Структура репозитория
```
subtracker/
├── backend/        # FastAPI-приложение
├── frontend/       # React + Vite
├── docker-compose.yml
├── SPEC.md         # что строим (фичи, модель, API)
└── AGENTS.md       # этот файл
```
Новый код бэкенда — в `backend/`, фронта — в `frontend/`. Не смешивать.

## Порты
- Backend (uvicorn): `8000`
- Frontend (Vite dev): `5173`
- PostgreSQL: `5432`

## Как поднять окружение
Backend:
```
cd backend
uv sync                      # установить зависимости из pyproject
cp .env.example .env         # заполнить переменные
alembic upgrade head         # накатить миграции
```
Frontend:
```
cd frontend
npm install
cp .env.example .env
```

## Команды
**Разработка (быстрая итерация, без Docker):**
- Backend dev-сервер: `cd backend && uv run uvicorn app.main:app --reload`
- Frontend dev-сервер: `cd frontend && npm run dev`

**Через Docker (всё разом):**
- Поднять всё: `docker compose up --build`

**Тесты:**
- Все тесты бэкенда: `cd backend && uv run pytest`
- Один тест: `cd backend && uv run pytest path/to/test.py::test_name`

**Качество:**
- Линт: `cd backend && uv run ruff check .`
- Формат: `cd backend && uv run ruff format .`

**Миграции:**
- Создать: `cd backend && uv run alembic revision --autogenerate -m "описание"`
- Накатить: `cd backend && uv run alembic upgrade head`

## Конвенции
- **Деньги — только `Decimal`, никогда `float`.** Округление до 2 знаков.
- Весь доступ к БД — **async** (async SQLAlchemy, async-эндпоинты).
- Вся валидация входных/выходных данных — через **Pydantic v2**.
- Бизнес-логику не держать в роутах: роут принимает запрос, валидирует, делегирует в сервис-слой, возвращает ответ.
- Ошибки — осмысленные HTTP-коды (401 / 403 / 404 / 422), не голый 500.
- **Изоляция пользователей:** пользователь видит и меняет только свои подписки — проверять владельца в каждом запросе.
- Именование: snake_case в Python, camelCase во фронте.
- Каждый новый эндпоинт сопровождается тестом.

## Чего НЕ делать
- Не писать деньги во `float`.
- Не менять схему БД руками — только через миграции Alembic.
- Не коммитить `.env` и секреты. Все переменные — в `.env.example` как шаблон.
- Не класть бизнес-логику и сырой SQL в роуты.
- Не давать одному пользователю доступ к данным другого.

## Порядок работы
- Делать по этапам из `SPEC.md`, по одному, с коммитом на каждом.
- Перед тем как писать фичу — свериться со `SPEC.md`.
- Коммиты — короткие и по-английски, в повелительном наклонении: `add subscription CRUD`, `fix billing cycle calc`.
- Один этап = один осмысленный коммит (или несколько, но не мешать разные этапы в один).

## Примечания по архитектуре
- **APScheduler — временное решение для MVP.** Он работает внутри процесса приложения: при перезапуске незавершённые напоминания могут теряться, и он не переживёт запуск в нескольких инстансах. Для учебного/MVP-этапа этого достаточно. Для настоящего продакшена сюда просится отдельная очередь задач или cron + таблица со статусом напоминаний — пометить как TODO, не выдавать за production-grade.