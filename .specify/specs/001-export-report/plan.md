# Implementation Plan: export-report

**Branch**: `[001-export-report]` | **Date**: 2026-10-22 | **Spec**: .specify/specs/001-export-report/spec.md

**Input**: Feature specification from `/specs/001-export-report/spec.md` and logic-spec `/specs/001-export-report/logic-spec.md`

## Summary

Цель: реализовать CLI-команду `/export-report`, которая собирает метрики из `practices/practice_03/lab/results/*.json`, опционально включает артефакты (`practices/practice_01/prompts.md`, `practices/practice_03/REPORT.md`), генерирует отчёт в формате Markdown или HTML и сохраняет в `reports/report-YYYY-MM-DD.{md|html}`. После генерации команда печатает путь к файлу и краткое резюме (кол-во обработанных файлов, кол-во метрик, статус Success). При отсутствии данных выводит ровно «Нет данных для отчёта» и не создаёт файл.

Технический подход: однопроцессный Python-скрипт `scripts/export_report.py` на стандартной библиотеке (argparse/json/glob/os/datetime). Сканирование и парсинг `.json`, фильтрация и пропуск битых файлов, построение таблицы, расчёт средних, генерация Markdown/HTML, запись в `reports/` (создаётся при необходимости).

## Technical Context

- Language/Version: Python 3.10+
- Primary Dependencies: стандартная библиотека (argparse, json, glob, os, datetime)
- Storage: файловая система (чтение из `practices/`, `docs/`, `lab/results/`; запись только в `reports/`)
- Testing: ручной прогон команды; интеграционный сценарий с фактическими `*.json` в `lab/results/`
- Target Platform: локальная среда разработчика (macOS/Linux), без внешних сервисов
- Project Type: CLI-script
- Performance Goals: генерация < 15 секунд при объёме данных практики 3
- Constraints: read-only для источников; исключить `node_modules/`, `.venv/`, `.git/`; `.jsonl` не обрабатывается
- Scale/Scope: десятки файлов результатов; один отчёт на дату

## Constitution Check

- Границы чтения соблюдены: только `practices/`, `docs/`, `lab/results/`; исключения — `node_modules/`, `.venv/`, `.git/`.
- Безопасность: только чтение источников; запись ограничена `reports/`.
- Демонстрационные каталоги и учебные практики не изменяются.

Gate Status: PASS (нарушений не выявлено).

## Project Structure

### Documentation (this feature)

```text
specs/001-export-report/
├── spec.md               # Feature spec (UI)
├── logic-spec.md         # Logic specification (Kiro)
├── plan.md               # This file (implementation plan)
├── checklists/
│   └── requirements.md   # Spec quality checklist
```

### Source Code (repository root)

```text
scripts/
└── export_report.py      # CLI-скрипт генерации отчёта

.opencode/
└── commands/
    └── export-report.md  # Команда OpenCode, вызывает скрипт с флагами

practices/practice_03/lab/results/   # Источник метрик (*.json)
practices/practice_01/prompts.md     # Артефакт (по выбору)
practices/practice_03/REPORT.md      # Артефакт (по выбору)

reports/                  # Выходной каталог (создаётся при выполнении)
```

**Structure Decision**: Single-project layout с одним CLI-скриптом без внешних зависимостей; команда OpenCode описывает вызовы.

## Implementation Details

1. CLI-параметры
   - `--format {md,html}` (по умолчанию `md`)
   - `--include-artifacts` | `--metrics-only` (взаимно исключающие)

2. Сканирование и парсинг метрик
   - glob: `practices/practice_03/lab/results/*.json`
   - Извлечение: `wall_seconds`, `decode_tokens_per_second` (float)
   - Обработка ошибок: пропуск файла, счётчик ошибок, продолжение
   - Исключение `.jsonl` обеспечивается паттерном `*.json`

3. Таблица метрик
   - Колонки: `Файл | Время, с | Скорость, tok/s`
   - Сортировка: по имени файла (алфавитно)
   - Округление: до 2 знаков после запятой
   - Строка «Среднее»: средние по всем успешно распарсенным файлам

4. Артефакты (опционально)
   - `practices/practice_01/prompts.md` и `practices/practice_03/REPORT.md`
   - Если файл отсутствует — «файл не найден»; генерация не прерывается

5. Генерация отчёта
   - Путь: `reports/report-YYYY-MM-DD.md` или `.html` (локальная дата)
   - Markdown: заголовок, таблица, секция артефактов (при выборе), нижний блок с метриками/статусом
   - HTML: те же секции в `<table>/<pre><code>`, инлайн CSS, без внешних зависимостей
   - Создание каталога `reports/` при отсутствии; перезапись файла допускается

6. Вывод результата
   - Успех: печать `Путь: ...` и `Краткое резюме: файлов N, метрик M, статус Success` (+ примечание об ошибках парсинга при наличии)
   - Нет данных: печать ровно «Нет данных для отчёта», файл не создаётся

## Risks & Mitigations

- Повреждённые JSON: пропускаем, считаем ошибки, продолжаем; негативный итог, если все повреждены
- Большие артефакты: включаем как есть; в v1 без пагинации и сжатия
- Несоответствие ключей: строгая проверка на наличие `wall_seconds`, `decode_tokens_per_second`

## Validation Plan

- Демо: `python3 scripts/export_report.py --format md --include-artifacts`
- Проверка HTML: `python3 scripts/export_report.py --format html --metrics-only`
- Негативный сценарий: временно переместить `lab/results/*.json` и убедиться в выводе «Нет данных для отчёта»

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
