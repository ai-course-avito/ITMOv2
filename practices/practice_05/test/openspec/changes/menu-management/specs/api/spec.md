## ADDED Requirements

### Requirement: List menu items
The API SHALL return a list of menu items at `GET /api/v1/menu`.

#### Scenario: Empty list initially
- WHEN a client requests GET `/api/v1/menu`
- THEN the API responds 200 with `[]`

### Requirement: Create menu item
The API SHALL create a menu item via `POST /api/v1/menu`.

#### Scenario: Valid create
- WHEN a client POSTs valid JSON `{ name, ingredients, sizes, priceCoffeeCoin }`
- THEN the API responds 201 with the created item including an integer `id`

### Requirement: Read/Update/Delete by id
The API SHALL support GET/PUT/DELETE `/api/v1/menu/{id}`.

#### Scenario: Read existing
- WHEN a client GETs `/api/v1/menu/{id}` for an existing item
- THEN the API responds 200 with the item

#### Scenario: Update existing
- WHEN a client PUTs updated JSON for an existing item
- THEN the API responds 200 with the updated item

#### Scenario: Delete existing
- WHEN a client DELETEs `/api/v1/menu/{id}`
- THEN the API responds 204 and subsequent GET responds 404
