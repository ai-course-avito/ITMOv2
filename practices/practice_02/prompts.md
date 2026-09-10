# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: practices/practice_01/problem.md — раздел Метрики.
- Что в нём нужно улучшить: сделать метрики проверяемыми, привязанными к SEC-1, API-1, REL-1, OUT-1; описать способы замера.
- Как поймём, что изменение полезно: контракт- и E2E-тесты подтверждают формат OUT-1, редактирование секретов, 413 для длинных diff, таймаут и контролируемые ошибки.

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | @practices/practice_01/problem.md — Метрики | Добавили проверяемые метрики для SEC-1, API-1, REL-1, OUT-1 | Контракт-тесты и E2E | Отклонены расплывчатые KPI |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | @practices/practice_01/context.md — Ограничения | Уточнили запреты (логирование, полномочия) | Проверка по CASE.md | Исключены нерелевантные правила |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | @practices/practice_01/problem.md — Почему метрики | Добавили обоснование, связали метрики с рисками | Peer review | Отклонены неподтверждённые доводы |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | @practices/practice_01/context.md — Формат результата | Выбрали JSON OUT-1 как дефолт | Сравнение альтернатив | Отклонены свободные тексты |
| RAG | [`rag/experiment.md`](rag/experiment.md) | @practices/practice_01/context.md — Факты и правила | Перенесли только релевантные правила | Ссылки на CASE.md | Исключены DB/i18n правила |
| ReAct | [`react/experiment.md`](react/experiment.md) | @practices/practice_01/prompts.md — Master Prompt | Уточнили шаги, остановку и DoD | Тест сценария | Отклонены лишние действия |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность |  |  |
| Непроверяемое требование |  |  |
| Пропущенный риск или источник |  |  |
