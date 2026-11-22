# 03_skill_review

- Модель: `opencode/big-pickle`, новая сессия `opencode run` в `review-api/`
- Время: 325 с, код выхода 0

## Запрос

```text
Отревьюй samples/training_pr.diff по процедуре проекта.
```

## Ход работы

### 1. `skill` → completed

Вход:

```json
{"name": "pr-diff-review"}
```

Результат:

```text
<skill_content name="pr-diff-review">
# Skill: pr-diff-review

# PR diff review

Процедура ревью одного diff по правилам проекта. Результат — JSON в формате OUT-1, прошедший валидатор.

## Вход

- `diff_path` — путь к unified diff внутри проекта, например `samples/training_pr.diff`.

## Процедура

1. **Предпроверка.** Вызови MCP-инструмент `review-tools_scan_diff` с `diff_path`.
   Если `verdict` = `blocked` — остановись: верни `reasons` и номера строк из `secrets`.
   Секреты не цитируй, diff дальше не анализируй (SEC-1, API-1).
2. **Правила.** Прочитай `docs/requirements.md`. Других правил не придумывай.
3. **Кандидаты.** Прочитай diff. Для каждого кандидата в риск найди подтверждение:
   строку из diff (файл + номер строки *нового* файла, считается от заголовка `@@ -a,b +c,d @@`)
   или ID правила. Кандидат без подтверждения отбрасывается (QA-1).
4. **Ответ.** Оставь не больше трёх рисков. Сохрани JSON в `reviews/<имя-diff>.json`
   по образцу `references/out1-example.json`. `evidence` — дословный фрагмент строки diff без ведущего `+`.
5. **Проверка.** Запусти
   `.venv/bin/python .opencode/skills/pr-diff-review/scripts/validate_review.py reviews/<имя-diff>.json --diff <diff_path>`.
   Пока код выхода не 0 — исправляй JSON по сообщениям валидатора. Валидатор не ослабляй.

## Границы

- Не меняй код приложения, тесты и `docs/` (SCOPE-1: сервис и ревьюер только советуют).
- Не делай approve, merge и git commit.
- Если данных недостаточно — напиши это в `summary`, а не додумывай.

## Что вернуть пользователю

- путь к JSON и последнюю строку вывода валидатора;
- список рисков в виде `файл:строка — риск (правило)`;
- что не проверено.

Base directory for this skill: /Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/.opencode/skills/pr-diff-review
Relative paths … (+421 симв.)
```

### 2. `review-tools_scan_diff` → completed

Вход:

```json
{"diff_path": "samples/training_pr.diff"}
```

Результат:

```text
{
  "diff_path": "samples/training_pr.diff",
  "chars": 1060,
  "limit": 20000,
  "within_api1_limit": true,
  "files": [
    "app/review_service.py",
    "app/api.py"
  ],
  "added_lines": 12,
  "secrets": [],
  "verdict": "ok",
  "reasons": []
}
```

