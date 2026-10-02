# R.C.T.F.

Файл ведёт OpenCode по вашим запросам. Агент записывает фактические результаты экспериментов и вносит изменения в связанные файлы. Свою оценку сообщайте ему в чате; вручную заполнять шаблон не нужно.

- **Role:**
- **Context:**
- **Task:**
- **Format:**

## Полный запрос

Role: SDLC editor for Practice 1 artifacts.
Context: @README.md (Practice 2), @prompts.md (weak artifact selection and proof), and the rules P1-03 from practices/practice_01/context.md. Target artifact: practices/practice_01/problem.md is unreliable: excludes API-1 scope (413 for >20,000), tied to P1-02, lacks metrics for API-1 and REL-1.
Task: Rewrite practices/practice_01/problem.md to align with P1-03: remove exclusion of length limit from "Что не входит", add measurable metrics for API-1 (413 at >20,000) and REL-1 (10s timeout with controlled response), and update "Как использовали AI" to rules prompt/P1-03. Preserve valid existing content and style.
Format: Return a diff-like proposal listing exact lines to change and the new lines; cite sources with file:line for P1-03 rules and tests.

## Что получили

Краткий результат: предложен дифф на три блока и источники: context.md:54-60; tests_integration.md:6; tests_load.md:5; tests_e2e.md:7; adr.md:13-18.

## Что изменили в исходном артефакте

- Файл и раздел: practices/practice_01/problem.md — «Что не входит», «Метрики», «Как использовали AI».
- Изменение: удалено исключение API-лимита, добавлены метрики API-1/REL-1, обновлены промпт/строка в prompts.md на P1-03.
- Как проверили: сопоставили с источниками из контекста (file:line), убедились в проверяемости требований (POST 20001->413; LLM >10s->контролируемый ответ). Требования понятны без доп. пояснений.
- Что отклонили: расширение области на SEC/OBS в problem.md — оставили это для ADR и анализа.
