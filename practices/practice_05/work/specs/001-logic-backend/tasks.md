---

description: "Executable task list for the Mathematical Calculation Service"
---

# Tasks: Mathematical Calculation Service

**Input**: Design documents from `/specs/001-logic-backend/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/v1.md`, `quickstart.md`

**Tests**: Included because the specification defines independent tests, contract matrices, numerical success criteria, and benchmark targets.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the backend package and test layout without changing unrelated frontend work.

- [X] T001 Create backend package directories and `__init__.py` files at `app/api/`, `app/math/`, `app/services/`, `tests/unit/`, and `tests/performance/` according to `specs/001-logic-backend/plan.md`.
- [X] T002 Add the runtime and test dependencies `numpy`, `httpx`, and the existing FastAPI/Pydantic/pytest constraints to `requirements.txt`.
- [X] T003 [P] Add backend test configuration and shared HTTP client fixtures in `tests/conftest.py` without changing existing frontend fixtures.
- [X] T004 [P] Add the service launch and API entrypoint smoke configuration in `app/main.py` so `uvicorn app.main:app` can start after the foundational route is registered.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement shared contract, validation, error, normalization, and cache infrastructure required by every operation.

**CRITICAL**: User story implementation starts only after this phase is complete.

- [X] T005 Define the common request envelope in `app/api/models.py` with `operation` restricted to `fourier_partial_sum`, `chebyshev_values`, `chebyshev_nodes`, or `interpolation_comparison`, `contract_version` restricted to `v1`, and operation-specific `parameters` with unknown fields forbidden.
- [X] T006 [P] Define shared response schemas in `app/api/models.py` for `NumericalSeries`, `ErrorSummary`, and `ServiceMetadata`, enforcing equal ordered x/y lengths, finite JSON numbers, tolerance fields `dtype`, `rtol`, `atol`, `duration_ms`, and `cache_status`.
- [X] T007 [P] Define the public error envelope and stable codes `MALFORMED_JSON`, `VALIDATION_ERROR`, `UNSUPPORTED_OPERATION`, `RESOURCE_LIMIT`, and `NUMERICAL_ERROR` in `app/api/models.py`, including affected field/operation, human-readable message, and applicable constraint/correction.
- [X] T008 Implement strict finite numeric, integer-range, interval-ordering, array-length, and payload/work-limit validators in `app/api/models.py`; enforce the exact constraints `order 1..10000`, Chebyshev value order `0..10000`, sample/grid length `1..10000`, interpolation node count `2..256`, and strictly increasing finite intervals before NumPy allocation.
- [X] T009 Implement canonical parameter normalization and cache-key serialization in `app/services/calculator.py`, preserving explicit x ordering, normalizing equivalent numeric inputs, and including `contract_version` in every key.
- [X] T010 Implement a bounded process-local LRU cache in `app/services/cache.py` with configurable capacity, `hit`/`miss` status, contract-version-aware entries, and safe behavior when an entry is incompatible or storage is unavailable.
- [X] T011 Implement shared structured exception handling in `app/api/routes.py` for malformed JSON, Pydantic validation failures, domain errors, resource-limit failures, and numerical failures without returning tracebacks, secrets, or arbitrary client expressions.
- [X] T012 Register the versioned `POST /api/v1/calculate` route in `app/main.py` and `app/api/routes.py`, delegating dispatch to `app/services/calculator.py` while keeping UI routes unaffected.
- [X] T013 [P] Add foundational validation and error-envelope tests in `tests/contract/test_api_validation.py` for missing fields, unexpected fields, malformed JSON, non-finite values, unsupported operations/versions, reversed or zero-width intervals, and requests outside every documented bound.

**Checkpoint**: The service starts, exposes `/api/v1/calculate`, rejects invalid input with the public error envelope, and has deterministic cache-key infrastructure.

---

## Phase 3: User Story 1 - Query a Fourier Partial Sum (Priority: P1) 🎯 MVP

