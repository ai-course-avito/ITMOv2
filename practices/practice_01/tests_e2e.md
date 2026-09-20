# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный | Доступен diff валидного размера | POST /api/reviews с diff | 200 и тело с summary, ≤3 risks, checks | OUT‑1 |
| Негативный | Тело без поля diff | POST /api/reviews с {} | 422 Unprocessable Entity | P1‑01 №1 |
| Граничный | diff > 20000 символов | POST /api/reviews | 413 Request Entity Too Large | API‑1 |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md):
- Что проверили и исправили сами: E2E фокус на проверяемости бизнес‑результата и границах SCOPE‑1.
