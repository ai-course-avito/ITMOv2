# Spec Delta

## ADDED Requirements

### Requirement: Subscription rules enforced by the database
The schema SHALL enforce subscription data rules independently of the API: `amount` greater than 0, `billing_cycle` among the allowed values, and `custom_interval_days` positive exactly when `billing_cycle` is `custom_days` and absent otherwise.

#### Scenario: Invalid row rejected
- **WHEN** a row with a non-positive amount, an unknown cycle, or a `monthly` cycle with an interval is inserted directly into the database
- **THEN** the insert fails with a constraint violation

#### Scenario: Existing data survives upgrade
- **WHEN** the new migration runs on a database that already contains subscriptions created by the seed script
- **THEN** it completes and those rows remain, with `start_date` and `next_billing_date` filled in

#### Scenario: Migration is reversible
- **WHEN** the new migration is downgraded
- **THEN** the added columns and constraints are removed and previous data remains
