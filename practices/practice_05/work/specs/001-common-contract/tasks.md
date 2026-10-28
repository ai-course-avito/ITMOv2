---

description: "Executable task list for the shared learning-site contract"
---

# Tasks: Shared Learning-Site Contract

**Input**: Design documents from `specs/001-common-contract/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included because the specification requires automated route, contract, accessibility, deterministic-output, and performance validation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the shared vocabulary and test fixtures without changing existing behavior.

- [X] T001 Create the shared contract module layout in `app/contract/__init__.py`, `app/contract/vocabulary.py`, and `app/contract/models.py`
- [ ] T002 [P] Create contract test directories and shared fixtures in `tests/contract/conftest.py`, `tests/unit/conftest.py`, and `tests/integration/conftest.py`
- [X] T003 [P] Document the implementation-to-contract traceability map in `specs/001-common-contract/README.md` linking FR-001 through FR-012 to source files and tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement versioning, shared errors, and normalization primitives required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement the `v1` route/topic/demo/status/operation/error vocabulary and reject unknown identifiers in `app/contract/vocabulary.py` (`/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, `/about/`; statuses `idle`, `playing`, `paused`, `stepping`, `completed`, `error`)
- [X] T005 Implement strict `Page`, `DemoState`, `MathRequest`, `MathResponse`, and `ContractError` Pydantic models in `app/contract/models.py`, including finite values, `time` in `[0, 1]`, non-negative integer `frame`, and `error` only for error state
- [X] T006 [P] Add normalization helpers for JSON paths, intervals, array ordering, float64 tolerance, and deterministic comparison in `app/contract/normalization.py`
- [X] T007 [P] Add shared error serialization and HTTP mapping for `MALFORMED_JSON`, `INVALID_CONTENT_TYPE`, `VALIDATION_ERROR`, `MISSING_FIELD`, `INVALID_TYPE`, `NON_FINITE_VALUE`, `INVALID_INTERVAL`, `OUT_OF_RANGE`, `RESOURCE_LIMIT`, `UNSUPPORTED_OPERATION`, `UNSUPPORTED_VERSION`, `NUMERICAL_ERROR`, `SERVICE_UNAVAILABLE`, and `TIMEOUT` in `app/contract/errors.py`
- [X] T008 Update `app/api/models.py` and `app/api/routes.py` to consume the shared v1 error/version models while preserving `/api/v1/calculate` and rejecting unknown request fields
- [X] T009 [P] Add foundational schema and vocabulary tests in `tests/contract/test_common_contract.py` covering exact enums, required fields, unknown-field rejection, finite numbers, interval ordering, and version stability

**Checkpoint**: Shared models, vocabulary, normalization, and errors are available to all story implementations.

---

## Phase 3: User Story 1 - Navigate a Consistent Learning Journey (Priority: P1) 🎯 MVP

**Goal**: Every required page exposes stable identity, complete navigation, semantic landmarks, anchors, breadcrumbs, and responsive focus behavior.

**Independent Test**: Request all six required routes, follow every primary navigation link, verify HTTP 200, unique title, exactly one `h1`, landmarks, canonical metadata, and complete return navigation; run the anchor checks at a 360px viewport with no horizontal overflow.

### Tests for User Story 1

- [X] T010 [P] [US1] Add route identity contract tests for six routes, unique titles/descriptions, one `h1`, canonical paths, breadcrumbs, and all navigation destinations in `tests/contract/test_page_contract.py`
- [ ] T011 [P] [US1] Add browser navigation and 360px anchor/focus/no-overflow tests in `tests/accessibility/test_common_navigation.py`

### Implementation for User Story 1

- [X] T012 [P] [US1] Define the six `Page` contract records, stable sections, topic identifiers, titles, descriptions, canonical paths, and breadcrumb metadata in `app/contract/pages.py`
- [ ] T013 [US1] Update `app/main.py` route registration and page metadata injection to expose `Page` identities while retaining static HTML delivery
- [X] T014 [US1] Update navigation/header/footer markup in `index.html`, `fourier/index.html`, `chebyshev/index.html`, `approximation/index.html`, `demos/index.html`, and `about/index.html` so every page links to all required routes and has `header`, `nav`, `main`, `footer`, one `h1`, and non-home breadcrumbs
- [X] T015 [US1] Add visible anchor focus, canonical metadata, and 360px overflow-safe styles in `static/css/style.css` and each page's existing stylesheet without changing the established dark academic visual language

**Checkpoint**: User Story 1 is independently navigable and verifiable as the MVP.

