# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| Webhook → Queue | Потеря события, повтор доставки | Эмуляция webhook, дублируем события | Идемпотентная постановка задачи, без дублей в очереди | Ключ задачи PR_SHA+commit_range |
| Worker → GitHub | Rate limit | Мокаем 403/429 GitHub API | Backoff, сохранение задачи, успешная публикация после окна | Логи попыток, X-RateLimit headers |
| Worker → LLM | 429/500 ошибки | Мокаем ответы 429/500 | Экспоненциальный backoff + джиттер, ограничение попыток | Время между попытками растёт |
| LLM → Validator | Невалидный JSON | Возвращаем несоответствующую схему | Ошибка валидации, отсутствие публикации, запись в DLQ | Сообщение об ошибке, метка в задаче |
| API POST /api/reviews | Отсутствует diff | Отправляем payload без diff | 422 и тело с описанием ошибки | OpenAPI схема, body errors |

Сценарий 429 Rate Limit (экстракт):

```python
def test_llm_rate_limit_backoff(client, llm_mock):
    llm_mock.on_call(1).return_429()
    llm_mock.on_call(2).return_429()
    llm_mock.on_call(3).return_ok(payload=VALID_JSON)
    start = now()
    process_task()
    assert now() - start >= expected_backoff_time(min_attempts=2)
```

## Как использовали AI

- Назначение запроса: определить критичные швы интеграций и сценарии деградации.
- Тип промпта: Master Prompt с фокусом на контракты.
- Ссылка на prompts.md: #P1-10
- Собственная верификация: убедились, что сценарии соответствуют архитектуре (webhook → bus → worker → LLM → GitHub) и закрывают 429/500, схемы и идемпотентность.
