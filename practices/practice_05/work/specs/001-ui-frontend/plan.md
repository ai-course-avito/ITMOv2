# Implementation Plan: UI/Frontend Modernization

**Branch**: `001-ui-frontend` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ui-frontend/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Deliver a mobile-first academic learning site with six consistent routes, shared design and persistence assets, accessible Fourier and Chebyshev demonstrations, scoped MathJax updates, and measurable SEO, accessibility, and performance validation. The implementation retains vanilla HTML/CSS/JS and SVG, serves pages through FastAPI, and keeps mathematical calculations behind the shared contract.

## Technical Context

<!--
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+ for FastAPI; modern browser JavaScript, HTML, and CSS

**Primary Dependencies**: FastAPI, Uvicorn, MathJax 3, Playwright; no frontend framework

**Storage**: Static files plus browser `localStorage`; no server-side user storage

**Testing**: Playwright browser checks, pytest server/contract checks, Lighthouse-style performance measurements

**Target Platform**: Linux CI/server and evergreen desktop/mobile browsers, including 360x640

**Project Type**: FastAPI-served static web application with browser demonstrations

**Performance Goals**: LCP <2.5s, TBT <200ms, CLS <0.1; active animation at 60fps; preferences within 100ms of FCP

**Constraints**: WCAG 2.1 AA, no 360px horizontal overflow, 44x44px controls, UI JS <=45KB gzipped excluding MathJax, reduced-motion support

**Scale/Scope**: Six routes, shared tokens/preferences, two demo families, up to 20 formula terms, static educational traffic without accounts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The gates pass in design, subject to implementation validation:

- Accessibility: semantic landmarks, keyboard controls, visible focus, live status, text alternatives, and reduced motion.
- Performance: small early preference bootstrap, deferred MathJax/non-critical code, and measured Lighthouse budgets.
- Numerical stability: UI consumes normalized contracts; stable numerical algorithms remain in the logic feature.
- Separation: shared assets, page content, demo state, and math contracts are separate concerns.
- Determinism/observability: demo state is explicit; service results include timing/cache metadata.
- Technology: Python 3.11+ FastAPI, vanilla HTML/CSS/JS, MathJax v3, and SVG only.

## Project Structure

### Documentation (this feature)

```text
specs/001-ui-frontend/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
app/
├── main.py               # FastAPI app and page/static routes
└── routes/               # page handlers; service routes belong to backend feature

static/
├── css/                  # shared tokens, layout, motion, focus, responsive styles
└── js/                   # preferences, MathJax helper, state machine, demo controllers

index.html                # home page
fourier/index.html
chebyshev/index.html
approximation/index.html
demos/index.html
about/index.html

tests/
├── js/                   # existing focused browser tests plus route/demo checks
├── contract/             # route and state contract checks
├── accessibility/        # keyboard, focus, and reduced-motion checks
└── performance/          # mobile budget reports/configuration
```

**Structure Decision**: Preserve existing content-page paths and add three missing routes. Create one FastAPI app for serving them, and move duplicated inline infrastructure to shared static assets. Keep service algorithms in the separately planned backend feature.

## Post-Design Constitution Check

The Phase 1 data model and contracts retain all six gates above. In particular, local demo calculations do not create a second undocumented API; accessible fallback content is specified for every demo; persistence failures fall back to in-memory/system settings; and performance/accessibility remain measurable release gates rather than unverified claims.

## Complexity Tracking

No constitution violations require justification.
