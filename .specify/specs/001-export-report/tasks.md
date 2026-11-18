# Tasks: export-report

## Phase 1: Setup

- [ ] T001 Create CLI skeleton with argparse in scripts/export_report.py (add --format {md,html}; --include-artifacts; --metrics-only)
- [ ] T002 Create command descriptor in .opencode/commands/export-report.md (invoke python3 scripts/export_report.py with flags)
- [ ] T003 Ensure reports directory creation logic in scripts/export_report.py (os.makedirs('reports', exist_ok=True))
- [ ] T004 Add module docstring and dataclass imports in scripts/export_report.py (PEP 8 compliance per practices/practice_03/STYLEGUIDE.md)

## Phase 2: Foundational (blocking)

- [ ] T005 Implement results scan using glob in scripts/export_report.py for practices/practice_03/lab/results/*.json
- [ ] T006 Implement JSON parsing function load_json_metrics(path) in scripts/export_report.py (extract wall_seconds, decode_tokens_per_second; error handling)
- [ ] T007 Define MetricRow dataclass in scripts/export_report.py (filename, wall_seconds, decode_tokens_per_second)
- [ ] T008 Implement sorting and average computation in scripts/export_report.py (alphabetical by filename; 2-decimal rounding)
- [ ] T009 Implement Markdown formatter format_markdown(...) in scripts/export_report.py (table + averages + summary)
- [ ] T010 [P] Implement HTML formatter format_html(...) in scripts/export_report.py (inline CSS; same sections as Markdown)
- [ ] T011 Implement file write and summary print in scripts/export_report.py (reports/report-YYYY-MM-DD.{md|html}; print path and resume)

## Phase 3: User Story 1 (P1) — Основной поиск и вывод

- [ ] T012 [US1] Add mutually exclusive flags group in scripts/export_report.py (--include-artifacts vs --metrics-only)
- [ ] T013 [P] [US1] Implement read_text_file() for artifacts in scripts/export_report.py (practices/practice_01/prompts.md; practices/practice_03/REPORT.md; annotate missing files)
- [ ] T014 [US1] Integrate artifact sections into output in scripts/export_report.py (Markdown and HTML "Артефакты" section)
- [ ] T015 [US1] Print final summary in scripts/export_report.py ("Краткое резюме: файлов N, метрик M, статус Success"; note parse_errors when >0)

## Phase 4: User Story 2 (P1) — Негативный результат

- [ ] T016 [US2] Detect "no data" cases in scripts/export_report.py (no .json files OR zero successfully parsed rows) and print exactly "Нет данных для отчёта"
- [ ] T017 [US2] Ensure no file is created on "no data" path in scripts/export_report.py (return early before write)

## Phase 5: User Story 3 (P2) — Ограничение области чтения и исключения

- [ ] T018 [US3] Enforce allowed read-scope by fixed glob in scripts/export_report.py (only practices/practice_03/lab/results/*.json)
- [ ] T019 [US3] Verify .jsonl excluded by pattern in scripts/export_report.py (pattern strictly *.json)
- [ ] T020 [US3] Ensure node_modules/.venv/.git are never accessed by code in scripts/export_report.py (no traversal outside allowed paths)

## Final Phase: Polish & Cross-Cutting

- [ ] T021 Update .opencode/commands/export-report.md with examples for md/html and artifacts/metrics-only
- [ ] T022 Add inline comments in scripts/export_report.py for non-obvious blocks (context sizes, averages, negative path)

---

## Dependencies

- Phase 2 (Foundational) must complete before Phase 3–5.
- Story order: US1 → US2 → US3 (US2 depends on core parsing flow; US3 is scope enforcement)

## Parallel Opportunities

- [P] T010 (HTML formatter) can be implemented in parallel with T009 (Markdown formatter).
- [P] T013 (artifact readers) can be implemented in parallel with T012 (flags) after skeleton is in place.

## Independent Test Criteria

- US1: Run `python3 scripts/export_report.py --format md --include-artifacts` → file `reports/report-YYYY-MM-DD.md` exists; summary printed; artifacts included.
- US2: Temporarily move/rename all `practices/practice_03/lab/results/*.json` → output exactly "Нет данных для отчёта"; file not created.
- US3: Place a dummy file under `node_modules/` → not scanned; ensure only `practices/practice_03/lab/results/*.json` are processed.

## MVP Scope

- MVP = US1: Markdown report generation with metrics-only path. Extend to artifacts and HTML in subsequent iterations.
