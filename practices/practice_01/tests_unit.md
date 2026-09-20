# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| SEC-1 | ReviewService перед отправкой в LLM удаляет токены/пароли/ключи из diff | diff с фрагментами: `token=abcd1234`, `password=Secret1!`, `-----BEGIN PRIVATE KEY-----…` | В llm.generate уходит prompt, где секреты заменены/вырезаны (например, `[REDACTED]`); исходные значения не попадают в LLM | TRAINING_PR.diff: app/review_service.py L19-22 — diff передаётся в LLM «как есть», без редактирования |
| REL-1 | Таймаут и обработка ошибки внешнего LLM | Мок LLM, который зависает >10s или бросает TimeoutError/Exception | ReviewService возвращает контролируемый ответ без исключения; таймаут ≤10s; отсутствие утечки исходного diff в тексте ошибки | TRAINING_PR.diff: app/review_service.py L21 — прямой вызов llm.generate без таймаута/try-except |
| OUT-1 + QA-1 | Ограничение количества рисков до 3 и фильтр рисков без evidence | Мок ответа LLM с 5 «рисками», 2 из них без ссылок на file:line | Возвращено не более 3 рисков; элементы без evidence отфильтрованы | TRAINING_PR.diff: app/review_service.py L19-22 — возвращается только `{"comment": answer}`, структура `risks` не формируется |
| API-1 | Отклонение слишком длинного diff на уровне входа | `len(diff)` = 20_001 символ | Возврат HTTP 413/ошибка валидации ещё до вызова ReviewService | TRAINING_PR.diff: app/api.py L35-38 — нет валидации размера, `payload["diff"]` передаётся напрямую |
| Валидация входа | Отсутствует обязательное поле `diff` в payload | `{}` или `{ "text": "..." }` | Валидатор возвращает 422 Unprocessable Entity; обработчик не падает KeyError | TRAINING_PR.diff: app/api.py L35-38 — `payload["diff"]` приведёт к KeyError и 500 |
| SCOPE-1 | Сервис не выполняет approve/merge/edit и не пишет код | Любой `diff` | В ответе нет действий approve/merge/edit; возвращаются только summary, risks≤3, checks | CASE.md: SCOPE-1; TRAINING_PR.diff: app/api.py L35-38 — эндпоинт принимает diff и возвращает совет (summary/risks/checks), не выполняя approve/merge/edit |

## Как использовали AI

- Для чего: спроектировать изолированные проверки поведения ReviewService и валидации входа по правилам SEC-1, API-1, REL-1, OUT-1, QA-1.
- Тип промпта: master prompt (QA‑инженер)
- Строка в [`prompts.md`](prompts.md): P1-07 — Юнит‑проверки по TRAINING_PR.diff
- Что проверили и исправили сами: сопоставили каждый сценарий с правилами и точными ссылками file:line из TRAINING_PR.diff; исключили предположения вне diff; ожидания сформулированы как проверяемые эффекты функций
