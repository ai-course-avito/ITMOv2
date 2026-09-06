# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный: ревью валидного diff | Доступен эндпоинт | POST валидный diff | 200 и JSON с summary, risks≤3 (file, line, evidence, risk), checks | CASE.md OUT-1 |
| Негативный: пустое тело | — | POST {} | 422 Unprocessable Entity | Pydantic валидация |
| Граничный: длинный diff | — | POST diff длиной >20000 | 413 Payload Too Large | CASE.md API-1 |
| Отказоустойчивость: таймаут LLM | Мок LLM timeout | POST валидный diff | Контролируемая ошибка | CASE.md REL-1 |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: Увязали сценарии с правилами OUT-1, API-1, REL-1.
