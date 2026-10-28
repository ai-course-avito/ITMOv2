# Page and Demonstration Contract v1

## Page routes

| Route | Topic | Required identity |
|---|---|---|
| `/` | `home` | Hero, features, highlights, demos entry, CTA |
| `/fourier/` | `fourier-series` | Explanation, formulas, partial-sum demo |
| `/chebyshev/` | `chebyshev-polynomials` | Formulas, nodes/interpolation demo |
| `/approximation/` | `approximation-theory` | Error comparison and methods |
| `/demos/` | `demonstrations` | Accessible links to demos |
| `/about/` | `about` | Purpose, methodology, accessibility |

Every route returns HTTP 200, has one `h1`, unique title/description, `header`, `nav`, `main`, `footer`, canonical path, and links to all required destinations. Non-home pages expose breadcrumbs.

## Demo state JSON

```json
{
  "contract_version": "v1",
  "demo_id": "fourier-square-wave",
  "status": "stepping",
  "parameters": {"order": 10, "speed": 1},
  "time": 0.2,
  "frame": 10,
  "formula_highlight": 2,
  "calculation": {"mode": "local", "status": "ready", "operation": "fourier_partial_sum"},
  "error": null
}
```

The visual plot, labels, `role="status"` announcement, accessible description, and fallback summary must all be rendered from this committed object.

## Fallback requirements

When the renderer or service is unavailable, the page keeps a textual summary containing the demo name, normalized parameters, mathematical target, current status, and any corrective error. The fallback must not be an unlabeled empty graph. Reduced motion prevents autoplay; keyboard and explicit controls remain available.
