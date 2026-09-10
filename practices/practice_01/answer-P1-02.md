Summary

[0] PR adds ReviewService.review that prompts an LLM with a diff and returns {"comment": ...}, and exposes a new FastAPI POST endpoint /api/reviews that calls this service. Health endpoint is unchanged.

Risks

candidate: [1] Отсутствует валидация входного JSON и обработка ошибок в API; обращение к payload["diff"] может вызвать KeyError и 500 вместо пользовательской ошибки.
   file: [2] app/api.py:36-37
   evidence: [3]
   - "@app.post(\"/api/reviews\")" (line 35)
   - "def create_review(payload: dict) -> dict[str, str]:" (line 36)
   - "return review_service.review(payload[\"diff\"])" (line 37)
   rule: [4] нет явных правил в context.md (правило не задано)
   check: [5] Отправить POST /api/reviews без поля "diff" или с неверной схемой и убедиться, что сервер возвращает 500/KeyError вместо ожидаемой 422 с описанием валидации.

Checks

[6] POST /api/reviews с телом {} ожидаемо приводит к исключению KeyError (проверка негативного сценария).
[7] POST /api/reviews с телом {"diff": "..."} возвращает объект {"comment": string} (позитивный сценарий, проверка контракта).