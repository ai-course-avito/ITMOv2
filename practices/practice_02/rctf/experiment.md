# R.C.T.F.

- Role: я технический писатель, готовлю E2E‑тесты для FastAPI‑сервиса AI‑ревью PR.
- Context: POST `/api/reviews`, вход JSON `{"diff": "..."}`; ответ по TRAINING_PR.diff: `{ "comment": "..." }`. CASE: API‑1 (413 при diff > 20000), OBS‑1 (в логах только request_id, duration, status), REL‑1 (таймаут LLM 10с). Вне scope: GitHub/БД/auth. LLM — замокан.
- Task: переписать tests_e2e.md под 3–4 сценария (позитивный, негативный, граничный, опционально таймаут), выдать воспроизводимый Evidence на основе TRAINING_PR.diff и CASE.
- Format: одна таблица `Сценарий | Предусловия | Действие | Наблюдаемый результат | Evidence`; Evidence = HTTP‑статус + проверяемое поле + строка лога без содержимого diff; в конце раздел «Как использовали AI» со ссылкой на P2‑03 в prompts.md.

## Что получили

- Позитивный: корректный diff → HTTP 200; `$.comment` непустой; лог `request_id=<uuid> status=200 duration=<ms>` без подстроки `diff --git`.
- Негативный: отсутствует `diff` → HTTP 422; `$.detail` упоминает `diff`; лог `request_id=<uuid> status=422 duration=<ms>` без содержимого diff.
- Граничный: длина `diff` ровно 20000 → HTTP 200; `$.comment` непустой; лог `status=200` без содержимого diff.
- Негативный: `diff` длиной > 20000 → HTTP 413; лог `request_id=<uuid> status=413 duration=<ms>` без содержимого diff.

## Что изменили в исходном артефакте

- Было: 1 сценарий с размытым Evidence (лог/тест‑раннер), ожидаемые поля `summary/risks/checks`.
- Стало: 4 сценария; Evidence стандартизован до «HTTP‑статус + поле ответа + лог без diff»; контракт ответа выровнен с TRAINING_PR.diff (`comment`).
- Проверка: сверка с TRAINING_PR.diff (app/api.py L35–38; app/review_service.py L19–22) и CASE.md (API‑1, OBS‑1).
- Что отклонили: AS IS‑описание 500 KeyError для отсутствующего `diff` (заменено на TO BE 422); сценарии с реальным LLM‑вызовом (вне scope).

## Как использовали AI

- Тип промпта: RCTF.
- Строка в `prompts.md`.
