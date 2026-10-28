# web-appearance Specification

## Purpose
Определяет внешний вид и настройки интерфейса: тему, язык, адаптивность под телефон и рекламный блок для бесплатного плана.

## Requirements

### Requirement: Theme
The web app SHALL provide a dark and a light theme, SHALL use the dark theme when the user has not chosen one, and SHALL remember the choice in the browser.

#### Scenario: First visit
- **WHEN** a user opens the app for the first time
- **THEN** the dark theme is shown regardless of the system setting

#### Scenario: Switching theme
- **WHEN** the user presses the theme switch
- **THEN** all screens change theme immediately and the choice survives a reload

### Requirement: Language
The web app SHALL provide Russian and English interfaces with a switch, SHALL take every interface text from a translation dictionary, and SHALL remember the choice in the browser.

#### Scenario: Switching language
- **WHEN** the user switches from RU to EN
- **THEN** all interface texts, dates and amounts change language without a reload

#### Scenario: Complete dictionaries
- **WHEN** the dictionaries are compared
- **THEN** both languages contain exactly the same keys

#### Scenario: Backend messages
- **WHEN** the backend returns an error
- **THEN** the user sees a message in the selected language, not the raw backend text

### Requirement: Responsive layout
The web app SHALL work from a phone width of 360 px to a desktop width of 1440 px without horizontal page scroll, with the layouts shown in the mockups for phone and desktop.

#### Scenario: Phone width
- **WHEN** the screen is narrower than 768 px
- **THEN** the overview and the list use the single-column phone layout and the add form opens as a bottom sheet

#### Scenario: Desktop width
- **WHEN** the screen is 1280 px wide
- **THEN** the overview shows three summary cards in a row and the add form opens as a side panel

### Requirement: Accessible controls
The web app SHALL use real buttons, links and labelled inputs for interactive elements, SHALL give icon-only buttons a text label, and SHALL close the side panel and bottom sheet with the Escape key.

#### Scenario: Keyboard
- **WHEN** the user opens the add panel and presses Escape
- **THEN** the panel closes and focus returns to the control that opened it

### Requirement: Ad placeholder for the Free plan
The web app SHALL show an ad placeholder banner for users on the Free plan and SHALL NOT show it for users on the Pro plan.

#### Scenario: Free plan
- **WHEN** the signed-in user has the plan `free`
- **THEN** the banner is shown on the Overview and Subscriptions screens

#### Scenario: Pro plan
- **WHEN** the signed-in user has the plan `pro`
- **THEN** no banner is shown

### Requirement: Backend address
The web app SHALL read the backend address from a build-time setting and SHALL default to `http://localhost:8000`.

#### Scenario: Default address
- **WHEN** no address is configured
- **THEN** requests go to `http://localhost:8000`
