# P1-03c. Продуктовый сценарий и план поставки

**Для файлов:** `practices/practice_01/product_management.md`, `practices/practice_01/project_management.md`

## Промпт

```text
Роль: product engineer + delivery lead. Читай только practices/practice_01/TRAINING_PR.diff, CASE.md, analysis.md, adr.md. Не менять эти файлы.

Задача: сгенерировать product_management.md (use case + user stories) и project_management.md (план поставки).

Правила кейса: SEC-1, API-1 (413), REL-1 (таймаут 10с), OUT-1, SCOPE-1, QA-1, OBS-1.

product_management.md: «Первый рабочий сценарий» в формате When/Then; таблица Use case (актор, триггер, предусловия, результат, ошибка); Mermaid sequenceDiagram с реальными участниками — Client(dev/CI), FastAPI, ReviewService, LLM provider — и ветками API-1 (413), REL-1 (таймаут→контролируемый ответ), OBS-1 (лог метаданных). Никаких абстрактных «User → System → AI». Два Gherkin-сценария (позитив 200+OUT-1; негатив >20000→413); блок «Как использовали AI».

project_management.md: таблица инкрементов (≥3: OUT-1, REL-1, API-1/SEC-1) с колонками Человек/AI/Проверка/Зависимости; Mermaid gantt: `dateFormat YYYY-MM-DD`, минимум 6 задач с разными длительностями 1–2д, параллельность OUT-1/REL-1, финальный milestone «Peer review PR»; блок «Как использовали AI».

Формат: `File: <path>` + полное содержимое. Без Chain of Thought.
```