**Goal**: Return ordered, finite square-wave Fourier partial-sum samples using the specified odd-harmonic formula, with deterministic normalized metadata and observable caching.

**Independent Test**: Submit valid interval and explicit-x requests, compare selected outputs to `S_N(x)=(4/π)Σ[k=0..N-1] sin((2k+1)x)/(2k+1)`, verify `N=1`, ordering, schema metadata, and repeated-request determinism.

### Tests for User Story 1

- [X] T014 [P] [US1] Add Fourier contract tests in `tests/contract/test_fourier_contract.py` covering interval sampling, explicit ordered `x_values`, complete metadata, and one finite y value per x value.
- [X] T015 [P] [US1] Add Fourier numerical identity tests in `tests/unit/test_fourier.py` for `N=1`, representative positive orders, discontinuity values at multiples of π, and `rtol=1e-10`, `atol=1e-12` comparison tolerance.
- [X] T016 [P] [US1] Add Fourier determinism/cache tests in `tests/contract/test_fourier_determinism.py` verifying identical normalized requests produce matching samples and parameters on cache misses and hits while exposing cache status.

### Implementation for User Story 1

- [X] T017 [US1] Define `FourierPartialSumRequest` in `app/api/models.py` with positive integer `order`, either ordered finite `x_values` length `1..10000` or finite `interval` plus `sample_count` length `1..10000`, mutually exclusive input forms, and pre-allocation resource checks.
- [X] T018 [US1] Implement float64 square-wave partial sums in `app/math/fourier.py` using `S_N(x)=(4/π)Σ[k=0..N-1] sin((2k+1)x)/(2k+1)`, explicitly handling `N=1`, preserving x order, and rejecting non-finite output.
- [X] T019 [US1] Add Fourier dispatch and response metadata in `app/services/calculator.py`, including periodic/radian domain metadata, normalized parameters, tolerance, duration, cache status, and a `NumericalSeries` result.
- [X] T020 [US1] Wire `fourier_partial_sum` request routing in `app/api/routes.py` and verify the endpoint returns HTTP 200 for valid inputs and the structured validation/numerical errors for invalid inputs.

**Checkpoint**: US1 is independently deployable and demonstrates the primary Fourier interaction without depending on later stories.

---

## Phase 4: User Story 2 - Evaluate Chebyshev Polynomials and Nodes (Priority: P1)

**Goal**: Return stable first-/second-kind polynomial values and declared roots/extrema nodes with exact counts, ascending order, and mapped interval bounds.

**Independent Test**: Request low-order values and valid nodes, verify identities and recurrence, check endpoint behavior, count/distinctness/order/bounds, and assert structured errors for unsupported orders or node counts.

### Tests for User Story 2

- [X] T021 [P] [US2] Add Chebyshev value contract tests in `tests/contract/test_chebyshev_contract.py` for both `first` and `second` kinds, order zero and one, finite x arrays, and response metadata.
- [X] T022 [P] [US2] Add recurrence and endpoint tests in `tests/unit/test_chebyshev.py` for `T_0=1`, `T_1=x`, `U_0=1`, `U_1=2x`, subsequent recurrence, `T_n(±1)`, and `U_n(±1)` within `rtol=1e-10`, `atol=1e-12`.
- [X] T023 [P] [US2] Add node convention tests in `tests/unit/test_chebyshev_nodes.py` for exact root/extrema counts, ascending distinct nodes, `[-1,1]` bounds, mapped intervals, and declared `roots`/`extrema` metadata.

### Implementation for User Story 2

