# R.C.T.F.

- **Role:** Системный редактор правил CASE.md, выравнивающий контракт с тестами и контекстом.
- **Context:** practices/practice_01/CASE.md (API-1=20000 символов, OUT-1=summary/risks/checks), context.md и tests_* фиксируют 64 KiB и сервисный формат comments+summary.
- **Task:** Сформировать минимальный патч к CASE.md: унифицировать API-1 на 64 KiB (413/422), разделить OUT-1 по областям применения (P1 учебный vs сервис), добавить ссылки на tests_* и context.md.
- **Format:** Вернуть структурированный патч (diff-like) и перечень ссылок на строки/файлы-основания; ограничение до 200 слов.

## Полный запрос
Role: системный редактор правил. Context: CASE.md vs context.md/tests_* несогласованы по лимиту diff и формату результата. Task: подготовить минимальный патч к CASE.md: API-1=64 KiB (413/422), OUT-1 — разделён (P1: summary/risks/checks; сервис: comments+summary), добавить ссылки на tests_* и context.md. Format: diff-патч + список ссылок (до 200 слов).

## Что получили
<!-- OUTPUT:RCTF:START -->
Patch
- API-1: - diff длиннее 20 000 символов отклоняется с HTTP 413.
         + diff длиннее 64 KiB отклоняется с HTTP 413/422.
- OUT-1: + разделить по области применения.
         + Учебный (P1): summary, risks[], checks[] (risks ≤3: file,line,evidence,risk).
         + Сервис: {comments[{file,line?,text}], summary}. Добавить ссылки на источники.

References
practices/practice_01/CASE.md:64–72 | Место правок API-1/OUT-1.
practices/practice_01/context.md:39–41 | Формат сервиса (comments+summary), лимит 64 KiB.
practices/practice_01/tests_e2e.md:7–8 | Граничный кейс 64 KiB, статусы 413/422.
practices/practice_01/tests_unit.md:28–31 | Бюджет 64 KiB (unit-проверка лимита).
practices/practice_01/tests_integration.md:9–10 | Контракт API (422 на отсутствующий diff).
<!-- OUTPUT:RCTF:END -->
Патч с заменой «20 000 символов» на «64 KiB», уточнение «413/422». Раздел «OUT-1: Форматы» с двумя подпунктами (Учебный/Сервисный) и ссылками на tests_e2e.md, tests_integration.md, tests_unit.md и context.md.

## Что изменили в исходном артефакте

- Файл и раздел:
  - practices/practice_01/CASE.md, «Правила репозитория»: API-1 и OUT-1.
- Изменение:
  - API-1 → 64 KiB с 413/422; OUT-1 → два формата и области применения + ссылки на tests_*.
- Как проверили:
  - Grep: нет «20 000»; AC в product_management.md и все tests_* согласованы; Master Prompt не конфликтует с OUT-1.
- Что отклонили:
  - Объединить форматы без разграничения; оставить 20 000 символов.
