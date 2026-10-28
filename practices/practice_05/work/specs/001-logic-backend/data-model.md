# Data Model

## Common Request Envelope

| Field | Type | Rules |
|---|---|---|
| `operation` | enum | `fourier_partial_sum`, `chebyshev_values`, `chebyshev_nodes`, `interpolation_comparison` |
| `contract_version` | string | `v1` only initially |
| `parameters` | object | Operation-specific, no unknown fields |

## Request Entities

### FourierPartialSumRequest

`order` is an integer in `1..10000`. The input uses either an ordered finite `x_values` array of `1..10000` values or finite `interval` plus `sample_count` in `1..10000`; the two forms are mutually exclusive. Work and payload limits are checked before allocation.

### ChebyshevValueRequest

`kind` is `first` or `second`; `order` is `0..10000`; `x_values` contains `1..10000` finite points in `[-1, 1]` with only roundoff-scale endpoint clamping permitted.

### ChebyshevNodeRequest

`kind` is `roots` or `extrema`; `count` is `1..10000` for roots and `2..10000` for extrema; `interval` is finite and strictly increasing. Nodes are returned ascending and mapped to the requested interval.

### InterpolationComparisonRequest

`target` is `runge` or `cosine`; `node_count` is `2..256`; `interval` is finite and strictly increasing; `evaluation_grid` is an ordered finite array of `1..10000` values inside the interval or a bounded grid specification. Both node strategies are always calculated.

## Response Entities

### NumericalSeries

Contains ordered `x` and `y` arrays of equal length, `domain` metadata, and units/coordinate convention. Values must be finite JSON numbers.

### ErrorSummary

Contains strategy name, pointwise signed error array (approximation minus target), and `max_absolute_error` computed from that returned array.

### ServiceMetadata

Contains `operation`, `contract_version`, normalized `parameters`, `tolerance` (`dtype`, `rtol`, `atol`), `duration_ms`, `cache_status`, and domain/node convention metadata.

## Relationships and Invariants

- One request maps to one operation-specific result and one `ServiceMetadata` object.
- Every returned x coordinate corresponds to exactly one y coordinate.
- Interpolation returns both `chebyshev` and `uniform` results over the identical evaluation grid.
- Cache hits and misses are semantically identical.
- Any non-finite intermediate or final value becomes a structured numerical error rather than a partial response.
