# OpenSpec in practice_05

This folder uses OpenSpec as a dev-only dependency (no global install required).

Prerequisites
- Node.js 20.19.0+ (check with `node --version`).

Where Things Live
- `openspec/config.yaml` — project config
- `openspec/changes/` — in-flight changes
- `openspec/specs/` — main specs

Commands (no global install)
- List changes: `npm exec -y @fission-ai/openspec@latest -- list`
- Create change: `npm exec -y @fission-ai/openspec@latest -- new change <name>`
- Status: `npm exec -y @fission-ai/openspec@latest -- status --change <name>`
- Validate all: `npm exec -y @fission-ai/openspec@latest -- validate --all`

Delta Rules
- Use headers `## ADDED/MODIFIED/REMOVED/RENAMED Requirements`.
- Each `### Requirement: <name>` must include at least one `#### Scenario:`.

Local Validation Script
Run:
```
bash practices/practice_05/scripts/check.sh
```
It runs OpenSpec validation and fails on errors.

Feature Plan (Coffee Backend)
- Change: coffee-backend-foundation
  - Why: minimal foundation to iterate safely.
  - How: health endpoints, /api namespace, user stub routes.
  - Implications: enables later real auth, menu, orders, payments.
