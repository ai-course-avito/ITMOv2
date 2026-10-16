# Tasks

## 1. Shared cost computation and summary coverage

- [x] 1.1 Add `schemas/types.py` (`MoneyStr`) and `active_monthly_costs` in `services/stats.py`, make `get_stats_summary` use it; verify all existing stats tests still pass unchanged
- [x] 1.2 Add summary tests for every `spending-stats` summary/monthly-cost scenario not yet covered (weekly 6.00 -> 26.00, custom 19.90/90 -> 6.63, empty, inactive and foreign ignored, 401); verify they pass

## 2. Breakdown endpoint

- [x] 2.1 Add breakdown schemas and `get_stats_breakdown` (by subscription, by cycle, shares half-up, zero-total guard); verify service tests for ordering, grouping of custom intervals, share values, empty and rounds-to-zero cases
- [x] 2.2 Add `GET /api/stats/breakdown` to the stats router; verify API tests: ordering, `monthly_total` and each list's sum equal the summary, inactive excluded, isolation between two real users, 401

## 3. List search, filter, sort, computed fields

- [x] 3.1 Add `SubscriptionListItem`, enums for `sort`/`order`, and `list_subscriptions` v2 (SQL filters, Python search/sort/page, computed `monthly_cost`/`charge_date`/`days_until`); verify service tests for casefold and Cyrillic search, literal `%`, note search, stable sort with id tiebreak, descending order, nulls last, paging after sorting
- [x] 3.2 Wire query params in the router (`q` max 100, `billing_cycle`, `sort`, `order`) using `get_today`; verify API tests for each new spec scenario, default order still by id, 422 cases, and that a stale stored `next_billing_date` is rolled forward in the response without being changed in the database
- [x] 3.3 Verify backward compatibility: existing subscription API tests pass unchanged and create/get/patch responses contain no new fields

## 4. Docs and integration

- [x] 4.1 Update `SPEC.md` (API section for breakdown, list options and computed fields, scalability note; replace the "needed from backend" list with what is implemented); verify every endpoint and query parameter in `/openapi.json` appears in the document
- [x] 4.2 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`; verify all green
- [x] 4.3 End-to-end on local Postgres via `./scripts/dev.sh --seed`: breakdown for the demo user, list with `q`, `sort=charge_date`, `billing_cycle`, Cyrillic search; verify expected values (breakdown total equals the summary)
