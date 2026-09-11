# P1-03b. Анализ процесса и архитектурное решение

**Для файлов:** `practices/practice_01/analysis.md`, `practices/practice_01/adr.md`

## Промпт

```text
Роль: solution architect. Читай только practices/practice_01/TRAINING_PR.diff, CASE.md, context.md, problem.md. Не менять эти файлы.

Задача: сгенерировать analysis.md (AS IS/TO BE) и adr.md (архитектурное решение).

Правила кейса (обязательные): SEC-1, API-1 (413), REL-1 (таймаут 10с), OUT-1 (структура ответа), SCOPE-1, QA-1, OBS-1 (лог только метаданных). Игнорируй snake_case/i18n.

analysis.md: AS IS — 4-шаговый поток по TRAINING_PR.diff и 5 затыков, привязанных к правилам; TO BE — Mermaid flowchart с ветками API-1 (413), SEC-1 (маскирование), REL-1 (таймаут→контролируемый ответ), OUT-1 (сборка), OBS-1; таблица «Разница» ≥3 строки с колонкой «Как проверим изменение»; блок «Как использовали AI».

adr.md: статус accepted; сегодняшняя дата; ответственный — студент; Контекст (перечисление правил); Решение (5 конкретных пунктов); минимум 3 альтернативы с обоснованием отказа; Последствия и главный риск + «Как проверим»; заголовок `## Архитектурная схема` с Mermaid flowchart LR: Client → FastAPI(API-1) → ReviewService(SEC-1) → LLM(REL-1) → OUT-1 → Client + стрелка на Logger(OBS-1); блок «Как использовали AI».

Формат: `File: <path>` + полное содержимое. Без Chain of Thought.
```
