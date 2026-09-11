# Журнал запросов и проверок

Не сохраняйте скрытую Chain of Thought и полный чат. Нужны запрос, краткий результат, ссылка на изменённый артефакт и ваша проверка.

| ID | Артефакт и цель | Инструмент / модель | Тип промпта | Запрос или ссылка на него | Результат или ссылка | Что приняли | Что отклонили или исправили | Как проверили |
|---|---|---|---|---|---|---|---|---|
| P1-01 | Baseline-ревью `TRAINING_PR.diff` | openai/gpt-5 | zero-shot | Посмотри PR TRAINING_PR.diff и найди проблемы | См. подробный вывод: [resault_ai.md](resault_ai.md) | Принято: отсутствие валидации входа (KeyError->500), нет обработки ошибок/таймаута LLM, ответ не соответствует OUT-1 (возврат `{"comment": "..."}`). | Отклонено: гипотезы без evidence и вне scope (аутентификация/rate limiting, версионирование API, стиль, потенциальный import). | Проверка: сопоставление с TRAINING_PR.diff (app/api.py:35-38; app/review_service.py:19-22), логический прогон кода; подтверждено несоответствие OUT-1 (возврат `{"comment": "..."}`). |
| P1-02 | Повторное ревью с master prompt | openai/gpt-5 | master prompt | Используй Master Prompt v1 ниже и файл `practices/practice_01/TRAINING_PR.diff`. Соблюдай SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1. | Ответ: JSON со `summary`, `risks` (≤3) и `checks`; риски подтверждены evidence (file:line) из diff или правилом. | Принято: только подтверждённые риски; формат OUT-1 соблюдён. | Отклонено: неподтверждённые гипотезы (напр., аутентификация) — не включены в риски. | Проверено сопоставлением строк TRAINING_PR.diff (app/review_service.py:19-22; app/api.py:35-37) и правил; ручная валидация формата. |
| P1-03 | Домашка: сгенерировать `context.md` и `problem.md` (контекст и проблема) | openai/gpt-5 | master prompt | См. [`hw_prompts/01_context_problem.md`](hw_prompts/01_context_problem.md) | [`context.md`](context.md), [`problem.md`](problem.md): Summary, таблица AS IS, Context Pack с 7 правилами, 3 измеримые метрики, «Как использовали AI» | Принято: привязка каждого пункта к SEC-1/API-1/REL-1/OUT-1/OBS-1; 3 метрики (доля OUT-1, 5xx при таймауте, доля 413) | Отклонено: правила snake_case/i18n (не относятся к кейсу); метрики без источника данных (CSAT/VTG/IRR) | `make test` grep `## Context Pack` и `## Метрики` — OK; сверка с [`CASE.md`](CASE.md) и [`TRAINING_PR.diff`](TRAINING_PR.diff) |
| P1-04 | Домашка: сгенерировать `analysis.md` и `adr.md` (анализ процесса и архитектурное решение) | openai/gpt-5 | master prompt | См. [`hw_prompts/02_analysis_adr.md`](hw_prompts/02_analysis_adr.md) | [`analysis.md`](analysis.md) с TO BE flowchart и таблицей «Разница»; [`adr.md`](adr.md) с 3 альтернативами и `## Архитектурная схема` | Принято: 9-узловой TO BE flowchart с ветвями API-1/REL-1; связность компонентов схемы ADR с TRAINING_PR.diff | Отклонено: async-очередь как основной вариант (не соответствует первому сценарию); альтернативы без обоснования отказа | grep `## TO BE`, `## Архитектурная схема` — OK; сверка компонентов (FastAPI, ReviewService, LLM, Logger) с diff |
| P1-05 | Домашка: сгенерировать `product_management.md` и `project_management.md` (сценарий и план поставки) | openai/gpt-5 | master prompt | См. [`hw_prompts/03_product_project.md`](hw_prompts/03_product_project.md) | [`product_management.md`](product_management.md): When/Then, use case, sequenceDiagram под кейс, 2 Gherkin; [`project_management.md`](project_management.md): 3 инкремента и Gantt с параллельностью и milestone | Принято: Gherkin позитив/негатив 413; sequenceDiagram с реальными участниками (Client/FastAPI/ReviewService/LLM); Gantt с разными длительностями | Отклонено: абстрактный TEMPLATE-sequenceDiagram; Gantt со всеми задачами по 1 дню без параллельности | grep ```gherkin и ```mermaid — OK; сверка полей OUT-1 в AC с [`CASE.md`](CASE.md) |
| P1-06 | Домашка: сгенерировать `tests_unit.md`, `tests_integration.md`, `tests_e2e.md` (функциональные проверки) | openai/gpt-5 | master prompt | См. [`hw_prompts/04_tests_func.md`](hw_prompts/04_tests_func.md) | [`tests_unit.md`](tests_unit.md) 3 строки (SEC-1/API-1/OUT-1); [`tests_integration.md`](tests_integration.md) 2 строки; [`tests_e2e.md`](tests_e2e.md) 3 сценария включая граничный | Принято: конкретные входы/выходы (`token=abcd1234`, длина 20001, 20000 ровно); привязка каждой строки к правилам CASE.md | Отклонено: «проверить что работает» без ожидаемого результата; отсутствие граничного E2E-сценария | Ручная сверка полей OUT-1 в проверках; проверка соответствия строкам TRAINING_PR.diff (app/api.py:35-37; app/review_service.py:19-22) |
| P1-07 | Домашка: сгенерировать `tests_load.md` (нагрузочные проверки) | openai/gpt-5 | master prompt + few-shot | См. [`hw_prompts/05_tests_load.md`](hw_prompts/05_tests_load.md) | [`tests_load.md`](tests_load.md): 5 сценариев (база, большие diff/413, деградация LLM, soak, stress ramp), p50/p95/p99, системные метрики, «Условие включения» | Принято: реалистичные пороги, длительности ≥15/45 мин, evidence k6/Locust + Grafana/APM + трассы; учтены API-1/REL-1/OUT-1 | Отклонено: короткие ≤5 мин прогоны, размытый evidence «CASE.md», отсутствие p99 и системных метрик | Сверка порогов и длительностей; проверка distribution ≈10–15% больших diff; учтён fallback при таймауте |
| P1-08 | Домашка: пересобрать `prompts.md` — журнал и Master Prompt v1 | openai/gpt-5 | master prompt | См. [`hw_prompts/06_prompts_journal.md`](hw_prompts/06_prompts_journal.md) | [`prompts.md`](prompts.md): P1-01/P1-02 в таблице, Master Prompt v1 (8 разделов), Risks-блок (OUT-1/REL-1/API-1) с evidence и check, сравнение по 4 признакам | Принято: 8 разделов master prompt; 3 риска с evidence file:line из TRAINING_PR.diff; сравнение включает границы AI и воспроизводимую проверку | Отклонено: сохранение скрытой Chain of Thought; гипотезы вне scope (auth/rate limit) в Risks; неподтверждённые пункты сравнения | grep `P1-01`, `P1-02` — OK; полнота 8 разделов master prompt; каждая ячейка сравнения обоснована |
| P1-09 | Финальное ревью всех артефактов Практики 1 и точечные правки | openai/gpt-5 | master prompt (reviewer) | См. [`hw_prompts/07_ reviewer_all.md`](hw_prompts/07_%20reviewer_all.md) | Список точечных правок по 11 файлам: `dateFormat` в Ганте → `YYYY-MM-DD`; 3-я альтернатива в [`adr.md`](adr.md); реальный sequenceDiagram в [`product_management.md`](product_management.md); настоящий `slides/practice_01.pptx`; заполнение колонки «Вывод команды» и пометка Peer review в [`prompts.md`](prompts.md) | Принято: точечные правки, привязанные к правилам SEC-1/API-1/REL-1/OUT-1/OBS-1 и строкам TRAINING_PR.diff; сохранены якоря `make test` | Отклонено: массовые перезаписи заполненных разделов; правки TRAINING_PR.diff/CASE.md/README.md/Makefile; правки без evidence или без ссылки на правило | `make test` в practices/practice_01/ — зелёный; git diff по каждому файлу минимальный; проверка неизменности запрещённых файлов |

