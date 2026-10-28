# Omnixon admin panel

Web admin panel for the [Omnixon](../omnixon-backend) service: agents (with versions, diff and rollback),
models, MCP servers, tokens, usage statistics, knowledge base (RAG), memories, users and their history, a playground
for `/request` and `/request-stream`, and service health/metrics. It covers **every** endpoint of
the API (see the table below).

Stack: React 19, TypeScript, Vite, Tailwind CSS v4, [shadcn/ui](https://ui.shadcn.com) (Base UI; the
`sidebar-08` layout, `Field`, `InputGroup`, `ButtonGroup`, `Combobox`, `Item`, `Empty` and a Data Table on TanStack Table for every table), React Router, TanStack Query, and the
[React Bits](https://reactbits.dev) *Tech Text* wordmark on the sign-in page.

## Run

```bash
cp .env.example .env.local      # OMNIXON_URL = where the service listens
npm install
npm run dev                     # http://localhost:5173
```

Sign in with a token of any role (the first, an owner, is the service's `INITIAL_API_KEY`). The panel offers what the role may use:
**regular** gets the Playground (as its own agent, with text, files and voice) and Settings; **user** adds its own agent (prompt, model, tools,
MCP servers, versions), knowledge base, memories, users and history, tokens for its agent and usage; **admin** and **owner** get everything,
including agents, models, MCP servers, metrics and working as any agent (an owner also hands out `admin` and `owner` tokens). A visitor who is not
signed in sees a front page describing Omnixon, with Login at the top left.

### Why a proxy

The service sends no CORS headers, so a browser cannot call it from another origin. The panel therefore
calls its own origin: Vite in development (`vite.config.ts`) and nginx in the Docker image
(`docker/nginx.conf.template`) forward `/api/*` to the service, and `/_ops/*` to its `/healthz`, `/readyz`
and `/metrics` (a prefix of its own, so the panel's `/metrics` page does not collide with them).
If the service does get CORS later, "API URL" on the sign-in screen (or in Settings) can point at it directly.

### Docker

```bash
docker build -f docker/Dockerfile.panel -t omnixon-admin-panel .
docker run -p 8080:80 -e OMNIXON_URL=http://omnixon-api:8000 omnixon-admin-panel
```

`OMNIXON_URL` has no trailing slash. All Docker files live in `docker/` (as in the backend); the build context is the repository root. `docker/docker-compose.yaml` is an example for a service running on the host, `docker/docker-compose.local.yaml` runs Omnixon and the panel together from `../omnixon-backend/.env` (`docker compose -f docker/docker-compose.local.yaml up -d --build`).

## Endpoint coverage

| Page | Endpoints |
|---|---|
| Dashboard | `GET /healthz`, `GET /readyz`, `GET /api/v1/`, `GET /admin/agents/self`, counts from the list endpoints |
| Metrics | `GET /metrics` (parsed into a table, raw view) |
| Playground (the user's chats beside the conversation, remembered per agent; settings in a dialog; the first page of regular and user tokens) | `POST /request`, `POST /request-stream` (SSE), attachments (file or URL), `save_message`, `use_memo`, `trace` (the chain of calls), send as another unit; Stop calls `POST /users/{id}/interrupt` and the cut answer is marked "interrupted" |
| Agents (list: edit, duplicate, delete; MCP servers in the same dialog) | `GET/POST /admin/agents`, `GET/PATCH/DELETE /admin/agents/{id}`, `GET /admin/agents/self` |
| Agent → MCP servers | `GET /admin/agents/{id}/mcp-servers`, `POST/DELETE /admin/agents/{id}/mcp-servers/{mcp_id}` |
| Agent → Versions | `GET /admin/agents/{id}/versions`, `GET …/versions/{n}`, `GET …/versions/{n}/diff?to=`, `POST /admin/agents/{id}/rollback` |
| Models (the connection is under the list "External model settings": base URL, use proxy, API token; the token is write-only) | `GET/POST /admin/models`, `GET/PATCH/DELETE /admin/models/{id}` |
| MCP servers | `GET/POST /admin/mcp-servers`, `GET/PATCH/DELETE /admin/mcp-servers/{id}` |
| Tokens (role, agent; the secret is shown once) | `GET/POST /admin/tokens`, `PATCH/DELETE /admin/tokens/{id}`, `GET /tokens/self` |
| Usage (charts: requests, tokens, cost, time per token and model) | `GET /admin/usage`, `GET /admin/usage/monthly` |
| Knowledge base | `GET /admin/rag` (list all / search), `POST /admin/rag`, `GET/PATCH/DELETE /admin/rag/{id}` |
| Memories | `GET/POST /admin/memories` (list, search by meaning), `GET/PATCH/DELETE /admin/memories/{id}` |
| Users & history (open to every role: the users of the agent and their chats) | `GET|POST /users/{id}/chats`, `GET|PATCH|DELETE /users/{id}/chats/{chat}`, `GET|DELETE /users/{id}/chats/{chat}/history`, `GET /users/recent` (who wrote lately), `GET /users?query=` (suggestions), `POST /users`, `GET/PATCH/DELETE /users/{id}`, `GET/DELETE /users/{id}/history` |

## Things that follow from the API

- **Roles.** `regular < user < admin < owner`. An owner hands out any role, an admin and a user `regular` and `user` (a user only for
  its own agent); the token of `INITIAL_API_KEY` is an owner that cannot be deleted. The panel shows only what the role may use and the
  service refuses the rest (403).
  Everything else is editable by an admin: a model, an MCP server, an agent (prompt, model,
  tools, limits, MCP servers), a memory's text and a knowledge-base entry (content, text to embed, metadata);
  ids, timestamps, the owner of a memory and the messages of a history are not editable by the API.
- **Versions.** Each version of an agent can be viewed (prompt, model with its parameters, settings, MCP
  servers), compared with the current one or any other, and restored with one click (Roll back, recorded as a
  new version). Older/Newer in the viewer walk through the history.

- **No user list.** There is no endpoint that lists every user (an agent can have very many), so user id boxes search by the
  start of the id: `GET /users?query=` after 3 characters, among the users **of one agent** (ids differ from agent to agent). In the
  Playground and in Users & history that agent is the one of your token; an admin may pick another (the panel then sends
  `X-Act-As-Agent`), and changing it empties the user box. A user id that does not exist is fine: the service creates the user on the
  first message. The "Recent users" table lists the users of the agent that wrote lately (`GET /users/recent`: those whose messages the service still keeps, latest first); the panel remembers nothing in the browser.
- **Knowledge base.** Without a query every entry of the agent is listed (`GET /admin/rag` pages of 1000); with a query the
  semantic search runs. **Export JSON** downloads the entries as a plain `["text", ...]` array and **Import JSON** adds the strings of such a
  file (validated first: invalid JSON, not an array, non-string or empty items and an empty array each get a clear message; entries already
  there are never touched).
- **Names.** Agents, models, MCP servers and tokens have a required name; every table, card, picker, dialog title and the breadcrumb
  uses it. Old entities without one get the service's fallback (model: its own model name; agent: the start of the prompt, else `Agent <id>`;
  `MCP <id>`). Cards also show the technical value (a model's own name, the start of an agent's prompt, an MCP url).
- **Pickers.** Every card in a picker is 4rem tall and the list shows exactly five whole cards, then scrolls.
- **Agent edits are optimistic-locked.** Saving sends the version the form was based on
  (`expected_version`); if the agent changed meanwhile you get a conflict message instead of an overwrite.
- **Agent config.** `tools` is always returned by the service (default `rag` + `memory`), so a tools list
  equal to the default is shown as "default". Limits and `auto_memory` set to empty are sent as `null`,
  which resets them to the service default.
- Editing a model or MCP server records a new version of every agent that uses it (done by the service).
- Deleting is blocked by the service when a record is in use (409): a model used by an agent, an agent
  with tokens; the message is shown in a toast.

- **Markdown.** Answers are shown as markdown (tables, lists, links, task lists) and fenced code is coloured like on GitHub (with the panel's own text and background), with the language and a copy button. HTML in an answer is never run.

## The chain of calls

The Playground sends `trace: true` (a switch on the left) and shows, above every answer, the chain behind it:
each call to the model and each tool the model called (memory, knowledge base, MCP tools) with arguments,
results, tokens and times. In a stream the steps appear as they finish. It is the `chain-of-thought` component of
[AI Elements](https://ai-sdk.dev/elements) (`components/ai-elements/`), adapted to Base UI, drawn by `components/trace-view.tsx`.
Needs a service that knows `trace` (the backend with `ai/trace.py`, omnixon-lib 3.4.0).

## Pickers

Choosing an agent, a model, an MCP server or a token is choosing a **card**: an icon, the title, the id, and below them what belongs to
the entity. What belongs to it is a **link** when it is another entity (an agent's model, a token's agent), so a card leads on to the next
one; plain facts (tools, a transport, a masked token) are chips. Every card also has an arrow that opens the entity itself, and the same
links work as `?open=ID` on the Models and MCP servers pages (they open that record's editor). Once something is chosen the field
keeps a small card of it (icon, title, id, a link to open it), not text. The cards are made by `lib/options.ts` and drawn by
`OptionCombobox` (`components/form.tsx`); user ids use `UserSuggest`. Short fixed lists (a theme, a transport) stay plain selects.
Nothing in the interface separates attributes with a middle dot or a dash: they are chips, links or separate lines.

## One look everywhere

- **Page**: `Page` + `PageHeader` (title, description, the primary action on the right) fill the whole window;
  a table fills what is left, its rows scroll under a sticky header and the pager stays at the bottom.
- **Bars above lists**: `QueryBar` is the same card on Knowledge base, Memories and Users & history; every table has
  the same search (`InputGroup`), row count, `Columns` menu and pager (`ButtonGroup`).
- **Forms**: the shadcn `Field` through `FormField` / `SwitchField` / `CheckboxField` (`components/form.tsx`);
  every dialog is a `FormDialog`, every confirmation a `ConfirmDialog` (`components/dialogs.tsx`).
- **Tables**: `idColumn`, `createdColumn`, `actionsColumn` and `rowAction.{open,edit,duplicate,remove}` give every
  table the same ID column, date format, icons (delete is always the trash can) and tooltips.
- **Typography** is decided once in `src/index.css`: every column heading (sortable or not) has the same size, weight and
  colour (`[data-slot=table-head]`), and `.value-mono` is the look of ids, urls and tokens.
- **Look**: Vercel's Geist. Colours are Geist's own tokens (gray 100-1000, gray alpha for borders, blue for focus, green/amber/red for status), read from [vercel.com/geist/colors](https://vercel.com/geist/colors), mapped onto the shadcn variables in `src/index.css`. Radii follow Geist's materials: 6px controls, 12px cards, menus and modals, 16px the largest surfaces. Borders are 1px hairlines, shadows are Geist's soft ones, the font is Geist and Geist Mono. Change the look in `src/index.css` only.
- IDs are written plainly (`12`), never `#12`.

## Layout

```
src/lib/api.ts          typed client for every endpoint + SSE reader (streamMessage)
src/lib/auth.tsx        sign-in state (the token: role, agent; via /tokens/self)
src/lib/queries.ts      TanStack Query client, useAction (mutation + toast + invalidate)
src/components/ui/      shadcn components (Base UI flavour: `render` prop instead of `asChild`)
src/components/         app shell and the shared pieces: page.tsx, form.tsx, dialogs.tsx, display.tsx, data-table.tsx, nav-items.tsx, agent-*.tsx
src/pages/              one file per page
```

## End-to-end tests (Playwright in Docker)

`docker/docker-compose.e2e.yaml` starts the whole chain: Postgres (pgvector) → the Omnixon API (built from the
sibling repo `../omnixon-backend`, or `OMNIXON_REPO=<path>`) → this panel behind nginx → a Playwright container
running `e2e/*.spec.ts` in Chromium.

```bash
npm run test:e2e         # build, run, exit code = test result (about 2 minutes the first time)
npm run test:e2e:down    # remove the stack
```

Nothing is published on the host, the database lives in tmpfs and the compose project has its own name
(`omnixon_admin_e2e`), so it cannot touch your own containers or volumes. The HTML report and failure
traces land in `playwright-report/` and `test-results/`.

The stack has no real OpenRouter key, so no test needs a model answer: where the service would call a
provider the tests expect its 502 (the fake key is refused by OpenRouter itself, so the run needs internet).
Covered: sign in/out, dashboard and metrics, models, agents (create, edit, versions, diff, rollback, delete),
MCP servers (create, attach, detach, edit, delete, rejected options), tokens and roles, usage, the front page, voice, users, memories, the playground
(JSON and SSE error paths, Stop and interrupting, with a fake OpenAI-compatible model server `fake-llm` from the service repository), external model settings and the knowledge-base error path.

To run the specs against a panel you already have: `BASE_URL=http://localhost:5173 OMNIXON_TOKEN=<admin token>
npx playwright test` (needs `npx playwright install chromium` once; the tests create and delete their own data).

## Checks

```bash
npm run build     # type-check + production build
npm run lint
```
