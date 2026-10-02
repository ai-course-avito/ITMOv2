---
name: ui-check
description: Use for implementing or reviewing Olympiad Start UI changes. Follow the product contract and project rules, validate observable behavior in a real browser, and report evidence.
---

# Procedure
1. Read `docs/requirements.md`, `AGENTS.md` and the current `index.html` / `styles.css`.
2. Restate observable acceptance criteria for the requested feature: exact sections, counts, names, prices, CTA texts and anchors.
3. Before implementation, create or identify a check that fails when the requested behavior is missing (a Playwright scenario or a `browser_evaluate` assertion).
4. Make the smallest coherent implementation. Vanilla HTML/CSS/JS only. Do not add a framework, library or npm package.
5. Run `git diff --check`.
6. If Playwright MCP is available, serve the page with `python3 -m http.server 8000` and run one real browser scenario relevant to the feature: open the page, use the feature by mouse and by keyboard, check the console for errors, and confirm no horizontal scroll at 360px and 1280px.
7. Review the diff for unrelated changes, requirement drift and invented real-world claims (addresses, reviews, guarantees, results, years of operation).
8. Report changed files, checks actually run, browser scenario and anything not verified.

Do not commit unless the user explicitly asks.
