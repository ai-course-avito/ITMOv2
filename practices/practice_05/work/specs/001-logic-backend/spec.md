# Feature Specification: Mathematical Calculation Service

**Feature Branch**: `001-logic-backend`

**Created**: 2026-10-28

**Status**: Ready for planning

**Input**: Define the server-side mathematical operations needed by the Fourier, Chebyshev, and approximation demonstrations.

## User Scenarios & Testing

### User Story 1 - Query a Fourier partial sum (Priority: P1)

As a learner, I can request samples of a Fourier partial sum for a square wave and use them to inspect convergence and the Gibbs effect.

**Why this priority**: Fourier partial sums are the primary interactive mathematical demonstration and establish the service's request, validation, and response conventions.

**Independent Test**: Request a valid order and interval, verify the response schema, compare selected samples against the analytic square-wave partial-sum formula, and repeat the request to verify determinism.

**Acceptance Scenarios**:

1. **Given** an order `N` in the supported range and a valid sample count and interval, **When** a Fourier partial-sum request is made, **Then** the service returns ordered x/y samples, normalized parameters, operation metadata, and a successful status.
2. **Given** two identical valid requests, **When** they are processed, **Then** their normalized parameters and numeric samples match within the documented tolerance.
3. **Given** a request for `N=1`, **When** it is processed, **Then** the result contains the first odd harmonic and does not attempt to use an empty sum.

---

### User Story 2 - Evaluate Chebyshev polynomials and nodes (Priority: P1)

As a learner, I can obtain values of Chebyshev polynomials and node locations to understand orthogonality, endpoint behavior, and stable interpolation.

**Why this priority**: Chebyshev values and nodes are the core mathematical data used by the Chebyshev and approximation pages.

**Independent Test**: Request first- and second-kind values and nodes for valid orders, compare low-order results with known identities, and verify node ordering and interval bounds.

**Acceptance Scenarios**:

1. **Given** a valid non-negative order and finite x values in `[-1, 1]`, **When** first-kind values are requested, **Then** the response satisfies `T_0(x)=1`, `T_1(x)=x`, and the documented recurrence for subsequent orders within tolerance.
2. **Given** a valid positive order, **When** Chebyshev nodes are requested, **Then** exactly the requested number of distinct nodes is returned, every node lies in `[-1, 1]`, and the node convention is declared in metadata.
3. **Given** an unsupported order or node count, **When** the request is made, **Then** the service returns a structured validation error naming the supported range.

---

### User Story 3 - Interpolate and compare approximation errors (Priority: P2)

As a learner, I can compare an approximation built from Chebyshev nodes with one built from uniform nodes and inspect the error on a declared evaluation grid.

**Why this priority**: The comparison explains why node choice matters and connects the Fourier and Chebyshev topics to approximate computation.

**Independent Test**: Request an interpolation comparison for a supported target function, verify that both methods use the declared nodes and grid, and check that error summaries correspond to returned samples.

**Acceptance Scenarios**:

1. **Given** a supported target function, interval, node count, and evaluation grid, **When** an interpolation comparison is requested, **Then** the response identifies the target, node strategy, interval, node count, grid, approximations, and pointwise errors.
2. **Given** a valid smooth target and increasing supported node counts, **When** the comparison is repeated, **Then** the response reports finite error values and does not silently omit either node strategy.
3. **Given** an unknown target function or invalid interval, **When** the request is made, **Then** the service rejects it with a stable error code and does not evaluate arbitrary user-supplied code.

## Edge Cases

- `N=0`, the minimum and maximum supported orders, and a request just outside each boundary.
- Zero, one, and maximum supported sample counts.
- Non-finite values, malformed JSON, missing fields, and unexpected fields.
- Reversed or zero-width intervals.
- Evaluation exactly at `x=-1`, `x=1`, and near both endpoints.
- Requests that would allocate excessive memory or exceed a configured computation limit.
- Duplicate requests arriving concurrently with the same normalized parameters.
- Cache storage unavailable or containing an incompatible contract version.
- A numerical operation encounters overflow, cancellation, or a non-finite intermediate result.

## Requirements

### Functional Requirements

