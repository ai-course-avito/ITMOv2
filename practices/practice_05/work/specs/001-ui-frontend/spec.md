# Feature Specification: UI/Frontend Modernization
Feature Branch: 001-ui-frontend
Created: 2026-10-27
Status: Draft
Provenance: Authored by Subagent UI-Team (openai/gpt-5, VseLLM Data Light)
Input (summary): Redesign the frontend of an educational site on Fourier series, Chebyshev polynomials, and approximation theory into a modern, mobile-first, framework-light experience using vanilla HTML/CSS/JS, MathJax v3, and SVG/Canvas demos. Deliver dark-first theming with dynamic gradients, an explicit motion/animation system, synced animated visual explanations with formulas, and strong accessibility/SEO. Adhere to LCP < 2.5s, TBT < 200ms, CLS < 0.1 on mid-range mobile and WCAG 2.1 AA.

## User Scenarios & Testing
P1: As a learner, I can toggle between dark and light themes with live dynamic gradient backgrounds that adapt intensity, so I can study comfortably in different environments. Independent Test: Run on a mid-range mobile in both prefers-color-scheme modes and manual toggle. Acceptance 1: Theme toggle updates CSS variables and gradient intensity within 150ms without layout shifts (CLS delta < 0.02). Acceptance 2: Theme choice and gradient intensity persist across reloads and pages for at least 30 days.

P1: As a learner, I see animated visual explanations (e.g., building a Fourier series term-by-term) synchronized with MathJax-rendered formulas, so I can connect math to visuals. Independent Test: Trigger play/step on Fourier page with network simulated at 3G Fast. Acceptance 1: When animation time t changes, corresponding MathJax expression highlights the matching term within 50ms and re-typesets only affected inline nodes. Acceptance 2: Pausing animation freezes the canvas/SVG and the highlighted formula state with no reflow.

P1: As a mobile user, I get a readable, scroll-first layout with the “VII Landing Page” structure adapted to academics (hero, features, highlights, demos, CTA) and clear section anchors. Independent Test: Load Home/Fourier/Chebyshev pages at 360×640 viewport. Acceptance 1: All sections fit within a single column with tap targets ≥44×44px and no horizontal scroll. Acceptance 2: In-page anchor navigation scrolls with reduced-motion aware smooth scrolling and maintains 16px+ focus outlines.

P1: As a learner, I can control demos with play, pause, step, reset, and speed settings for both Fourier and Chebyshev visualizations. Independent Test: Operate controls with mouse, touch, and keyboard only. Acceptance 1: Keyboard users can Tab to each control, Space/Enter activates, Left/Right arrows step, and controls have aria-labels and role semantics. Acceptance 2: Changing speed updates animation tick rate within one frame (≤16ms @60Hz) without desynchronizing formula highlights.

P1: As a user with motion sensitivity, I can enable reduced motion so animations become subtle or static while preserving comprehension via state changes and annotated frames. Independent Test: Emulate prefers-reduced-motion and toggle site setting. Acceptance 1: Motion transitions switch to cross-fade ≤100ms or jump cuts with visual annotations; no continuous parallax or auto-play. Acceptance 2: All demos default to paused on first load with reduced-motion; user can still step through discrete frames.

P2: As a thematic learner, I can choose among gradient presets (e.g., Spectral, Oceanic, Aurora) and adjust intensity from subtle to vivid, staying within contrast guidelines. Independent Test: Toggle presets/intensity on Chebyshev page. Acceptance 1: All foreground text maintains contrast ratio ≥4.5:1 against gradient at all intensities. Acceptance 2: Switching presets does not trigger repaint jank over 50ms on mid-range mobile (no dropped frames during idle).

P2: As a returning user, my preferences for theme, gradient preset/intensity, motion settings, and last demo state persist across pages and sessions. Independent Test: Set preferences, navigate across all pages, reload after 24 hours. Acceptance 1: Preferences load and apply before first paint or within 100ms of FCP without causing layout shift (CLS delta < 0.01). Acceptance 2: If storage unavailable, site gracefully degrades to system preferences without console errors.

