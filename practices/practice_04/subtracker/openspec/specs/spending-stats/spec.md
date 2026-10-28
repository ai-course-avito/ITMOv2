# spending-stats Specification

## Purpose

Shows a user how much their active subscriptions cost per month and per year, and where that money goes, so they can see spending at a glance and spot the expensive items.

## Requirements

### Requirement: Spending summary
`GET /api/stats/summary` SHALL return `monthly_total`, `yearly_total` and `currency` for the caller's active subscriptions. `monthly_total` is the sum of each subscription's monthly-equivalent cost; `yearly_total` is `monthly_total` times 12. Money is returned as decimal strings with two places.

#### Scenario: Totals for mixed cycles
- **WHEN** a user has active monthly 9.99 and yearly 120.00 subscriptions
- **THEN** `monthly_total` is "19.99" and `yearly_total` is "239.88"

#### Scenario: No active subscriptions
- **WHEN** the user has no active subscriptions
- **THEN** both totals are "0.00" and the currency is the user's default currency

#### Scenario: Inactive and foreign subscriptions ignored
- **WHEN** the user has an inactive subscription and another user has active ones
- **THEN** neither contributes to the user's totals

### Requirement: Monthly-equivalent cost
A subscription's monthly-equivalent cost SHALL be its amount for `monthly`, amount divided by 12 for `yearly`, amount times 52 divided by 12 for `weekly`, and amount times 30 divided by the interval for `custom_days`, each rounded half-up to two places before summing.

#### Scenario: Yearly
- **WHEN** a yearly subscription costs 120.00
- **THEN** its monthly-equivalent cost is 10.00

#### Scenario: Weekly
- **WHEN** a weekly subscription costs 6.00
- **THEN** its monthly-equivalent cost is 26.00

#### Scenario: Custom interval
- **WHEN** a subscription costs 19.90 every 90 days
- **THEN** its monthly-equivalent cost is 6.63

### Requirement: Breakdown by subscription
`GET /api/stats/breakdown` SHALL return `by_subscription`: one item per active subscription of the caller with `id`, `name`, `billing_cycle`, `monthly_cost` and `share_percent`, ordered by `monthly_cost` descending and then by `name`.

#### Scenario: Ordered by cost
- **WHEN** a user has active subscriptions costing 5.00, 20.00 and 10.00 per month
- **THEN** `by_subscription` lists them as 20.00, 10.00, 5.00

#### Scenario: Share of total
- **WHEN** one of two active subscriptions costs 75.00 of a 100.00 monthly total
- **THEN** its `share_percent` is "75.00"

#### Scenario: Inactive excluded
- **WHEN** a subscription is inactive
- **THEN** it does not appear in the breakdown

### Requirement: Breakdown by billing cycle
The breakdown SHALL also return `by_cycle`: one item per billing cycle that has at least one active subscription, with `billing_cycle`, `subscription_count`, `monthly_cost` (sum for that cycle) and `share_percent`, ordered by `monthly_cost` descending and then by cycle name.

#### Scenario: Grouped by cycle
- **WHEN** a user has two monthly and one yearly active subscription
- **THEN** `by_cycle` has a `monthly` item with count 2 and a `yearly` item with count 1

#### Scenario: Custom intervals are one group
- **WHEN** subscriptions with different custom intervals exist
- **THEN** they are all counted under `custom_days`

### Requirement: Breakdown is consistent with the summary
The breakdown SHALL include `currency` and `monthly_total`, equal to the summary's values, and the monthly costs of `by_subscription` and of `by_cycle` MUST each add up to `monthly_total`. Shares MUST be rounded half-up to two places, so their sum may differ from 100 by rounding.

#### Scenario: Same total
- **WHEN** both endpoints are requested for the same data
- **THEN** `monthly_total` is identical and each list's costs sum to it

#### Scenario: Empty state
- **WHEN** the user has no active subscriptions
- **THEN** `by_subscription` and `by_cycle` are empty and `monthly_total` is "0.00"

#### Scenario: Total rounds to zero
- **WHEN** active subscriptions exist but every monthly cost rounds to 0.00
- **THEN** every `share_percent` is "0.00" and the request succeeds

### Requirement: Stats are private and authenticated
Both stats endpoints SHALL require a valid access token and MUST only use the caller's own subscriptions.

#### Scenario: No token
- **WHEN** either endpoint is requested without an access token
- **THEN** the system responds 401

#### Scenario: Another user's data
- **WHEN** two users have subscriptions
- **THEN** each user's breakdown contains only their own items
