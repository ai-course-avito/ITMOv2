# Mathematical API Contract v1

## Endpoint

`POST /api/v1/calculate`

The request uses the `MathRequest` envelope in [data-model.md](../data-model.md). Supported operations are `fourier_partial_sum`, `chebyshev_values`, `chebyshev_nodes`, and `interpolation_comparison`.

## Response

HTTP `200` returns `operation`, `contract_version`, `data`, and common metadata: normalized parameters, domain/interval semantics, float64 tolerance, duration, and cache status. Arrays are ordered explicitly; output positions retain their coordinate correspondence.

## Errors

HTTP `400` is used for malformed JSON, invalid content type, unsupported operation, or unsupported version. HTTP `422` is used for missing, malformed, non-finite, out-of-range, semantically invalid, or resource-limit parameters. HTTP `503`/`504` may represent unavailable or timed-out services. All errors use the `ContractError` envelope and must not expose implementation details.

## Determinism and limits

Identical operation, version, and normalized parameters produce identical metadata relevant to meaning and numeric outputs within the declared tolerance. Timing and cache status may differ. Inputs and work remain bounded by the existing service limits: order up to 10,000, samples up to 10,000, interpolation nodes up to 256, and bounded request body size.
