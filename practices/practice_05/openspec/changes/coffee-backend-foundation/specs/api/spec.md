## ADDED Requirements

### Requirement: Health endpoints
The service SHALL expose `GET /health` returning 200 and `GET /ready` returning 200 when dependencies are OK.

#### Scenario: Health OK
- WHEN a client requests GET /health
- THEN the API responds 200 with a small JSON payload `{ "status": "ok" }`

#### Scenario: Readiness OK
- WHEN a client requests GET /ready
- THEN the API responds 200

### Requirement: API namespace
The API SHALL serve under `/api` and reserve `/api/v1` for the first public version.

#### Scenario: Namespace exists
- WHEN a client requests GET /api
- THEN the server responds 200 or 404 but not 5xx

### Requirement: User routes (stubs)
The service SHALL define stub routes for user registration and login without real persistence.

#### Scenario: Register stub
- WHEN a client POSTs to /api/v1/users/register with minimal JSON
- THEN the API responds 201 with a stub user id

#### Scenario: Login stub
- WHEN a client POSTs to /api/v1/users/login with valid-looking credentials
- THEN the API responds 200 with a stub token
