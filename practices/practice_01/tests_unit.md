# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| `API-1` — лимит размера | Валидатор `ReviewRequest` отклоняет слишком длинный `diff` | `diff` длиной 20 001 символ | `ValidationError` на уровне модели (route отвечает 413) | `tests/test_review_request.py::test_diff_too_long` |
| Валидация обязательного поля | Отсутствие `diff` в теле обрабатывается как ошибка валидации, а не `KeyError` | JSON-тело без ключа `diff` | `ValidationError`, не исключение времени выполнения | `tests/test_review_request.py::test_missing_diff_field` |
| `REL-1` — timeout LLM-вызова | `ReviewService.review` оборачивает `llm.generate` таймаутом 10с | Мок `LLM`, зависающий дольше 10 секунд | Контролируемое исключение вместо зависания вызова | `tests/test_review_service.py::test_llm_timeout` |
| `SEC-1` — редактирование секретов | Секреты из `diff` вычищаются перед формированием prompt | `diff`, содержащий тестовый token вида `ghp_xxx` | Итоговый prompt содержит `[REDACTED]` вместо токена | `tests/test_review_service.py::test_secret_redaction` |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: убедились, что каждая проверка изолирует ровно один компонент (валидатор либо `ReviewService`) и ссылается на конкретное правило из Context Pack, а не на общую формулировку «добавить тесты» из P1-01.
