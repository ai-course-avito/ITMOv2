# Few-shot

- Артефакт Практики 1: practices/practice_01/CASE.md (раздел «Материалы для Context Pack»: правила SEC-1, API-1, OUT-1)
- Что хотим улучшить: устранить несогласованность лимита размера diff (20 000 символов vs 64 KiB) и двусмысленность формата результата OUT-1 (учебный vs сервисный), добавить трассировку к tests_*.

## Примеры

### Хороший результат
API-1: «diff длиннее 64 KiB отклоняется с HTTP 413/422 (см. tests_e2e.md, tests_unit.md, tests_integration.md)».
OUT-1: «Для учебного запуска (P1) — summary/risks/checks; для сервиса — comments[] + summary». В CASE.md явно указаны области применения и ссылки на tests_* и context.md.

### Плохой результат
API-1 оставляет «20 000 символов», OUT-1 смешивает «risks/checks» с «comments», без ссылок на тесты.

## Запрос
Сформируй правки к practices/practice_01/CASE.md, чтобы:
1) унифицировать API-1 на 64 KiB, с оговоркой 413/422;
2) разделить OUT-1 для учебного P1 (summary/risks/checks) и сервиса (comments + summary) c явной областью применения;
3) дать ссылки на соответствующие tests_* и context.md.
Верни краткий патч-текст и список ссылок-оснований.

## Что получили
<!-- OUTPUT:FEW_SHOT:START -->
1) Patch
- API-1: - diff длиннее 20 000 символов отклоняется с HTTP 413.
          + diff длиннее 64 KiB отклоняется с HTTP 413/422.
- OUT-1:  + форматы результата различаются по контексту.
          + Учебный запуск P1: summary, risks[], checks[] (risks ≤3: file,line,evidence,risk).
          + Сервис: {comments[{file,line?,text}], summary}. Ссылки добавлены.

2) References
 - practices/practice_01/CASE.md:65 — "API-1: diff длиннее 64 KiB отклоняется с HTTP 413/422." (цитата)
 - practices/practice_01/CASE.md:68–69 — "OUT-1: форматы результата различаются… Учебный… Сервис: {comments[…], summary}" (цитата)
 - practices/practice_01/context.md:39–41 — формат сервиса (comments+summary), лимит 64 KiB.
 - practices/practice_01/tests_e2e.md:7–8 — граничный кейс 64 KiB, статусы 413/422 (подтверждает лимит/коды для превышения размера).
 - practices/practice_01/tests_unit.md:28–31 — бюджет 64 KiB (unit‑проверка лимита).
 - practices/practice_01/tests_integration.md:9–10 — 422 на отсутствующий diff (другой негативный кейс, не про лимит).
<!-- OUTPUT:FEW_SHOT:END -->
Патч-текст с заменой «20 000 символов» на «64 KiB»; примечание к OUT-1 с разделением форматов; ссылки на tests_unit.md (ограничение 64 KiB), tests_integration.md (413/422), tests_e2e.md (граничный кейс), context.md (64 KiB как ориентир).

## Что изменили в исходном артефакте

- Файл и раздел:
  - practices/practice_01/CASE.md, раздел «Правила репозитория»: API-1 и OUT-1.
- Изменение:
  - API-1 → «64 KiB», добавить «413/422»; OUT-1 → явное разделение учебного и сервисного формата + ссылки на tests_* и context.md.
- Как проверили:
  - Grep по репозиторию не содержит «20 000»; все упоминания лимита — «64 KiB». Сверка с tests_* и product_management.md (AC на 64 KiB).
- Что отклонили:
  - Вариант оставить «20 000 символов» ради простоты; вариант объединить форматы OUT-1 в один без области применения.
