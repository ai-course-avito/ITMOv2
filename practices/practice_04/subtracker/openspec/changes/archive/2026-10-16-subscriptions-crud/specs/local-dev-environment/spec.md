# Spec Delta

## ADDED Requirements

### Requirement: Seed refuses production
The demo-data seed SHALL refuse to run when the application environment is `production`, because it creates an account with a publicly documented password.

#### Scenario: Production environment
- **WHEN** the seed is started with the environment setting equal to `production`
- **THEN** it exits with an error, creates nothing, and the dev script does not start the server

#### Scenario: Development environment
- **WHEN** the environment setting is `development` or unset
- **THEN** the seed runs as before
