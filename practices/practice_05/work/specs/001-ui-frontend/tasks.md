---

description: "Executable task list for UI/Frontend Modernization"
---

# Tasks: UI/Frontend Modernization

**Input**: Design documents from `/specs/001-ui-frontend/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Included because the feature specification defines independent browser, accessibility, responsive, SEO, MathJax, persistence, and performance acceptance scenarios.

## Phase 1: Setup

**Purpose**: Establish the FastAPI application, shared asset directories, and test dependencies without changing user-facing behavior.

- [X] T001 Create the planned application and test directories in `app/`, `static/css/`, `static/js/`, `static/js/demos/`, `tests/contract/`, `tests/accessibility/`, and `tests/performance/`
- [X] T002 Add FastAPI and Uvicorn runtime dependencies plus pytest and Playwright test dependencies in `requirements.txt` and `package.json`
- [X] T003 [P] Add Python and browser-test ignore patterns to `.gitignore` for `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `dist/`, `*.egg-info/`, `coverage/`, and `*.log`
- [X] T004 [P] Add the development and validation commands for FastAPI, Playwright, pytest, and performance checks to `README.md`

---

## Phase 2: Foundational

**Purpose**: Implement shared infrastructure required by every story.

**Checkpoint**: The application serves all planned page paths, shared assets load, and the shared state/contract modules can be exercised before story-specific work begins.

