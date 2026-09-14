# Chain of Verification

- Проверяемый черновик или утверждение:
  - «API-1 в CASE.md должен указывать лимит 64 KiB, а не 20 000 символов; OUT-1 должен быть разделён на учебный (summary/risks/checks) и сервисный (comments+summary) форматы с явной областью применения и ссылками на tests_* и context.md».

## Запрос на проверку
Проверь факты в репозитории:
1) Какие значения лимита diff встречаются в CASE.md, context.md, tests_* и product_management.md?
2) Где и как описан формат результата OUT-1 в CASE.md и Context Pack? Есть ли конфликт с tests_*?
Верни таблицу вопросов/источников/evidence и итоговую рекомендацию.

## Вопросы проверки и evidence

| Вопрос | Источник или проверка | Результат |
|---|---|---|
| Лимит diff в CASE.md | CASE.md:64–71 | 20 000 символов → конфликт |
| Лимит diff в context.md | practices/practice_01/context.md:39 | 64 KiB |
| Лимит в tests_* | tests_e2e.md:7–8; tests_unit.md:5–6; tests_integration.md:9–10 | 64 KiB, 413/422 |
| Формат OUT-1 в CASE.md | CASE.md:67–69 | summary/risks/checks (учебный) |
| Формат OUT-1 в Context Pack | context.md:39–41 | comments[] + summary (сервис) |
| AC в product_management.md | product_management.md:78–81 | 64 KiB подтверждён |

## Исправленный результат
<!-- OUTPUT:COV:START -->
Patch
- API-1: - diff длиннее 20 000 символов отклоняется с HTTP 413.
         + diff длиннее 64 KiB отклоняется с HTTP 413/422.
- OUT-1: + разделён по области применения.
         + Учебный (P1): summary, risks[], checks[] (risks ≤3: file,line,evidence,risk).
         + Сервис: {comments[{file,line?,text}], summary}; добавлены ссылки на источники.

References
| file:lines | evidence |
|---|---|
| practices/practice_01/context.md:39–41 | Формат сервиса (comments+summary), лимит 64 KiB |
| practices/practice_01/tests_e2e.md:7–8 | Граничный кейс 64 KiB, статусы 413/422 |
| practices/practice_01/tests_unit.md:28–31 | Бюджет 64 KiB (unit-проверка лимита) |
| practices/practice_01/tests_integration.md:9–10 | Контракт API (422 на отсутствующий diff) |
| practices/practice_01/product_management.md:69–81,88–91 | AC: лимит 64 KiB, структура comments+summary |
| practices/practice_01/CASE.md:64–72 | Место правок API-1/OUT-1 |
<!-- OUTPUT:COV:END -->
Рекомендация: обновить CASE.md — API-1 «64 KiB» (413/422), разделить OUT-1 (учебный vs сервисный), добавить ссылки на tests_* и context.md.

## Что изменили в исходном артефакте

- Файл и раздел:
  - practices/practice_01/CASE.md, «Правила репозитория»: API-1 и OUT-1.
- Изменение:
  - Уточнили лимит и области применения форматов.
- Что отклонили:
  - Сохранение 20 000 символов и единый OUT-1 без контекста.

Скрытые рассуждения модели не сохраняйте; нужны только вопросы, evidence и исправленный результат.
