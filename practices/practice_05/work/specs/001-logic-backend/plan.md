# Implementation Plan: Mathematical Calculation Service

**Branch**: `001-logic-backend` | **Date**: 2026-10-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-logic-backend/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Implement a versioned FastAPI mathematical calculation service for Fourier square-wave partial sums, Chebyshev values and nodes, and safe interpolation comparisons. Pydantic v2 models enforce strict, bounded JSON inputs; NumPy float64 implementations use stable recurrences and barycentric interpolation; a bounded deterministic LRU cache exposes hit/miss metadata.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2, NumPy, pytest/httpx

**Storage**: Process-local bounded LRU cache; no persistent storage

**Testing**: pytest with FastAPI TestClient/httpx; contract, numerical, validation, determinism, cache, and benchmark tests

**Target Platform**: Linux server and CI, Python 3.11+ runtime

**Project Type**: JSON web service with reusable mathematical service modules

**Performance Goals**: Typical workload p50 <80ms and p95 <250ms, with bounded allocations and no unbounded cache growth

**Constraints**: WCAG-independent backend contract; strict finite inputs, allowlisted operations/targets, bounded payload/work, deterministic float64 output, no arbitrary expression execution or secret logging

**Scale/Scope**: Four operations, contract version `v1`, orders up to 10,000, samples/grid up to 10,000, interpolation nodes up to 256, educational single-process traffic

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The gates pass before research:

- Accessibility/clarity: API schemas, stable errors, and metadata support readable UI and fallback clients.
- Performance: bounded work and payload checks precede NumPy allocation; benchmark targets match the constitution.
- Numerical stability: analytic Fourier formula, recurrence/Clenshaw-compatible Chebyshev evaluation, analytic nodes, and barycentric interpolation are required.
- Separation: routes, validation schemas, numerical services, cache, and public contracts remain separate.
- Determinism/observability: normalized parameters, fixed float64 ordering, timing, tolerance, and cache metadata are specified.
- Technology: Python 3.11+ and FastAPI are mandated by the constitution.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
app/
├── main.py                 # FastAPI app and route registration
├── api/
│   ├── models.py            # request/response/error schemas
│   └── routes.py            # versioned calculation endpoint
├── math/
│   ├── fourier.py           # partial sums
│   ├── chebyshev.py         # values and nodes
│   └── interpolation.py     # allowlisted functions and barycentric comparison
└── services/
    ├── calculator.py        # dispatch, normalization, metadata
    └── cache.py             # bounded LRU

tests/
├── contract/                # JSON schema and HTTP/error contract tests
├── unit/                    # numerical and validation tests
└── performance/             # representative latency/resource checks
```

**Structure Decision**: Extend the existing `app/` FastAPI project with explicit API, math, and service layers. Keep the calculation contract in `specs/001-logic-backend/contracts/` and test it independently from the frontend routes and browser tests.

## Post-Design Constitution Check

The Phase 1 artifacts preserve all gates: the contract gives clients explicit schemas and stable errors; bounded limits and the benchmark guide enforce performance; recurrence, analytic nodes, and barycentric interpolation enforce numerical stability; API, math, cache, and route responsibilities are separated; normalized parameters, tolerance, timing, and cache metadata provide deterministic observability; and the implementation remains within Python 3.11+, FastAPI, and the existing project technology constraints. No unresolved clarification remains.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | The selected four-layer structure is the minimum separation needed for stable numerical code, HTTP validation, and cache observability. |
