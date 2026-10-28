# Spec Delta

## Purpose

Показывает на одном экране, сколько пользователь тратит на подписки в месяц и в год, куда уходят деньги и какие списания ближайшие.

## ADDED Requirements

### Requirement: Spending totals
The Overview screen SHALL show the monthly total, the yearly total and the number of active subscriptions, taking the totals from the backend and showing them in the user's currency.

#### Scenario: Totals shown
- **WHEN** the user opens the Overview screen
- **THEN** it shows the monthly and yearly totals exactly as returned by the backend and the count of active subscriptions

#### Scenario: Paused subscriptions mentioned
- **WHEN** the user has paused subscriptions
- **THEN** the active-subscriptions card tells how many are paused

#### Scenario: No subscriptions
- **WHEN** the user has no subscriptions
- **THEN** the totals show zero and the screen invites the user to add the first subscription

### Requirement: Money is not computed in the browser
The web app SHALL display money amounts as strings returned by the backend and SHALL NOT sum or convert amounts itself.

#### Scenario: Amount formatting
- **WHEN** the backend returns `"15.49"`
- **THEN** the screen shows 15.49 with the currency symbol, without floating-point rounding

### Requirement: Spending breakdown chart
The Overview screen SHALL show a donut chart and a legend with the share of each active subscription in the monthly spend, in the order returned by the backend.

#### Scenario: Shares shown
- **WHEN** the backend returns a breakdown with several subscriptions
- **THEN** each subscription has a colored segment and a legend row with its name and share percent

#### Scenario: Chart is described for assistive technology
- **WHEN** a screen reader reads the chart
- **THEN** it finds a text description of the chart

#### Scenario: Zero total
- **WHEN** the monthly total is 0.00
- **THEN** the chart shows an empty ring and no legend rows

### Requirement: Top five most expensive
The Overview screen SHALL show the five subscriptions with the highest monthly cost as horizontal bars scaled to the most expensive one.

#### Scenario: Top five
- **WHEN** the user has more than five active subscriptions
- **THEN** only the five most expensive are shown, the first with a full-width bar

### Requirement: Upcoming charges
The Overview screen SHALL list upcoming charges for the next 7 or 30 days, selectable by the user, with the name, the date, the amount and how soon it is charged.

#### Scenario: Default period
- **WHEN** the user opens the Overview screen
- **THEN** the list shows charges for the period selected by default and is sorted by date

#### Scenario: Changing the period
- **WHEN** the user switches between 7 and 30 days
- **THEN** the list is reloaded for the chosen period

#### Scenario: Nothing upcoming
- **WHEN** there are no charges in the chosen period
- **THEN** the list shows a message instead of empty space

### Requirement: Loading and error states
The Overview screen SHALL show a loading state while data is requested and an error state with a retry action when the backend is unreachable.

#### Scenario: Backend unreachable
- **WHEN** a request fails with a network error
- **THEN** the screen shows an error message and a retry button, and no stale numbers
