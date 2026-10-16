# Spec Delta

## MODIFIED Requirements

### Requirement: List and read subscriptions
The system SHALL return only the caller's subscriptions from `GET /api/subscriptions`, with an optional `is_active` filter and `limit` (default 100, maximum 500) and `offset` paging. Unless a sort is requested, items are ordered by `id`. `GET /api/subscriptions/{id}` SHALL return one of the caller's subscriptions.

#### Scenario: List own only
- **WHEN** two users each have subscriptions and one of them lists
- **THEN** only that user's subscriptions are returned

#### Scenario: Active filter
- **WHEN** the list is requested with `is_active=true`
- **THEN** inactive subscriptions are not returned

#### Scenario: Default order
- **WHEN** the list is requested without `sort`
- **THEN** items are ordered by `id` ascending

#### Scenario: Unknown id
- **WHEN** a user requests a subscription id that does not exist
- **THEN** the system responds 404

## ADDED Requirements

### Requirement: Search subscriptions
The list SHALL accept `q` (at most 100 characters) and return only subscriptions whose name or note contains `q`, ignoring letter case and surrounding spaces, for Latin and Cyrillic text alike. Characters such as `%` and `_` MUST be matched literally. A blank `q` is ignored.

#### Scenario: Case-insensitive match
- **WHEN** the user searches `net` and has a subscription named "Netflix"
- **THEN** it is returned

#### Scenario: Cyrillic match
- **WHEN** the user searches `яндекс` and has a subscription named "Яндекс Плюс"
- **THEN** it is returned

#### Scenario: Note is searched
- **WHEN** the search text occurs only in a subscription's note
- **THEN** that subscription is returned

#### Scenario: Wildcards are literal
- **WHEN** the user searches `%`
- **THEN** only subscriptions containing a percent sign are returned

#### Scenario: Query too long
- **WHEN** `q` is longer than 100 characters
- **THEN** the system responds 422

### Requirement: Filter by billing cycle
The list SHALL accept `billing_cycle` and return only subscriptions with that cycle; an unknown value is rejected.

#### Scenario: Cycle filter
- **WHEN** the list is requested with `billing_cycle=yearly`
- **THEN** only yearly subscriptions are returned

#### Scenario: Unknown cycle
- **WHEN** `billing_cycle` is not an allowed value
- **THEN** the system responds 422

### Requirement: Sort the list
The list SHALL accept `sort` (`id`, `name`, `amount`, `monthly_cost`, `charge_date`) and `order` (`asc`, `desc`, default `asc`). Sorting MUST apply before paging, ties MUST be broken by `id` ascending, names compare ignoring letter case, and items without a `charge_date` come last in either order.

#### Scenario: Sort by name
- **WHEN** the list is requested with `sort=name`
- **THEN** names are in case-insensitive alphabetical order

#### Scenario: Sort by monthly cost descending
- **WHEN** the list is requested with `sort=monthly_cost&order=desc`
- **THEN** the most expensive monthly-equivalent subscription is first

#### Scenario: Sort by next charge
- **WHEN** the list is requested with `sort=charge_date`
- **THEN** the soonest real charge is first and inactive subscriptions are last

#### Scenario: Paging after sorting
- **WHEN** `sort=name&limit=2&offset=2` is requested
- **THEN** the third and fourth subscriptions in name order are returned

#### Scenario: Unknown sort field
- **WHEN** `sort` or `order` is not an allowed value
- **THEN** the system responds 422

### Requirement: Computed fields in list items
Each list item SHALL include `monthly_cost` (monthly-equivalent cost as a two-place decimal string), `charge_date` and `days_until`. For an active subscription `charge_date` is the first billing date on or after today counted from its stored `next_billing_date`, and `days_until` is the days from today to it. For an inactive subscription both are null. Other subscription responses are unchanged.

#### Scenario: Stale stored date
- **WHEN** an active monthly subscription's stored `next_billing_date` is in the past
- **THEN** its list item shows the next monthly occurrence as `charge_date` and the stored date is not modified

#### Scenario: Inactive subscription
- **WHEN** a subscription is inactive
- **THEN** its `charge_date` and `days_until` are null while `monthly_cost` is still present

#### Scenario: Monthly cost value
- **WHEN** a yearly subscription costs 120.00
- **THEN** its list item has `monthly_cost` "10.00"
