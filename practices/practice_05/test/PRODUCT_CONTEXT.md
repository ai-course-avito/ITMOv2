# PRODUCT_CONTEXT: Coffee Shop Backend (FastAPI)

## Vision
Build a simple coffee shop backend to support menu management, ordering, pricing and discounts, and store status. The goal is clarity and incremental delivery using Spec‑Driven Development (SDD) with OpenSpec.

## Audience
- Students practicing SDD and OpenSpec
- Developers iterating features safely with specs, tasks, and tests

## Glossary
- CoffeeCoin: in‑house, fictional currency used for pricing and payments
- Menu Item: coffee drink with name, ingredients, sizes, and price
- Order: customer’s selection of items with total in CoffeeCoin
- Store Status: open/closed derived from business hours
- Roles: Customer (places orders), Barista (fulfills), Admin (manages menu)

## Architecture (High Level)
- Stack: Python 3 + FastAPI
- Data: in‑memory (dict/list) initially; SQLite optional later
- API: REST with auto OpenAPI docs at `/docs` and `/openapi.json`
- Tests: `pytest` + `fastapi.testclient`
- Run: `uvicorn app.main:app --reload`

Rationale
- FastAPI provides type hints, validation, and OpenAPI out of the box
- In‑memory keeps setup simple for practice; can swap to SQLite later

## Features
Planned and active changes under `openspec/changes/`:
- Foundation (FastAPI) — `openspec/changes/foundation-fastapi/`
- Menu management — planned
- News feed (local JSON / in‑memory) — planned
- Payments (CoffeeCoin, mock) — planned
- Discounts (happy hour / history / daily) — planned
- Store hours (open/closed) — planned
- Composition & cost endpoints — planned
- Extras (2+): e.g., Loyalty points, Reviews — planned

Update this list as changes are added/archived.

## Project Rules & Conventions
- SDD via OpenSpec: every feature documents Why / How / What follows
- Small, incremental changes; validate specs before code
- Tests cover key endpoints and scenarios first
- Prefer explicit, simple code; comment only where non‑obvious
