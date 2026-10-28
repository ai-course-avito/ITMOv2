# Research: Mathematical Calculation Service

## FastAPI and Validation

- **Decision**: Use FastAPI with Pydantic v2 request models and one versioned JSON calculation endpoint. Configure models with `extra="forbid"`, finite numeric types, explicit bounds, and custom exception handling that maps malformed bodies and domain failures to the public error envelope.
- **Rationale**: FastAPI integrates typed schemas and OpenAPI while allowing a stable application-specific error shape instead of leaking framework validation details. Pydantic provides `FiniteFloat`, strict fields, and forbidden-extra validation.
- **Alternatives considered**: Manual dictionary validation was rejected because it duplicates schema rules and weakens generated documentation. Separate endpoints per operation were rejected for v1 because the common operation/version/metadata envelope is the primary contract convention.

## Numerical Algorithms

- **Decision**: Compute Fourier partial sums with the specified odd-harmonic formula in float64, evaluate Chebyshev T/U through recurrence with explicit orders 0 and 1, generate roots/extrema analytically with cosine formulas, and evaluate interpolation through barycentric weights rather than monomial coefficients.
- **Rationale**: These choices avoid unstable polynomial conversion and endpoint cancellation, preserve requested sample ordering, and make the educational formulas directly traceable. Validate finiteness after every operation.
- **Alternatives considered**: SciPy special functions and polynomial root solving add dependencies or unnecessary numerical paths. `arccos`/trigonometric quotient evaluation and Vandermonde/`polyfit` interpolation were rejected for endpoint stability. FFT/DCT was deferred because the initial contract accepts arbitrary samples and intervals.

## Limits and Tolerances

- **Decision**: Initial public limits are Fourier order 1..10,000, sample/grid count 1..10,000, interpolation nodes 2..256, and bounded work estimates before allocation. Use `float64`, comparison tolerance `rtol=1e-10`, `atol=1e-12`, scale-aware node matching, and reject non-finite input/output.
- **Rationale**: Limits support the demonstrations while preventing unbounded memory/work. Tolerances distinguish contract comparison from exact mathematical error.
- **Alternatives considered**: Larger unconstrained limits were rejected because they undermine p95 latency and resource-limit requirements. Silent clipping was rejected except for roundoff-scale mapped endpoints.

## Interpolation Targets and Security

- **Decision**: Expose a fixed target-function vocabulary (`runge`, `cosine`) implemented by internal callables. Never evaluate client-provided expressions. Return both Chebyshev and uniform node results, signed or absolute pointwise error consistently, and maximum absolute error derived from the returned grid.
- **Rationale**: An allowlist satisfies the educational need without code execution risk. Returning both strategies makes the node-choice comparison independently verifiable.
- **Alternatives considered**: Accepting Python/JavaScript expressions was rejected as unsafe. A generic plugin registry is unnecessary for the initial two-target scope.

## Determinism and Cache

- **Decision**: Normalize numbers, intervals, arrays, and defaults before calculation and cache by contract version plus canonical normalized parameters. Use a bounded process-local LRU; expose `cache_status` as `hit` or `miss` without changing result values.
- **Rationale**: Canonical keys make repeated requests deterministic and observable while avoiding persistent learner data. Cache bounds prevent memory growth.
- **Alternatives considered**: Persistent or distributed caches were rejected because the service is stateless and educational traffic is small. Unbounded memoization was rejected by FR-016.

## Testing and Evidence

- **Decision**: Use pytest and FastAPI TestClient/httpx for contract, numerical identity, malformed input, resource-limit, determinism/cache, and representative latency tests. Keep public JSON examples in the contract document and runnable validation in quickstart.
- **Rationale**: The same HTTP boundary used by the frontend is tested, while pure math tests isolate numerical regressions.
- **Alternatives considered**: Browser-only validation was rejected because it cannot prove server-side numerical and error invariants. SciPy-based reference tests are optional and not a runtime dependency.