## Requirements
- Functional Requirements: The site shall provide a dark-first theme with a light alternative, exposed via a toggle that switches CSS custom properties at runtime without reloading.
- Functional Requirements: Dynamic gradient backgrounds shall be defined by preset tokens (name, angle, stops) and an intensity scalar that adjusts stop opacity and luminance while preserving text contrast ≥4.5:1.
- Functional Requirements: A motion/animation system shall define named tokens for duration, easing, delay, and distance; defaults shall respect prefers-reduced-motion by shortening or removing movement.
- Functional Requirements: MathJax v3 shall re-typeset only affected nodes on dynamic updates; animations shall signal formula-highlight state without full-page reflow.
- Functional Requirements: Demo controls shall include play, pause, step-forward, reset, and speed (0.25×, 0.5×, 1×, 2×) with accessible roles, labels, and keyboard bindings.
- Functional Requirements: The layout shall follow a mobile-first, single-column structure with progressive enhancement to multi-column at defined breakpoints (e.g., 640px, 960px, 1200px).
- Functional Requirements: Accessibility shall meet WCAG 2.1 AA including focus visibility, semantics, aria-live for status updates, color contrast, and keyboard operability across all controls.
- Functional Requirements: SEO shall include semantic HTML5 landmarks, descriptive titles/meta, canonical URLs, structured data (BreadcrumbList, WebSite), and clean anchor slugs per section.
- Functional Requirements: Performance budgets shall be enforced: LCP < 2.5s, TBT < 200ms, CLS < 0.1 on mid-range mobile over 3G Fast, with first render not blocked by non-critical scripts or fonts.
- Functional Requirements: User preferences (theme, gradient preset/intensity, motion, demo speed) shall persist using lightweight storage; initialization shall apply critical preferences before first paint where possible.
- Functional Requirements: Reduced-motion behavior shall disable auto-playing animations, replace large movements with fades ≤100ms, and provide step-wise exploration for demos.
- Functional Requirements: The site shall avoid heavy JS frameworks; use vanilla HTML/CSS/JS, MathJax v3, and SVG/Canvas for interactive demos only, loading scripts defer or async as appropriate.
- Functional Requirements: The “VII Landing Page” academic structure shall be implemented: hero (title, tagline, CTA), features (topics), highlights (key concepts), demos (interactive), CTA (continue learning), with consistent section tokens.
- Functional Requirements: Error and empty states shall be designed for demos (e.g., unsupported browser, failed init) with text alternatives and static illustrative frames.

### Key Entities
- Theme tokens: color-bg, color-bg-elev, color-text, color-text-subtle, color-border, color-accent, color-accent-contrast, gradient-angle, gradient-stop-1, gradient-stop-2, gradient-stop-3, gradient-intensity, shadow-depth-1/2, radius-sm/md/lg, spacing-2/4/8/12/16, font-sans, font-mono, font-size-xs/sm/md/lg/xl/2xl, line-height-tight/normal/loose.
- Animation tokens: motion-fast-100, motion-200, motion-300, motion-slow-500 (ms); ease-standard (cubic-bezier), ease-emph, ease-decel, ease-accel; transform-distance-4/8/12 (px); opacity-fade-0-1; reduced-motion: off (default) or on (prefers/site setting).
- Demo control states: idle, playing, paused, stepping, completed; speed: 0.25×, 0.5×, 1×, 2×; time-t normalized [0,1]; error: init-failed, unsupported; sync flags: formula-highlight-on/off, retypeset-pending.

## Success Criteria
- 95% of pages achieve LCP ≤ 2.5s, TBT ≤ 200ms, CLS ≤ 0.1 on Moto G Power class device over 3G Fast in Lighthouse CI (median of 5 runs).
- 100% of interactive controls are keyboard operable and meet contrast ≥ 3:1 for UI components and ≥ 4.5:1 for text; automated axe-core shows 0 critical violations.
- 90%+ of animation state transitions complete within 150ms of user action; formula highlight sync delta ≤ 50ms relative to animation time changes.
- Preference load and apply within 100ms of FCP on 95% of sessions; no more than 1 style recalculation per preference at init; CLS from preference application ≤ 0.01.
- MathJax re-typeset scope limited to ≤ 10 nodes per interaction; re-typeset time ≤ 120ms on mid-range mobile in demos with up to 20 terms.
- JavaScript payload attributable to UI modernization ≤ 45KB gzipped across all pages excluding MathJax; no third-party runtime frameworks added.

## Assumptions
- Content pages already exist for Home, Fourier, Chebyshev, Approximation Theory, Demos, About and will be updated in-place with new structure and tokens.
- MathJax v3 is the only math rendering library; no server-side rendering is required for math.
- SVG is preferred for explanatory diagrams; Canvas is used for performance-critical animations; both are acceptable.
- No backend changes are required; SEO improvements rely on static HTML enhancements and metadata.
- User preference storage can rely on localStorage; if unavailable, in-memory settings are acceptable for the session.

## Out of Scope (UI)
- Building or integrating a component framework or design system library beyond site-level tokens.
- Server-rendered theming, user accounts, or multi-tenant branding systems.
- Complex 3D/WebGL visualizations; only 2D SVG/Canvas are considered.
- Authoring new mathematical content; this spec covers presentation, structure, and interaction for existing or concurrently authored content.
- Internationalization/localization; English-only layout and typography are assumed for this iteration.
