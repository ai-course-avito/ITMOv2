# Tasks

## 1. Model and migration

- [x] 1.1 Add `start_date`, `next_billing_date`, `note` and the CHECK constraints (amount, cycle, interval rule) to the `Subscription` model; verify model tests reject each invalid row with an integrity error and accept valid ones
- [x] 1.2 Write the Alembic revision (new columns backfilled via temporary default, `owner_id` index, CHECKs, reversible); verify on a scratch Postgres database `upgrade head`, `downgrade -1`, `upgrade head` and `alembic check` with seed-created rows present
- [x] 1.3 Extend `tests/test_migrations.py` to cover the new revision and to assert a violating insert fails; verify it passes with `TEST_POSTGRES_URL` set

## 2. Billing date arithmetic

- [x] 2.1 Add `occurrence` and `first_on_or_after` to `services/billing.py` for all four cycles; verify unit tests for weekly, custom days, monthly month-end clamp (Jan 31 -> Feb 28/29 -> Mar 31), leap-day yearly, anchor in the future and anchor today
- [x] 2.2 Add the default `next_billing_date` helper used on create and recompute; verify a unit test that the result is never earlier than today and never earlier than `start_date`

## 3. CRUD

- [x] 3.1 Add `schemas/subscriptions.py` (`BillingCycle`, create/update/read, cross-field validation, two-decimal string amount); verify schema tests for every 422 scenario in the spec
- [x] 3.2 Add `services/subscriptions.py` with owner-scoped create, list (filter, paging), get, merge-validate update, delete; verify service tests including that a foreign id returns nothing
- [x] 3.3 Add `routers/subscriptions.py` (POST 201, GET list, GET one, PATCH, DELETE 204, 404 and 422 mapping) and include it in `main.py`; verify API tests for each scenario in `subscription-management`
- [x] 3.4 Add isolation tests with two real users covering read, patch and delete of the other user's id, ignored `owner_id`, and more than 5 subscriptions on free; verify they pass
- [x] 3.5 Verify `/api/stats/summary` still returns correct totals for subscriptions created through the API; add one test for it

## 4. Upcoming charges

- [x] 4.1 Add `get_today` dependency and `GET /api/subscriptions/upcoming` (days 1..365, default 7, sorted, active and own only, no writes); verify API tests for inside/outside window, today, rolled-forward past date, inactive and other-user exclusion, invalid `days`
- [x] 4.2 Verify the read has no side effects with a test that compares stored `next_billing_date` before and after the call

## 5. Seed, docs, integration

- [x] 5.1 Update `scripts/seed.py` to the new fields with dates relative to today; verify the seed test still passes and the demo user has at least two upcoming charges within 30 days
- [x] 5.2 Update `SPEC.md`: model fields, new endpoints with examples, upcoming semantics, UTC-today limitation, roadmap without the APScheduler stage; verify every endpoint in `/openapi.json` for subscriptions appears in the document
- [x] 5.3 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, then the Postgres migration test; verify all green
- [x] 5.4 End-to-end on local Postgres via `./scripts/dev.sh --seed`: log in as the demo user, create, patch and delete a subscription, call upcoming and stats; verify expected status codes and values
