# R.C.T.F.

- Role: Ревьюер артефактов AI (исправляющий ошибки/галлюцинации модели в списке проблем).
- Context: Практика 1, артефакт prompts.md — раздел P1‑02 Result; Context Pack (context.md).
- Task: Сформировать RCTF‑запрос для переработки JSON‑ответа: подтвердить риски с evidence и checks, перенести неподтверждённые в «Открытые вопросы», убрать галлюцинации.
- Format: Список Confirmed risks (file, line, evidence, risk, checks[]) и Open questions (question, suggested checks[]).

## Полный запрос

Текст промпта:

```
Role: ревьюер артефактов AI.
Context: prompts.md (P1‑02 Result), context.md (QA‑1, OUT‑1), TRAINING_PR.diff.
Task: перепиши JSON в P1‑02 Result — для каждого риска добавь evidence и checks; неподтверждённые — в Open questions; удали галлюцинации.
Format: JSON c двумя разделами: confirmed_risks[] и open_questions[]. В confirmed_risks элементы: file, line, evidence, risk, checks[]. В open_questions: question, suggested_checks[].
Constraints: Используй только TRAINING_PR.diff и context.md. Не добавляй риски без источников.
```

## Что получили

Исправленный артефакт (P1‑02 Result JSON) — уточнены проверки, evidence без двусмысленности:

```json
{
  "summary": "Добавлен POST /api/reviews и метод ReviewService.review с вызовом внешнего LLM. Ввод не валидируется, промпт формируется из сырого diff, ответ неструктурирован.",
  "risks": [
    {
      "file": "app/api.py",
      "line": 36,
      "evidence": "def create_review(payload: dict) -> dict[str, str]:\n    return review_service.review(payload[\"diff\"])",
      "risk": "Невалидированный body и доступ к payload[\"diff\"] без проверки → возможен KeyError и 500 вместо 4xx."
    },
    {
      "file": "app/review_service.py",
      "line": 20,
      "evidence": "prompt = f\"Review this pull request and find problems:\n{diff}\"",
      "risk": "Prompt-инъекция: сырой diff может содержать инструкции, влияющие на модель. Нужны системные инструкции и явные разделители."
    },
    {
      "file": "app/review_service.py",
      "line": 20,
      "evidence": "prompt включает весь diff без ограничений (см. правило API-1)",
      "risk": "Неограниченный размер входа → риск переполнения контекста и задержки/стоимости. Ввести API-1 (≤20 000 символов) с 413."
    }
  ],
  "checks": [
    "POST /api/reviews с {} ⇒ текущее поведение: 500; после ввода схемы запроса — 422.",
    "Передать diff с тестовым token и убедиться, что при защите секреты редактируются ([REDACTED]).",
    "Отправить diff > 20 000 символов ⇒ ожидать 413; при меньшем размере — успешный ответ."
  ]
}
```

## Что изменили в исходном артефакте

- Файл и раздел: practices/practice_01/prompts.md — «P1‑02 Result (OUT‑1)».
- Предложение изменения: структурировать риски и вопросы в JSON; удалить галлюцинации.
- Как проверили: сопоставили с TRAINING_PR.diff, контекстом QA‑1/OUT‑1; проверили, что каждый риск имеет evidence и checks.
- Что отклонили: любые новые риски без источников.
- Примечание: исходный файл Практики 1 не изменяли; предлагаемое изменение описано в этом эксперименте.
