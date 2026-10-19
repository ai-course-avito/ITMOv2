## ADDED Requirements

### Requirement: UI availability
The service SHALL serve a static UI under `/ui/` and redirect `/` to `/ui/`.

#### Scenario: Redirect
- WHEN a client requests GET `/`
- THEN the server responds 307/302 to `/ui/`

#### Scenario: UI index
- WHEN a client requests GET `/ui/`
- THEN the server responds 200 with HTML containing "Coffee Shop"

### Requirement: Health display
The UI SHALL display current health and readiness fetched from backend endpoints.

#### Scenario: Health OK
- WHEN `/health` returns `{ "status": "ok" }`
- THEN the UI shows `Health: ok` with a positive visual style
