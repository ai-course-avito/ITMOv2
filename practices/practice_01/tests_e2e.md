# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный (Happy path) | API доступно; LLM доступен | POST `/api/reviews` с валидным `diff` | 200 и JSON `{summary, risks[], checks[]}` | CASE.md OUT-1 |
| Альтернативный (LLM таймаут) | LLM отвечает >10с | POST с валидным `diff` | контролируемый ответ без 5xx | CASE.md REL-1 |
| Исключение (слишком длинный diff) | — | POST с `diff` > 20000 | 413 Payload Too Large | CASE.md API-1 |
| Ошибка ввода (отсутствует diff) | — | POST без поля `diff` | 422 с описанием отсутствующего поля | US-01 |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): prompts.md#master-4
- Что проверили и исправили сами: сценарии согласованы с user stories и ограничениями CASE.md.
