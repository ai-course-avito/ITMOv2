# Proposal

## Why

The approved frontend (tabs Overview / Subscriptions, donut and top-5 charts, grouped and searchable list) needs data the API does not provide yet: a per-subscription and per-cycle spending breakdown, search and sorting of the list, and the real next charge date for every subscription (the stored `next_billing_date` goes stale after it passes). Doing this on the client would duplicate billing rules; doing it first on the backend keeps the frontend change purely about UI. See `SPEC.md` section 8.

## What Changes

- Add `GET /api/stats/breakdown`: active subscriptions' monthly-equivalent cost, each with its share of the total, grouped by subscription and by billing cycle. Totals match `/api/stats/summary`.
- Specify the already implemented `GET /api/stats/summary` (it has no spec today) so both stats endpoints live in one capability.
- Extend `GET /api/subscriptions` with `q` (search in name and note, case-insensitive, works for Cyrillic), `billing_cycle` filter, `sort` (`id`, `name`, `amount`, `monthly_cost`, `charge_date`) and `order` (`asc`, `desc`). Default behaviour (order by `id`) is unchanged.
- List items gain three computed read-only fields: `monthly_cost`, `charge_date` (next real charge, rolled forward from the stored date) and `days_until`. For inactive subscriptions `charge_date` and `days_until` are null.
- Update `SPEC.md` (API section; the "needed from backend" list becomes implemented).

Out of scope: categories (decided against), pagination metadata/total count, Pro features, any frontend code, database migrations (no schema change).

## Capabilities

### New Capabilities
- `spending-stats`: monthly/yearly spending summary and the breakdown of monthly spending by subscription and by billing cycle, for the caller's active subscriptions.

### Modified Capabilities
- `subscription-management`: the list requirement changes (extra query options, extra computed fields in list items; default ordering unchanged) and new requirements cover search, cycle filter, sorting, and computed list fields.

## Impact

- Code: `backend/app/services/stats.py`, `routers/stats.py`, `schemas/stats.py`; `services/subscriptions.py`, `routers/subscriptions.py`, `schemas/subscriptions.py`; reuse of `services/billing.py`.
- API: new `/api/stats/breakdown`; additive query params and response fields on the list endpoint (backwards compatible; create/get/patch responses unchanged).
- Data: none; no migration.
- Docs: `SPEC.md`.
