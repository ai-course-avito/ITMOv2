# Журнал экспериментов Практики 2

 - Выбранный слабый артефакт Практики 1: practices/practice_01/tests_load.md
 - Что в нём нужно улучшить: критерии и методика без неподтверждённых норм; явные ссылки на правила и метрики
 - Как поймём, что изменение полезно: pass/fail завязан только на p95 (REL-1), 413 (API-1) и OBS-1; нет спорных чисел; сценарии остаются воспроизводимыми

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | practices/practice_01/tests_load.md | Добавлены сценарии, методика, критерии pass/fail по REL-1/API-1/OBS-1 | Сверка с CASE.md/problem.md; читаемость сценариев | Убраны произвольные пороги и распределения |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | practices/practice_01/tests_load.md | Сжали критерии до подтверждённых норм; уточнили формулировки | Цитаты и ссылки в rctf/experiment.md | Новые SLO/ошибки % без источников |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | practices/practice_01/tests_load.md | Точечные правки: 100% контролируемых ответов при таймауте; лишние пороги удалены | Таблица вопросов и evidence | «Нет вызова LLM» как критерий — отклонено |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | practices/practice_01/tests_load.md | Выбрана стратегия A+B: критерии по нормам + наблюдения без порогов | Сопоставление с критериями выбора | Экспериментальные пороги |
| RAG | [`rag/experiment.md`](rag/experiment.md) | practices/practice_01/tests_load.md | Подтвердили цитатами нормы; собрали минимальные правки | Таблица ссылок file:lines | Внешние источники |
| ReAct | [`react/experiment.md`](react/experiment.md) | practices/practice_01/tests_load.md | Пошаговое удаление неподтверждённых мест и уточнения | Локальная сверка после каждого шага | Изменение rps/длительностей шагов |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность | tests_load.md — уточнили формулировку про «нет вызова LLM» как дополнительную проверку | CASE.md:65; tests_integration.md:5 |
| Непроверяемое требование | tests_load.md — убрали «ошибки ≤1%», «стабилизация ≤60с», «восстановление ≤2 мин» | problem.md:19–20 подтверждают только p95 и 413 |
| Пропущенный риск или источник | tests_load.md — добавили ссылку на OBS-1 и SECRET_MARKER в методике/критериях | CASE.md:70; tests_integration.md:8 |
