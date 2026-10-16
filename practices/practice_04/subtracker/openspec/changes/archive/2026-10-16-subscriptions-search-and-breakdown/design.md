# Design

## Context

Observed state: `GET /api/stats/summary` computes monthly/yearly totals in `services/stats.py` using `services/billing.monthly_cost` (rounded half-up per subscription); it has tests but no spec. `GET /api/subscriptions` filters by owner and `is_active`, orders by `id`, pages with `limit/offset`. `services/billing.first_on_or_after` already computes the real next charge date, and `get_today` is an injectable dependency. Tests run on SQLite in memory, production on PostgreSQL. See proposal.md for motivation and SPEC.md section 8 for the screens this serves.

## Goals / Non-Goals

**Goals:**
- Everything the Overview and Subscriptions tabs need arrives in one request each, with money logic only on the backend.
- Search, sorting and computed fields behave identically on SQLite and PostgreSQL, including Cyrillic.
- Existing behaviour and response shapes stay backward compatible.

**Non-Goals:**
- Categories, total-count/pagination metadata, caching, SQL-side sorting for huge lists.
- Changing create/get/patch responses or any database schema.

## Decisions

1. **One cost computation, two endpoints.** `services/stats.py` gets `active_monthly_costs(session, user)` returning `(subscription, monthly_cost)` pairs for active subscriptions (using `billing.monthly_cost`). Both `summary` and `breakdown` build on it, so their totals cannot diverge. Alternative: separate queries per endpoint - rejected (duplicated rules, drift risk).
2. **Breakdown shape**: `{currency, monthly_total, by_subscription[], by_cycle[]}`. `share_percent = cost / monthly_total * 100`, quantized half-up to two places; if `monthly_total` is 0 every share is `0.00` (covers subscriptions that round to 0.00, no division by zero). Shares are not forced to sum to 100. `by_cycle` groups `custom_days` into one bucket. Alternative: a top-N `limit` parameter - rejected; the frontend slices the sorted list.
3. **Money serialization**: a small `MoneyStr` annotated type (`schemas/types.py`) serializing a `Decimal` as a two-place string, used by the new schemas. Existing schemas keep their own serializers for now (no churn in tested code); they can migrate later.
4. **List: filter in SQL, the rest in Python.** SQL applies owner, `is_active`, `billing_cycle`. Search (`q`), sorting and paging run in Python on that result. Reasons: SQLite `lower()`/`LIKE` are ASCII-only (Cyrillic would fail in tests), `%`/`_` escaping is avoided, and `charge_date`/`monthly_cost` sort keys are computed, not stored. Alternative: `ILIKE` and SQL `ORDER BY` - rejected for those reasons. Trade-off: loads all of one user's matching rows per request; acceptable for a personal tracker (tens to hundreds of rows) and documented in SPEC.md.
5. **Search semantics**: strip `q`, `casefold()` both sides, substring match on `name` or `note`; blank `q` is ignored; max 100 characters validated at the edge.
6. **Sorting**: `sort` in `id|name|amount|monthly_cost|charge_date`, `order` in `asc|desc`. Implemented as: sort by `id` ascending, then one stable sort by the key (reverse for `desc`), so ties always fall back to `id` ascending. Items with no `charge_date` (inactive) are separated and appended last in both orders. Names use `casefold()` keys. Paging slices after sorting.
7. **List item**: `SubscriptionListItem` extends `SubscriptionRead` with `monthly_cost`, `charge_date`, `days_until`; built by a service function from the ORM row and `today`. `charge_date` is `first_on_or_after(next_billing_date, ...)` for active rows, null for inactive. Only the list returns it; adding it to get/create/patch would need `today` everywhere and the frontend does not need it there.
8. **Router stays thin**: query parameters use enums/`Literal` types so invalid values are 422 automatically; the router passes a small `SubscriptionListQuery` dataclass to the service. `/api/stats/breakdown` lives in the existing stats router.
9. **No migration**; no new dependencies.

## Risks / Trade-offs

- [Python-side sort/page does not scale to very large lists] -> Fine for the target audience; revisit with SQL ordering (and PostgreSQL `unaccent`/`ILIKE`) if lists grow.
- [Shares may not sum to exactly 100.00] -> Documented in the spec; the UI can display them rounded.
- [List responses are larger] -> Three extra small fields per item; additive and backward compatible.
- [Sorting by `amount` mixes cycles] -> Provided intentionally for "as billed"; `monthly_cost` is the comparable sort and is the one the UI should default to for cost.
- [UTC "today"] -> Same known limitation as upcoming charges (SPEC.md section 6).
