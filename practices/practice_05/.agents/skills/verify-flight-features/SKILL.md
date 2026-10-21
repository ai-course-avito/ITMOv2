---
name: verify-flight-features
description: Verify the practice_05 flight search and price-history features after backend or frontend changes, using mocked Ignav responses and an isolated SQLite database. Use for release checks or evidence of a working A/B flow; do not use for live fare searches.
---

# Verify flight features

Run the project check from `practices/practice_05`:

```bash
backend/.venv/bin/python .agents/skills/verify-flight-features/scripts/run.py --report verification/flight-features.md
```

The runner executes backend tests, builds the frontend, and checks the A/B flow through FastAPI with a mocked Ignav client. Its scenario covers the first price, a lower second price, an empty result, invalid input, and the corresponding SQLite history. It never calls Ignav or reads the real API key. The report records commands, outcomes, and observed comparison values; give the user the report path and summarize failures precisely.

If the local Python environment or `node_modules` is missing, install the project's documented dependencies before running. If a check fails, fix the relevant code and rerun the skill. Do not treat an existing report as proof that current code passed. A successful run verifies local behavior against a mock, not the availability or live pricing of Ignav.
