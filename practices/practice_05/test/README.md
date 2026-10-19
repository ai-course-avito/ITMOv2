# Coffee Backend (FastAPI) — practice_05/test

What runs on localhost
- App base: http://localhost:8000/
- Health: GET http://localhost:8000/health → { "status": "ok" }
- Readiness: GET http://localhost:8000/ready → { "ready": true }
- API base (reserved): http://localhost:8000/api
- API v1 root: GET http://localhost:8000/api/v1/ → { "service": "coffee-backend", "version": "v1" }
- OpenAPI docs: http://localhost:8000/docs
 - Frontend UI: http://localhost:8000/ui/ (автоматический редирект с "/")

Run locally
- Create venv: `python -m venv .venv && . .venv/bin/activate`
- Install deps: `pip install fastapi uvicorn pytest`
- Start server: `uvicorn app.main:app --reload`

Tests
- `pytest -q`

OpenSpec
- `npm exec -y @fission-ai/openspec@latest -- validate --all`

Structure
- app/main.py — FastAPI app (health, ready, /api, /api/v1)
- tests/ — pytest tests
- openspec/ — OpenSpec artifacts
