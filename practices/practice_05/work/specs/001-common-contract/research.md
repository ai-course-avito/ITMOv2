# Research: Shared Learning-Site Contract

## Decision: One versioned contract with separate projections

Use contract version `v1` and keep four related contracts separate:

- `PageContract` for route identity, SEO, landmarks, and navigation.
- `DemoState` for the committed state of an interactive demonstration.
- `MathRequest` and `MathResponse` for calculation services.
- `ContractError` plus fallback metadata for validation, degradation, and accessibility.

The layers share identifiers, vocabulary, normalized parameters, and versioning. They do not share DOM selectors or arbitrary implementation fields.

## Rationale

The repository already has six static page routes and a versioned FastAPI endpoint at `/api/v1/calculate`. Reusing those boundaries avoids a second transport contract while allowing local demos and service-backed demos to expose the same observable state. A separate `DemoState` is required because playback states such as `playing` and `paused` are not mathematical results.

## Decision: Preserve the existing calculation envelope

Keep `operation`, `contract_version`, and operation-specific `parameters` in requests. Keep `data` and common `metadata` in successful responses. Extend metadata with explicit result ordering and execution details only when this does not change the meaning of existing fields.

Supported operations remain `fourier_partial_sum`, `chebyshev_values`, `chebyshev_nodes`, and `interpolation_comparison`. Strict Pydantic models, finite numeric inputs, allowlisted operations, bounded arrays, and deterministic float64 results remain the validation baseline.

## Decision: Atomic demo transitions

Demo updates follow `candidate -> validate -> normalize -> calculate -> commit -> render`. Invalid candidates do not replace the last valid state. The committed state is the source for plot data, visible labels, formulas, live announcements, and text fallback. Pending results must be ignored if a newer state has been committed.

## Decision: Stable vocabulary and errors

Use language-neutral identifiers and statuses: `v1`, `home`, `fourier-series`, `chebyshev-polynomials`, `approximation-theory`, `demonstrations`, `about`; demo statuses `idle`, `playing`, `paused`, `stepping`, `completed`, `error`; and stable error codes such as `VALIDATION_ERROR`, `MISSING_FIELD`, `INVALID_TYPE`, `NON_FINITE_VALUE`, `INVALID_INTERVAL`, `OUT_OF_RANGE`, `RESOURCE_LIMIT`, `UNSUPPORTED_OPERATION`, `UNSUPPORTED_VERSION`, `NUMERICAL_ERROR`, `SERVICE_UNAVAILABLE`, and `TIMEOUT`.

Errors contain `code`, `field`, `message`, `constraint`, and `retryable`. Existing API responses can retain the current envelope and progressively improve error-code specificity without changing v1 field meaning.

## Decision: Text fallback is normative

Every visual demo has a textual summary, current parameter/status description, and error explanation that remain useful without JavaScript, SVG/Canvas, or MathJax. MathJax source is not the only explanation of a formula. Reduced-motion mode disables autoplay but keeps explicit keyboard/button stepping.

## Alternatives considered

- DOM `data-*` attributes as the primary contract: rejected because they are not typed, versioned, or suitable for the backend.
- One envelope for UI state and math results: rejected because playback and calculation semantics differ.
- Backend-only calculations: rejected because local rendering is needed for responsiveness and service failure fallback.
- Arbitrary expression strings: rejected for safety, determinism, cacheability, and educational clarity.
- Changing `v1` to semantic `1.0.0`: rejected because existing routes, models, and tests already use `v1`.

## Resolved unknowns

- Runtime: Python 3.11+, FastAPI, Pydantic v2, NumPy, vanilla HTML/CSS/JS, and MathJax v3 are mandated by the constitution and existing project.
- Persistence: none; demo state is client-side and calculation cache is process-local.
- Public interfaces: static page routes plus `/api/v1/calculate`; both require explicit contracts.
- Numeric comparison: use operation-specific `rtol`/`atol`, never exact float equality; exclude timing and cache status from deterministic numeric comparison.
