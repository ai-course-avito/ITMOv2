# Улучшение через паттерн ReAct

## 1. Сконструированный ReAct-промпт
Инструкция: Модель должна выполнять итеративный цикл рассуждения и действия для сборки проверенного артефакта по файлу @practices/practice_01/TRAINING_PR.diff и устранить слабости в @practices/practice_01/prompts.md.

Симулируемые инструменты:
- RunTests: имитация запуска make test (проверяет наличие обязательных секций и заполненность артефактов).
- StaticAnalysis: имитация статической проверки consistency (поиск противоречий, лишних полномочий, нарушений формата candidate/evidence/check).
- BoundaryCheck: имитация граничных сценариев (пустой payload, длинный diff, исключение LLM).

Формат цикла:
- Thought [i]: краткое рассуждение о следующем шаге.
- Action [i]: какой инструмент и что именно проверяем.
- Observation [i]: что обнаружили и как это влияет на артефакт.

Ограничения:
- Работать только по фактам TRAINING_PR.diff; не придумывать правила.
- Максимум 3 риска. Каждый риск в формате candidate -> evidence (file:lines) -> check (AS IS vs TO BE).

Выход:
- По завершении 3+ циклов верни Final Answer: обновлённый master prompt и список рисков, готовый к использованию.
- Дополнительно: создай/обнови файл practices/practice_02/chain_of_verification/prompts.md и помести туда новый исправленный артефакт (та же версия, что в Final Answer), без логов.

## 2. Лог выполнения ReAct-цикла

Thought [1]: Проверить формальные несоответствия исходного prompts.md: противоречия, лишние полномочия, отсутствие строгого формата.
Action [1]: StaticAnalysis → анализ раздела "Master Prompt v2" и дублирующих блоков.
Observation [1]: Найдены противоречия: промпт требует «заполнять все файлы» и содержит второй конфликтующий блок. Формат candidate/evidence/check не закреплён. Решение: сузить полномочия до анализа diff, закрепить формат и лимит в 3 риска.

Thought [2]: Проверить воспроизводимость: достаточно ли информации для тестирования и сравнения двух запусков.
Action [2]: RunTests → соотнести с Makefile-проверками и таблицей «Сравнение двух запусков».
Observation [2]: В prompts.md незаполнены таблицы «Сравнение двух запусков» и «Peer review». Требуется закрепить DoD: ссылки file:lines, evidence и reproducible checks. Решение: включить явные критерии и DoD в промпт.

Thought [3]: Проверить граничные условия и безопасность.
Action [3]: BoundaryCheck → смоделировать пустой payload, исключение LLM и длинный diff.
Observation [3]: Подтверждены риски: 500 на пустом payload (KeyError), 5xx без маппинга при исключении LLM, отсутствие лимита/редактирования diff. Решение: включить соответствующие checks в итоговый артефакт.

## 3. Финальный артефакт (Final Answer)

Master Prompt (ReAct-verified)
Role: AI-reviewer (только анализ diff)
Inputs: @practices/practice_01/TRAINING_PR.diff
Goal: Найти до 3 рисков по фактам diff. Для каждого вернуть candidate -> evidence -> check на русском языке.
Output format (строго):
```
candidate: <кратко суть>
evidence: <file:lines> — <цитата или описание по diff>
check: <как воспроизвести и какой ожидаемый результат (AS IS vs TO BE)>
```
Rules:
- Только факты из diff; не придумывать правила.
- Если нет прямого evidence — риск не включать.
- Максимум 3 риска; остановиться после третьего.
- Не изменять файлы и не одобрять изменения; только анализ.
Steps:
1) Прочитать TRAINING_PR.diff и выписать кандидатов в риски.
2) Для каждого найти точные file:lines и краткий evidence.
3) Составить проверку (check) с AS IS и TO BE.
4) Вернуть результат строго в указанном формате.
Definition of Done:
- Каждый риск имеет file:lines, evidence и воспроизводимую проверку.
- Нет домыслов; всё подтверждено diff.

Риски (итог):
```
candidate: Нет валидации входа в POST /api/reviews
evidence: app/api.py:35-38 — create_review(payload: dict) обращается к payload["diff"] без проверки наличия и типа
check: POST /api/reviews с {} → (AS IS) 500 из-за KeyError; (TO BE) 422/400 с описанием ошибки
```
```
candidate: Нет обработки исключений LLM и контролируемого ответа
evidence: app/review_service.py:19-22 — self.llm.generate(prompt) вызывается без try/except
check: Смоделировать исключение из LLM → (AS IS) 5xx без маппинга; (TO BE) 502/503 с контролируемым сообщением
```
```
candidate: Неконтролируемый размер diff и риск prompt injection
evidence: app/review_service.py:19-22 — diff вставляется в промпт без ограничений
check: Очень длинный/вредоносный diff → (TO BE) отказ по лимиту или усечение; инъекция не влияет на системные инструкции
```
```
candidate: Превышение лимита размера diff (API-1) → 413
evidence: CASE.md: API-1 — diff > 20 000 символов → 413; TRAINING_PR.diff: app/review_service.py:19-22 — нет ограничений
check: POST diff=25k → (AS IS) уходит в LLM; (TO BE) 413 Content Too Large, без вызова LLM
```
