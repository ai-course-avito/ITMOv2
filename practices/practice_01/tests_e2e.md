# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный: ревьюер получает полезный отчёт | сервис запущен, LLM с Context Pack, diff ≤20 000 символов без секретов | `POST /api/reviews` с diff; ревьюер подтверждает каждый риск | HTTP 200; `summary` + `risks` (≤3, с `file`/`line`/`evidence`/`risk`) + `checks`; ревьюер принял решение на основе проверок | лог запроса: `request_id`, длительность, статус (OBS-1); отчёт из ответа |
| Негативный: секреты в diff не утекают | сервис запущен, включён фильтр SEC-1 | отправить diff с тестовым токеном и приватным ключом | в prompt внешнего LLM `[REDACTED]`; в ответе есть риск SEC-1 с evidence; в логе нет содержимого diff | перехват prompt (DummyLLM/прокси) и содержимое лога |
| Граничный: слишком длинный diff | сервис запущен, лимит 20 000 символов (API-1) | отправить diff длиной 25 000 символов | HTTP 413 с понятным сообщением; LLM не вызван; пользователь может повторить с укороченным diff | статус-код ответа, счётчик вызовов LLM |
| Отказ LLM: нет 500 при падении внешнего сервиса | LLM недоступен/таймаут дольше 10 с | отправить корректный diff | контролируемый ответ об ошибке (не HTTP 500); сервис продолжает работать; `/health` отвечает «ok» | статус-коды `create_review` и `/health`; длительность в логе |

Автоматизация E2E-сценариев (после реализации сервиса, пример стартового набора):

```bash
# 1. Позитивный: отчёт с рисками и проверками
curl -s -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" \
  -d '{"diff":"--- a/app/review_service.py\n+++ b/app/review_service.py\n+        prompt = f\"...\n"}' | python -c "import json,sys; d=json.load(sys.stdin); assert 'summary' in d and 'risks' in d and 'checks' in d"

# 2. Негативный: секреты не уходят в LLM
curl -s -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" \
  -d '{"diff":"token=secret123"}' && grep -R "secret123" . --include="*.log" | wc -l  # ожидаем 0

# 3. Граничный: diff длиннее лимита
python -c "open('big.diff','w').write('x'*25000)" && \
curl -si -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d @big.diff | head -n 1  # HTTP/1.1 413
```

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-01, P1-02
- Что проверили и исправили сами: сценарии описывают путь пользователя целиком (запрос → отчёт → решение человека) и покрывают позитив, негатив (SEC-1) и границу (API-1); команды проверяют наблюдаемый результат, а не внутренности