---

## Phase 4: User Story 2 - Consume a Stable Demonstration Contract (Priority: P1)

**Goal**: Parameter changes commit atomically, preserve the last valid state on failure, and expose consistent visual, accessible, service, and fallback projections.

**Independent Test**: Change a valid Fourier and Chebyshev parameter with keyboard/pointer controls, verify all projections use the same normalized state without reload, submit invalid values and verify structured errors with unchanged state, then force initialization failure and verify textual feedback.

### Tests for User Story 2

- [ ] T016 [P] [US2] Add DemoState transition tests for defaults, valid normalization, `idle -> playing -> paused|completed`, `idle|paused -> stepping`, invalid candidates, and stale pending results in `tests/unit/test_demo_state_contract.py`
- [ ] T017 [P] [US2] Add browser tests for keyboard/pointer parameter updates, `role="status"`, `aria-describedby`, fallback summaries, initialization errors, reduced motion, and no full-page reload in `tests/accessibility/test_demo_contract.py`
- [ ] T018 [P] [US2] Add local/service parity integration tests for Fourier and Chebyshev demos in `tests/integration/test_demo_execution.py`

### Implementation for User Story 2

- [X] T019 [P] [US2] Extend `static/js/demo-state.js` with `contract_version`, demo identifiers, normalized `parameters`, `time`, `frame`, `formula_highlight`, calculation metadata, structured errors, and immutable last-valid-state handling
- [ ] T020 [US2] Implement candidate validation and atomic commit sequencing in `static/js/demo-state.js` as `validate -> normalize -> calculate -> commit -> render`, including cancellation/version guards for pending requests
- [X] T021 [P] [US2] Adapt `static/js/demos/chebyshev.js` to use `node_count` for interpolation nodes, explicit `polynomial_order` when needed, and the shared DemoState instead of independent DOM state
- [X] T022 [P] [US2] Extract/adapt the Fourier demo script in `static/js/demos/fourier.js` and update its loader in `fourier/index.html` to publish the shared DemoState and avoid direct unsynchronized label/plot updates
- [ ] T023 [US2] Add shared status, error, accessible-description, and text-fallback bindings to `static/js/demo-projections.js` and the demo markup in `fourier/index.html`, `chebyshev/index.html`, and `demos/index.html`
- [ ] T024 [US2] Add reduced-motion handling, explicit keyboard stepping, and service/local failure fallback in `static/js/demo-runtime.js` and `static/css/style.css`

**Checkpoint**: Both demo families update atomically and remain understandable when rendering or service capabilities degrade.

---

## Phase 5: User Story 3 - Preserve Mathematical Meaning Across Layers (Priority: P1)

**Goal**: Formulas, metadata, accessible descriptions, plots, and numeric samples describe the same operation, parameters, interval, units, and ordering deterministically.

**Independent Test**: Compare a known Fourier partial sum and Chebyshev approximation across formula labels, response metadata, accessible text, plotted data, and repeated API responses within declared tolerance.

### Tests for User Story 3

- [X] T025 [P] [US3] Add MathResponse contract tests for operation, version, normalized parameters, domain, ordering, units, tolerance, duration, cache metadata, and structured errors in `tests/contract/test_math_response_contract.py`
- [X] T026 [P] [US3] Add deterministic numerical comparison tests for repeated Fourier and Chebyshev requests using `abs(actual - expected) <= atol + rtol * abs(expected)` in `tests/unit/test_math_determinism.py`
- [X] T027 [P] [US3] Add cross-layer metadata/accessible-text parity tests for known Fourier and Chebyshev inputs in `tests/integration/test_math_meaning_parity.py`

### Implementation for User Story 3

- [X] T028 [US3] Add explicit output ordering, coordinate meaning, interval/unit metadata, finite-output checks, and algorithm/tolerance metadata to `app/api/models.py` and `app/services/calculator.py` without changing existing v1 field semantics
- [ ] T029 [US3] Ensure deterministic normalized request keys and cache-before-compute behavior in `app/services/cache.py` and `app/services/calculator.py`, excluding `duration_ms` and `cache_status` from numeric equality
- [ ] T030 [P] [US3] Update Fourier and Chebyshev explanation/formula labels and accessible descriptions to use the same `order`, `node_count`, `polynomial_order`, interval, and signal/target vocabulary in `fourier/index.html`, `chebyshev/index.html`, and `static/js/demo-projections.js`
- [ ] T031 [US3] Add plain-text mathematical summaries and source-readable formula alternatives in `index.html`, `fourier/index.html`, `chebyshev/index.html`, `approximation/index.html`, and `demos/index.html`, including each demo fallback block for no-JavaScript/no-MathJax operation
- [X] T032 [US3] Add API response validation for malformed/non-finite/invalid payloads and safe error mapping without tracebacks or sensitive data in `app/api/routes.py` and `app/contract/errors.py`

