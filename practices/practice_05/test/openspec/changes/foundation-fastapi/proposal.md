# Foundation: FastAPI service

## Why
We need a minimal, testable backend to iterate safely. FastAPI gives OpenAPI docs, validation, and good DX, so we can focus on features.

## How
- Create FastAPI app with `/health` and `/ready` endpoints.
- Reserve `/api` base and `/api/v1` router for future public endpoints.
- Provide run instructions and a basic test suite (pytest).

## What follows
- Subsequent features (menu, orders, payments) live under `/api/v1`.
- OpenAPI docs available at `http://localhost:8000/docs` in dev.
- Baseline tests ensure service is healthy before expanding scope.
