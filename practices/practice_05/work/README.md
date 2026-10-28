# Fourier and Chebyshev Education Site

## Development

Install the Python dependencies from `requirements.txt`, then run:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The six routes are `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, and `/about/`.

## Validation

```bash
python3 -m pytest -q tests/contract tests/accessibility
npm run test:e2e
```

The browser tests require Playwright Chromium. The Python Playwright test additionally requires the Python `playwright` package.
The FastAPI service also exposes the versioned calculation endpoint at
`POST /api/v1/calculate`. The request/response contract is documented in
`specs/001-logic-backend/contracts/v1.md`; runnable scenarios are in
`specs/001-logic-backend/quickstart.md`.

Backend validation is covered by:

```bash
pytest tests/contract tests/unit tests/performance -q
```

The shared v1 contract is documented in `specs/001-common-contract/`. It covers route identity, `DemoState`, `/api/v1/calculate`, stable errors, deterministic numeric metadata, and text fallbacks. Browser smoke tests can be run against a managed server with `TEST_BASE_URL=http://127.0.0.1:PORT`.
