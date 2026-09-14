# CoV: Финальный артефакт (очищенный)

## Master Prompt (CoV-verified)
Role: AI-reviewer (только анализ diff)
Inputs: @practices/practice_01/TRAINING_PR.diff
Goal: Найти до 3 рисков по фактам diff. Для каждого вернуть candidate -> evidence -> check на русском языке.
Output format (строго):
```
candidate: <кратко суть>
evidence: <file:lines> - <цитата или описание по diff>
check: <как воспроизвести и какой ожидаемый результат (AS IS vs TO BE)>
```
Rules:
- Только факты из diff; без выдуманных правил.
- Если нет evidence в diff — риск не включать.
- Максимум 3 риска.
Steps:
1) Прочитать TRAINING_PR.diff и выписать кандидатов в риски.
2) Для каждого найти file:lines и краткий evidence.
3) Составить проверку (check) с AS IS и TO BE.
4) Вернуть результат в указанном формате.

Риски:
```
candidate: Нет валидации входа в POST /api/reviews
evidence: app/api.py:35-38 - create_review(payload: dict) обращается к payload["diff"] без проверки
check: POST /api/reviews с {} -> (AS IS) 500 из-за KeyError; (TO BE) 422/400 с описанием ошибки
```
```
candidate: Нет обработки исключений LLM и контролируемого ответа
evidence: app/review_service.py:19-22 - self.llm.generate(prompt) вызывается без try/except
check: Смоделировать исключение из LLM -> (AS IS) 5xx без маппинга; (TO BE) 502/503 с контролируемым сообщением
```
```
candidate: Неконтролируемый размер diff и риск prompt injection
evidence: app/review_service.py:19-22 - diff вставляется в промпт без ограничений
check: Очень длинный/вредоносный diff -> (TO BE) отказ по лимиту или усечение; инъекция не влияет на системные инструкции

```
candidate: Превышение лимита размера diff (API-1) должно давать 413
evidence: CASE.md: API-1 — diff > 20 000 символов → HTTP 413; TRAINING_PR.diff: app/review_service.py:19-22 — нет ограничений
check: POST с diff=25k → (AS IS) запрос уходит в LLM; (TO BE) 413 Content Too Large, без вызова LLM
```

## Улучшенный CoV-промпт
Step 1: Baseline — обзор изменений (3-5 предложений) и до 3 рисков в формате candidate/evidence/check.
Step 2: Verification Questions — 3-5 критических вопросов (валидация, исключения, безопасность, граничные условия, форматы).
Step 3: Verification Execution — независимые ответы; отмечай, нужна ли правка.
Step 4: Final — исправь базовый ответ по результатам проверки; оставь только проверенные факты.
Ограничения: только факты из TRAINING_PR.diff; максимум 3 риска; если нет evidence — исключи пункт.
