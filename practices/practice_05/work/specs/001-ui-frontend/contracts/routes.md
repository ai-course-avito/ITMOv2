# Route and SEO Contract

| Route | Required content |
|---|---|
| `/` | Hero, topics/features, highlights, demos entry, CTA. |
| `/fourier/` | Explanation, inline/block MathJax, partial-sum demo. |
| `/chebyshev/` | Explanation, formulas, node/interpolation demo. |
| `/approximation/` | Approximation concepts, error comparison, CTA. |
| `/demos/` | Cross-topic demo index and accessible links. |
| `/about/` | Project purpose, methodology, and accessibility information. |

Every route returns HTTP 200, has a unique title and description, one `h1`, `header`, `nav`, `main`, and `footer`, and includes a canonical URL. Every page includes `WebSite` structured data or references the site-level object; non-home pages include a `BreadcrumbList`.
