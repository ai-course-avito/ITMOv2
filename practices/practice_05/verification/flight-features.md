# Flight feature verification

Mocked Ignav; isolated temporary SQLite; no live fare request.

## Backend tests: PASS

```text
............................                                             [100%]
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /Users/emilramazanov/itmo/vibecoding3s/ITMOv2/practices/practice_05/backend/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
28 passed, 1 warning in 0.95s
```

## After-edit hook tests: PASS

```text
✔ after-edit returns failure to agent, supports before args and patches, skips reports (3187.11675ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3264.596083
```

## Frontend build: PASS

```text
> cheap-flights-frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.3 building for production...
transforming...
✓ 32 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.50 kB │ gzip:  0.35 kB
dist/assets/index-x2Gg8bCq.css    5.25 kB │ gzip:  1.72 kB
dist/assets/index-n-B9Bt4s.js   239.73 kB │ gzip: 75.06 kB
✓ built in 331ms
```

## Offline A/B scenario: PASS

```text
first=no_previous_price, second=compared, difference=-500.0 RUB (-12.5%), empty=no_current_price, invalid_http=422, mocked_upstream_calls=3, saved_rows=3
```
