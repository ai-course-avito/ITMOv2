# Research: UI/Frontend Modernization

**Date**: 2026-10-28

## Decision: Serve the static frontend through FastAPI

**Rationale**: The constitution requires FastAPI, while the UI spec requires framework-light static HTML/CSS/JS. FastAPI can provide the six page routes and static assets without adding a frontend build system.

**Alternatives considered**: Python `http.server` is insufficient for the required application contract. A JavaScript framework would violate the framework-light constraint and add unnecessary payload.

## Decision: Use shared static assets

**Rationale**: The current pages reference missing `/static/css/tokens.css` and `/static/js/prefs.js`, while preference and demo logic is duplicated inline. Shared assets reduce drift and make cross-page persistence testable.

**Alternatives considered**: Keeping scripts inline preserves duplication. A component framework is out of scope.

## Decision: Use an explicit demo state machine

**Rationale**: The spec names `idle`, `playing`, `paused`, `stepping`, `completed`, and `error` states and requires synchronized visual, formula, and accessibility updates. A small centralized module makes atomic transitions and keyboard behavior testable.

**Alternatives considered**: Independent event handlers permit inconsistent status and speed behavior. A general state library is disproportionate to two demo families.

## Decision: Use SVG and scoped MathJax typesetting

**Rationale**: The current Fourier plot is SVG and the demos are small enough for accessible SVG paths. MathJax v3 supports passing affected nodes to `typesetPromise`, avoiding global re-typesetting.

**Alternatives considered**: Canvas makes accessible text alternatives and DOM inspection harder. Global re-typesetting violates the performance scope requirement.

## Decision: Keep Russian learner-facing content and language-neutral identifiers

**Rationale**: Existing pages and the common contract use Russian. Keep `lang="ru"` and Russian text, while routes, test IDs, state names, and contract fields remain stable ASCII identifiers.

**Alternatives considered**: Converting all content to English creates out-of-scope content work and conflicts with existing pages.

## Decision: Keep lightweight demos local while sharing the backend contract

**Rationale**: The existing Fourier feature requires client-side calculation without a server API. Local state preserves animation responsiveness while the shared and logic contracts define the future/server-backed response shape.

**Alternatives considered**: Requesting every animation frame from the backend would conflict with 60fps and reduced-motion requirements.

## Decision: Validate with Playwright and performance budgets

**Rationale**: Playwright covers routes, DOM, keyboard, persistence, MathJax, and SVG behavior. Lighthouse-style measurements are required for LCP, TBT, CLS, and payload budgets.

**Alternatives considered**: Existing focused tests do not cover accessibility, SEO, responsive layout, or performance. Python Playwright is useful for server tests but is not currently installed.
