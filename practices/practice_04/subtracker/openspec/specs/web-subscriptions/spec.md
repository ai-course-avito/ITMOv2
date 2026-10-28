# web-subscriptions Specification

## Purpose
Даёт пользователю управлять списком своих подписок: находить, фильтровать и сортировать их, добавлять, править, приостанавливать и удалять.

## Requirements

### Requirement: Subscription list
The Subscriptions screen SHALL list the user's subscriptions with name, note, next charge date and how soon it is charged, billing cycle with the payment amount, and monthly cost.

#### Scenario: List shown
- **WHEN** the user opens the Subscriptions screen
- **THEN** every subscription is shown with the fields above, using the computed values returned by the backend

#### Scenario: Empty list
- **WHEN** the user has no subscriptions
- **THEN** the screen shows an empty state with an action to add the first one

### Requirement: Grouping by time to charge
The list SHALL group active subscriptions by days until the next charge into "Today", "This week", "This month" and "Later", followed by a group of paused subscriptions, and SHALL omit empty groups.

#### Scenario: Group boundaries
- **WHEN** subscriptions have 0, 2, 25 and 120 days until charge
- **THEN** they appear in the groups Today, This week, This month and Later respectively

#### Scenario: Paused group
- **WHEN** a subscription is inactive
- **THEN** it appears in the paused group, dimmed, with no charge date

### Requirement: Search, filter and sort
The Subscriptions screen SHALL let the user search by name or note, filter by active or paused state and by billing cycle, and sort by next charge, amount, monthly cost or name, and SHALL pass these choices to the backend list endpoint.

#### Scenario: Search
- **WHEN** the user types in the search field
- **THEN** after a short pause the list shows only matching subscriptions

#### Scenario: Filters combine
- **WHEN** the user selects "Active" and the cycle "Year"
- **THEN** only active yearly subscriptions are shown

#### Scenario: Default sort
- **WHEN** the user has not chosen a sort
- **THEN** the list is sorted by the nearest charge date

### Requirement: List and card views
The Subscriptions screen SHALL offer a switch between a list view and a card view of the same data, and SHALL remember the choice in the browser.

#### Scenario: Switching view
- **WHEN** the user selects the card view and reloads the page
- **THEN** the cards are still shown

### Requirement: Add a subscription
The web app SHALL provide a form to add a subscription with name, amount, start date, billing cycle, optional custom interval in days, optional note and active flag, shown in a side panel on wide screens and in a bottom sheet on phones.

#### Scenario: Successful add
- **WHEN** the user fills in valid values and saves
- **THEN** the panel closes and the new subscription appears in the list and in the totals

#### Scenario: Custom interval field
- **WHEN** the user selects the billing cycle "Custom"
- **THEN** a field for the number of days (1 to 3650) appears, and it is hidden for other cycles

#### Scenario: Backend validation error
- **WHEN** the backend answers 422
- **THEN** the panel stays open and shows the error next to the affected field

#### Scenario: Cancel
- **WHEN** the user closes the panel without saving
- **THEN** nothing is created

### Requirement: Edit, pause and delete
The web app SHALL let the user edit a subscription in the same panel, pause or resume it, and delete it after an explicit confirmation.

#### Scenario: Edit
- **WHEN** the user opens the actions menu of a subscription and chooses edit
- **THEN** the panel opens filled with its values and saving updates the list

#### Scenario: Pause and resume
- **WHEN** the user pauses an active subscription
- **THEN** it moves to the paused group and no longer counts in the totals

#### Scenario: Delete needs confirmation
- **WHEN** the user chooses delete and confirms
- **THEN** the subscription disappears from the list and the totals

#### Scenario: Delete declined
- **WHEN** the user chooses delete and cancels the confirmation
- **THEN** the subscription stays

### Requirement: Pro calendar is locked
The navigation SHALL show the Calendar tab with a lock and a Pro label, and SHALL NOT open a screen for it.

#### Scenario: Locked tab
- **WHEN** the user activates the Calendar tab
- **THEN** nothing navigates and the tab is announced as unavailable on the current plan
