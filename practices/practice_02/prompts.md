# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: `practices/practice_01/product_management.md` (раздел "User Stories и acceptance criteria").
- Что в нём нужно улучшить: критерии приёмки были описаны свободным текстом и допускали двусмысленность; привести их к воспроизводимым Gherkin-сценариям.
- Как поймём, что изменение полезно: в файле появляются блоки ```gherkin``` для каждой story; Makefile Практики 1 «grep -q '```gherkin' product_management.md» проходит; критерии однозначно проверяются тестами из `tests_*`. 

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | `practices/practice_01/product_management.md` (раздел «User Stories и acceptance criteria») | Переписали критерии US-01..US-05 как Gherkin-сценарии в код-блоках ```gherkin``` | Проверка: `make -C practices/practice_01 test` проходит шаг с `grep -q '```gherkin' product_management.md`; сценарии согласованы с метриками `problem.md` | Отклонено: свободные формулировки без Given/When/Then |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | `practices/practice_01/adr.md` (раздел Decision/Rationale) | Уточнили критерии выбора (срок, сложность, риск) для варианта A и добавили OBS-1 как интеграционную точку | Проверка: в `adr.md` присутствуют обновлённые разделы Decision/Rationale и Integration points; согласовано с CASE.md | Отклонено: переход к C (воркер) в первом инкременте |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | `practices/practice_01/product_management.md` (US-02) | Исправили формулировку сценария: «20001 символов» и явный Then про 413 Payload Too Large | Проверка: визуальный diff; согласовано с CASE.md API-1 и tests_integration.md | Отклонено: детализированное сообщение об ошибке вне объёма |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | `practices/practice_01/project_management.md` (Риски и митигации) | Зафиксировали выбор базовых regex-паттернов для SEC-1 как стартовую стратегию | Проверка: таблица альтернатив → выбор A; риск обновлён в project_management.md | Отклонено: интеграция внешнего сканера секретов на первом шаге |
| RAG | [`rag/experiment.md`](rag/experiment.md) | `practices/practice_01/product_management.md` (US-03 Метрика) | Добавили ссылку на правило SEC-1 из CASE.md в метрике US-03 | Проверка: ссылка/упоминание SEC-1 рядом с метрикой; источники в rag/experiment.md | Отклонено: добавление новых правил без источников |
| ReAct | [`react/experiment.md`](react/experiment.md) | `practices/practice_01/tests_e2e.md` | Добавили E2E сценарий «Отсутствует diff → 422» | Проверка: таблица e2e содержит новый сценарий; согласовано с US-01 | Отклонено: запуск реального сервиса без моков в рамках практики |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность: «20001 символ» в US-02 | product_management.md (US-02) | исправили на «20001 символов», добавили явный Then → 413 |
| Непроверяемое требование: P95 «≤ SLA» | problem.md (метрики) | уточнили целевое значение «≤ 1.5 с (с таймаутами LLM)» |
| Пропущенный сценарий: E2E на отсутствие diff | tests_e2e.md | добавлен сценарий «Отсутствует diff → 422», привязан к US-01 |
