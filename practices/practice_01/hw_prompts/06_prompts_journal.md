# P1-03f. Журнал промптов и Master Prompt v1

**Для файла:** `practices/practice_01/prompts.md`

## Промпт

```text
Роль: prompt engineer + technical writer. Читай practices/practice_01/TRAINING_PR.diff, CASE.md, resault_ai.md и все ранее сгенерированные артефакты Практики 1. Не менять эти файлы.

Задача: собрать prompts.md — журнал двух запусков и Master Prompt v1.

Правила кейса: SEC-1, API-1 (413), REL-1 (таймаут 10с), OUT-1 (summary+risks≤3{file,line,evidence,risk}+checks), SCOPE-1, QA-1, OBS-1.

Содержимое prompts.md:
- Заголовок и вводная про журнал.
- Таблица со строками P1-01 (zero-shot baseline на TRAINING_PR.diff, ссылка на resault_ai.md) и P1-02 (повтор с master prompt): 9 колонок — инструмент/модель, тип, запрос, результат, что приняли, отклонили, как проверили.
- Секции «P1-01 — три слабых места ответа» и «P1-01 — какой информации не хватило» (по 3 буллета).
- Master Prompt v1 с 8 разделами: Цель/Роль, Входы, Задача/артефакты, Формат, Полномочия, Процесс, Проверки/Evidence, Definition of Done.
- Блок Risks (OUT-1, ≤3): OUT-1 (формат), REL-1 (таймаут), API-1 (длина); каждый с evidence (file:line из TRAINING_PR.diff) и check.
- Таблица «Сравнение двух запусков» по 4 признакам, все ячейки заполнены.
- Таблица «Peer review» с HTML-комментарием `<!-- ожидается после открытия PR -->`.

Формат: `File: <path>` + полное содержимое. Без Chain of Thought.
```
