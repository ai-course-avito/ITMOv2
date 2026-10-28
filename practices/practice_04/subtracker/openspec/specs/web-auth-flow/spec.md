# web-auth-flow Specification

## Purpose
Позволяет человеку создать аккаунт и войти из браузера, сохраняет сессию между перезагрузками и не пускает неавторизованных на экраны с данными.

## Requirements

### Requirement: Login form
The web app SHALL provide a login form with email and password that signs the user in through the backend and opens the Overview screen.

#### Scenario: Successful login
- **WHEN** the user submits a registered email and the correct password
- **THEN** the app stores the session and shows the Overview screen

#### Scenario: Wrong credentials
- **WHEN** the backend answers 401 to the login request
- **THEN** the app stays on the form and shows an error message in the selected language, without revealing whether the email exists

### Requirement: Registration form
The web app SHALL provide a registration form on the same page, switchable with the login form, and SHALL sign the user in after a successful registration.

#### Scenario: Successful registration
- **WHEN** the user submits a new email and a password of at least 8 characters
- **THEN** the app creates the account, signs the user in and shows the Overview screen

#### Scenario: Email already taken
- **WHEN** the backend answers 409 to the registration request
- **THEN** the app shows a message that the email is already registered

#### Scenario: Invalid input
- **WHEN** the email is malformed or the password is shorter than 8 characters
- **THEN** the app shows a field-level message and does not call the backend for registration

### Requirement: Session persistence
The web app SHALL keep the session in the browser so that a page reload does not sign the user out, and SHALL renew the access token with the refresh token when the backend answers 401 to an authorized request.

#### Scenario: Reload keeps the session
- **WHEN** a signed-in user reloads the page
- **THEN** the app stays signed in and shows the same screen

#### Scenario: Access token expired
- **WHEN** an authorized request gets 401 and the refresh token is valid
- **THEN** the app obtains a new access token and repeats the request once without bothering the user

#### Scenario: Refresh token expired
- **WHEN** the refresh request also fails with 401
- **THEN** the app clears the session and shows the login form

### Requirement: Protected screens
The web app SHALL show the Overview and Subscriptions screens only to a signed-in user.

#### Scenario: Not signed in
- **WHEN** an anonymous visitor opens the Overview or Subscriptions address
- **THEN** the app redirects to the login form

#### Scenario: Signed in on the login page
- **WHEN** a signed-in user opens the login address
- **THEN** the app redirects to the Overview screen

### Requirement: Sign out
The web app SHALL let a signed-in user sign out and SHALL remove the stored session.

#### Scenario: Sign out
- **WHEN** the user chooses to sign out
- **THEN** the stored tokens are removed and the login form is shown
