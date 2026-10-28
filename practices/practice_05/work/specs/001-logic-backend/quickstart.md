# Quickstart Validation

## Prerequisites

- Python 3.11+
- Install dependencies with `pip install -r requirements.txt`.

## Run the service

From the repository root:

```bash
uvicorn app.main:app --reload
```

The versioned calculation endpoint is documented in [contracts/v1.md](contracts/v1.md). OpenAPI is available at `/docs`.

## Contract checks

Run the complete backend checks after implementation:

```bash
pytest tests/contract tests/unit -q
```

Expected result: valid requests for all four operations return HTTP 200 with finite arrays and complete metadata; malformed, unsupported, non-finite, out-of-range, and over-limit requests return the documented structured error without HTTP 500.

## Manual smoke scenarios

1. POST a `fourier_partial_sum` request with `order: 1` and ordered x values. Confirm `y = 4/pi * sin(x)` and preserved x ordering.
2. POST `chebyshev_values` for first-kind orders 0, 1, and 2 at `x=-1,0,1`. Confirm identities and finite output.
3. POST `chebyshev_nodes` with `kind: roots`, `count: 8`, and `interval: [-1,1]`. Confirm eight ascending nodes in bounds and `node_convention` metadata.
4. POST `interpolation_comparison` for `runge`, increasing `node_count`, and a fixed evaluation grid. Confirm both strategies, pointwise errors, and maximum errors are present.
5. Repeat any identical request. Confirm normalized parameters and numeric arrays match within `rtol=1e-10`, `atol=1e-12`, while metadata changes only in permitted cache/timing fields.

## Performance validation

Run the representative benchmark test:

```bash
pytest tests/performance -q
```

The configured workload must meet p50 below 80ms and p95 below 250ms, with bounded cache size and no unbounded allocation. Record environment and sample workload with benchmark evidence.
