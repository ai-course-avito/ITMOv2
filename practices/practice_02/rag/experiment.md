# RAG

Файл ведёт OpenCode по вашим запросам. Агент записывает фактические результаты экспериментов и вносит изменения в связанные файлы. Свою оценку сообщайте ему в чате; вручную заполнять шаблон не нужно.

- Вопрос к источникам:
  - Какой лимит diff принят в артефактах и тестах? Какой формат результата должен применяться в учебном сценарии P1 и в сервисе? Какие источники подтверждают это?

## Разрешённые источники

| Файл или документ | Зачем нужен | Какой фрагмент используем |
|---|---|---|
| practices/practice_01/CASE.md | Базовые правила (API-1, OUT-1) | Раздел «Материалы для Context Pack», строки с API-1/OUT-1 |
| practices/practice_01/context.md | Контекст и формат для сервиса | Формат входа/выхода, лимит 64 KiB |
| practices/practice_01/tests_unit.md | Evidence лимита | Таблица, строки про лимит и валидацию |
| practices/practice_01/tests_integration.md | Evidence статусов 413/422 | Строки про API POST и лимит |
| practices/practice_01/tests_e2e.md | Evidence граничного кейса | Сценарий про 64 KiB и 413/422 |
| practices/practice_01/product_management.md | AC по лимиту | Gherkin сценарии 78–81 |

## Запрос
Собери подтверждения из источников по двум вопросам: лимит diff (в KiB, ожидаемо 64 KiB) и форматы OUT-1 (учебный vs сервисный). Верни сжатое резюме с прямыми ссылками на строки.

## Ответ со ссылками на источники
<!-- OUTPUT:RAG:START -->
Findings
- practices/practice_01/CASE.md:65 — "API-1: diff длиннее 64 KiB отклоняется с HTTP 413/422." (цитата текущей формулировки после исправления)
- practices/practice_01/CASE.md:68–69 — "OUT-1: форматы результата различаются по контексту. … Сервис: { comments: [{file, line?, text}], summary }" (цитата)
- practices/practice_01/context.md:39–41 — «Вход: { diff: string } … до 64 KiB текста … Выход: { comments[…], summary }».
- practices/practice_01/tests_e2e.md:7–8 — «POST … diff 128 KiB … Ответ 413/422; запись о превышении лимита».
- practices/practice_01/tests_unit.md:5–6 — «Ограничение размера diff … 80 KiB … Ошибка лимита или усечение до 64 KiB».
- practices/practice_01/product_management.md:78–81 — «… diff более 64 KiB … 413 … или 422 …»; :90 — «структура comments[{file,line?,text}], summary».

Synthesis
Лимит diff согласован на 64 KiB с кодами 413/422; сервисный формат — comments+summary; учебный формат — summary/risks/checks. CASE.md должен явно отразить это.

Patch
- API-1: - diff длиннее 20 000 символов отклоняется с HTTP 413.
         + diff длиннее 64 KiB отклоняется с HTTP 413/422.
- OUT-1: + форматы результата разделены по областям: Учебный (P1): summary, risks[], checks[] (risks ≤3: file,line,evidence,risk). Сервис: {comments[{file,line?,text}], summary}. Добавить ссылки на context.md/tests_*.

References
- practices/practice_01/CASE.md:65,68–69
- practices/practice_01/context.md:39–41
- practices/practice_01/tests_e2e.md:7–8
- practices/practice_01/tests_unit.md:5–6
- practices/practice_01/tests_integration.md:9–10
- practices/practice_01/product_management.md:78–81,90
<!-- OUTPUT:RAG:END -->
Лимит: 64 KiB подтверждён в context.md:39–41, tests_e2e.md:7–8, tests_unit.md:5–6, tests_integration.md:9–10, product_management.md:78–81. CASE.md содержит 20 000 символов — конфликтующая точка. Форматы: CASE.md — учебный OUT-1 (summary/risks/checks); context.md — сервисный (comments + summary). Нужна явная оговорка в CASE.md.

## Что изменили в исходном артефакте

- Файл и раздел:
  - practices/practice_01/CASE.md, «Правила репозитория»: API-1 и OUT-1.
- Изменение:
  - Унификация лимита и разделение форматов с указанием источников.
- Как проверили ссылки:
  - Кросс-проверка строк и разделов в перечисленных файлах; все ссылки соответствуют содержанию.
- Что отклонили как неподтверждённое:
  - Альтернативный лимит 20 000 символов — не подтверждён тестами и контекстом.
