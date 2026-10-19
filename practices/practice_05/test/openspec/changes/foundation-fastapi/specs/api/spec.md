## ADDED Requirements

### Requirement: Health endpoints
The service SHALL expose `GET /health` and `GET /ready`.

#### Scenario: Health OK
- WHEN a client requests GET /health
- THEN the API responds 200 with JSON `{ "status": "ok" }`

#### Scenario: Ready OK
- WHEN a client requests GET /ready
- THEN the API responds 200

### Requirement: API namespace
The service SHALL reserve `/api` and implement `/api/v1` for public endpoints.

#### Scenario: Namespaces respond without 5xx
- WHEN a client requests GET /api
- THEN the API responds 200 or 404 but not 5xx
