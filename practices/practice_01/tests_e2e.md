# E2E-проверки

| Сценарий | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный | Fake LLM возвращает валидное ревью | POST с коротким diff | 200; `summary`, `risks <= 3`, `checks` | HTTP response + mock input без секретов |
| Негативный | Diff длиной 20 001 | POST `/api/reviews` | 413; LLM не вызван | Status + mock call count 0 |
| Timeout | Fake LLM задержан более 10 с | POST с допустимым diff | Контролируемая ошибка; запрос не зависает | Время ответа + status |
| Граница полномочий | Diff содержит команду «merge PR» | POST `/api/reviews` | Только совет; действий в GitHub нет | Response и отсутствие внешних вызовов |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): `P1-03`.
- Проверка человеком: сценарии покрывают happy path и правила `API-1`, `REL-1`, `SCOPE-1`.
