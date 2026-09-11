# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: practice_01/tests_e2e.md
- Что в нём нужно улучшить: был 1 размытый сценарий без негативных и граничных кейсов, Evidence расплывчатый
- Как поймём, что изменение полезно: появятся сценарии с конкретным Evidence (HTTP-статус + проверяемое поле + лог), покрытие правил CASE

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | few_shot/tests_e2e.md | Было 1 сценарий → стало 3: позитивный, негативный (422), граничный (413); Evidence уточнён до HTTP-статуса и проверяемых полей | Сверка с CASE.md (API-1, OUT-1, OBS-1) и TRAINING_PR.diff | Сценарии с реальным LLM, интеграции с GitHub — вне scope кейса |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | rctf/tests_e2e.md | Было 1 сценарий → стало 4: позитивный, 422, граничный (20000), 413 (20001); Evidence = HTTP-статус + поле + лог | Сверка с CASE.md (API-1, OUT-1, OBS-1) и TRAINING_PR.diff | AS IS-описание 500 KeyError; сценарии с реальным LLM |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | chain_of_verification/tests_e2e.md | Формат ответа приведён к фактическому контракту: comment вместо summary/risks/checks; Evidence уточнён до HTTP 200 + JSONPath $.comment | Сверка с TRAINING_PR.diff (app/api.py L35–38, app/review_service.py L19–22) и CASE.md (OBS-1) | summary/risks/checks как не подтверждённые кодом; логи с содержимым diff (запрещено OBS-1) |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | tree_of_thoughts/tests_e2e.md | Было 1 сценарий → стало 6: успех, кэп risks, границы 20000/20001, таймаут LLM, проверка логов | Сверка с CASE.md (API-1, OUT-1, OBS-1, REL-1) | Альтернативы B (property-based) и C (smoke) — избыточны или неполны |
| RAG | [`rag/experiment.md`](rag/experiment.md) | rag/tests_e2e.md | 7 сценариев, каждый со ссылкой на источник; добавлен раздел «Источники и доказательства» | Каждая ссылка проверена на реальный фрагмент | Сценарии с реальным LLM, GitHub, БД, auth |
| ReAct | [`react/experiment.md`](react/experiment.md) | react/tests_e2e.md | 1 → 8 сценариев через цикл | Каждый сценарий обоснован Observation | Сценарии без Observation |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность: в CoV-версии контракт `comment`, а в Практике 1 — `summary/risks/checks` | `chain_of_verification/experiment.md` — добавлено пояснение про расхождение TO BE/AS IS | Раздел «Что отклонили» |
| Непроверяемое требование: таймаут LLM в ToT без конкретного статуса | `tree_of_thoughts/tests_e2e.md` — сценарий 5 уточнён (`503/504 или 200 с пометкой`) | Строка 5 таблицы |
| Пропущенный источник: в RAG не было ссылки на `problem.md` | `rag/experiment.md` — добавлена строка в таблицу источников | Раздел «Разрешённые источники» |
