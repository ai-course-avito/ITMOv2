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
