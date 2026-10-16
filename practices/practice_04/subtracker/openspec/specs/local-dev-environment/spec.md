# local-dev-environment Specification

## Purpose

Lets the project owner run and evaluate the backend on their own machine without Docker, using a single documented command, with optional demo data.

## Requirements

### Requirement: One-command local start
The project SHALL provide a script that, with PostgreSQL and `.env` available, applies migrations and starts the backend on port 8000.

#### Scenario: Normal start
- **WHEN** the owner runs the dev script with PostgreSQL running
- **THEN** migrations are applied and the API answers on `http://localhost:8000` including `/docs`

#### Scenario: PostgreSQL unavailable
- **WHEN** the database cannot be reached
- **THEN** the script stops before starting the server and prints a message naming the unreachable `DATABASE_URL` host and port

### Requirement: Demo data seeding
The project SHALL provide an optional, idempotent seed that creates a demo user with sample subscriptions covering every billing cycle.

#### Scenario: Seed on empty database
- **WHEN** the seed runs on a migrated empty database
- **THEN** a demo user and sample subscriptions exist, and logging in as the demo user succeeds

#### Scenario: Seed run twice
- **WHEN** the seed runs a second time
- **THEN** no duplicate user or subscriptions are created

### Requirement: Health check
The system SHALL expose `GET /health` without authentication.

#### Scenario: Database reachable
- **WHEN** a client requests `/health` and the database responds
- **THEN** the system responds 200 with status `ok`

#### Scenario: Database unreachable
- **WHEN** a client requests `/health` and the database does not respond
- **THEN** the system responds 503

### Requirement: Browser access from the dev frontend
The system SHALL accept cross-origin requests from the configured frontend origins (default `http://localhost:5173`) and from no others.

#### Scenario: Allowed origin
- **WHEN** a preflight request comes from `http://localhost:5173`
- **THEN** the response allows the origin and the `Authorization` header

#### Scenario: Other origin
- **WHEN** a request comes from an origin not in the configured list
- **THEN** no CORS allow headers are returned
