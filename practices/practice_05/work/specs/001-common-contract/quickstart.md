# Quickstart: Validate the Shared Contract

## Prerequisites

- Python 3.11+ and project dependencies from `requirements.txt`.
- Node dependencies installed when browser tests are run.

## Start the application

From `practices/practice_05/work`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Route validation

Request `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, and `/about/`. Each must return `200`, exactly one `h1`, the four landmarks, unique title metadata, and navigation links to every required route. At a 360px viewport, activate section anchors and confirm visible focus and no horizontal scroll.

## Math contract validation

POST the example request from [math-api.md](contracts/math-api.md) to `/api/v1/calculate`. Verify `contract_version`, operation, normalized parameters, domain semantics, tolerance, duration, cache status, finite ordered arrays, and deterministic repeated numeric results. Submit missing, malformed, non-finite, reversed-interval, and out-of-range values; verify a structured error and unchanged prior valid state.

## Demonstration validation

For each demo, start at its documented default, change one parameter with keyboard and pointer controls, and verify that the visible value, plotted result, accessible status, and fallback summary use the same normalized state without a reload. Force an initialization/service failure and confirm a textual explanation remains. Enable reduced motion and confirm autoplay is disabled while explicit stepping works.

## Automated checks

Run the repository's pytest and browser smoke suites. Browser checks should use the project `webapp-testing` workflow and verify routes, landmarks, MathJax/source fallback, controls, graph containers, status announcements, and mobile overflow. Performance evidence should record route LCP/TBT/CLS and representative API p50/p95 against the constitution budgets.
