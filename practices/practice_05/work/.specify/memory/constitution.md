# Project Constitution: Fourier & Chebyshev Education Site

## Core Principles

### I. Accessibility and Clarity (Non-negotiable)
All UI must meet WCAG 2.1 AA. Math content must be readable with and without JavaScript. Interactive controls are fully operable with keyboard, have ARIA labels, and provide descriptive alternatives.

### II. Performance Budgets
Pages must meet: LCP < 2.5s, TBT < 200ms, CLS < 0.1 on mid-range mobile. Frontend JS kept minimal; heavy work is offloaded or reduced. Backend endpoints meet p50 < 80ms, p95 < 250ms for typical params.

### III. Numerical Stability First
Prefer analytic formulas and stable recurrences (barycentric interpolation, Clenshaw) over naïve polynomial evaluation. Validate ranges and handle edge cases explicitly.

### IV. Spec-Driven Separation of Concerns
UI, Logic, and Contract evolve in parallel but are synchronized through explicit API schemas, state machines, and invariants. No cross-layer assumptions beyond the Common Contract.

### V. Observability and Determinism
Expose timing and cache metadata. For identical inputs and contract version, return deterministic outputs (within dtype tolerance). Avoid hidden randomness.

## Additional Constraints
- Technology: Python 3.11+ (FastAPI), vanilla HTML/CSS/JS, MathJax v3, SVG/Canvas for demos.
- Content: LaTeX via MathJax on all pages with inline and block delimiters; dynamic updates trigger scoped re-typeset.
- Visual: Dark theme with dynamic gradients, reduced-motion support, mobile-first layout; follow academic variant of “VII Landing Page”.

## Workflow and Quality Gates
1. Specify → Plan → Checklist → Tasks → Analyze → Implement → Converge for each feature.
2. Run Analyze before Implement; fix issues at the source (spec/plan/tasks).
3. Implementation proceeds in Setup/Foundational → Story phases; Converge must pass before closing a feature.

## Governance
- This constitution guides all features. Amendments require a documented rationale and reviewer approval.
- PRs must reference spec/task IDs and include evidence for performance and accessibility budgets.

Version: 1.0 | Ratified: 2026-10-27 | Last Amended: 2026-10-27
