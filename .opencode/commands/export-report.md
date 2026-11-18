---
description: Export Report — generate summary report per feature spec and logic spec.
handoffs: []
---

## UI

Ask the user two choices and then run the script accordingly:

1. Format: Markdown (`md`) or HTML (`html`)
2. Content: only metrics (`--metrics-only`) or metrics + artifacts (`--include-artifacts`)

## Constraints (from spec)

- Read sources only from: `practices/`, `docs/`, `lab/results/`
- Do not touch: `node_modules/`, `.venv/`, `.git`
- Negative case: if there is no data, print exactly `Нет данных для отчёта` and do not create a file

## Logic (from logic-spec)

- Metrics from `practices/practice_03/lab/results/*.json`: `wall_seconds`, `decode_tokens_per_second`
- Artifacts (optional): `practices/practice_01/prompts.md`, `practices/practice_03/REPORT.md`
- Output path: `reports/report-YYYY-MM-DD.{md|html}` (local date)
- Summary print: path, files processed, metrics count, status `Success` (and parse error count if any)

## Run

Choose flags based on the UI selections and execute the script:

```
# Markdown + artifacts
python3 scripts/export_report.py --format md --include-artifacts

# Markdown + metrics only
python3 scripts/export_report.py --format md --metrics-only

# HTML + artifacts
python3 scripts/export_report.py --format html --include-artifacts

# HTML + metrics only
python3 scripts/export_report.py --format html --metrics-only
```

## Output Handling

- If the script prints `Нет данных для отчёта` → show it and stop
- Otherwise, show:
  - The path line (`Путь: reports/report-YYYY-MM-DD.{md|html}`)
  - The summary line (`Краткое резюме: файлов N, метрик M, статус Success`)

## References

- Feature spec: `.specify/specs/001-export-report/spec.md`
- Logic spec: `.specify/specs/001-export-report/logic-spec.md`
- Plan: `.specify/specs/001-export-report/plan.md`
- Tasks: `.specify/specs/001-export-report/tasks.md`
