# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный | Валидный diff <= 20,000 | POST /api/reviews | 200; JSON содержит summary, risks, checks | OUT-1; app/api.py:35-38 форма ответа пока {comment} |
| Негативный | diff отсутствует | POST /api/reviews с {} | 422 вместо 500 | FastAPI Request Body правило; текущее поведение — KeyError |
| Граничный | diff длиной 20,001 | POST /api/reviews | 413 Payload Too Large | API-1; в коде проверок нет |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-03
- Что проверили и исправили сами: соотношение сценариев с правилами OUT-1 и API-1