- [X] T024 [US2] Define `ChebyshevValueRequest` and `ChebyshevNodeRequest` in `app/api/models.py`, enforcing value `kind` `first|second`, value order `0..10000`, finite x values in `[-1,1]`, node `kind` `roots|extrema`, root count `1..10000`, extrema count `2..10000`, and finite strictly increasing intervals.
- [X] T025 [US2] Implement float64 T/U recurrence evaluation in `app/math/chebyshev.py`, handling orders zero and one explicitly, clamping only roundoff-scale endpoints, checking finite intermediates, and avoiding `arccos`/sine-quotient endpoint cancellation.
- [X] T026 [US2] Implement analytic Chebyshev roots and extrema in `app/math/chebyshev.py`, returning ascending nodes with exact requested counts and mapping via midpoint/half-width while clamping only roundoff-scale endpoint drift.
- [X] T027 [US2] Add Chebyshev value/node dispatch and metadata in `app/services/calculator.py`, declaring polynomial kind, node convention, ordering, source interval, mapped interval, tolerance, duration, and cache status.
- [X] T028 [US2] Wire `chebyshev_values` and `chebyshev_nodes` into `app/api/routes.py` and add stable validation responses for unsupported orders, counts, kinds, x domains, and intervals.

**Checkpoint**: US1 remains passing and US2 independently supplies all polynomial/node data needed by the Chebyshev page.

---

## Phase 5: User Story 3 - Interpolate and Compare Approximation Errors (Priority: P2)

**Goal**: Compare Chebyshev-node and uniform-node interpolation for allowlisted targets over a declared evaluation grid, returning both approximations and verifiable pointwise/max errors.

**Independent Test**: Request `runge` or `cosine` with a valid interval, node count, and grid; confirm both strategies use the declared grid and node count, errors are finite and derived from returned values, and unknown targets/arbitrary expressions are rejected.

### Tests for User Story 3

- [X] T029 [P] [US3] Add interpolation contract tests in `tests/contract/test_interpolation_contract.py` for `runge` and `cosine`, both strategies, declared grid, target/interval/node metadata, pointwise signed errors, and maximum absolute errors.
- [X] T030 [P] [US3] Add barycentric numerical tests in `tests/unit/test_interpolation.py` for exact node matches, endpoint/near-endpoint evaluation, increasing supported node counts, finite results, and max-error consistency from returned pointwise errors.
- [X] T031 [P] [US3] Add interpolation security/validation tests in `tests/contract/test_interpolation_validation.py` for unknown targets, expression-like payloads, invalid intervals, duplicate/invalid grid points, node bounds, and resource limits.

### Implementation for User Story 3

- [X] T032 [US3] Define `InterpolationComparisonRequest` in `app/api/models.py` with target allowlist `runge|cosine`, strictly increasing finite interval, `node_count 2..256`, and ordered finite evaluation grid length `1..10000` inside the interval or a bounded grid specification.
- [X] T033 [US3] Implement allowlisted `runge` and `cosine` target functions in `app/math/interpolation.py`; reject all client-supplied expressions and keep the square wave out of arbitrary target evaluation.
- [X] T034 [US3] Implement stable barycentric interpolation in `app/math/interpolation.py` for Chebyshev and uniform nodes, using normalized weights, exact scale-aware node matches, finite denominator/output checks, and no Vandermonde or monomial coefficient solve.
- [X] T035 [US3] Implement interpolation comparison assembly in `app/math/interpolation.py`, preserving the evaluation grid and returning both approximations, target samples, signed pointwise errors, and `max_absolute_error` computed from those returned errors.
- [X] T036 [US3] Add interpolation dispatch and response metadata in `app/services/calculator.py`, including target, node strategies, node count, interval, evaluation grid, tolerance, duration, and cache status.
- [X] T037 [US3] Wire `interpolation_comparison` into `app/api/routes.py` and return stable `VALIDATION_ERROR`, `RESOURCE_LIMIT`, or `NUMERICAL_ERROR` responses without evaluating arbitrary input.

**Checkpoint**: All three stories are independently testable through the same versioned endpoint and both interpolation strategies are always present.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete contract, performance, documentation, and operational safeguards.

