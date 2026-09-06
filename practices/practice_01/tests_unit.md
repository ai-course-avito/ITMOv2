# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| Формирование prompt | Строку prompt в `ReviewService.review` | `diff = "abc"` | Вызов `llm.generate` с `"Review this pull request and find problems:\nabc"` | `app/review_service.py:20-22` |
| Прозрачная прокладка ответа | Оборачивание ответа LLM в `{comment: ...}` | Ответ LLM: `"ok"` | Возвращается `{"comment": "ok"}` | `app/review_service.py:21-22` |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02, P1-03.
- Что проверили и исправили сами: проверили соответствие формулировок фактическим строкам diff.
