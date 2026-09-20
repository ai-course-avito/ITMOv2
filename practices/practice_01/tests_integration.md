# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| `api.py` → `ReviewService` (HTTP → бизнес-логика) | payload без ключа `diff` → `KeyError` → 500 вместо 4xx; изменение контракта эндпоинта | `POST /api/reviews` с `{}` и с `{"diff": 123}` | ответ 400/422 с описанием ошибки, а не HTTP 500; типаж diff проверен | curl/POST от клиента; проверка статус-кодов и тела ошибки |
| `api.py` → фильтр API-1 (длина diff) | diff >20 000 не отклоняется, огромный запрос уходит в LLM | `POST /api/reviews` с diff длиной 25 000 символов | HTTP 413, LLM не вызван | мок LLM с счётчиком вызовов |
| `ReviewService` → фильтр SEC-1 → LLM | секреты проскакивают в prompt внешнего LLM | DummyLLM-клиент, который сохраняет prompt; diff с token и ключом | в prompt `[REDACTED]`, секретов нет | запись последнего prompt из заглушки |
| `ReviewService` → LLM (timeout REL-1) | ошибка/таймаут LLM пробрасывается в HTTP 500 и блокирует воркер | мок LLM спит 15 с при timeout 10 с | контролируемый ответ об ошибке, HTTP 200/503 с понятным телом, воркер продолжает отвечать | статус-код и тело ответа; `/health` отвечает после таймаута |
| `ReviewService` → форматирование OUT-1 | ключи JSON не соответствуют контракту (`comment` вместо `summary`/`risks`/`checks`) | мок LLM возвращает произвольный текст | ответ ровно с полями `summary`, `risks` (≤3), `checks` | сравнение ключей JSON с OUT-1 |
| `ReviewService` → лог OBS-1 | в лог попадает содержимое diff или ответа модели | лог-клиент, пишущий в память; проход одного ревью | записи содержат только `request_id`, длительность, статус | поиск строк diff/ответа в записях лога |

Примеры воспроизведения (после реализации сервиса):

```bash
# 1. payload без diff
curl -si -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d "{}"
# ожидаем 400/422

# 2. diff длиннее лимита
python -c "open('big.diff','w').write('x'*25000)"
curl -si -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d @- < big.diff
# ожидаем HTTP 413

# 3. секреты не уходят в LLM
curl -s -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" \
  -d '{"diff":"api_token=secret123"}' -w "\nstatus=%{http_code}\n"
# в логе/мониторинге prompt содержит [REDACTED], а не secret123
```

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-01, P1-02
- Что проверили и исправили сами: проверяли именно связки компонентов (HTTP→сервис→фильтр→LLM→формат→лог), а не изолированные функции; каждый сценарий даёт воспроизводимую команду или мок