### 3. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md</path>
<type>file</type>
<content>
1: # Контракт сервиса AI-review
2: 
3: Источник правил — Context Pack Практики 1 (`practices/practice_01/context.md`, ветка `practice_01`).
4: 
5: ## Эндпоинт
6: 
7: `POST /api/reviews` принимает JSON `{"diff": "<unified diff>"}` и возвращает результат ревью от LLM.
8: `GET /health` возвращает `{"status": "ok"}`.
9: 
10: ## Правила
11: 
12: | ID | Правило |
13: |---|---|
14: | SEC-1 | Перед отправкой во внешний LLM из diff удаляются токены, пароли и приватные ключи. |
15: | API-1 | diff длиннее 20 000 символов отклоняется с HTTP 413. |
16: | REL-1 | Внешний LLM-вызов имеет timeout 10 секунд; ошибка превращается в контролируемый ответ. |
17: | OUT-1 | Ответ ревью содержит `summary`, массив `risks` (≤ 3, поля `file`, `line`, `evidence`, `risk`) и массив `checks`. |
18: | SCOPE-1 | Сервис только советует: не пишет код и не выполняет действия в GitHub. |
19: | QA-1 | Риск включается в ответ, только если подтверждён строкой diff или правилом. |
20: | OBS-1 | В лог пишутся только `request_id`, длительность и статус; diff и ответ модели не логируются. |
21: 
22: ## Фича A — входная валидация (API-1)
23: 
24: 1. Нет поля `diff` или оно не строка → HTTP 422, LLM не вызывается.
25: 2. Пустой diff (после `strip()`) → HTTP 422, LLM не вызывается.
26: 3. Длина diff больше 20 000 символов → HTTP 413 с телом `{"detail": "diff too large"}`, LLM не вызывается.
27: 4. Ровно 20 000 символов — допустимо, запрос обрабатывается.
28: 
29: ## Фича B — ошибка зависимости (REL-1)
30: 
31: 1. LLM не ответил за 10 секунд → HTTP 504 с телом `{"detail": "llm timeout"}`.
32: 2. LLM бросил исключение → HTTP 502 с телом `{"detail": "llm unavailable"}`; текст исключения наружу не отд … (+85 симв.)
```

### 4. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/samples/training_pr.diff"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/samples/training_pr.diff</path>
<type>file</type>
<content>
1: diff --git a/app/review_service.py b/app/review_service.py
2: index 21bf12a..814c7d1 100644
3: --- a/app/review_service.py
4: +++ b/app/review_service.py
5: @@ -1,10 +1,23 @@
6:  from typing import Protocol
7:  
8:  
9:  class LLM(Protocol):
10: -    def generate(self, prompt: str) -> str: ...
11: +    def generate(self, prompt: str) -> str:
12: +        ...
13:  
14:  
15:  class ReviewService:
16:      def __init__(self, llm: LLM) -> None:
17:          self.llm = llm
18: +
19: +    def review(self, diff: str) -> dict[str, str]:
20: +        prompt = f"Review this pull request and find problems:\n{diff}"
21: +        answer = self.llm.generate(prompt)
22: +        return {"comment": answer}
23: diff --git a/app/api.py b/app/api.py
24: index 7c99aa1..da41e4f 100644
25: --- a/app/api.py
26: +++ b/app/api.py
27: @@ -1,8 +1,17 @@
28:  from fastapi import FastAPI
29:  
30:  from app.dependencies import review_service
31:  
32:  app = FastAPI()
33:  
34:  
35: +@app.post("/api/reviews")
36: +def create_review(payload: dict) -> dict[str, str]:
37: +    return review_service.review(payload["diff"])
38: +
39: +
40:  @app.get("/health")
41:  def health() -> dict[str, str]:
42:      return {"status": "ok"}

(End of file - total 42 lines)
</content>
```

### 5. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/.opencode/skills/pr-diff-review/references/out1-example.json"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/.opencode/skills/pr-diff-review/references/out1-example.json</path>
<type>file</type>
<content>
1: {
2:   "summary": "Добавлен эндпоинт POST /api/reviews, который передаёт diff в LLM без проверок входа.",
3:   "risks": [
4:     {
5:       "file": "app/api.py",
6:       "line": 10,
7:       "evidence": "return review_service.review(payload[\"diff\"])",
8:       "risk": "Нет проверки длины diff: запрос длиннее 20 000 символов не отклоняется с HTTP 413 (API-1)."
9:     }
10:   ],
11:   "checks": [
12:     "Отправить POST /api/reviews с diff длиннее 20 000 символов и проверить ответ 413."
13:   ]
14: }

