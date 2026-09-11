# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| Валидация входа | Pydantic-модель `ReviewRequest` отклоняет payload без ключа `diff` | `{"data": "текст"}` (без ключа `diff`) | `ValidationError`, HTTP 422 | `app/api.py:36-37` — текущий код не валидирует payload |
| SEC-1: очистка секретов | SecretFilter заменяет токены и пароли на `[REDACTED]` | Diff со строкой `token=abc123secret` | В промпте для LLM строка содержит `[REDACTED]` вместо `abc123secret` | `app/review_service.py:20` — diff отправляется без очистки |
| OUT-1: формат ответа | ResponseFormatter возвращает JSON с обязательными полями `summary`, `risks`, `checks` | Ответ LLM: `"No issues found"` | JSON: `{"summary": "No issues found", "risks": [], "checks": []}` | `app/review_service.py:22` — возвращается `{"comment": answer}` вместо OUT-1 формата |
| OBS-1: логирование | Middleware логирует только `request_id`, длительность и статус | Обычный запрос к `/api/reviews` | В логе: `request_id`, `duration_ms`, `status`. Нет diff и ответа модели | `app/api.py:36-37` — текущий код не логирует |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02
- Что проверили и исправили сами: проверили, что каждая unit-проверка ссылается на конкретную строку из TRAINING_PR.diff и правило из CASE.md. Убедились, что проверки изолированы (каждая проверяет один компонент без зависимостей от внешних сервисов)
