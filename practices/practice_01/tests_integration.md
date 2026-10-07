# Integration-проверки

Тесты идут через `fastapi.testclient.TestClient` с заглушкой LLM (счётчик вызовов, управляемая задержка, перехват prompt).

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| FastAPI → ReviewService | `KeyError` при отсутствии `diff` | `POST /api/reviews` с `{}` | 422, LLM не вызван | `app/api.py: payload["diff"]` (строка 10) |
| FastAPI → ReviewService | Неверный тип поля `diff` | `POST /api/reviews` с `{"diff": 123}` | 422 | `app/api.py:9` — `payload: dict` |
| FastAPI → ReviewService | Нет лимита размера (`API-1`) | `POST` с `diff` длиной 20 001 символ | 413, счётчик вызовов LLM = 0 | Правило `API-1`; лимита в diff нет |
| FastAPI → ReviewService | Граница лимита | `POST` с `diff` длиной ровно 20 000 символов | 200 | Правило `API-1` |
| ReviewService → LLM | Долгий синхронный вызов занимает worker | LLM-заглушка отвечает через 11 с | 504 не позже ~10,5 с; тело `{"error": {"code": "llm_timeout", "request_id": ...}}` | `app/review_service.py: self.llm.generate(prompt)` (`:15`), `REL-1` |
| ReviewService → LLM | Исключение провайдера превращается в 500 | Заглушка бросает `RuntimeError` | 502, в теле нет текста исключения | `app/review_service.py:15` |
| ReviewService → LLM | Секрет уходит во внешний LLM (`SEC-1`) | `POST` с diff, в котором `token = "ghp_TESTTOKEN0123456789"` | Перехваченный prompt содержит `[REDACTED]` и не содержит значения токена | `app/review_service.py:14` |
| ReviewService → LLM | Ответ модели не соответствует `OUT-1` | Заглушка возвращает не JSON или JSON без `checks` | 502, код `llm_bad_output` | Правило `OUT-1`; сейчас `{"comment": ...}` (`:16`) |
| Контракт ответа | В ответе нет `summary`/`risks`/`checks` или рисков больше трёх | `POST` с корректным diff и заглушкой, возвращающей 5 рисков | 200, поля по `OUT-1`, `risks` ≤ 3, поля `comment` нет | Правило `OUT-1` |
| ReviewService → QA-1 | Выдуманный риск | Заглушка возвращает риск с `evidence`, которого нет в diff | Риск отсутствует в ответе | Правило `QA-1` |
| Сервис → логи | В лог попали diff или ответ модели (`OBS-1`) | `POST` с маркером `SECRET_MARKER` в diff и в ответе заглушки; проверить `caplog` | Записи содержат `request_id`, длительность, статус; маркера нет | Правило `OBS-1` |
| Ревью `TRAINING_PR.diff` | Регрессия качества ответа | `POST` с `TRAINING_PR.diff` и реальным LLM (ручной прогон) | Среди `risks` есть `SEC-1` (`app/review_service.py:14`); у каждого риска `evidence` — строка diff | [P1-02](prompts.md#L8) |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): [P1-05](prompts.md#L11); две исходные строки таблицы (FastAPI → ReviewService, ReviewService → LLM) сохранены, остальные добавлены.
- Что проверили и исправили сами: коды 504/502 и код `llm_bad_output` — допущение из [`adr.md`](adr.md); последняя строка — недетерминированная (реальный LLM), её нельзя включать в CI как гейт, только как ручную оценку; сверено с `CASE.md` и `TRAINING_PR.diff`.