- **FR-001**: The service MUST expose a versioned interface for Fourier partial sums, Chebyshev polynomial values, Chebyshev nodes, and interpolation comparisons.
- **FR-002**: Every operation MUST accept structured input with an operation name, contract version, and explicitly named parameters.
- **FR-003**: Every successful response MUST include operation name, contract version, normalized parameters, ordered output data, domain metadata, numeric tolerance, computation duration, and cache status.
- **FR-004**: Every failure MUST include a stable error code, affected field or operation, human-readable message, and the applicable constraint or correction.
- **FR-005**: Fourier partial sums MUST support the square-wave definition `S_N(x)=(4/π)Σ[k=0..N-1] sin((2k+1)x)/(2k+1)` for every supported positive integer `N`.
- **FR-006**: Fourier responses MUST preserve the requested x ordering and return one finite y value for each x value unless the request fails validation.
- **FR-007**: Chebyshev value operations MUST support first-kind values and second-kind values using numerically stable recurrence or equivalent accuracy, including orders zero and one.
- **FR-008**: Chebyshev node operations MUST declare whether roots or extrema are returned, return the requested count, and keep nodes within the declared interval after mapping.
- **FR-009**: Interpolation comparisons MUST use an allowlisted target-function vocabulary and MUST never execute arbitrary expressions received from a client.
- **FR-010**: Interpolation responses MUST include both Chebyshev-node and uniform-node results, pointwise errors, maximum absolute error, and the evaluation grid used for comparison.
- **FR-011**: The service MUST validate integer ranges, finite numeric values, interval ordering, sample counts, and resource limits before calculation.
- **FR-012**: The service MUST use stable numerical methods appropriate to the operation and MUST report a structured numerical error if finite output cannot be produced.
- **FR-013**: Identical normalized requests and contract versions MUST produce deterministic results within the operation's documented tolerance.
- **FR-014**: Repeated identical requests MAY be served from a bounded cache, but cache hits and misses MUST be observable in response metadata and MUST not change result semantics.
- **FR-015**: Typical valid requests MUST meet p50 latency below 80ms and p95 latency below 250ms under the project benchmark workload, excluding client rendering and network transfer.
- **FR-016**: The service MUST reject requests that exceed configured computation or payload limits before allocating unbounded resources.
- **FR-017**: The service MUST not log or return secrets, arbitrary executable input, or unnecessary personal data.

### Key Entities

- **FourierPartialSumRequest**: Operation parameters containing positive order, x interval or explicit x samples, sample count when applicable, and contract version.
- **ChebyshevValueRequest**: Polynomial kind, non-negative order, finite evaluation points, and contract version.
- **ChebyshevNodeRequest**: Node convention, positive node count, target interval, and contract version.
- **InterpolationComparisonRequest**: Allowlisted target, interval, node count, evaluation grid specification, and contract version.
- **NumericalSeries**: Ordered coordinate/value arrays with domain and unit metadata.
- **ErrorSummary**: Pointwise error values and aggregate absolute-error metrics for a named approximation strategy.
- **ServiceMetadata**: Operation, contract version, normalized parameters, timing, cache status, tolerance, and implementation-independent result metadata.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of valid requests in the contract test matrix return schema-valid responses with finite values and complete metadata.
- **SC-002**: 100% of invalid boundary, malformed, non-finite, and unsupported-operation cases return the documented structured error without a server error or process crash.
- **SC-003**: Fourier samples match the analytic partial-sum definition within the documented tolerance for all reference orders and points in the numerical test matrix.
- **SC-004**: Chebyshev low-order identities, recurrence checks, node counts, and interval bounds pass for 100% of reference cases.
- **SC-005**: Identical requests return deterministic outputs within tolerance in 100% of repeated-request tests, including cache hits and misses.
- **SC-006**: The benchmark workload meets p50 latency below 80ms and p95 latency below 250ms, with no unbounded memory growth.
- **SC-007**: Interpolation comparison responses always include both node strategies and error summaries for 100% of supported targets and valid parameter combinations.

## Assumptions

- The initial target function set is small and explicitly allowlisted; it includes the square wave and at least one smooth function used by the educational demonstrations.
- Requests and responses use JSON-compatible numeric arrays and a documented contract version.
- The client may still calculate lightweight Fourier curves locally, but the service remains the authoritative contract for server-backed demonstrations and tests.
- The supported limits for orders, samples, node counts, and payload sizes are selected during planning and recorded in the public contract.
- The service is stateless from the learner's perspective; caching is an optimization and not a source of correctness.
- Authentication, accounts, and persistent learner data are outside this feature.
