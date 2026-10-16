# Spec Delta

## Purpose

Lets a person create an account, sign in, and keep a session via short-lived access tokens and refresh tokens, so that protected endpoints can identify the current user.

## ADDED Requirements

### Requirement: User registration
The system SHALL allow registering with an email and a password via `POST /api/auth/register`, storing only a hash of the password. Emails MUST be unique case-insensitively and passwords MUST be at least 8 characters.

#### Scenario: Successful registration
- **WHEN** a client posts a valid new email and a password of 8+ characters
- **THEN** the system responds 201 with the user id, email and plan, and the response never contains the password or its hash

#### Scenario: Duplicate email
- **WHEN** a client registers an email that already exists (in any letter case)
- **THEN** the system responds 409

#### Scenario: Invalid input
- **WHEN** the email is malformed or the password is shorter than 8 characters
- **THEN** the system responds 422

### Requirement: User login
The system SHALL issue an access token and a refresh token via `POST /api/auth/login` for correct credentials.

#### Scenario: Successful login
- **WHEN** a client posts a registered email and the correct password
- **THEN** the system responds 200 with `access_token`, `refresh_token`, and `token_type` equal to `bearer`

#### Scenario: Wrong credentials
- **WHEN** the password is wrong or the email is unknown
- **THEN** the system responds 401 with the same message in both cases

### Requirement: Token expiry and type
Every issued token SHALL carry an expiry and a type (`access` or `refresh`). Access tokens MUST be short-lived and refresh tokens longer-lived, with lifetimes configurable.

#### Scenario: Expired token rejected
- **WHEN** a protected endpoint receives an access token whose expiry has passed
- **THEN** the system responds 401

#### Scenario: Token without expiry rejected
- **WHEN** a protected endpoint receives a validly signed token that has no expiry
- **THEN** the system responds 401

#### Scenario: Refresh token is not an access token
- **WHEN** a refresh token is used as a Bearer token on a protected endpoint
- **THEN** the system responds 401

### Requirement: Token refresh
The system SHALL issue a new access token via `POST /api/auth/refresh` when given a valid refresh token.

#### Scenario: Successful refresh
- **WHEN** a client posts a valid, unexpired refresh token of an existing user
- **THEN** the system responds 200 with a new access token

#### Scenario: Access token used for refresh
- **WHEN** a client posts an access token to the refresh endpoint
- **THEN** the system responds 401

### Requirement: Protected endpoints require authentication
Protected endpoints SHALL respond 401 when the Bearer token is missing, malformed, or refers to a user that no longer exists.

#### Scenario: Missing token
- **WHEN** a request to `/api/stats/summary` has no Authorization header
- **THEN** the system responds 401

#### Scenario: Valid token
- **WHEN** a request carries a valid access token
- **THEN** the endpoint acts as that user and returns only that user's data

### Requirement: Account plan
Every user SHALL have a plan, `free` or `pro`, which is `free` on registration. `GET /api/auth/me` SHALL return the authenticated user's id, email, plan, and default currency. Free accounts MUST NOT be limited in the number of subscriptions.

#### Scenario: New user is free
- **WHEN** a user registers and then requests `/api/auth/me`
- **THEN** the response contains `plan` equal to `free`

#### Scenario: Pro user
- **WHEN** a user whose plan was set to `pro` requests `/api/auth/me`
- **THEN** the response contains `plan` equal to `pro`

#### Scenario: /me requires authentication
- **WHEN** `/api/auth/me` is requested without a valid access token
- **THEN** the system responds 401

### Requirement: Mandatory signing secret
The system MUST refuse to start when no signing secret is configured; it SHALL NOT fall back to a built-in default.

#### Scenario: Secret missing
- **WHEN** the application starts without `SECRET_KEY`
- **THEN** startup fails with an error naming the missing setting
