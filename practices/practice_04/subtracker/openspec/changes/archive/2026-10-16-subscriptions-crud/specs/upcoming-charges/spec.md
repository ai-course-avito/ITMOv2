# Spec Delta

## Purpose

Tells a user which of their active subscriptions will be charged soon, as a simple on-screen reminder computed on request, without e-mail or background jobs.

## ADDED Requirements

### Requirement: Upcoming charges list
`GET /api/subscriptions/upcoming` SHALL return the caller's active subscriptions that are charged within the next `days` days (inclusive of today), where `days` defaults to 7 and MUST be between 1 and 365. Each item SHALL contain `id`, `name`, `amount`, `billing_cycle`, `charge_date` and `days_until`, sorted by `charge_date` and then `name`.

#### Scenario: Charge inside window
- **WHEN** an active subscription is charged in 3 days and `days` is 7
- **THEN** it is returned with `days_until` equal to 3

#### Scenario: Charge outside window
- **WHEN** an active subscription is charged in 10 days and `days` is 7
- **THEN** it is not returned

#### Scenario: Charge today
- **WHEN** a subscription is charged today
- **THEN** it is returned with `days_until` equal to 0

#### Scenario: Invalid window
- **WHEN** `days` is 0, 366 or not a number
- **THEN** the system responds 422

### Requirement: Only own active subscriptions
The upcoming list MUST contain only the caller's subscriptions and MUST exclude inactive ones.

#### Scenario: Inactive excluded
- **WHEN** a subscription with `is_active` false would be charged tomorrow
- **THEN** it is not returned

#### Scenario: Other users excluded
- **WHEN** another user has a subscription charged tomorrow
- **THEN** it is not returned to the caller

### Requirement: Charge date rolls forward
When a subscription's stored `next_billing_date` is in the past, the system SHALL compute `charge_date` as the first date on or after today in the sequence that starts at `next_billing_date` and repeats by the billing cycle. The system MUST NOT modify stored data while answering this request.

#### Scenario: Past date rolled forward monthly
- **WHEN** a monthly subscription has `next_billing_date` 40 days ago
- **THEN** `charge_date` is the next monthly occurrence on or after today

#### Scenario: Read has no side effects
- **WHEN** the upcoming list is requested
- **THEN** the stored `next_billing_date` values are unchanged

### Requirement: Billing cycle date arithmetic
Date steps SHALL be: `weekly` 7 days, `custom_days` the interval in days, `monthly` one calendar month, `yearly` one calendar year. For monthly and yearly steps, when the target month has no such day, the charge date SHALL be the last day of that month, and each occurrence MUST be counted from the original `next_billing_date` so the day of month does not drift.

#### Scenario: Month-end clamp
- **WHEN** a monthly subscription's anchor date is January 31
- **THEN** its February occurrence is the last day of February and its March occurrence is March 31

#### Scenario: Leap-day yearly
- **WHEN** a yearly subscription's anchor date is February 29
- **THEN** in a non-leap year its occurrence is February 28