(End of file - total 14 lines)
</content>
```

### 6. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/.opencode/skills/pr-diff-review/scripts/validate_review.py"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/.opencode/skills/pr-diff-review/scripts/validate_review.py</path>
<type>file</type>
<content>
1: """Валидатор ответа ревью в формате OUT-1.
2: 
3: Проверяет структуру (summary, risks ≤ 3, checks) и, если передан --diff,
4: что каждый риск указывает на файл из diff, а `evidence` дословно стоит
5: в строке нового файла с указанным номером. Код выхода 0 — ответ принят.
6: """
7: import argparse
8: import json
9: import re
10: import sys
11: from pathlib import Path
12: 
13: HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
14: 
15: 
16: def new_file_lines(diff_text: str) -> dict[str, dict[int, str]]:
17:     """file -> {номер строки нового файла: содержимое} для строк контекста и добавленных."""
18:     result: dict[str, dict[int, str]] = {}
19:     current, line = None, 0
20:     for raw in diff_text.splitlines():
21:         if raw.startswith("+++ "):
22:             path = raw[4:].strip()
23:             current = path[2:] if path.startswith("b/") else path
24:             result.setdefault(current, {})
25:         elif raw.startswith("--- "):
26:             continue
27:         elif (m := HUNK.match(raw)):
28:             line = int(m.group(1))
29:         elif current and (raw.startswith("+") or raw.startswith(" ")):
30:             result[current][line] = raw[1:]
31:             line += 1
32:     return result
33: 
34: 
35: def validate(review: dict, diff_text: str | None) -> list[str]:
36:     errors = []
37:     if not isinstance(review.get("summary"), str) or not review["summary"].strip():
38:         errors.append("summary: нужна непустая строка")
39:     risks = review.get("risks")
40:     if not isinstance(risks, list):
41:         errors.append("risks: нужен массив")
42:         risks … (+2695 симв.)
```

### 7. `bash` → error

Вход:

```json
{"command": "ls reviews 2>/dev/null || ls"}
```

Результат:

```text
The user has specified a rule which prevents you from using this specific tool call. Here are some of the relevant rules [{"permission":"*","action":"allow","pattern":"*"},{"permission":"bash","pattern":"*","action":"deny"},{"permission":"bash","pattern":"sh scripts/check.sh","action":"allow"},{"permission":"bash","pattern":".venv/bin/python .opencode/skills/pr-diff-review/scripts/validate_review.py *","action":"allow"},{"permission":"bash","pattern":"git status*","action":"allow"},{"permission":"bash","pattern":"git diff*","action":"allow"}]
```

### 8. `glob` → completed

Вход:

```json
{"pattern": "reviews/*"}
```

Результат:

```text
No files found
```

### 9. `write` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/reviews/training_pr.json", "content": "{\n  \"summary\": \"Эндпоинт POST /api/reviews вызывает LLM без входной валидации (422/413), передаёт diff в промт без удаления секретов и не задаёт timeout; ответ не содержит summary/risks/checks (OUT-1).\",\n  \"risks\": [\n    {\n      \"file\": \"app/api.py\",\n      \"line\": 10,\n      \"evidence\": \"return review_service.review(payload[\\\"diff\\\"])\",\n      \"risk\": \"Нет входной валидации: отсутствующее/нестроковое/пустое поле diff даёт KeyError или 200 вместо HTTP 422, … (+1257 симв.)
```

Результат:

```text
Wrote file successfully.

[check-after-edit] sh scripts/check.sh → PASS
...........                                                              [100%]
11 passed in 0.13s
```

### 10. `bash` → completed

Вход:

```json
{"command": ".venv/bin/python .opencode/skills/pr-diff-review/scripts/validate_review.py reviews/training_pr.json --diff samples/training_pr.diff", "workdir": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api"}
```

Результат:

```text
OK: reviews/training_pr.json соответствует OUT-1, 3 риск(а) подтверждены строками diff
```

`reviews/training_pr.json` — `OK: reviews/training_pr.json соответствует OUT-1, 3 риск(а) подтверждены строками diff`

**Риски:**
- `app/api.py:10` — нет входной валидации: KeyError/200 вместо 422, нет 413 на длинный diff (API-1)
- `app/review_service.py:14` — diff уходит в промт LLM без удаления секретов (SEC-1)
- `app/review_service.py:15` — вызов LLM без timeout 10 с и без обработки ошибки (REL-1)

**Не проверено / отброшено:**
- Кандидат OUT-1 (`app/review_service.py:16`: ответ `{"comment": answer}` без `summary`/`risks`/`checks`) — подтверждён строкой, но лимит ≤ 3 рисков.
- OBS-1 и SCOPE-1: в diff нет логирования и действий в GitHub — подтверждений нет (QA-1).
- Предпроверка `scan_diff`: verdict ok, секретов и нарушений API-1 нет.

