# Spec Delta

## Purpose

Lets an authenticated user keep an accurate list of their own paid subscriptions, with validated money and billing data, so spending can be computed and reminders produced.

## ADDED Requirements

### Requirement: Create a subscription
The system SHALL let an authenticated user create a subscription via `POST /api/subscriptions` with `name`, `amount`, `billing_cycle`, optional `custom_interval_days`, `start_date`, optional `next_billing_date`, optional `note`, and optional `is_active` (default true). The subscription MUST belong to the caller.

#### Scenario: Successful creation
- **WHEN** a user posts a valid subscription
- **THEN** the system responds 201 with the stored subscription including its `id`, and it appears in that user's list

#### Scenario: Next billing date omitted
- **WHEN** `next_billing_date` is not provided
- **THEN** the system sets it to the first billing date on or after today, counted from `start_date` by the billing cycle

#### Scenario: Unauthenticated
- **WHEN** the request has no valid access token
- **THEN** the system responds 401

### Requirement: Subscription field validation
The system SHALL reject invalid subscriptions with 422. `name` MUST be 1 to 255 characters; `amount` MUST be greater than 0, at most two decimal places and below 100000000; `billing_cycle` MUST be one of `monthly`, `yearly`, `weekly`, `custom_days`; `note` MUST be at most 500 characters.

#### Scenario: Non-positive amount
- **WHEN** `amount` is 0 or negative
- **THEN** the system responds 422

#### Scenario: Too many decimals
- **WHEN** `amount` has more than two decimal places
- **THEN** the system responds 422

#### Scenario: Unknown billing cycle
- **WHEN** `billing_cycle` is not one of the allowed values
- **THEN** the system responds 422

#### Scenario: Next billing date before start date
- **WHEN** `next_billing_date` is earlier than `start_date`
- **THEN** the system responds 422

### Requirement: Custom interval rules
For `billing_cycle` equal to `custom_days` the system SHALL require `custom_interval_days` as a positive integer. For every other cycle `custom_interval_days` MUST NOT be provided.

#### Scenario: Custom cycle without interval
- **WHEN** a subscription with `custom_days` has no `custom_interval_days`
- **THEN** the system responds 422

#### Scenario: Interval on a non-custom cycle
- **WHEN** a `monthly` subscription includes `custom_interval_days`
- **THEN** the system responds 422

### Requirement: Money precision
Amounts SHALL be stored and returned without floating-point error. Responses MUST serialize `amount` as a decimal string with two decimal places.

#### Scenario: Exact amount
- **WHEN** a subscription with amount `10.10` is created and read back
- **THEN** the response `amount` is exactly `"10.10"`

### Requirement: List and read subscriptions
The system SHALL return only the caller's subscriptions from `GET /api/subscriptions`, ordered by `id`, with an optional `is_active` filter and `limit` (default 100, maximum 500) and `offset` paging. `GET /api/subscriptions/{id}` SHALL return one of the caller's subscriptions.

#### Scenario: List own only
- **WHEN** two users each have subscriptions and one of them lists
- **THEN** only that user's subscriptions are returned

#### Scenario: Active filter
- **WHEN** the list is requested with `is_active=true`
- **THEN** inactive subscriptions are not returned

#### Scenario: Unknown id
- **WHEN** a user requests a subscription id that does not exist
- **THEN** the system responds 404

### Requirement: Update a subscription
The system SHALL let a user partially update their own subscription via `PATCH /api/subscriptions/{id}`. The merged result MUST satisfy all validation rules. When `billing_cycle`, `custom_interval_days` or `start_date` changes and `next_billing_date` is not supplied, the system SHALL recompute `next_billing_date`; otherwise it MUST keep the stored value.

#### Scenario: Partial update
- **WHEN** a user patches only `amount`
- **THEN** the system responds 200 and all other fields keep their values

#### Scenario: Update makes record invalid
- **WHEN** a user patches `billing_cycle` to `custom_days` without any interval
- **THEN** the system responds 422 and the stored subscription is unchanged

#### Scenario: Cycle change recomputes date
- **WHEN** a user changes `billing_cycle` without supplying `next_billing_date`
- **THEN** `next_billing_date` is recomputed for the new cycle

### Requirement: Delete a subscription
The system SHALL let a user permanently delete their own subscription via `DELETE /api/subscriptions/{id}`.

#### Scenario: Successful delete
- **WHEN** a user deletes their subscription
- **THEN** the system responds 204 and a following read responds 404

### Requirement: Per-user isolation
The system MUST NOT reveal or change another user's subscriptions through any subscription endpoint. A subscription owned by someone else SHALL be indistinguishable from a missing one.

#### Scenario: Read someone else's subscription
- **WHEN** user B requests, updates or deletes a subscription owned by user A
- **THEN** the system responds 404 and user A's subscription is unchanged

#### Scenario: Owner cannot be set by the client
- **WHEN** a create or update request includes an `owner_id` or `id` field
- **THEN** the field is ignored and the subscription belongs to the caller

### Requirement: Free plan has no subscription limit
The system SHALL NOT limit how many subscriptions a free-plan user can create.

#### Scenario: Many subscriptions on free
- **WHEN** a free user creates more than 5 subscriptions
- **THEN** every creation succeeds with 201