- [X] T005 Implement the FastAPI application and static/page route mounting in `app/main.py` for `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, and `/about/`
- [X] T006 [P] Create shared theme, gradient, spacing, typography, focus, responsive, and reduced-motion tokens in `static/css/tokens.css` and `static/css/site.css`
- [X] T007 [P] Implement the versioned preference bootstrap and safe localStorage fallback for `ui:preferences:v1` in `static/js/prefs.js`, validating `theme` (`dark` or `light`), `gradientPreset` (`spectral`, `oceanic`, or `aurora`), `gradientIntensity` (`0` to `1.5`), `reducedMotion`, `demoSpeed` (`0.25`, `0.5`, `1`, or `2`), and `lastDemoState`
- [X] T008 [P] Implement the shared demo state machine and atomic update notification API in `static/js/demo-state.js` with statuses `idle`, `playing`, `paused`, `stepping`, `completed`, and `error`, normalized `time` in `[0,1]`, and failed-update preservation in `static/js/demo-state.js`
- [X] T009 [P] Implement MathJax v3 configuration for `$...$`, `\(...\)`, `$$...$$`, and `\[...\]`, plus a helper that passes only affected formula nodes to `MathJax.typesetPromise()` in `static/js/mathjax.js`
- [X] T010 Add shared route, state, preference, and error contract fixtures in `tests/contract/fixtures.py` based on `contracts/routes.md`, `contracts/demo-ui.md`, `contracts/preferences.md`, and `data-model.md`
- [X] T011 [P] Add route smoke and shared contract tests in `tests/contract/test_routes.py` and `tests/contract/test_shared_state.py`

---

## Phase 3: User Story 1 - Persistent Theme and Preferences (Priority: P1)

**Goal**: Learners can switch theme, gradient preset/intensity, and motion preferences with persistence across routes and safe storage fallback.

**Independent Test**: Open Chebyshev at 360x640, toggle theme, choose each gradient preset, change intensity and reduced motion, navigate to another required route, reload, and verify values persist without horizontal overflow or console errors when storage is unavailable.

### Tests for User Story 1

- [ ] T012 [P] [US1] Add Playwright tests for theme, gradient preset, intensity, reduced-motion toggle, cross-route persistence, and localStorage-unavailable fallback in `tests/accessibility/test_preferences.py`
- [ ] T013 [P] [US1] Add responsive and contrast assertions for the theme controls, 44x44px tap targets, visible focus, and no horizontal overflow at 360x640 in `tests/accessibility/test_theme_responsive.py`

### Implementation for User Story 1

- [X] T014 [P] [US1] Add the shared preferences controls and accessible labels to the page shell in `static/js/prefs.js` and `static/css/site.css`
- [X] T015 [P] [US1] Add dark-first/light theme variables, three gradient presets, intensity scaling, and text-contrast-safe surfaces in `static/css/tokens.css`
- [X] T016 [US1] Apply preference bootstrap before non-critical page scripts and persist successful changes across all six page templates in `index.html`, `fourier/index.html`, `chebyshev/index.html`, `approximation/index.html`, `demos/index.html`, and `about/index.html`
- [X] T017 [US1] Add `prefers-reduced-motion` handling, site-level reduced-motion overrides, and <=100ms fade/jump transitions in `static/css/site.css` and `static/js/prefs.js`

**Checkpoint**: Theme and preferences work independently on every required route, survive reloads, and degrade without console errors when storage is unavailable.

---

## Phase 4: User Story 2 - Synchronized Interactive Demonstrations (Priority: P1)

**Goal**: Learners can play, pause, step, reset, and change speed for Fourier and Chebyshev demonstrations while plots, formulas, labels, and live status remain synchronized.

**Independent Test**: Operate both demos by pointer and keyboard, verify exact speed options, update the Fourier order and Chebyshev node count, confirm only affected formula nodes are re-typeset, and verify reduced motion blocks autoplay while preserving stepping.

### Tests for User Story 2

- [X] T018 [P] [US2] Add Fourier and Chebyshev DOM/state contract tests for `data-demo-id`, status live regions, atomic updates, plot descriptions, fallback regions, and exact speed values in `tests/contract/test_demo_ui.py`
- [ ] T019 [P] [US2] Add keyboard interaction tests for Tab, Space/Enter, Left/Right stepping, play/pause, reset, and reduced-motion behavior in `tests/accessibility/test_demo_keyboard.py`
- [ ] T020 [P] [US2] Add MathJax synchronization tests that verify affected-node re-typesetting, formula highlight state, no raw delimiters, and no full-page reflow in `tests/contract/test_mathjax_sync.py`

### Implementation for User Story 2

- [ ] T021 [P] [US2] Implement the Fourier square-wave SVG controller with order range `1` to `50`, default `10`, client-side partial sums, accessible path description, and text fallback in `static/js/demos/fourier.js`
- [X] T022 [P] [US2] Implement the Chebyshev interpolation SVG controller with documented node-count state, accessible description, static fallback, and error state in `static/js/demos/chebyshev.js`
- [ ] T023 [US2] Wire both controllers to `static/js/demo-state.js` so every transition updates plot data, visible labels, formula highlight, `role="status"`, and `localStorage` only after validation
- [ ] T024 [US2] Implement explicit play/pause, step-forward, reset, exact speeds `0.25x`, `0.5x`, `1x`, `2x`, and Left/Right keyboard stepping in `static/js/demo-state.js` and `static/js/demos/controls.js`
- [ ] T025 [US2] Add Fourier and Chebyshev formula term markup with stable highlight targets and scoped MathJax update calls in `fourier/index.html`, `chebyshev/index.html`, and `static/js/mathjax.js`
- [ ] T026 [US2] Replace placeholder demo sections with the required controls, SVG/Canvas labels, fallback text, and error/unsupported-browser states in `fourier/index.html`, `chebyshev/index.html`, `approximation/index.html`, and `demos/index.html`

**Checkpoint**: Both demo families are independently operable, accessible, synchronized, and reduced-motion compliant.

---

## Phase 5: User Story 3 - Mobile Learning Structure and SEO (Priority: P1)

**Goal**: Learners can navigate six coherent academic pages on mobile with hero/features/highlights/demos/CTA structure, semantic SEO, and accessible anchors.

**Independent Test**: Load all six routes at 360x640 and desktop breakpoints, navigate each section anchor, verify one `h1`, semantic landmarks, canonical metadata, structured data, and no horizontal scrolling.

### Tests for User Story 3

- [ ] T027 [P] [US3] Add route/content tests for six HTTP 200 routes, unique title/description, exactly one `h1`, required section anchors, and navigation links in `tests/contract/test_page_structure.py`
- [ ] T028 [P] [US3] Add SEO tests for canonical URLs, `WebSite` structured data, non-home `BreadcrumbList`, language metadata, and semantic `header`/`nav`/`main`/`footer` landmarks in `tests/contract/test_seo.py`
- [ ] T029 [P] [US3] Add mobile and desktop viewport tests for single-column 360px layout, 640/960/1200px progressive enhancement, focus-visible anchors, and horizontal overflow in `tests/accessibility/test_responsive_pages.py`

### Implementation for User Story 3

- [X] T030 [P] [US3] Create the home page with hero, features, highlights, demos entry, CTA, academic navigation, and Russian learner-facing content in `index.html`
- [X] T031 [P] [US3] Create the demonstrations index and project About page with semantic landmarks, accessible descriptions, and navigation in `demos/index.html` and `about/index.html`
- [X] T032 [US3] Migrate Fourier, Chebyshev, and Approximation pages to the shared shell and required hero/features/highlights/demos/CTA section structure in `fourier/index.html`, `chebyshev/index.html`, and `approximation/index.html`
- [X] T033 [US3] Add responsive layout breakpoints at 640px, 960px, and 1200px plus clean anchor scrolling that respects reduced motion in `static/css/site.css`
- [ ] T034 [US3] Add unique descriptions, canonical URLs, `WebSite` data, non-home `BreadcrumbList` data, and stable section IDs to all six page templates in `index.html`, `fourier/index.html`, `chebyshev/index.html`, `approximation/index.html`, `demos/index.html`, and `about/index.html`

**Checkpoint**: All six pages are navigable, mobile-first, semantically structured, and SEO-compliant independently of the interactive demos.

---

## Phase 6: Polish and Cross-Cutting Validation

**Purpose**: Validate the completed feature against the constitution, specification, contracts, and quickstart without weakening requirements.

- [ ] T035 [P] Run axe-core/Playwright accessibility checks and record zero critical violations in `tests/accessibility/README.md`
- [ ] T036 [P] Run five mobile Lighthouse-style measurements over Fast 3G and record median LCP <2.5s, TBT <200ms, CLS <0.1, and UI JS <=45KB gzipped excluding MathJax in `tests/performance/README.md`
- [ ] T037 [P] Run MathJax, Fourier, route, preference, keyboard, responsive, and SEO checks through `scripts/test_e2e.sh` and update the runner for FastAPI in `scripts/test_e2e.sh`
- [ ] T038 Review all six routes against `specs/001-ui-frontend/quickstart.md`, `specs/001-ui-frontend/contracts/`, and `.specify/memory/constitution.md`, then document residual risks and evidence in `HANDOFF.md`
- [ ] T039 Remove duplicated inline preference/demo infrastructure from page templates after shared modules pass, preserving authored content and required test selectors in `fourier/index.html`, `chebyshev/index.html`, and `approximation/index.html`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup must complete before Foundational.
- Foundational must complete before any user story.
- User stories may proceed in parallel after Foundational, but US2 and US3 touch the same page templates and should be sequenced by file owner.
- Polish depends on all selected user stories.

### User Story Dependencies

- **US1**: Starts after Foundational; independent of US2 and US3.
- **US2**: Starts after Foundational; consumes shared preference/state/MathJax infrastructure but does not require US3.
- **US3**: Starts after Foundational; can proceed independently, with final template integration coordinated with US2.

### Parallel Opportunities

- T006-T011 can run in parallel where files do not overlap.
- T012-T013 and T018-T020 and T027-T029 are independent test tasks within their story phases.
- T021-T022, T030-T031, and T035-T037 can run in parallel.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational.
2. Complete US1 to establish stable shared shell and persistence.
3. Complete US2 for the Fourier MVP and accessible demonstration controls.
4. Validate US1 and US2 independently before adding the remaining page structure.

### Incremental Delivery

1. Deliver shared infrastructure.
2. Deliver persistent theme/preferences.
3. Deliver synchronized Fourier/Chebyshev demonstrations.
4. Deliver all six routes, SEO, responsive layout, and cross-cutting validation.

## Independent Story Tests

- **US1**: Preferences persist across routes/reloads, controls remain accessible, storage failure is silent, and 360px layout has no overflow.
- **US2**: Both demos expose contract DOM, keyboard controls update atomic state, plots/formulas/status stay synchronized, and reduced motion prevents autoplay.
- **US3**: Six routes return 200, have one `h1` and required landmarks/metadata, anchors work at mobile and desktop breakpoints, and no horizontal overflow exists.

## Notes

- Every task uses the required `- [ ] T### [P?] [US?] description` checklist format.
- `[P]` is used only where files and dependencies permit parallel work.
- Task descriptions include exact repository paths and quote the relevant enum/range constraints where applicable.
