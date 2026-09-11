# E2E-проверки

| Сценарий пользователя | Предусловия | Действие | Наблюдаемый результат | Evidence |
|---|---|---|---|---|
| Позитивный — валидный diff | diff ≤ 20 000 символов, без секретов, LLM отвечает вовремя | POST /api/reviews с `{"diff": "diff --git ..."}` | HTTP 200, тело содержит `summary`, `risks` (≤3, с file/line/evidence/risk), `checks` | diff line 35-37, 20-22 — OUT-1 |
| Негативный — diff превышает лимит | diff ровно 20 001 символ | POST /api/reviews с `{"diff": "x"*20001}` | HTTP 413 (API-1) до вызова LLM | diff line 20 — `f"...:\n{diff}"` без size check, API-1 |
| Граничный — payload без diff | тело `{"other": "value"}` | POST /api/reviews | HTTP 422 с описанием ошибки валидации (не 500) | diff line 36-37 — `payload["diff"]` без Pydantic-валидации |
| Негативный — LLM timeout | LLM задерживает > 10 секунд | POST /api/reviews с валидным diff | HTTP 200 с контролируемым ответом `summary` + пустые `risks` (REL-1) | diff line 21 — `self.llm.generate(prompt)` без try/except и timeout |
| Негативный — секреты в diff | diff содержит `token=sk-abc123` | POST /api/reviews с `{"diff": "...token=sk-abc123..."}` | HTTP 200; token не передан в LLM (SEC-1: [REDACTED]) | diff line 20 — `f"...:\n{diff}"` без redact |

## Как использовали AI

- Для чему: проектирование E2E-сценариев (позитивный, негативный, граничный) на основе правил репозитория
- Тип промпта: zero-shot (P1-01), затем уточнение с master prompt (P1-02)
- Строка в `prompts.md`: P1-01, P1-02
- Что проверили и исправили сами: каждый сценарий привязан к конкретному правилу (API-1, SEC-1, REL-1, OUT-1) и строкам diff
