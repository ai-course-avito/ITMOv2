# HANDOFF: ai-review-api

Для того, кто продолжает работу с чистого листа. Состояние: ветка `practice_4`, HEAD `c00ccea`, фичи A и B слиты, `CHECK PASS`.

## Что это

Маленький FastAPI-сервис: `POST /review` принимает `{"diff": "..."}`, возвращает ревью; `GET /health`. LLM заменен заглушкой без сети (`app/llm.py`), подставляется через `Depends(get_llm_client)`. Контракт: `docs/requirements.md`.

## Что сделано

Базовая точка: `09bb973` (scaffold), среда агента: `5ff4dc1`. Дальше два коммита, оба меняют `app/main.py` и добавляют по одному файлу тестов.

### Фича A: входная валидация (`121675b`)

- Пустой diff или только пробельные символы: `422` (валидатор `ReviewRequest.diff_must_not_be_blank`, стандартная схема FastAPI).
- Diff больше `MAX_DIFF_BYTES = 100000` байт в UTF-8: `413`, тело `{"error": "diff_too_large", "detail": ..., "max_bytes": 100000}`. Ровно 100000 байт проходит.
- При отказе LLM не вызывается.
- Файлы: `app/main.py`, `tests/test_review_validation.py`.

### Фича B: ошибка зависимости (`c00ccea`)

- Исключение LLM или таймаут (`LLM_TIMEOUT_SECONDS = 10`): `502`, тело `{"error": "llm_unavailable", "detail": ...}`, без стектрейса и текста исходной ошибки.
- Вызов идет в одноразовом `ThreadPoolExecutor(max_workers=1)` с `result(timeout=...)` и `shutdown(wait=False)`, чтобы ответ не ждал зависший LLM.
- Валидация (A) срабатывает раньше обращения к LLM.
- Файлы: `app/main.py`, `tests/test_review_llm_failure.py`.

## Как проверено

Команда: `sh scripts/check.sh` (это `python -m pytest -q` из `.venv`, в конце `CHECK PASS` / `CHECK FAIL`). Прогнана при подготовке этого файла: **56 passed, 1 warning, `CHECK PASS`**. Предупреждение: `StarletteDeprecationWarning` про `httpx` в `TestClient`, на результат не влияет.

| Файл | Тестов | Что покрывает |
|---|---|---|
| `tests/test_review_validation.py` | 7 | A: пустой/пробельный diff (3 варианта) → 422 и LLM не вызван; ровно 100000 байт → 200; +1 байт → 413; тело `diff_too_large`; размер считается в байтах, не в символах |
| `tests/test_review_llm_failure.py` | 6 | B: исключение → 502; нет стектрейса и секрета в ответе; таймаут → 502; ответ не ждет зависший LLM; 422 и 413 при падающем LLM без вызова LLM |
| `tests/test_review_basic.py` | 3 | заглушка по умолчанию, детерминизм, отсутствие поля `diff` → 422 |
| `tests/test_example.py`, `tests/test_health.py` | 1 + 1 | пример стиля, `/health` |
| `tests/test_diff_parser.py` | 38 | парсер MCP-сервера `diff-inspector` (не связан с API) |

Тесты фич писались по skill `tdd-feature` (сначала падающий тест, `fail_first.sh`). Отдельная независимая проверка возможна агентом `tester` (`.claude/agents/tester.md`).

## Что осталось и слабые места

Контракт A и B выполнен, открытых пунктов из `docs/requirements.md` нет. Ниже улучшения, в контракт не входят.

1. **Зависший поток LLM после таймаута.** `shutdown(wait=False)` не убивает поток: он живет, пока `llm.review` не вернется. Потоки не daemon, поэтому зависший вызов может задержать остановку процесса; при частых таймаутах потоки копятся. Нужна отмена на уровне клиента (таймаут HTTP-клиента) или общий ограниченный пул.
2. **Нет логирования причины сбоя.** Блок `except Exception` в `app/main.py` глотает ошибку: клиент получает `llm_unavailable`, в логах ничего. Нельзя отличить таймаут от исключения. Добавить `logging` (тип ошибки, таймаут или нет, без содержимого diff).
3. **Diff из пробелов больше лимита дает 422, а не 413.** Валидатор `ReviewRequest` срабатывает до проверки размера. Контракт этот случай прямо не описывает; решить, какой код правильный, и при необходимости добавить тест. Тот же порядок: невалидный JSON/тип поля дает 422 раньше любой проверки размера.
4. **Тело `422` не в формате style guide.** Это стандартная схема FastAPI (контракт это разрешает), а не `{"error": ..., "detail": ...}`. Тесты проверяют только код 422, не тело.
5. **Размер проверяется поздно:** 413 возвращается после того, как FastAPI уже разобрал весь JSON в память. Ограничения на уровне сервера или по `Content-Length` нет.
6. **Таймаут жестко задан** константой `LLM_TIMEOUT_SECONDS = 10`; конфигурации через окружение нет. Тесты подменяют ее через `monkeypatch`.
7. **Таймаут-тесты зависят от времени** (`TEST_TIMEOUT_SECONDS = 0.05`, порог ответа 2.5 с); на очень медленной машине возможна нестабильность.
8. `LLMClient` это заглушка (считает `diff --git`, возвращает один фиксированный комментарий); реального клиента нет.

## Правила среды

- **`AGENTS.md`** (его же подтягивает `CLAUDE.md`): код в `app/`, тесты в `tests/`; стиль в `docs/style-guide.md` (5 правил: имена, тест на каждый код ответа, зависимости только через `Depends`, ошибки в формате `{"error": "<snake_case>", "detail": ...}`, без лишних комментариев); новые тесты по образцу `tests/test_example.py`; LLM в тестах всегда подменять через `app.dependency_overrides[get_llm_client]`.
- **Не менять без поручения:** `docs/requirements.md` и `scripts/check.sh`.
- **После каждого изменения** запускать `sh scripts/check.sh`, ждать `CHECK PASS`.
- **Skill `tdd-feature`** (`.claude/skills/tdd-feature/`): новая фича или баг идут так: контракт и пример → падающий тест → `sh .claude/skills/tdd-feature/scripts/fail_first.sh tests/<файл>::<тест>` (нужен `FAIL-FIRST OK` по правильной причине) → минимальный код → `check.sh` → `git diff`. Перед тестом прочитать `writing-good-tests.md` из того же каталога.
- **Hook** (`.claude/settings.json` → `.claude/hooks/check-after-edit.sh`): PostToolUse на `Edit|Write|MultiEdit`. После правки файла в `app/`, `tests/` или `mcp_server/` сам запускает `check.sh`; при `CHECK FAIL` возвращает `decision: block` с хвостом pytest, при успехе добавляет `check.sh: CHECK PASS` в контекст. Лог: `.claude/hooks/check-after-edit.log`.
- **MCP `diff-inspector`** (`.mcp.json`, stdio, `python mcp_server/server.py`): tool `inspect_diff(diff, max_bytes=100000)` разбирает unified diff и возвращает файлы, добавленные/удаленные строки, `size_bytes`, `too_large`, `would_be_accepted`. Использовать, чтобы заранее узнать, примет ли API этот diff. Пустой diff и текст без признаков diff дают ошибку tool. Рядом в `.mcp.json` подключен `context7` (документация библиотек, нужна сеть).
- **Python:** `check.sh` берет `$PYTHON`, иначе `.venv`, иначе `python` из PATH. Зависимости в `requirements.txt`.