P1-01 — три слабых места ответа
- Нет соответствия формату OUT-1: модель вернула произвольный `{"comment": "..."}` вместо `summary/risks/checks`, что делает результат непригодным для автоматической обработки.
- Гипотезы без evidence и вне scope (аутентификация, rate limiting, версионирование) смешаны с подтверждёнными наблюдениями — снижается доказательность и читаемость.
- Недостаточно воспроизводимых проверок: не даны короткие шаги/критерии, по которым можно проверить выводы (AC/DoD не сформулированы).

P1-01 — какой информации модели не хватило
- Формализованный контракт результата (OUT-1): точные поля и формат ответа.
- Явные правила/ограничения задачи: SEC-1, API-1 (≤20000 и 413), REL-1 (таймаут 10с и контролируемая ошибка), OBS-1 (логирование без контента).
- Критерии приёмки и способ проверки: что считается доказательством, какие проверки запускать и когда остановиться (Definition of Done).

## Master Prompt v1

Соберите здесь контракт второго запуска. Не копируйте все документы целиком — ставьте ссылки на файлы и переносите только необходимый для задачи контекст.

### 1. Цель и роль

- Цель: провести ревью файла `TRAINING_PR.diff` и выдать совет по рискам/проверкам, соблюдая обязательные правила.
- Роль AI: AI-reviewer, только консультации (SCOPE-1), без прав на approve/merge/edit.

