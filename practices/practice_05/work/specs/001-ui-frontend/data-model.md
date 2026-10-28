# Data Model: UI/Frontend Modernization

## Page

| Field | Type | Rules |
|---|---|---|
| `route` | string | `/`, `/fourier/`, `/chebyshev/`, `/approximation/`, `/demos/`, or `/about/`. |
| `title` | string | Unique, descriptive document title. |
| `heading` | string | Exactly one primary `h1`. |
| `topic` | string | Stable language-neutral page identifier. |
| `sections` | array | Clean anchors such as `hero`, `features`, `highlights`, `demos`, and `cta`. |

## ThemePreferences

| Field | Type | Rules |
|---|---|---|
| `theme` | enum | `dark` or `light`; dark is default. |
| `gradientPreset` | enum | `spectral`, `oceanic`, or `aurora`. |
| `gradientIntensity` | number | Inclusive range `0` to `1.5`. |
| `reducedMotion` | boolean | Explicit setting overrides media preference. |
| `demoSpeed` | enum | `0.25`, `0.5`, `1`, or `2`. |
| `lastDemoState` | object | Last valid demo identifier and parameters. |

Storage failures are non-fatal. Invalid or unsupported values fall back to system defaults.

## DemoState

| Field | Type | Rules |
|---|---|---|
| `demoId` | enum | `fourier-square-wave` or `chebyshev-interpolation`. |
| `status` | enum | `idle`, `playing`, `paused`, `stepping`, `completed`, or `error`. |
| `time` | number | Normalized range `[0, 1]` where applicable. |
| `order` | integer | Fourier order in its documented safe range; default `10`. |
| `nodeCount` | integer | Chebyshev node count in its documented safe range. |
| `speed` | enum | `0.25`, `0.5`, `1`, or `2`. |
| `formulaHighlight` | integer/null | Active term index or `null`. |
| `errorCode` | string/null | Stable code when `status=error`. |

State transitions:

```text
idle -> playing -> paused
idle -> stepping -> paused
paused -> playing
paused -> stepping -> paused
playing -> completed
any non-error state -> error
error -> idle (reset)
```

Reduced motion prevents automatic transition to `playing`; explicit stepping remains available.

## FormulaUpdate

| Field | Type | Rules |
|---|---|---|
| `target` | DOM node reference | Only affected formula node(s). |
| `tex` | string | Authored TeX, not arbitrary learner input. |
| `highlightIndex` | integer/null | Matches `DemoState.formulaHighlight`. |
| `retypesetPending` | boolean | Cleared after scoped MathJax completion. |

## Validation Rules

- Numeric values must be finite.
- Integer controls reject fractional values.
- A failed update leaves the last valid state unchanged.
- Every visualization has a textual status and static fallback description.
