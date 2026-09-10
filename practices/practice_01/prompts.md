# Журнал запросов и проверок

Не сохраняйте скрытую Chain of Thought и полный чат. Нужны запрос, краткий результат, ссылка на изменённый артефакт и ваша проверка.

| ID | Артефакт и цель | Инструмент / модель | Тип промпта | Запрос или ссылка на него | Результат или ссылка | Что приняли | Что отклонили или исправили | Как проверили |
|---|---|---|---|---|---|---|---|---|
| P1-01 | Baseline-ревью `TRAINING_PR.diff` | gpt5 | zero-shot | [prompts/P1-01.prompt.md](prompts/P1-01.prompt.md) | [prompts/P1-01.result.md](prompts/P1-01.result.md) — 10 находок: KeyError без валидации (`app/api.py:37`), prompt injection и утечка секретов в LLM (`app/review_service.py:20`), нет timeout/обработки ошибок LLM-вызова, нет лимита размера diff | Риски, подтверждённые diff: KeyError на `payload["diff"]`, diff в LLM без очистки секретов, отсутствие timeout, отсутствие лимита размера | Слабые места: (1) 10 находок без приоритезации вместо топ-3 рисков; (2) спекулятивные пункты без evidence — Python <3.9, конфликт со стиль-гайдом; (3) нет воспроизводимых проверок для каждой находки. Не хватило: правил репозитория (SEC-1, API-1, REL-1, OUT-1), формата ответа `summary/risks/checks`, границ помощника (SCOPE-1) | Сверили каждую находку со строками `TRAINING_PR.diff`: 4 риска подтверждены строками diff, 2 пункта отклонены как не подтверждённые |
| P1-02 | Повторное ревью `TRAINING_PR.diff` | gpt5 | master prompt | [prompts/P1-02.prompt.md](prompts/P1-02.prompt.md) | 5 рисков: KeyError на `payload["diff"]` (app/api.py:37); отправка diff в LLM без редактирования (SEC-1) (app/review_service.py:20); нет timeout/обработки ошибок (REL-1) (app/review_service.py:21); нет проверки длины diff и HTTP 413 (API-1) (app/api.py:35-37); формат ответа не соответствует OUT-1 (app/review_service.py:22). | Подтверждены: см. строки diff выше и правила SEC-1, API-1, REL-1, OUT-1. | Отклонены: OBS-1 (логирование) и иные неподтверждённые догадки — отсутствуют в diff. | Сопоставили строки `TRAINING_PR.diff` 19-22, 35-37 с CASE.md правилами; проверили, что риски опираются на QA-1. |
| P1-03 |  |  |  |  |  |  |  |  |

## Master Prompt v1

### 1. Цель и роль

- Цель: Review diff, and write result to prompts.md in P1-02 row.
- Роль AI: Code-reviewer

### 2. Входы и источники

- Обязательный вход: TRAINING_PR.diff
- Разрешённые файлы и источники: TRAINING_PR.diff, prompts.md, CASE.md: SEC-1...QA-1.
- Context Pack — факты, правила, примеры и ограничения: python 3.10, TRAINING_PR.diff, prompts.md, CASE.md: SEC-1...QA-1.

### 3. Задача и артефакты

- Что сделать: Check for mistakes, potential risks. Document anything you did in prompts.md in table.
- Что вернуть: short list with important changes in a format {file:line} - description, in Russian language, professional formal style. Also fill P1-02 row in a journal

### 4. Формат результата

- Структура ответа: short list with important changes in a format {file:line} - description, in Russian language, professional formal style. Also fill P1-02 row in a journal
- Ограничения объёма: 

### 5. Полномочия и запреты

- Разрешено: review and suggest, list questions.
- Запрещено: change codebase/anything except prompts.md. Dont make up any rules. Never invent facts.

### 6. Рабочий процесс и остановка

- Шаги: Parse .diff line by line, group issues, write summary.
- Когда остановиться и запросить человека: If data in provided sources missing, stop and ask for it.

### 7. Проверки и evidence

- Как проверять утверждения: Review your summary and check for hallucinations / mistakes.
- Какое evidence сохранить: 

### 8. Definition of Done

- Задача закончена, когда: All changes reviewed, work documented in prompts.md.

## Сравнение двух запусков

| Проверка | Zero-shot | С master prompt | Вывод команды |
|---|---|---|---|
| Есть ссылка на файл или строку |  |  |  |
| Вывод подтверждён diff или правилом |  |  |  |
| Соблюдены границы AI |  |  |  |
| Есть воспроизводимая проверка |  |  |  |

## Peer review

| Где другой команде пришлось догадываться | Что исправили | Если не исправили — почему |
|---|---|---|
| 1 |  |  |
| 2 |  |  |
| 3 |  |  |
