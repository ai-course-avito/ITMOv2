---
name: sync-omnixon-lib
description: Use when a route, a query/path parameter, or a request/response model of omnixon-backend was added, changed or removed, when omnixon-library's contract test fails, or before releasing omnixon-lib - anything that may leave the Python client behind the service.
---

# Sync omnixon-library with omnixon-backend

## Overview

The library must offer every route of the service with the same models. Its contract test
(`tests/test_server_contract.py`) compares **models only**: a new route, a new query parameter or a
changed answer type passes it unnoticed. `scripts/check_sync.py` closes that gap: it dumps the
service's OpenAPI schema and reports, against the library's snapshot and `omnixon/main.py`, every
changed route, parameter and model, and every route the client does not call.

**Done = `check_sync.py` prints `RESULT: in sync` and `uv run pytest` passes in omnixon-library.**
Green tests alone are not done.

## Steps

1. From the folder holding both repositories:
   `python3 .claude/skills/sync-omnixon-lib/scripts/check_sync.py` (read-only; exit 1 = work to do,
   2 = the backend does not import: fix that first). Copy the report into your notes or a todo
   list NOW: it is the to-do list, and after step 2 the parameter and model changes are no longer
   shown (they are found against the old snapshot; afterwards only uncalled routes are checked).
2. `python3 .claude/skills/sync-omnixon-lib/scripts/check_sync.py --write` replaces
   `omnixon-library/tests/server_openapi.json` (never edit the snapshot by hand).
3. Work through every line of the report in `omnixon-library` (table below).
4. `uv run pytest` in omnixon-library, then step 1 again until `in sync`. Then
   `uv run --group test pytest` in omnixon-mcp: its tools are written by hand and its contract test reads the same snapshot, so **a new route
   needs a tool** (or an entry in `LEFT_OUT` of `tests/test_contract.py` with the reason), and a route whose role changed to admin goes into
   `ADMIN_ONLY` in `omnixon-mcp/src/omnixon_mcp/access.py` (and the tool's `role` follows).
5. Bump the version: `uv version X.Y.Z` (additive = minor, removed/renamed/now required = major).
6. Report what changed and how it was verified. Do not commit unless the user asks; never push.

## What each report line means in the library

| Report line | Change in omnixon-library |
|---|---|
| `NEW ROUTE` / `NOT CALLED BY THE CLIENT` | A method in `omnixon/main.py`, next to its siblings, through `async with self._session() as client:`, user ids as `_q(user_id)`, `_raise_for_status(r)`, typed return. A test in `tests/test_client.py` asserting method, path and exact JSON body. A line in `README.md`. |
| `CHANGED ROUTE` `+ query:x` | A keyword argument of the method, sent in `params=` only when given (or with the service's default). Test the query string. |
| `CHANGED ROUTE` `~ body` / `~ answer` | The model the method sends / parses. |
| `NEW MODEL` | Class in `omnixon/schemes.py`, exported in `omnixon/__init__.py`, added to `MODELS` in the contract test. |
| `CHANGED MODEL` `+`/`-`/`~` field | Same field, type and required-ness in `schemes.py` (`string?` = `Optional[str]`, `(optional)` = has a default). Precise on purpose? Add to `KNOWN_DIFFERENCES` with a comment why. |
| `REMOVED ...` | Remove the method/field and its tests and README text; major version. |
| `CLIENT CALLS A ROUTE THE SERVICE DOES NOT HAVE` | The client is wrong or the route was renamed: fix the path. |

## Common mistakes

- Stopping when `pytest` is green: routes and parameters are not in the contract test.
- Building `httpx.AsyncClient` in a method instead of `self._session()`.
- "Simplifying" `model_dump(exclude_unset=True)` in `create_agent`/`update_agent`: an explicit `None` resets a config key on the service.
- Forgetting `README.md` (it lists every method) or the `__init__.py` export.
- A route the client should never call (ops endpoints): add it to `IGNORED_ROUTES` in the script with a reason, do not leave the report red.

The admin panel (`omnixon-frontend/src/lib/api.ts`, `types.ts`) follows the same API but is not
checked by this skill: mention it to the user when routes changed.
