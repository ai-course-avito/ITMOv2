# database-migrations Specification

## Purpose

Ensures the database schema is created and evolved only through versioned migrations, so any environment can reach the same schema reproducibly.

## Requirements

### Requirement: Schema created by migrations
Applying all migrations to an empty PostgreSQL database SHALL create every table the application models require (`users`, `subscriptions`) with their constraints.

#### Scenario: Fresh database
- **WHEN** `alembic upgrade head` runs against an empty database
- **THEN** the `users` and `subscriptions` tables exist with a unique constraint on user email, a `plan` column on users defaulting to `free`, and a foreign key from subscriptions to users

#### Scenario: Re-running is safe
- **WHEN** `alembic upgrade head` runs on an already up-to-date database
- **THEN** it completes without error and changes nothing

### Requirement: Migrations match models
The migrations SHALL be in sync with the application models; autogenerating a new revision after the initial one MUST produce no schema changes.

#### Scenario: No drift
- **WHEN** an autogenerate comparison runs after `alembic upgrade head`
- **THEN** it reports no differences

### Requirement: Reversible initial migration
The initial migration SHALL be reversible.

#### Scenario: Downgrade
- **WHEN** `alembic downgrade base` runs after `upgrade head`
- **THEN** the application tables are removed

### Requirement: Subscription rules enforced by the database
The schema SHALL enforce subscription data rules independently of the API: `amount` greater than 0, `billing_cycle` among the allowed values, and `custom_interval_days` between 1 and 3650 exactly when `billing_cycle` is `custom_days` and absent otherwise, and dates within 2000-01-01 to 2100-12-31.

#### Scenario: Invalid row rejected
- **WHEN** a row with a non-positive amount, an unknown cycle, or a `monthly` cycle with an interval is inserted directly into the database
- **THEN** the insert fails with a constraint violation

#### Scenario: Out-of-range values rejected
- **WHEN** a row with `custom_interval_days` above 3650, or a start or next billing date outside 2000-01-01 to 2100-12-31, is inserted directly
- **THEN** the insert fails with a constraint violation

#### Scenario: Existing data survives upgrade
- **WHEN** the new migration runs on a database that already contains subscriptions created by the seed script
- **THEN** it completes and those rows remain, with `start_date` and `next_billing_date` filled in

#### Scenario: Migration is reversible
- **WHEN** the new migration is downgraded
- **THEN** the added columns and constraints are removed and previous data remains
