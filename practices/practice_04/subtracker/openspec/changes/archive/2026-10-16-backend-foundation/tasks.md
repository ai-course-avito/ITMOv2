# Tasks

## 1. Dependencies, config, SPEC

- [x] 1.1 Add `alembic`, `argon2-cffi` and dev `ruff` to `backend/pyproject.toml`; verify `cd backend && uv sync && uv run ruff check .` succeeds
- [x] 1.2 Make `secret_key` required; add token TTLs and `cors_origins` to `app/config.py` and `.env.example`; set `SECRET_KEY` in `tests/conftest.py`; verify startup without `SECRET_KEY` fails and `uv run pytest` still passes the existing 10 tests
- [x] 1.3 Write `SPEC.md` at repo root: product goal and audience, Free/Pro table (Free unlimited + ads; Pro no ads + drag-and-drop, calendar, forecast, necessity rating, savings suggestions), domain model, API list, staged roadmap (later changes for Pro features and Stripe), TODOs on refresh-token revocation and APScheduler; verify it covers every endpoint added in this change and marks each Pro feature as not yet implemented
- [x] 1.4 Add `plan` (CHECK free/pro, default `free`) to the `User` model; verify model tests create a user with plan `free`

## 2. Migrations

- [x] 2.1 Initialise async Alembic in `backend/alembic/` wired to `settings.database_url` and `Base.metadata`; verify `uv run alembic current` runs
- [x] 2.2 Generate and review the initial migration for `users` and `subscriptions`; verify `upgrade head`, `downgrade base`, `upgrade head` on a scratch Postgres database and `alembic check` reports no drift
- [x] 2.3 Add a Postgres-only migration test (skipped without a configured URL); verify it passes locally and is skipped in a plain `uv run pytest` run without the env var

## 3. Auth

- [x] 3.1 Add `app/security.py` (argon2 hash/verify, JWT encode/decode with `exp`, `iat`, `sub`, `type`) with unit tests for hashing, expiry, missing `exp`, and wrong type
- [x] 3.2 Add `services/auth.py` and `schemas/auth.py` (register, authenticate, issue tokens, refresh); verify service tests cover duplicate email in different case and wrong password
- [x] 3.3 Add `routers/auth.py` with `/api/auth/register`, `/login`, `/refresh` and include it in `main.py`; verify API tests for 201/409/422/200/401 scenarios from the user-auth spec
- [x] 3.4 Update `get_current_user` to use `HTTPBearer(auto_error=False)`, 401 on missing/invalid/wrong-type tokens; verify tests call `/api/stats/summary` with a real token and without one, with no dependency override
- [x] 3.5 Add `GET /api/auth/me` returning id, email, plan, default currency, plus `plan` in the register response; verify tests for free, pro and 401 scenarios

## 4. Health, CORS, local dev

- [x] 4.1 Add `GET /health` (503 when DB unreachable) and CORS middleware from `cors_origins`; verify tests for 200, 503, allowed and disallowed origin
- [x] 4.2 Add `backend/scripts/seed.py` (idempotent demo user with one subscription per billing cycle); verify running it twice leaves one user and no duplicates
- [x] 4.3 Add `backend/scripts/dev.sh` (DB reachability check, migrate, optional `--seed`, uvicorn); verify on local Postgres that `./scripts/dev.sh --seed` serves `/docs` and the demo user can log in and fetch `/api/stats/summary`
- [x] 4.4 Document local run in `SPEC.md` or backend README (commands, demo credentials location); verify the documented commands work from a clean shell

## 5. Integration checks

- [x] 5.1 Run `uv run ruff check .`, `uv run ruff format --check .` and full `uv run pytest`; verify all green
- [x] 5.2 Manual end-to-end via Swagger: register, login, refresh, call stats with the access token and with the refresh token (expect 401)
