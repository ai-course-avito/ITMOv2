# Baseline before city-airport UI changes

Run on 2026-10-29 from `practices/practice_05` with `backend/.venv/bin/python .agents/skills/verify-flight-features/scripts/run.py --report verification/flight-features.md`.

| Check | Baseline result |
| --- | --- |
| Backend tests | PASS: 26 tests |
| After-edit hook tests | PASS: 1 test |
| Frontend build | PASS: TypeScript and Vite |
| Offline A/B scenario | PASS: mocked upstream calls 3, saved rows 3, invalid HTTP 422 |

The runner used mocked Ignav responses and temporary SQLite. The original `verification/flight-features.md` was later regenerated after the UI changes; this file preserves the baseline outcome.
