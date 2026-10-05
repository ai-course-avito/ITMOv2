# AGENTS.md

## Project
Olympiad Start: a fictional one-page landing for a math olympiad training camp for kids.
`docs/requirements.md` is the source of truth for what to build. Read it before any change.
Before changing code, read `docs/style-guide.md` (5 rules that are easy to break).
If this file and `docs/requirements.md` disagree, follow `docs/requirements.md` and point out the conflict.

## Files
- `index.html`: the only page.
- `styles.css`: the only stylesheet.
- `script.js`: optional, only if a feature needs JavaScript.
- `docs/requirements.md`: product requirements. Do not edit unless asked.
- `scripts/check.sh`, `scripts/check_page.py`: the check runner. Do not edit or weaken unless asked.

Do not create other pages, stylesheets, folders or build files.
Project tooling lives only in `docs/`, `scripts/` and `.claude/`.

## Check
- Run `sh scripts/check.sh` from this folder. Exit code 0 = PASS, 1 = FAIL.
- It checks the page contract from `docs/requirements.md` (sections, exact counts, prices, anchors),
  stack rules (no `<img>`, no external resources) and `git diff --check`.
- A `PostToolUse` hook (`.claude/settings.json`) runs it after every Edit/Write in this folder.
  On FAIL it blocks with the failing checks: fix the cause, never the runner.
- It does not open a browser: keyboard, layout, contrast and console still need a browser check.
  Use the Playwright MCP server from `.mcp.json` for that (serve the page first, see "Run locally").

## Stack rules
- Vanilla HTML, CSS and JavaScript only.
- No frameworks, libraries, CDNs, npm packages or build steps.
- No external images or fonts; use inline SVG, CSS shapes or system fonts.

## Run locally
- Open `index.html` in a browser, or
- `python3 -m http.server 8000` and open http://localhost:8000
  (in a second worktree use another port, e.g. 8001: worktrees do not isolate ports)

## Content rules
- All visible text is in Russian. Code, class names and comments are in English.
- Use only the content given in `docs/requirements.md` (names, prices, counts, steps).
- Never invent real-world facts: addresses, real people, olympiad results, reviews,
  guarantees, years of operation.
- No photos of children or real people.

## Code style
- Semantic HTML: `header`, `nav`, `main`, `section`, `footer`; one `h1`; headings in order.
- Every section has an `id` that matches its anchor link.
- Class names: BEM-style (`program-card`, `program-card__price`).
- CSS: mobile-first, custom properties for colors and spacing in `:root`, `rem` units.
- 2-space indentation.
- Keep JavaScript minimal; prefer native HTML (`<details>`, anchor links) over JS.

## Accessibility
- All links and controls reachable and usable with the keyboard; visible focus styles.
- `alt` text on meaningful images, `aria-hidden="true"` on decorative SVGs.
- Text contrast at least WCAG AA.

## Before finishing a task
- [ ] `sh scripts/check.sh` prints `RESULT: PASS`.
- [ ] Everything listed for the current feature in `docs/requirements.md` is present, with exact counts.
- [ ] Every anchor link and CTA scrolls to an existing section.
- [ ] Layout works at 360px, 768px and 1280px with no horizontal scroll.
- [ ] Tab through the whole page: nothing is skipped or trapped.
- [ ] No console errors.
- [ ] No content that is not in `docs/requirements.md`.

## Workflow
- Build one feature at a time. Do not start Feature B until asked.
- Keep changes small and explain what changed and why.
- If a requirement is unclear, ask instead of guessing.
