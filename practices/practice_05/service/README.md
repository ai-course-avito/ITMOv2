# Subscription Service (Service)

## Search API

- GET /search/users
  - Headers: `X-Auth-User: <any>` (required)
  - Query params:
    - `q` (string, required, 2..100 chars)
    - `page` (int, default 1)
    - `page_size` (int, default 20, max 50)
  - Response:
    - `page`, `page_size`, `total`
    - `items`: list of objects with fields: `id`, `username`, `display_name`, `status`
  - Notes:
    - Case-insensitive substring match over `username`
    - Results sorted by `username` asc, then by `id`

### Examples

```bash
curl -H 'X-Auth-User: demo' 'http://localhost:8000/search/users?q=iv&page=1&page_size=20'
```
