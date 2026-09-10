# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API-1: размер diff | `ReviewService.review(diff)` с diff длиной > 20 000 символов | diff = "x" * 20001 | Исключение или контролируемая ошибка до вызова LLM | diff line 20 — `len(diff)` не проверяется |
| SEC-1: удаление секретов | `redact_secrets(diff)` с токеном | diff = `token=abc123def` | В prompt остаётся `[REDACTED]`, токен недоступен LLM | diff line 20 — `f"Review this...:\n{diff}"` без redact |
| OUT-1: формат ответа | `ReviewService.review(diff)` возвращает dict с ключами | ответ = `{"comment": "text"}` | Возвращает `summary`, `risks` (max 3), `checks` | diff line 22 — `return {"comment": answer}` нарушает OUT-1 |
| REL-1: таймаут LLM | `llm.generate` с timeout 10 секунд | LLM задерживает > 10s | try/except → контролируемый ответ, а не 500 | diff line 21 — `answer = self.llm.generate(prompt)` без try/except |
| OBS-1: логирование | логирование содержит только request_id, duration, status | любой вызов endpoint | в логе нет содержимого diff или ответа LLM | diff line 20-22 — нет `logger` вообще |
| SCOPE-1: сервис советует | `ReviewService.review` не вызывает GitHub API | любой вызов | сервис только возвращает ответ, не пишет код | diff line 13-16 — ReviewService.review не модифицирует код |

## Как использовали AI

- Для чего: проектирование unit-тестов на основе правил репозитория (SEC-1, API-1, REL-1, OUT-1, OBS-1, SCOPE-1)
- Тип промпта: zero-shot (P1-01), затем уточнение с master prompt (P1-02)
- Строка в `prompts.md`: P1-01, P1-02
- Что проверили и исправили сами: каждая строка таблицы привязана к конкретному правилу из CASE.md и строке diff
