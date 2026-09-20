# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API → ReviewService | Некорректное тело доходит до LLM | POST без `diff` и с 20 001 символом | 422/413, fake LLM не вызван | HTTP status + mock call count |
| ReviewService → LLM | Timeout превращается в 500 | Fake LLM спит более 10 секунд | Контролируемый ответ, запрос завершён | Время и HTTP status |
| LLM → response schema | LLM возвращает невалидный JSON | Fake LLM без `risks` | Контролируемая ошибка, не сырой `comment` | Schema assertion |
| Service → logging | В лог утекает diff | Diff с маркером `SECRET_TEST` | Маркера нет в captured logs | Log capture |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): `P1-03`.
- Проверка человеком: неизвестные детали реализации заменены fake LLM и внешне наблюдаемыми проверками.
