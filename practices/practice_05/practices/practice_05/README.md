Practice 05 — Subscription Service and Server-Backed Username Search

Overview

- Minimal subscription service with a static UI and two backend implementations:
  - stdlib HTTP server (default entry point, single-file)
  - FastAPI app (alternative backend used for tests and parity)
- One cross-cutting feature implemented on both sides (backend and UI): server-backed search by username among a user’s subscribers.
- Specs were authored and converged using an SDD workflow with GitHub SpecKit.

How To Run

- Start server and UI:
  - make -C practices/practice_05 run
  - open http://localhost:8000/

Feature: Username Search (Subscribers Only)

- Scope: search only among the current user’s subscribers
- Match field: username (case-insensitive substring)
- Query length: 2..100 (trim applied)
- Pagination: page/page_size with total in response
- Sort: username ASC, then id ASC
- Response item fields: id, username, status (sensitive fields are not returned)
- UI behavior: sends debounced queries (~300 ms), shows results in server order, displays total and current page count

API Contract

- Endpoint: GET /api/subscribers/search
- Auth: required (header X-Auth-User for this practice)
- Query params:
  - query: string, length 2..100, case-insensitive substring over username
  - page: number ≥ 1 (default 1)
  - page_size: number 1..50 (default 20)
- Response 200 (application/json):
  - { total: number, page: number, page_size: number, items: Array<{ id: string, username: string, status: 'active'|'blocked' }> }
- Errors:
  - 401 Unauthorized (missing auth)
  - 422 Unprocessable Entity (validation errors)
  - 429/5xx per project standards

Project Structure

- server.py — stdlib HTTP server (serves API and static UI)
- service/
  - app.py — FastAPI backend (feature parity, used by tests)
  - data/ — persisted JSON (safe for local dev)
- ui/
  - index.html — static UI, mounted by server
  - script.js — UI logic (subscribe, list, server-backed search)
  - styles.css — styles
  - README.md — UI notes
- specs/
  - 001-user-search-backend/ — backend spec, API contract
  - 002-user-search-ui/ — UI spec, contract expectations
- tests/
  - test_search.py — backend tests (FastAPI app)
  - ui/search.test.js — smoke tests for UI
- Makefile — run target
- data/ — JSON storage for stdlib server

SDD with GitHub SpecKit

- Authoring and convergence:
  - Separate specs for backend (001) and UI (002)
  - Convergence captured in “Согласование (v1)” sections
  - Explicit API contract normalized (path, params, response, errors)
- SpecKit assets live under .specify/ and .opencode/ with checklists, tasks, and workflows
- Outcome: specs drove implementation and tests; contract enforced consistency across teams

SpecKit vs OpenSpec (brief comparison)

- GitHub SpecKit (used here):
  - Markdown-first, repo-native SDD; lightweight checklists and workflows
  - Great for rapid feature cycles, cross-team convergence in a single repo
  - Tradeoff: less formal schema validation; relies on discipline and tests
- OpenSpec (contract-first frameworks, e.g., OpenAPI-driven):
  - Strongly typed, schema-driven contracts; generators for clients/servers
  - Better for multi-service/API-first ecosystems; tooling-rich
  - Tradeoff: heavier setup; requires stricter processes to stay flexible for UI/UX
- When to use:
  - SpecKit for feature-level SDD and fast convergence in app repos (as in this practice)
  - OpenSpec-style approaches for large, shared APIs where contract tooling and generation are critical

Notes and Decisions

- Search limited to subscribers; username-only matching
- Min length 2, max 100 (trim); server pagination with total
- Items: id, username, status; UI renders username and status for search results
- Display name removed from API and UI to prevent ambiguity
- Known future work: unify server implementations, extend tests to cover stdlib server, consider OpenAPI spec if promoting the API beyond this module