- [X] T038 [P] Add full cross-operation schema and success-criteria tests in `tests/contract/test_calculation_matrix.py` covering 100% valid operation cases, finite outputs, complete metadata, and all documented error codes.
- [X] T039 [P] Add concurrency/cache tests in `tests/unit/test_cache.py` for duplicate normalized requests, bounded capacity, incompatible contract versions, and cache storage failure without semantic result changes.
- [X] T040 [P] Add representative latency and memory-bound benchmark tests in `tests/performance/test_calculation_benchmark.py` targeting p50 below 80ms and p95 below 250ms for the documented workload.
- [X] T041 Update `README.md` with service startup, endpoint, dependency installation, test commands, and links to `specs/001-logic-backend/contracts/v1.md` and `quickstart.md`.
- [X] T042 Run every scenario in `specs/001-logic-backend/quickstart.md`, inspect OpenAPI `/docs`, and record contract, numerical, error, cache, and benchmark evidence in the implementation handoff.
- [X] T043 Review `app/` logging and exception paths to ensure no secrets, arbitrary executable input, tracebacks, or unnecessary personal data are logged or returned, then run the complete test suite without modifying unrelated worktree changes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T003 and T004 can run in parallel after directory creation if needed.
- **Foundational (Phase 2)**: Depends on T001-T002; T005-T008 establish schemas/validation, T009-T010 establish normalization/cache, T011-T012 establish HTTP integration, and T013 validates the foundation.
- **User Stories (Phases 3-5)**: Depend on foundational completion. US1 and US2 are both P1 and can proceed in parallel after Phase 2; US3 can proceed in parallel as soon as shared schemas are stable, but its final integration should use the completed cache/dispatch foundation.
- **Polish (Phase 6)**: Depends on all desired stories and their checkpoints.

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2; MVP scope and no dependency on US2 or US3.
- **US2 (P1)**: Depends only on Phase 2; shares common schemas/dispatch but is independently testable.
- **US3 (P2)**: Depends only on Phase 2 contract infrastructure; uses Chebyshev node algorithms conceptually but must retain an independently tested interpolation implementation.

### Within Each User Story

- Write story tests before implementation and verify they fail for the missing behavior.
- Define request models before numerical services; implement services before route integration.
- Complete the story checkpoint before relying on it in cross-cutting tests.

## Parallel Execution Examples

### After Phase 2

```text
Developer A: T014-T020 (US1 Fourier contract, math, and route)
Developer B: T021-T028 (US2 Chebyshev contract, math, and route)
Developer C: T029-T037 (US3 interpolation contract, math, and route)
```

### Within US1

```text
T014 tests/contract/test_fourier_contract.py
T015 tests/unit/test_fourier.py
T016 tests/contract/test_fourier_determinism.py
```

### Within US2

```text
T021 tests/contract/test_chebyshev_contract.py
T022 tests/unit/test_chebyshev.py
T023 tests/unit/test_chebyshev_nodes.py
```

### Within US3

```text
T029 tests/contract/test_interpolation_contract.py
T030 tests/unit/test_interpolation.py
T031 tests/contract/test_interpolation_validation.py
```

## Implementation Strategy

### MVP First: User Story 1 Only

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational validation, route, errors, normalization, and cache.
3. Complete Phase 3 US1 Fourier implementation and tests.
4. Stop and validate the Fourier contract, numerical formula, `N=1`, ordering, determinism, and cache metadata.
5. Demo or deploy the first server-backed mathematical operation.

### Incremental Delivery

1. Add US2 Chebyshev values and nodes, then run its independent checkpoint.
2. Add US3 interpolation comparison, then run its independent checkpoint.
3. Complete Phase 6 contract matrix, performance, security, documentation, and quickstart validation.

## Notes

- Every task uses the required checkbox, sequential ID, optional `[P]` marker, story label in story phases, and at least one concrete file path.
- `[P]` means the task uses different files and has no dependency on incomplete work in the same phase.
- Do not alter unrelated existing frontend or worktree changes while implementing this feature.
