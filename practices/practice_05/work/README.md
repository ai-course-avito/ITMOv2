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
