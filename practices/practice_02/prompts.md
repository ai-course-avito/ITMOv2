# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: practices/practice_01/problem.md — противоречит правилам P1-03 (исключает лимит diff), привязан к P1-02, метрики не покрывают API-1 и REL-1.
- Что в нём нужно улучшить: согласовать область с P1-03 (включить API-1 и REL-1), добавить метрики для 413 при >20,000 и таймаута LLM 10 с, обновить «Как использовали AI» до P1-03.
- Как поймём, что изменение полезно: устранено противоречие со всеми артефактами P1-03; присутствуют метрики под 413 и таймаут; интеграционные/E2E тесты, ожидающие 413 и контролируемый таймаут, согласованы с problem.md.

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | practices/practice_01/problem.md | Убрали исключение «лимиты на размер diff»; добавили метрики API-1 и REL-1; обновили «Как использовали AI» на P1-03 | POST {} -> 422; POST 20001 -> 413; LLM >10с -> контролируемый ответ | Метрики вне P1-03 (SEC) в problem.md |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | practices/practice_01/problem.md | Согласовали область с P1-03; добавили проверяемые метрики; указали источники | Сопоставление с context.md:54-60; tests_* file:line | Расширение области на SEC/OBS в problem.md |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | practices/practice_01/problem.md | Уточнили формулировки метрик как воспроизводимые шаги | Таблица вопросов + ссылки на tests_integration.md:6; tests_e2e.md:7; tests_load.md:5 | Добавление лишних метрик |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | practices/practice_01/problem.md | Зафиксировали, что 413 формируется на уровне FastAPI endpoint | Интеграционный тест POST 20001 -> 413; OpenAPI 413 | Реализация в middleware/сервисе |
| RAG | [`rag/experiment.md`](rag/experiment.md) | practices/practice_01/problem.md | Добавили метрики с привязкой к источникам (file:line) | context.md:54-60; adr.md:13-18; tests_* ссылки | Внешние источники вне списка |
| ReAct | [`react/experiment.md`](react/experiment.md) | practices/practice_01/problem.md | Пошаговая корректировка артефакта по разрешённым действиям | Логи шагов + ссылки на источники | Правки вне области P1-03 |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность |  |  |
| Непроверяемое требование |  |  |
| Пропущенный риск или источник |  |  |

## Снимок и доказательства

### Артефакт: practices/practice_01/problem.md (snapshot)

```
# Проблема и метрики

## Проблема

- Пользователь: разработчик или CI, вызывающий API для AI‑ревью PR.
- Ситуация: он отправляет diff в POST /api/reviews и ожидает стабильный валидированный ответ.
- Что происходит сейчас: тело запроса не валидируется (сырое dict), при отсутствии ключа "diff" возникает KeyError и 500; схема ответа не зафиксирована; LLM‑промпт формируется без ограничений формата и пост‑обработки.
- Почему это мешает пользователю или бизнесу: нестабильный контракт API ломает интеграции; ошибки 500 вместо 422 маскируют ошибки клиента; повышенные риски prompt injection и небезопасного вывода создают операционные и репутационные риски.
- Что не входит в задачу: выбор и настройка провайдера LLM; оптимизация качества ревью; лимиты на размер diff.

## Метрики

Выберите измеримые показатели, относящиеся к проблеме. Не используйте VTG, IRR, WACC, CSAT или другую метрику только ради названия.

| Метрика | Текущее значение или способ замера | Целевое изменение | Когда измеряем | Источник данных |
|---|---:|---:|---|---|
| Доля запросов с 5xx при невалидном теле | Отправить {} в /api/reviews, ожидание 500 | 0% (422 вместо 5xx) | До/после фикса | Логи/интеграционный тест |
| Наличие зафиксированной схемы ответа | Нет response_model | Есть response_model и валидация | После фикса | OpenAPI schema / тест ответа |

## Почему изменение метрики подтвердит решение проблемы

Снижение 5xx на невалидном входе и появление валидации ответа подтверждают стабилизацию контракта API и улучшают DX/надёжность интеграций.

## Как использовали AI

- Для чего: сформулировать проблему и измеримые метрики контракта API.
- Тип промпта: master prompt.
- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: проверили соответствие формулировок коду diff и правилам FastAPI; исключили лишние гипотезы.
```

### Proof: practices/practice_01/problem.md — ненадёжный артефакт

- Прямое противоречие по области с API-1:
  practices/practice_01/problem.md:9 исключает из задачи «лимиты на размер diff», тогда как API-1 включён в правила P1-03 во множестве артефактов:
  - practices/practice_01/prompts.md:113-119 — правила P1-03 содержат `API-1: A diff longer than 20,000 characters is rejected with an HTTP 413 error.`
  - practices/practice_01/context.md:54-60 — список правил включает API-1.
  - practices/practice_01/adr.md:13-18 — решение фиксирует API-1 (413 при >20,000).
  - practices/practice_01/analysis.md:13-16 — TO BE включает проверку длины и 413.
  - practices/practice_01/product_management.md:20 — acceptance criteria ожидают 413 при 20001 символе.
  - practices/practice_01/project_management.md:7 — Инкремент 1: «Валидация тела и лимит длины».
  - practices/practice_01/tests_integration.md:6 — ожидается 413 при >20k.
  - practices/practice_01/tests_load.md:5 — нагрузочный сценарий ожидает 413.
  - practices/practice_01/tests_e2e.md:7 — граничный кейс ожидает 413.

- Несогласованность фаз: problem.md привязан к P1-02, тогда как пакет артефактов — к P1-03.
  - practices/practice_01/problem.md:24-29 — «Строка в prompts.md: P1-02», master prompt.
  - Прочие артефакты (prompts.md раздел P1-03; context.md раздел «Правила и цели P1-03»; ADR/analysis/PM/tests) уже отражают правила SEC/API/REL/OUT/OBS для P1-03.

- Пробелы метрик относительно принятых требований P1-03:
  - practices/practice_01/problem.md:15-19 — метрики охватывают только 5xx на невалидном теле и наличие response_model; нет метрики для 413 (API-1) и нет метрики для таймаута LLM (REL-1).
  - В то же время документы фиксируют API-1 и REL-1: practices/practice_01/prompts.md:113-116; practices/practice_01/context.md:54-57; practices/practice_01/adr.md:13-16; practices/practice_01/analysis.md:13-16; practices/practice_01/product_management.md:20.

- Следствие: problem.md дезориентирует реализацию и валидацию, объявляя вне области то, что другие артефакты требуют, и не задавая метрик под обязательные правила P1-03. Это делает practices/practice_01/problem.md наименее надёжным артефактом набора.

### Как проверено

- Сверены строки в problem.md:9 и 24-29 с содержанием документа.
- Сопоставлены правила и ожидания в prompts.md:113-119; context.md:54-60; adr.md:13-18; analysis.md:13-16; product_management.md:20; project_management.md:7; tests_integration.md:6; tests_load.md:5; tests_e2e.md:7.
Файл ведёт OpenCode по вашим запросам. Агент записывает фактические результаты экспериментов и вносит изменения в связанные файлы. Свою оценку сообщайте ему в чате; вручную заполнять шаблон не нужно.

- Выбранный слабый артефакт Практики 1:
- Что в нём нужно улучшить:
- Как поймём, что изменение полезно:

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) |  |  |  |  |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) |  |  |  |  |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) |  |  |  |  |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) |  |  |  |  |
| RAG | [`rag/experiment.md`](rag/experiment.md) |  |  |  |  |
| ReAct | [`react/experiment.md`](react/experiment.md) |  |  |  |  |
