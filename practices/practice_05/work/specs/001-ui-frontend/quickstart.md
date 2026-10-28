# UI/Frontend Validation Quickstart

## Prerequisites

- Python 3.11+ with server dependencies.
- Node.js dependencies installed.
- Playwright Chromium available.

## Start

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

During migration only, the static fixture fallback is:

```bash
python3 -m http.server 8000
```

## Checks

1. Verify HTTP 200 and one `h1` for `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, and `/about/`.
2. On `/fourier/`, wait for network idle and verify one MathJax script, inline and block `mjx-container` nodes, and no visible raw delimiters.
3. Change Fourier order from 10 to 15 and verify label, SVG path, formula highlight, and live status update atomically.
4. Use keyboard focus, Space/Enter, and Left/Right controls; enable reduced motion and verify autoplay is blocked while stepping remains available.
5. Reload on another route and verify preferences and last demo state persist, including a storage-disabled fallback.
6. Run at 360x640 and verify no horizontal overflow, visible focus, accessible names, and zero critical axe violations.
7. Run five Lighthouse-style mobile measurements over Fast 3G. Require median LCP <2.5s, TBT <200ms, CLS <0.1, and UI JS <=45KB gzipped excluding MathJax.

See [data-model.md](./data-model.md), [demo-ui.md](./contracts/demo-ui.md), [preferences.md](./contracts/preferences.md), and [routes.md](./contracts/routes.md).
