# Design

## Context

Current state (observed): `Subscription` has `name`, `amount` (`Numeric(10,2)`), `billing_cycle` (free string), `custom_interval_days`, `is_active`, `owner_id`; no constraints beyond FK. `services/billing.py` converts amounts to a monthly cost and raises `ValueError` on bad cycles. Auth (`get_current_user`) exists; tests use SQLite in-memory with real tokens. Postgres is the real database; migrations are Alembic only. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Correct, strictly validated CRUD with isolation enforced in the query, not after the fact.
- Reminders that need no infrastructure and are deterministic and testable.
- Rules enforced both in the API (clear 422) and in the database (CHECK).

**Non-Goals:**
- Background jobs, e-mail/push, per-user timezones.
- Categories, per-subscription currency, soft delete, Pro/paywall logic.

## Decisions

1. **Layering**: `routers/subscriptions.py` (HTTP, status codes) -> `services/subscriptions.py` (queries, ownership, merge for PATCH) -> pure date/money functions in `services/billing.py`. No SQL in routers.
2. **Ownership in the query**: every read/update/delete uses `WHERE id = :id AND owner_id = :user`; no match returns 404. `session.get(Subscription, id)` is never used for these endpoints. Alternative (fetch then compare owner -> 403) rejected: it leaks existence.
3. **Schemas** (Pydantic v2): `SubscriptionCreate`, `SubscriptionUpdate` (all optional), `SubscriptionRead`. `BillingCycle` is a `StrEnum`. `amount: Decimal` with `gt=0`, `max_digits=10`, `decimal_places=2`; serialized as a two-decimal string, consistent with the stats response. Unknown fields such as `owner_id` are ignored (Pydantic default), so clients cannot set ownership.
4. **PATCH = merge then re-validate**: the service builds the merged dict from the stored row plus `model_fields_set` of the patch and validates it with the create schema's cross-field checks (interval rules, date order), so partial updates cannot create states that creation would reject. If cycle, interval or `start_date` changed and `next_billing_date` was not supplied, it is recomputed (decision 6).
5. **DB representation**: `billing_cycle` stays a `String` with CHECK constraints, not a PostgreSQL enum type. Reason: simpler migrations, works in the SQLite test database. CHECKs: `amount > 0`; `billing_cycle IN (...)`; `(billing_cycle = 'custom_days' AND custom_interval_days IS NOT NULL AND custom_interval_days > 0) OR (billing_cycle <> 'custom_days' AND custom_interval_days IS NULL)`.
6. **Date arithmetic** is implemented in pure functions without a new dependency: `occurrence(anchor, cycle, interval, n)` and `first_on_or_after(anchor, cycle, interval, today)`. Weekly/custom use day arithmetic and a ceiling division. Monthly/yearly add `n` months (12n for yearly) to the **anchor** and clamp the day to the month length, so Jan 31 gives Feb 28/29 then Mar 31 (no drift) and Feb 29 yearly gives Feb 28 in non-leap years. Alternative: `python-dateutil.relativedelta` - rejected only to avoid a dependency for ~20 lines; swap is easy if bugs appear.
7. **Default `next_billing_date`** on create (and recompute on PATCH) is `first_on_or_after(start_date, cycle, interval, today)`.
8. **Upcoming is computed, not stored**: load the user's active subscriptions, compute `charge_date` in Python, filter to `today <= charge_date <= today + days`, sort by (`charge_date`, `name`). The GET never writes. A stored `next_billing_date` that is in the past is therefore harmless and rolls forward at read time. Alternative: a scheduler advancing dates (APScheduler) - rejected: process-local, lossy on restart, and unnecessary at this scale.
9. **"Today"** comes from an injectable dependency (`get_today`, UTC date). Tests override it, so no clock mocking. Limitation: users in other time zones can see a one-day offset around midnight UTC.
10. **Route order**: `/upcoming` is declared before `/{subscription_id}` so it is not captured as an id.
11. **Delete** is a hard delete (204). Alternative: deactivate - users already have `is_active` for that.
12. **Migration**: one new Alembic revision adds `start_date` and `next_billing_date` (NOT NULL; backfilled with the current date via a temporary server default that is then dropped), `note` (nullable, 500), an index on `owner_id`, and the CHECK constraints; downgrade reverses. Autogenerate output is reviewed by hand because CHECK and server defaults are not detected reliably.
13. **Seed** is updated to set dates relative to today so the demo user has visible upcoming charges.

## Risks / Trade-offs

- [Backfilled dates on existing rows are all "today"] -> Acceptable: only demo data exists; the roll-forward logic keeps the list sensible; documented in SPEC.md.
- [Existing rows violating new CHECKs would make the migration fail] -> Fail loudly rather than silently fix; the only known data (seed) complies; verified on a scratch database.
- [Python-side filtering loads all of a user's active subscriptions] -> Fine for tens of rows per user; revisit with SQL date logic only if needed.
- [UTC "today"] -> Documented; per-user timezone is a later change.
- [`AGENTS.md` still lists APScheduler] -> Left as is by request; SPEC.md is the source of truth for the roadmap.
