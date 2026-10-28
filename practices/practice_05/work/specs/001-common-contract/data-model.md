# Data Model: Shared Learning-Site Contract

All models carry `contract_version: "v1"` where shown. Identifiers and field names are language-neutral; user-facing messages are Russian.

## Page

| Field | Type | Rules |
|---|---|---|
| `route` | string | One of `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, `/about/` |
| `topic` | enum | `home`, `fourier-series`, `chebyshev-polynomials`, `approximation-theory`, `demonstrations`, `about` |
| `title` | string | Unique document title |
| `description` | string | Unique meta description |
| `heading` | string | Exactly one primary `h1` |
| `sections` | string[] | Stable anchors such as `hero`, `features`, `highlights`, `demos`, `cta` |
| `canonical` | string | Canonical route path |
| `breadcrumb` | object[] | Empty for home; otherwise ordered `{label, href}` entries |
| `navigation` | object[] | Links to all required destinations |

Each page also exposes `header`, `nav`, `main`, `footer`, visible focus for anchors, and no horizontal overflow at 360px.

## DemoState

| Field | Type | Rules |
|---|---|---|
| `contract_version` | `"v1"` | Required |
| `demo_id` | enum | `fourier-square-wave` or `chebyshev-interpolation` |
| `status` | enum | `idle`, `playing`, `paused`, `stepping`, `completed`, `error` |
| `parameters` | object | Demo-specific, normalized before commit |
| `time` | finite number | `[0, 1]`, default `0` |
| `frame` | non-negative integer | Normalized frame index, default `0` |
| `formula_highlight` | integer or null | Active term index where applicable |
| `calculation` | object | `mode` (`local` or `service`), `status`, operation, optional request reference |
| `error` | ContractError or null | Non-null only for error state |

Fourier parameters use `order` and optional playback `speed`; Chebyshev parameters use `node_count` and optional `polynomial_order` only if needed by the visualization. `node_count` must not silently mean polynomial order.

## MathRequest

```json
{
  "operation": "fourier_partial_sum",
  "contract_version": "v1",
  "parameters": {"order": 3, "x_values": [-1.0, 0.0, 1.0]},
  "options": {"tolerance": {"dtype": "float64", "rtol": 1e-10, "atol": 1e-12}}
}
```

Parameters are strict and operation-specific. Numbers are finite, booleans are not integers, intervals are strictly increasing, and array/work limits are bounded. Unknown fields are rejected.

## MathResponse

Successful responses include `operation`, `contract_version`, `data`, and `metadata` with `normalized_parameters`, `domain`, `tolerance`, `duration_ms`, and `cache_status`. Numeric arrays declare their ordering and coordinate meaning; corresponding `x[i]` and `y[i]` entries have equal lengths. `duration_ms` and `cache_status` are diagnostic and excluded from deterministic numeric equality.

## ContractError

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "field": "parameters.order",
    "message": "Порядок должен быть целым числом от 1 до 10000.",
    "constraint": "1 <= order <= 10000",
    "retryable": false
  },
  "contract_version": "v1"
}
```

Validation errors preserve the last valid `DemoState`. Service errors must never expose tracebacks, secrets, or arbitrary expressions.

## State transitions and invariants

`idle -> playing -> paused|completed`, `idle|paused -> stepping`, and any state can become `error` only after a failed candidate update. A successful candidate update commits all projections together. The response must be finite, deterministic for identical normalized inputs, and within the declared operation tolerance.
