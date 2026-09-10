# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| FastAPI → ReviewService → LLM | LLM возвращает не-JSON (например, HTML или plain text) | LLM-мок возвращает `"not json"` | Сервис не падает с 500; возвращает контролируемый ответ с пустыми risks | diff line 21-22 — `answer = self.llm.generate(prompt)` → `return {"comment": answer}` без парсинга |
| FastAPI endpoint → ReviewService | payload без поля `diff` | POST /api/reviews с `{"other": "value"}` | HTTP 422, а не 500 (KeyError → ControlledError) | diff line 36-37 — `payload["diff"]` без валидации |
| FastAPI → размер diff → LLM | diff ровно 20 000 символов (граничный) | POST /api/reviews с diff длиной 20 000 | HTTP 200, LLM получает валидный запрос | diff line 20 — `f"...:\n{diff}"` без size check |
| SEC-1 + REL-1 + OUT-1 (комплекс) | секреты в diff + LLM медленный | diff с `Bearer abc` + LLM timeout 11s | ответ 200 с summary/risks/checks; в логе только request_id/duration/status; токен не попал в LLM | diff line 20-22 — нарушены все три правила |

## Как использовали AI

- Для чего: проектирование integration-тестов на пересечение компонентов и правил репозитория
- Тип промпта: zero-shot (P1-01), затем уточнение с master prompt (P1-02)
- Строка в `prompts.md`: P1-01, P1-02
- Что проверили и исправили сами: сверили сценарии с ADR и таблицей разницы в analysis.md