### 2. Входы и источники

- Обязательный вход: содержимое `practices/practice_01/TRAINING_PR.diff`.
- Разрешённые файлы и источники: только `TRAINING_PR.diff` и локальные контексты `context.md`, `problem.md`.
- Context Pack — факты, правила, примеры и ограничения: см. `practices/practice_01/context.md` (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1).

### 3. Задача и артефакты

- Что сделать: извлечь риски из diff, подтверждённые evidence или правилами; подготовить проверки.
- Что вернуть: JSON-структуру с `summary`, `risks` (макс. 3, поля `file`, `line`, `evidence`, `risk`), `checks`.

### 4. Формат результата

- Структура ответа: `{ "summary": str, "risks": list, "checks": list }`.
- Ограничения объёма: длина diff ≤ 20000 символов (API-1); если больше — вернуть 413; внешний вызов с таймаутом 10с (REL-1); не логировать содержимое (OBS-1).

### 5. Полномочия и запреты

- Разрешено: анализировать, советовать, формировать список risks/checks.
- Запрещено: approve, merge, edit; логировать diff/ответ; выходить за пределы входов.

### 6. Рабочий процесс и остановка

- Шаги: 1) Проверить длину diff (API-1). 2) Удалить секреты (SEC-1). 3) Сформировать prompt, вызвать LLM с таймаутом 10с (REL-1). 4) Сформировать структурированный ответ (OUT-1). 5) Логировать только request_id, длительность, статус (OBS-1).
- Когда остановиться и запросить человека: если diff пустой/битый; если после SEC-1 остаётся сомнение в корректности; если таймаут/ошибка LLM не позволяют сделать выводы.

### 7. Проверки и evidence

- Как проверять утверждения: сопоставлять каждый риск с конкретной строкой diff и/или явным правилом; отклонять неподтверждённые гипотезы (QA-1).
- Какое evidence сохранить: цитаты из `TRAINING_PR.diff` с координатами file:line; перечень проверок для воспроизведения.

Risks (OUT-1, макс. 3):

- candidate: OUT-1 — неверный формат ответа.
  evidence: app/review_service.py:19-22 (TRAINING_PR.diff):
    "def review(self, diff: str) -> dict[str, str]: ... return {\"comment\": answer}"
  check: вызвать `/api/reviews` и убедиться, что поле `summary` отсутствует, структура не соответствует OUT-1.

- candidate: REL-1 — нет таймаута/контролируемого ответа при сбое LLM.
  evidence: app/review_service.py:20-22 (TRAINING_PR.diff):
    "answer = self.llm.generate(prompt)" без try/except, без таймаута.
  check: смоделировать таймаут/исключение у LLM; ожидать контролируемый ответ, фактически — 5xx/исключение.

- candidate: API-1 — нет проверки длины diff и 413.
  evidence: app/api.py:35-37 (TRAINING_PR.diff):
    "return review_service.review(payload[\"diff\"])" — отсутствует проверка длины.
  check: отправить diff >20000 символов; ожидать 413; фактически — запрос уходит в LLM.

### 8. Definition of Done

- Задача закончена, когда: подготовлен ответ в формате OUT-1 с ≤3 рисками, каждый подтверждён evidence, даны проверки; соблюдены SEC-1, API-1, REL-1, OBS-1 и SCOPE-1.

## Сравнение двух запусков

| Проверка | Zero-shot | С master prompt | Вывод команды |
|---|---|---|---|
| Есть ссылка на файл или строку | P1-01: частично; есть app/api.py:35-38 и app/review_service.py:19-22 | P1-02: да; явные file:line по каждому риску | Master prompt даёт file:line по каждому риску; zero-shot — гипотезы |
| Вывод подтверждён diff или правилом | P1-01: частично; смешаны гипотезы без evidence с фактами | P1-02: да; каждый риск подтвержден diff/правилами (SEC/API/REL/OUT) | Master prompt удерживает evidence-only режим (QA-1) |
| Соблюдены границы AI | P1-01: в целом да; местами советы вне scope (auth/rate limit) | P1-02: да; соблюден SCOPE-1 | Master prompt соблюдает SCOPE-1; zero-shot выходит в auth/rate limit |
| Есть воспроизводимая проверка | P1-01: частично; проверки не оформлены как шаги/AC | P1-02: да; есть шаги: >20000->413, таймаут->контролируемый ответ, OUT-1 | Master prompt формирует checks по OUT-1/API-1/REL-1 |

## Peer review

| Где другой команде пришлось догадываться | Что исправили | Если не исправили — почему |
|---|---|---|
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |

