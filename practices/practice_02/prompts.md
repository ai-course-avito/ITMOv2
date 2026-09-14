# Журнал экспериментов Практики 2

- Выбранный слабый артефакт Практики 1: practices/practice_01/CASE.md
- Что в нём нужно улучшить:
  - Несогласованный лимит размера diff в правиле API-1: в CASE.md указано «diff длиннее 20 000 символов отклоняется с HTTP 413» (см. CASE.md:64–71), в остальных артефактах и тестах принят предел 64 KiB. Нужно унифицировать на 64 KiB.
  - Пересечение/двусмысленность формата результата OUT-1: в CASE.md он описывает «summary/risks/checks» (для учебного запуска), тогда как в Context Pack сервиса — «comments + summary». Нужно явно разделить контракты: OUT-1 (P1 учебный) vs OUT-1 (сервис), либо привести к одному набору с пометкой области применения.
  - Убрать расплывчатые формулировки и добавить трассируемость к тестам: где вводится правило, туда же дать ссылку на соответствующие тесты (unit/integration/load/e2e), чтобы исключить расхождения.
  - Предлагаемое исправление: в CASE.md заменить API-1 на «diff длиннее 64 KiB отклоняется 413/422», добавить примечание о различии артефактов P1 и сервиса для OUT-1, и ссылку на tests_* файлы с конкретными порогами.
- Как поймём, что изменение полезно:
  - Греп-проверка по репозиторию не находит «20 000» или других альтернативных лимитов; все упоминания консолидированы на «64 KiB».
  - Все тестовые артефакты согласованы: tests_unit.md, tests_integration.md, tests_load.md, tests_e2e.md указывают 64 KiB и ни один не противоречит CASE.md.
  - Второй запуск с Master Prompt больше не сталкивается с конфликтующими правилами OUT-1 и не требует ручных оговорок.
  - Evidence: ссылка на обновлённые строки CASE.md (API-1) и явное разграничение форматов результата.

| Техника | Файл эксперимента | Изменённый файл Практики 1 | Конкретное изменение | Проверка | Что отклонили |
|---|---|---|---|---|---|
| Few-shot | [`few_shot/experiment.md`](few_shot/experiment.md) | practices/practice_01/CASE.md | API-1 → 64 KiB (413/422); OUT-1 разделён (учебный/сервисный) | grep: нет «20 000»; tests_e2e: 413/422; ссылки на context/tests | Отклонено: 20 000 символов; единый OUT-1 |
| R.C.T.F. | [`rctf/experiment.md`](rctf/experiment.md) | practices/practice_01/CASE.md | Уточнить API-1 на 64 KiB; разделить OUT-1 (P1 учебный) и OUT-1 (сервис) | Grep: отсутствует «20 000»; все упоминания лимита — «64 KiB»; сверка с tests_* | Отклонено: оставить 20 000 символов «как проще»; смешивать форматы результата без явной области применения |
| Chain of Verification | [`chain_of_verification/experiment.md`](chain_of_verification/experiment.md) | practices/practice_01/CASE.md | Подтвердить 64 KiB и разделить OUT-1 по evidence | Таблица вопросов + ссылки; Patch применим | Отклонено: неподтверждённые правила |
| Tree of Thoughts | [`tree_of_thoughts/experiment.md`](tree_of_thoughts/experiment.md) | practices/practice_01/CASE.md | Выбрать стратегию (A) и описать Patch OUT-1/API-1 | Сверка References; критерии выбора | Отклонено: B/C стратегии |
| RAG | [`rag/experiment.md`](rag/experiment.md) | practices/practice_01/CASE.md | Согласовать факты: 64 KiB и форматы; предложить Patch | Findings с цитатами; Synthesis; Patch | Отклонено: выводы без цитат |
| ReAct | [`react/experiment.md`](react/experiment.md) | practices/practice_01/CASE.md | Зафиксировать конфликт → предложить Patch → Acceptance | Steps/Result заполнены; grep/ссылки | Отклонено: фабрикация evidence |

## Независимое ревью

| Замечание другой команды | Где исправили | Evidence |
|---|---|---|
| Двусмысленность (лимит/коды) | few_shot/experiment.md: References включают tests_integration.md:9–10 (отсутствие diff), что не подтверждает 413/422 для превышения размера | few_shot/experiment.md:32–37; tests_integration.md:9–10; tests_e2e.md:7–8 |
| Двусмысленность (лимит/коды) | rctf/experiment.md: References также ссылаются на tests_integration.md:9–10 вместо tests_e2e.md для лимита | rctf/experiment.md:21–25; tests_e2e.md:7–8 |
| Непроверяемое требование (цитаты) | rag/experiment.md: Требуются прямые цитаты; для CASE.md указано лишь «место правок» без цитаты | rag/experiment.md:21–44 (Findings), отсутствие цитаты для CASE.md |
| Пропущенный риск (фабрикация evidence) | react/experiment.md: Шаг 1/5 утверждает, что CASE.md уже содержит «64 KiB» и grep не находит «20 000», чего нет до правки | react/experiment.md:42–46, 50–55; CASE.md:64–71 (20 000 символов) |
| Двусмысленность (область применения форматов) | few_shot/rctf: Patch формулирует разделение OUT-1, но не указывает явную секцию/формат вставки в CASE.md | few_shot/experiment.md:24–37; rctf/experiment.md:12–26 |
| Источники без трассировки | tree_of_thoughts: References не содержат цитат; только список файлов/строк | tree_of_thoughts/experiment.md:52–58 |
| Что и где исправить | Обновить ссылки на tests_e2e.md для лимита; добавить прямые цитаты для CASE.md в RAG; скорректировать наблюдения в ReAct (показать конфликт до патча); конкретизировать секцию OUT-1 для вставки | few_shot/rctf/rag/react/tree_of_thoughts — соответствующие блоки Output |
