# Proposal

## Why

The product is a subscription tracker, but a user cannot yet add a subscription: the only data path is the demo seed script, so `/api/stats/summary` always shows zero for real users. The "reminders" promise also has nothing behind it. This change delivers the core user loop (manage subscriptions, see what is charged soon) so a frontend can be built on top of it.

## What Changes

- Add authenticated CRUD for subscriptions under `/api/subscriptions` (create, list, get, partial update, delete). A user only ever sees and changes their own subscriptions; someone else's subscription behaves as not found.
- Extend the subscription record with `start_date`, `next_billing_date` and an optional `note`.
- Validate subscriptions strictly: `amount > 0`; `billing_cycle` one of `monthly|yearly|weekly|custom_days`; `custom_interval_days` required and positive for `custom_days`, forbidden otherwise. Invalid input returns 422 (today an unknown cycle would surface as a 500 in the stats calculation).
- Add `GET /api/subscriptions/upcoming?days=N`: simple reminders, computed on request from `next_billing_date` and the billing cycle. No e-mail, no background scheduler.
- Enforce the same rules in the database with CHECK constraints via a new Alembic migration, and update the seed script to the new fields.
- Update `SPEC.md` (model, API, roadmap: the APScheduler stage is dropped because reminders are computed on request).

Out of scope: Pro features, payments, ads, categories, multi-currency per subscription, e-mail/push reminders, frontend. Free accounts have no limit on the number of subscriptions.

## Capabilities

### New Capabilities
- `subscription-management`: creating, reading, updating and deleting a user's own subscriptions with validated fields and strict per-user isolation.
- `upcoming-charges`: listing a user's upcoming charges within a time window, computed from billing cycle and next billing date.

### Modified Capabilities
- `database-migrations`: adds a requirement that subscription data rules are enforced by the database schema, not only by the API.

## Impact

- Code: `backend/app/models.py`, new `routers/subscriptions.py`, `schemas/subscriptions.py`, `services/subscriptions.py`, date arithmetic in `services/billing.py`, `main.py`; new Alembic revision; `scripts/seed.py`.
- API: new `/api/subscriptions*` endpoints; `/api/stats/summary` behaviour unchanged.
- Data: existing rows get `start_date` and `next_billing_date` defaulted to the migration date.
- Docs: `SPEC.md`. `AGENTS.md` still lists APScheduler in the stack; left untouched by request, so it is now out of date with the roadmap.
