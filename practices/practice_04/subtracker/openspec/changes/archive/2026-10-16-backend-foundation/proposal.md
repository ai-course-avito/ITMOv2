# Proposal

## Why

The backend currently has one feature (`/api/stats/summary`) that cannot be used for real: tables exist only inside tests (`create_all` on SQLite), nobody can obtain a JWT (no register/login), and there is no one-command way to run the project locally (Docker is not installed on the author's machine). `SPEC.md`, which AGENTS.md tells us to follow, does not exist. Without this foundation the project cannot be run, evaluated, or built upon (CRUD, frontend).

## What Changes

- Add Alembic with an initial migration for `users` and `subscriptions`; remove reliance on `create_all` outside tests.
- Add user auth: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`; passwords hashed with argon2; access + refresh JWTs with mandatory `exp`.
- Tighten token validation: `exp`/`sub` required, token type enforced (a refresh token is not accepted as an access token), missing credentials return 401.
- Make `SECRET_KEY` mandatory (no insecure default) and add CORS for the Vite dev origin and a `/health` endpoint.
- Add a local (non-Docker) dev workflow: a script that checks Postgres, applies migrations, optionally seeds a demo user with subscriptions, and starts uvicorn.
- Add `ruff`, `alembic`, `argon2-cffi`, `uvicorn`, `email-validator` to backend dependencies.
- Add a `plan` (`free` | `pro`, default `free`) to users and expose it via `GET /api/auth/me`, so the frontend can show/hide ads and Pro features. Tariffs are switched manually (no payments yet).
- Write `SPEC.md` (business model, domain model, API, staged plan) as the source of truth AGENTS.md refers to. Business model: Free is unlimited in subscriptions and supported by ads; Pro removes ads and adds comfort features (drag-and-drop ordering, calendar integration, spending forecast, necessity rating of subscriptions, savings suggestions).

Out of scope: enforcing or implementing any Pro feature (they ship in later changes, e.g. `plans-and-pro-features`), payments (Stripe), ad serving, subscription CRUD, `next_billing_date`, reminders/APScheduler, frontend, Docker files.

## Capabilities

### New Capabilities
- `user-auth`: registration, login, token refresh, verification of access tokens, and reporting the current user's plan (free/pro).
- `database-migrations`: the schema is created and evolved only through Alembic migrations.
- `local-dev-environment`: running the backend locally without Docker, with optional demo data and health check.

### Modified Capabilities
<!-- None: no specs exist yet; /api/stats/summary behavior is unchanged. -->

## Impact

- Code: `backend/app/auth.py`, `config.py`, `main.py`, new `app/routers/auth.py`, `app/schemas/auth.py`, `app/services/auth.py`, `app/security.py`; new `backend/alembic/`, `backend/scripts/`.
- API: new `/api/auth/*`, `/health`; existing `/api/stats/summary` now requires real tokens (401 instead of 403 when missing).
- Dependencies: `alembic`, `argon2-cffi`, `uvicorn[standard]`, `email-validator`, `ruff` (dev).
- Config: `.env.example` gains token lifetimes, CORS origins; `SECRET_KEY` becomes required (**BREAKING** for anyone relying on the default).
- Docs: new `SPEC.md`.