**Checkpoint**: The same mathematical meaning is observable through API, UI, accessibility text, and fallback representations.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete contract, performance budgets, and implementation documentation.

- [X] T033 [P] Add end-to-end contract matrix coverage for all FR-001 through FR-012 cases in `tests/contract/test_shared_contract_matrix.py`
- [ ] T034 [P] Add representative API p50/p95 and browser LCP/TBT/CLS measurements against constitution budgets in `tests/performance/test_common_contract_budgets.py` and `tests/performance/README.md`
- [X] T035 [P] Update `README.md` with the v1 contract vocabulary, route/API validation commands, fallback modes, and links to `specs/001-common-contract/contracts/`
- [ ] T036 Run all scenarios from `specs/001-common-contract/quickstart.md`, record failures and evidence in `tests/performance/README.md`, and resolve any contract or accessibility regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001-T003 can begin immediately.
- **Foundational (Phase 2)**: Depends on Setup; T004-T009 block all user stories.
- **User Stories (Phases 3-5)**: Depend on the Foundational phase and can run in parallel after T009, subject to shared-file conflicts.
- **Polish (Phase 6)**: Depends on all selected stories; T036 is the final convergence check.

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2; provides route and page identity used by browser checks.
- **US2 (P1)**: Independent after Phase 2; uses the shared DemoState models but does not depend on US1 implementation.
- **US3 (P1)**: Independent after Phase 2; uses existing math services and shared response models, with UI parity checks that can be developed alongside US2.

### Within Each User Story

- Write story tests before implementation and confirm they fail for the missing behavior.
- Create/extend models before services, services before endpoint/UI integration, and integration checks after core behavior.
- Keep story checkpoints independently runnable; do not use undocumented DOM fields as the sole assertion.

## Parallel Opportunities

- Setup: T002 and T003 can run in parallel with T001 after the target directories exist.
- Foundation: T006, T007, and T009 can run in parallel after the shared module layout is created; T008 follows the model/error decisions.
- US1: T010, T011, and T012 can run in parallel; T013-T015 integrate them.
- US2: T016-T018 can run in parallel; T019, T021, and T022 touch separate state/demo files; T020, T023, and T024 follow shared state integration.
- US3: T025-T027 can run in parallel; T030 can run alongside backend metadata work T028-T029; T031-T032 follow the established response vocabulary.
- Cross-cutting: T033-T035 can run in parallel before T036.

## Parallel Example: User Story 1

```text
Task: "Add route identity contract tests in tests/contract/test_page_contract.py"
Task: "Add browser navigation and 360px anchor tests in tests/accessibility/test_common_navigation.py"
Task: "Define Page contract records in app/contract/pages.py"
```

## Parallel Example: User Story 2

```text
Task: "Add DemoState transition tests in tests/unit/test_demo_state_contract.py"
Task: "Add browser demo accessibility tests in tests/accessibility/test_demo_contract.py"
Task: "Adapt Chebyshev demo in static/js/demos/chebyshev.js"
Task: "Adapt Fourier demo in static/js/demos/fourier.js"
```

## Parallel Example: User Story 3

```text
Task: "Add MathResponse contract tests in tests/contract/test_math_response_contract.py"
Task: "Add deterministic numerical tests in tests/unit/test_math_determinism.py"
Task: "Update formula/accessibility vocabulary in fourier/index.html and chebyshev/index.html"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational contract primitives.
3. Complete Phase 3 User Story 1.
4. Run the independent route, navigation, accessibility, and 360px checks.
5. Stop and demo the complete learning journey before adding interactive/math parity work.

### Incremental Delivery

1. Deliver shared v1 primitives and route navigation as the MVP.
2. Add atomic local/service demo state and fallback behavior in US2.
3. Add numerical/API/UI meaning parity and deterministic response guarantees in US3.
4. Run the final contract matrix, performance evidence, quickstart, and convergence checks.

## Format Validation

All implementation tasks use `- [ ]`, sequential IDs `T001`-`T036`, `[P]` only for parallelizable tasks, `[US1]`/`[US2]`/`[US3]` on story-phase tasks, and an explicit repository-relative file path.
