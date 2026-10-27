# Implementation Plan: Логика проверяемого ревью PR

**Branch**: `practice_05` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-review-logic/spec.md`, [CONTRACT.md v1.0](../../../CONTRACT.md), [approval](../../../evidence/approval.md).

## Summary

Синхронный для клиента API принимает текстовый diff, проверяет ограничения, маскирует согласованные секреты, вызывает один async adapter и выдаёт проверенную рекомендацию. FastAPI также отдаёт отдельные статические файлы UI. Demo использует детерминированные правила по реально показанным строкам; live — HTTPX chat/completions adapter. Ответ сначала маскируется, потом окончательно проверяется вместе с evidence. Код этим планом не создаётся.

## Technical Context

**Language/Version**: Python 3.13 (локально проверен 3.13.7).

**Primary Dependencies**: FastAPI 0.162.0, HTTPX 0.28.1, Uvicorn 0.54.0; зависимости и Makefile ведёт root.

**Storage**: Только оперативная память одного запроса, без DB/истории.

**Testing**: unittest / IsolatedAsyncioTestCase, HTTPX ASGITransport и MockTransport, инъекция fake adapter; браузерную e2e-проверку ведёт root.

**Target Platform**: Локальный Linux, браузер через localhost, без публичной публикации.

**Project Type**: Небольшое web-приложение с API и static UI.

**Performance Goals**: Один внешний анализ ≤10 секунд, UI прекращает ожидание через 15 секунд; эксплуатационный throughput не заявляется.

**Constraints**: 20 000 Unicode code points до нормализации; 0–3 риска с точной цитатой, 1–10 checks; один вызов, нет retry/fallback. Приложение логирует только request_id/duration_ms/status.

**Scale/Scope**: Один экран, один diff за попытку, два режима, никаких аккаунтов/GitHub/истории.

## Constitution Check

| Gate | До research | После design |
| --- | --- | --- |
| Независимые specs и снимки before | PASS: evidence/before/logic и /ui сохранены координатором | PASS: текущая spec ссылается на v1.0 |
| Явное решение человека до кода | PASS: approval.md, «Тогда одобряю» | PASS: только документы, код ещё не начат |
| summary, ≤3 risks, checks и подтверждение | PASS: обязательная строка/координаты у каждого риска | PASS: contracts/api.md и валидатор в плане |
| SEC-1, ключ вне клиента/repo, OBS-1 | PASS: конечное покрытие описано | PASS: маскирование до внешнего вызова и перед финальной валидацией, минимальный журнал |
| Сквозная приёмка и честное demo | PASS: запланированы success и ошибки | PASS: root владеет e2e, mode demo видим, live не имитируется |

Нарушений нет. Выбор обязательной цитаты — принятое уточнение QA-1, а не неподтверждённое автоматическое согласование.

## Project Structure

### Documentation (this feature)

```text
specs/002-review-logic/
├── spec.md
├── contract-proposal.md
├── checklists/requirements.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/api.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

Пути ниже от корня project; это запланированная структура.

```text
app/
├── __init__.py
├── api.py          # app.api:app, HTTP boundary, GET /, /static/*, safe envelope/log
├── config.py       # REVIEW_MODE/REVIEW_LLM_URL/MODEL/KEY
├── diff.py         # validation, partial hunks, coordinate index
├── secrets.py      # finite redaction coverage
├── review.py       # orchestration, final output/evidence validation
└── llm.py          # demo rules and async chat/completions adapter
tests/
├── test_logic.py   # agent logic
├── test_api.py     # agent logic
└── test_e2e.py     # root
static/            # UI team: index.html, app.js, styles.css
requirements.txt   # root
Makefile           # root
README.md          # root
```

**Structure Decision**: Одна FastAPI app, шесть небольших модулей с одной ответственностью; model dictionaries валидируются строго без неявных преобразований типов. Сервис получает adapter через инъекцию, поэтому tests не требуют внешней сети и ключей. UI и логика используют один origin.

## Implementation Sequence

1. Конфигурация и safe errors; парсер координат и маскирование.
2. Общий validator и service pipeline; demo и успешный API.
3. Граничные входы, async live adapter, таймаут/отмена/сбои, безопасный журнал.
4. API/unit проверки; соединение с UI и e2e под управлением root.

Полный публичный сценарий допускается только после проверок приватности и ошибок. Детали и обоснования — в [research.md](research.md), контракт — в [contracts/api.md](contracts/api.md).

## Complexity Tracking

Нарушений constitution и дополнительных инфраструктурных слоёв нет; исключения не требуются.
