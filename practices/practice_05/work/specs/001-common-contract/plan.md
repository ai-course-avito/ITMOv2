# Implementation Plan: Shared Learning-Site Contract

**Branch**: `001-common-contract` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-common-contract/spec.md`

## Summary

Define one versioned `v1` contract across the six static learning routes, interactive demo state, mathematical service, and non-visual fallback. Preserve the existing `/api/v1/calculate` envelope, add explicit page/demo/error schemas and vocabulary, and make demo updates atomic so every visual and accessible projection reflects the same normalized state.

## Technical Context

**Language/Version**: Python 3.11+, browser JavaScript (vanilla)

**Primary Dependencies**: FastAPI, Pydantic v2, NumPy, pytest/httpx, Playwright/webapp-testing, MathJax v3

**Storage**: No persistent storage; client demo state and process-local calculation cache

**Testing**: pytest/httpx contract tests, numerical/determinism tests, browser route/accessibility smoke tests, responsive and performance checks

**Target Platform**: Linux server/CI and modern desktop/mobile browsers, including reduced-motion and degraded-rendering modes

**Project Type**: Static educational web application with a versioned JSON calculation service

**Performance Goals**: Demo state projection within 150ms under normal conditions; LCP <2.5s, TBT <200ms, CLS <0.1; API p50 <80ms and p95 <250ms for typical parameters

**Constraints**: WCAG 2.1 AA, keyboard operation, finite strict bounded inputs, deterministic float64 results, stable field meanings, no arbitrary expressions, no horizontal overflow at 360px, useful fallback without JS/SVG/MathJax

**Scale/Scope**: Six routes, two interactive demo families, four calculation operations, contract version `v1`, educational single-process traffic

## Constitution Check

*GATE: Pass before Phase 0 research; re-check after Phase 1 design.*

- Accessibility and clarity: PASS. Page landmarks, keyboard controls, live status, formula/source fallback, and textual demo summaries are normative.
- Performance budgets: PASS. Existing bounded API limits are retained; client state updates avoid full reloads; quickstart requires evidence against all budgets.
- Numerical stability: PASS. The common contract requires finite values, operation-specific tolerances, deterministic ordering, and preserves existing stable math service boundaries.
- Separation of concerns: PASS. Page, demo, math, and error contracts are separate and connected only through versioned vocabulary and normalized parameters.
- Observability and determinism: PASS. Responses expose duration/cache metadata; repeated normalized inputs have deterministic numeric meaning.
- Technology constraints: PASS. Design stays within Python 3.11+, FastAPI, vanilla HTML/CSS/JS, MathJax v3, and SVG/Canvas.

No gate violations or unresolved clarifications remain.

## Project Structure

```text
app/
├── api/                 # Existing FastAPI request/response models and routes
├── math/                # Existing Fourier, Chebyshev, interpolation algorithms
└── services/            # Existing dispatch and bounded cache
static/
├── js/                  # Demo state, controls, projections, and fallback bindings
└── ...                  # Six page bundles and shared styles
tests/
├── contract/            # Shared schema, vocabulary, route, and API tests
├── unit/                # State transition and normalization tests
├── integration/         # Local/service/fallback integration paths
└── performance/         # API and browser budget evidence
specs/001-common-contract/
├── contracts/           # Page/demo and mathematical API contracts
├── data-model.md
├── quickstart.md
└── research.md
```

**Structure Decision**: Extend the existing `app/`, `static/`, and `tests/` layers. Keep normative shared contracts in this feature directory; do not introduce a second backend or a DOM-only source of truth.

## Post-Design Constitution Check

PASS. Phase 1 artifacts define accessible page identity and fallback behavior, bounded and measurable performance expectations, stable numerical metadata and tolerances, explicit UI/logic/API separation, deterministic observability, and the mandated technology stack. No unresolved clarification remains.

## Complexity Tracking

No violations. The four contract projections are the minimum separation required because route identity, interactive playback state, mathematical results, and failure/fallback behavior have different lifecycles and consumers.
