# AGENTS.md — Omnixon (backend, library, admin panel)

Briefing for an agent working in this folder. It merges the former `AGENTS.md` files of the three repositories:
`omnixon-backend` (the service), `omnixon-library` (the Python client) and `omnixon-frontend` (the admin panel),
plus `omnixon-mcp` (the API as an MCP server, last section).
Paths written as `../omnixon-backend` etc. in the sections below are relative to the repository they describe
(here: `./omnixon-backend`, `./omnixon-library`, `./omnixon-frontend`). `docker-compose.yml` and `.env` in this
folder start the whole stack (`docker compose up -d --build`). Agent settings and hooks are in `.claude/`.

---

# Backend (omnixon-backend)

Read this first. It is the briefing for an agent working in this repository: what the project is,
how it is built, how to run and test it, the rules this project follows, and the traps that already
cost time. `README.md` is the user-facing description; this file is for working on the code.

## What this is

**Omnixon** unifies LLM interaction for automated systems. A client (a Telegram bot, a website, ...)
sends a text request for a *user*; Omnixon builds the context (message history, memories, knowledge
base, MCP tools), calls the model through **OpenRouter**, stores the exchange and returns the answer,
optionally as a **server-sent-events stream**.

Three repositories belong together (they live next to each other in `~/Documents/dev/`):

| Repo | What | Stack |
|---|---|---|
| `omnixon-backend` (this one, GitLab project `unlink/unilink-api`, GitHub mirror `europrom-injectors/unilink`) | the service | FastAPI, asyncpg + pgvector, pydantic-ai |
| `omnixon-lib` | Python client of this API, published on PyPI as `omnixon-lib` | httpx, pydantic |
| `unlink-telegram-bot` | Telegram bot that uses the lib | aiogram 3 |

Keep them consistent: **an API change usually means a lib change** (see "Keeping omnixon-lib in sync").

## Working agreements with the user (lixelv)

- The user writes **Russian**; answer in Russian. Code, comments, commit messages, docs: English.
- Work in **steps, one commit per step**, with a clear message ending in the trailer
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (use the attribution the harness gives).
  **Never push** unless asked ("push to dev" was an explicit request once). The branch is `dev`;
  `main` is the base for PRs. Do not rewrite pushed history.
- If something is unclear, **ask before building** (the user asked for this explicitly). Offer
  suggestions for improving the project; the user welcomes them.
- Report faithfully: what was verified, what was not, what went wrong. The user values root causes
  found by actually reproducing problems, not guesses.
- Local data is not valuable ("forget about the past DB"), but **never delete things you did not
  create** (see "Docker pitfalls": a Docker volume of the user's was lost once by mistake).

## Repository map

```
app/
  main.py                 FastAPI app, lifespan (PostgresPool), exception handlers, setup_logging()
  core/                   config.py (env), logging.py (JSON logs), masking.py (secrets), errors.py
                          (exception -> HTTP status), metrics.py (Prometheus), tools.py (tool names),
                          decorators.py
  database/
    foundation.py         PostgresPool (pool, migrations runner, seeding) + low-level fetch/execute
    context.py            PostgresConnectionWithContext: per-request DB access + Context(agent,token,user)
    methods.py            PostgresDB = all mixins + insure_user
    mixins/               one mixin per entity: agent, agent_version, token, user, message, rag, model,
                          mcp_server, memory
    models.py             pydantic row models (Agent, AgentConfig, Token, NewToken, User, Message, RAG, Model, MCPServer, Memory); ROLES/RANK/token_hash
    retention.py          deletes messages older than MESSAGE_TTL_DAYS (background task, batches)
    migrations/<n>.sql    the schema, applied in order
    schema.reference.sql  CURRENT state for humans to read — NOT used for migrating
  ai/
    endpoint.py           agent_endpoint (JSON) and agent_stream_endpoint (SSE), system prompt building
    agent.py              generate_agent(model, mcp_servers, tools): pydantic-ai Agent + RAG tool
    memory.py             memory prompt block, remember/recall/forget tools, embeddings, near-duplicates,
                          auto_memory extraction, embedding backfill
    resilience.py         provider retries, dead MCP servers (probe + temporary exclusion)
    attachments.py        Attachment model (url|data), pydantic-ai content, history notes
    utils.py              generate_model (request_json -> OpenRouterModel), build_mcp_server,
                          get_conversation_history, embeddings, proxy http client
  access.py               WHO MAY DO WHAT: roles, require(role), ensure_agent_access, can_manage_token, GRANTS
  middlewares/postgres.py PURE ASGI middleware: Bearer token -> request.state.db, request log + metrics
  routers/                main.py (request/user/history) and admin.py (agent/agent_version/model/
                          mcp_server/token/rag/memory/usage); health.py (/healthz /readyz /metrics, no token);
                          request/response pydantic models live next to their routes
  tests/                  conftest.py (fixtures), shared.py (helpers/constants/fakes the files share), and one file per aspect:
                          test_api_*.py = HTTP tests against the running stack, test_unit_*.py = logic, migrations (scratch DBs),
                          logging, masking, tools (no API needed). pytest config (pythonpath=app, testpaths) is in pyproject.toml
  ai/test/                IGNORED by git (.gitignore has `test`): local scratch, do not rely on it
docker/                   Dockerfile.{api,test,env,mcp-calculator}, docker-compose.{test,dev,prod}.yaml,
                          mcp-calculator/server.py (tiny MCP server used by tests), and the two server deploy
                          files docker-compose.{prod,dev}-deploy.yml (Swarm / dev server, from another team
                          member; they pass env and use `uvicorn`; used by the pipeline, not by the tests)
.gitlab/ci, .gitlab-ci.yml            build + promote + deploy pipeline (watches app/**, pyproject.toml, uv.lock);
                          the deploy jobs name their compose file as `docker/docker-compose.<env>-deploy.yml`
.github/workflows/test.yml            CI: builds the test stack and runs the tests
scripts/dump_openapi.py   writes the OpenAPI snapshot used by omnixon-lib's contract test
pyproject.toml, uv.lock   dependencies (uv). No requirements.txt any more.
```

## Domain model

- **Model** (`models`): a JSON that is an *OpenRouter request body*: `{"model": "...", ...}`. Model `0`
  is the default, seeded from `DEFAULT_MODEL` on first start. Key mapping lives in `ai/utils.py`
  (`model_settings`): OpenRouter options (`provider`, `models`, `preset`, `transforms`, `reasoning`,
  `usage`) -> `openrouter_<key>`; sampling keys (`temperature`, `top_p`, `max_tokens`, `seed`,
  `presence_penalty`, `frequency_penalty`, `logit_bias`, `parallel_tool_calls`, `stop`) -> pydantic-ai
  settings; **everything else is sent as `extra_body`**. A tiny `max_tokens` on a reasoning model (e.g.
  12 on glm) yields an empty answer and a 502.
- **Agent** (`agents`): `prompt`, `model_id` and **`config` JSONB**. An agent made for the initial token (`ensure_initial_token`, name "Default agent") starts with an **empty prompt**; an empty prompt sends no system message at all (only the memory instructions, when the tool is on). Default config
  `{"tools": ["rag", "memory"]}`; optional `message_limit` (latest messages given to the model, also the
  size of the `GET history` window), `memo_limit` (memories shown at once; >= 1) and `auto_memory`
  (bool; **unset = on**, env `DEFAULT_AUTO_MEMORY`; see Memory). Unset limits fall
  back to env `DEFAULT_MESSAGE_LIMIT` (10) / `DEFAULT_MEMO_LIMIT` (20). The API returns only what is
  stored. On PATCH only given config keys change; **`null` removes a key** (back to default).
- **There are no units any more** (migration 11 turned each into a token). The main entity is the **agent**, and access is a **token** bound
  to it:
  - `roles(name, rank)`: **regular < user < admin < owner**. `tokens(id, name NOT NULL, agent_id NOT NULL, role, token_sha256 UNIQUE, timestamp)`.
    **Only the sha256 of a secret is stored**; the secret (`<3>_<60>` chars) is returned once, in the answer to `POST /admin/tokens`
    (`NewToken.token`); `Token.token_sha256` is `exclude=True`. A token's role can be changed with `PATCH /admin/tokens/{id} {role}` (up to what the caller may hand out and only for tokens it may manage; a token cannot change its own role, the initial token stays an owner: 409). An agent with tokens
    cannot be deleted (409). Deleting a token stops it at once.
  - The **initial token** = `INITIAL_API_KEY`: made/raised to `owner` at start (`ensure_initial_token`, own agent "Default agent");
    `Token.is_initial` is computed from the hash; it can be neither deleted nor lowered (409). A token cannot delete itself (409).
  - `access.py` is the whole permission model (read it before touching a route). **regular**: main API (`/request*`, users, history,
    `/tokens/self`, `/agents/self`). **user** (+ everything below on its OWN agent only): the agent (read/PATCH/versions/rollback), its
    knowledge base, memories, MCP servers (`POST /mcp-servers` attaches to the own agent at once; edit/delete only if attached to the own
    agent AND to no other; read if attached; detach OK; attaching an existing one is admin-only), users and messages (main API), tokens of the
    agent (list/make `regular` and `user`/rename/delete up to `user`), usage of the tokens of its agent, `GET /models` (it may pick one
    with `PATCH agent {model_id}`; it cannot make/change models). **admin**: any agent, models, MCP list, tokens of any agent up to `user`,
    all usage, and **acting as another agent** (`X-Act-As-Agent: <id>` -> `context.agent`; 403 below admin, 404 unknown; the role and the
    usage stay the caller's). **owner**: tokens of any role (`GRANTS` in access.py: regular 0, user 2, admin 2, owner 4).
    Routes are gated by `Depends(require(role))` (the admin router needs `user` at least) and by `ensure_agent_access` /
    `default_agent_id` (agent ids in paths/params) inside handlers. **A new route must be given a role and, if it takes an agent id, a scope
    check; add it to `_cases` in tests/test_api_roles.py** (`test_every_role_is_stopped_at_the_door_it_may_not_pass`).
  - Tests: `test_every_role_*`, `test_which_roles_a_token_may_hand_out`, `test_which_tokens_a_token_may_rename_and_delete`, mcp/rag/memory
    scope tests (HTTP), and `tests/test_unit_access.py` (access matrix, migration 11 on legacy data).
- **User** (`users`): `external_id` (<= 64 chars) per **agent** (`users.agent_id`; the same id on two agents is two users). There is no list of all users; `GET /users?query=` finds the
  users **of the agent in context** whose id **starts with** `query` (at least 3 characters, `limit` <= 50, sorted; `%` and `_` are
  literal; served by the `(agent_id, external_id text_pattern_ops)` index), for suggestions in clients. `GET /users/recent` (`recent_users`, model `RecentUser` = User + `last_active` + `messages`) lists the agent's users that have messages still kept (`MESSAGE_TTL_DAYS`), latest first: derived from `messages`, so there is nothing to keep in sync (the panel used localStorage before). It must stay declared BEFORE `/users/{user_id}`. `user_id` empty/omitted on `/request` creates a
  user (uuid4 hex) and returns it as `response.user`.
- **Names**: `agents`, `models`, `mcp_servers` have a nullable `name` column (migration 10); a token's name is required and stored (NOT NULL). It is **required on create**
  (`Name` = trimmed, 1-120 chars, in the routers) and optional on update (`COALESCE`, so it cannot be blanked). Row models
  (`database/models.py`, base class `Named`) always return a non-empty `name`: stored name, else the fallback - Model: `request_json["model"]`
  (else `Model <id>`), MCPServer `MCP <id>`, Agent: `prompt_title(prompt)` (first non-empty line, 60 chars) else `Agent <id>`.
  Rows made internally (rollback copies, the seeded model 0) have a NULL name and so show the fallback.
  A name is not behaviour: it is not part of the version snapshot, and renaming records no version.
- **Self endpoints** (main API, any role): `GET /api/v1/tokens/self` (id, name, role, agent_id, is_initial) and `GET /api/v1/agents/self`
  (the agent in context, i.e. the acted-as one). The admin panel signs in with them to learn the role.
- **Usage** (`usage_logs`, `usage_monthly`; `ai/usage.py`, `database/usage_compaction.py`, `routers/usage.py`): every model call is written on the
  **token that made the request** (also when an admin acts as another agent): `kind` request|stream|auto_memory, `model`, `status` (ok | HTTP
  status | cancelled), `duration_ms`, input/output tokens, `cost` (NULL when the provider did not say) and the token's name. **No texts are
  stored.** Cost comes from OpenRouter (`usage: {include: true}` is set in `generate_model` unless the model says otherwise; it is
  `ModelResponse.provider_details["cost"]`). pydantic-ai leaves token counts at 0 for models without a price table, so `ai/utils.py`
  patches `pydantic_ai.models.openai._map_usage` to take them from the response (a real request test guards it). It also makes the OpenRouter response types accept any `service_tier` (a provider answered `provisioned`, which the OpenAI literal refused, failing the whole answer): `_accept_any_service_tier`. Rows older than
  `USAGE_TTL_DAYS` (30) are folded into one `usage_monthly` row per (token, month, model) that never expires (`compact_usage`, a background
  task); a deleted token's rows stay with `token_id` NULL and its old name. `GET /admin/usage` (days, token_id, agent_id; by day/token/model)
  and `/admin/usage/monthly`; a user token sees the tokens of its own agent, admin all.
- **Agent versions** (`agent_versions`): every change that alters behaviour (prompt, model, config, MCP
  attachments, and edits of the model/MCP records the agent uses) adds a numbered version holding a
  **snapshot with copies** of the model `request_json` and the MCP configs. `record_agent_version` only
  inserts when the snapshot differs from the latest; call it after every such mutation (routers do).
  Rollback reuses the model/MCP records when unchanged, else creates new ones (never edits shared records)
  and is itself recorded as a new version. `expected_version` on PATCH gives optimistic locking (409).
- **Chat** (`chats`, migration 13; `ChatMethods`, `routers/chat.py`): `user_id`, `title` (NULL = the start of the first message, set once by `touch_chat`, not for the default chat; the model always shows a non-empty fallback `Default chat` / `Chat <id>`), `is_default` (at most one per user: where a request without `chat_id` goes, made lazily by `ensure_default_chat`; the old `/users/{id}/history` routes are its history), `updated_at` (latest message). **Every message belongs to a chat** (`messages.chat_id NOT NULL`, `context.chat`): the history given to the model, the window `message_limit` and clearing are per chat; the memories stay per (user, agent). `/request*` take `chat_id` (404 for a chat that is not the user's) and `MessageResponse.chat_id` says where it was written. The interrupt registry is still per (agent, user): one answer streams to a user at a time, whatever the chat. Deleting a user or a chat deletes the messages (cascade).
- **Message** (`messages`): history rows `{"type": "user"|"assistant", "content": ..., "attachments": [notes]}`
  plus `agent_version`. Messages **expire**: older than `MESSAGE_TTL_DAYS` (7) are ignored on read at once
  and deleted by a background task. Memories do not expire.
- **Memory** (`memories`): facts per **(user, agent)** with an `embedding` (never returned by the API). With
  the `memory` tool the model gets `remember`/`recall`/`forget`. **Memory is on by default** (the `memory`
  tool is in the default tools and `auto_memory` is on). **What is remembered goes in front of the user's
  message** as a `<Memory>…</Memory>` block (newest `memo_limit`; "Nothing is remembered…" when empty), built
  per request in `ai/endpoint._user_prompt`; it is NOT stored in the history and NOT in the system prompt, which
  only carries the static `MEMORY_INSTRUCTIONS` (so it stays cacheable and the same for every user). `recall` and `GET /admin/memories?query=` search **by meaning** (cosine
  distance <= 0.82, thresholds measured on text-embedding-3-small) then by words. `remember` drops only
  exact/near-verbatim restatements (<= 0.06): merely similar facts (<= 0.25) are saved and shown to the
  model so it can `forget` the outdated one (embeddings alone cannot tell "likes tea" from "does not like
  tea"). `auto_memory` (on unless an agent sets `false` or `DEFAULT_AUTO_MEMORY=false`): after a **saved**
  exchange a background call (`schedule_extraction`, one more model call per request) asks the model for
  new lasting facts (max 5, never known ones, only from what the user wrote and the answer). Without the embedding service memory still works (words only).
  Memories made before embeddings are filled in at start (`run_backfill`).
- **RAG** (`rag`): per-agent knowledge base, a table partitioned by `agent_id` (`rag_<agent_id>` is
  created lazily and dropped when the agent is deleted); search is cosine distance (`<=>`). `GET /admin/rag` **without `query` lists** all
  entries of the agent (`get_all_rag`, order by id, `limit` <= 1000, `offset`); with `query` it searches (`limit` <= 100, 422 above).
- **Agent connections** (`agent_connections`, migration 14; `AgentConnectionMethods`, `routers/agent_connection.py`, **admin+ only**):
  agent1 -> agent2 with a `description` (1-1000), unique pair, no self-loop, cascade on agent delete. A connection is part of agent1's
  behaviour: `connections: [{agent2_id, description}]` is in the version snapshot (`normal()` gives old snapshots `[]`, so no needless
  version), every create/PATCH/DELETE records a version of agent1, deleting an agent records one of each agent that called it, and a
  rollback restores agent1's connections (skipping agents that are gone). **Built-in tools** (`ai/agent_calls.py`, registered when the agent
  has outgoing connections, whatever `config.tools` says): `list_agents` (id, name, description) and `ask_agent(agent_id, request)`: the
  called agent runs IN PROCESS (`agent_run`, usage kind `agent_call`, same token) on the request text only (not the caller's conversation),
  as the user `agent_<caller id>:<id of the person the chain started with>` (a person id that does not fit 64 chars -> 16-char sha256), in
  that user's default chat. `access.call_chain` (ContextVar `CallChain(agents, human)`) keeps the chain: an agent already in it is refused,
  and at most `AGENT_CALL_DEPTH` (3) agents after the first. Access = `access.may_act_as` (shared with `X-Act-As-Agent` in the middleware):
  admin+ token, OR a connection from the previous agent of the chain to the target. Refusals and failures are the tool's result text,
  never an error of the caller. Tests: `test_unit_agent_calls.py` (FunctionModel scripts the calls), `test_api_agent_connections.py`, `_cases`.
- **MCP server** (`mcp_servers`) + `agent_mcp_servers`: external tool servers attached to agents. Config
  is `url`, optional `transport` (`streamable_http` default | `sse`) and the options in `ai.utils.MCP_OPTIONS`.

**Attachments**: `attachments` on `/request` and `/request-stream` (`url` or base64 `data`, `media_type`,
`name`; image/audio/video/PDF/text). Passed to the model after the text; the history keeps only a note
(kind/type/name, never the data or URL). The model must handle them (tests use `google/gemini-2.5-flash-lite`
for vision); a model that cannot gives a 502 with the provider's reason.

Request flags: `save_message` (store the exchange, default true) and `use_memo` (give the model the
previous messages, default true), `trace` (default false: also return the chain of calls, see below). `use_memo=false` affects **history only**; memory is controlled by the
agent's `tools`.

## Model connection and interrupting

- **Connection of a model** (migration 12; columns, NOT keys of `request_json`, which the router rejects): `base_url` (NULL = OpenRouter; the API
  always shows an effective one), `use_proxy` (default true; false = `_get_direct_client`, only matters when `OPENROUTER_PROXY` is set) and
  `api_token` (NULL = the deployment key). A non-OpenRouter `base_url` makes `generate_model` build a plain `OpenAIChatModel` (OpenRouter-only
  options then go to `extra_body`). `api_token` is `Field(exclude=True)` (never returned; `has_api_token` computed), masked in logs by name, and
  agent version snapshots hold only `model_connection {base_url, use_proxy, own_api_token: 8-char sha256 fingerprint}`; a rollback copy keeps the
  key of the record it replaces. PATCH: None keeps, `""` clears `base_url`/`api_token`.
- **Interrupt** (`ai/interrupt.py`): registry `(agent_id, user_id) -> ActiveStream`. `/request-stream` registers itself; `POST /users/{id}/interrupt`
  and any new `/request*` of the pair call `interrupt.stop`, which sets `wanted`, waits (<= 15 s) until the stream has saved
  (`save_interrupted`: user message + assistant message with `"interrupted": true` if something was said, and auto_memory) and returns. The source of
  chunks runs in ONE task of its own (`until_stopped`: producer + queue): a task per chunk broke pydantic-ai's anyio cancel scopes ("exit cancel scope
  in a different task") — found by the stream tests. Usage status `interrupted` is not an error. With `REDIS_URL` it works across replicas (`ai/interrupt_bus.py`: a running stream holds the key `omnixon:stream:<agent>:<user>` (TTL 30 s, renewed),
  Stop / a new request of the pair publishes on `omnixon:stop`, the owner replica stops and saves and answers on `omnixon:stopped:<id>` with what was said);
  without it, per process. **Swarm**: the api may run as several replicas (`API_REPLICAS` in the prod deploy file, Redis service `omnixon_redis` in both deploy files and
  the root compose): start-up is safe (migrations under an advisory lock, `ensure_initial_token` under one, the embedding backfill by one replica via
  `pg_try_advisory_lock`), background jobs are safe to run twice (usage folding is `DELETE ... RETURNING`), the MCP-down cache and metrics stay per replica.
  The test stack has a second replica `api2` (`API_URL_2`) and a test that stops a stream on one replica from the other.
- Tests use `docker/fake-llm/server.py` (`fake/pong*`, `fake/echo*`, `fake/slow*` = 40 words 0.25 s apart; `/log?model=` shows what it received, e.g. the
  Authorization header) through `FAKE_LLM_URL`.

## Request flow

`DatabaseMiddleware` authenticates the Bearer token -> `request.state.db` (a `PostgresDB` with
`Context`), logs one JSON line per request -> router -> `agent_endpoint` / `agent_stream_endpoint`:
build system prompt (agent prompt + memory block) -> history -> `generate_agent` (model, MCP toolsets,
tools) -> run -> store messages (+ `auto_memory` in the background). `ai/resilience.py` wraps the run:
**provider failures that may pass (5xx, 408/429, timeouts, dropped connections, empty answers) are retried
twice more** (pause 1 s, 2 s) **from where the run broke** (`ai/resume.py`: the complete messages of the failed attempt are kept and the next one
continues with them, so tools that already returned are NOT called again; usage, history and trace cover all attempts; a stream that already sent
text is not restarted); 4xx such as a bad model name fail at once. **An MCP server never breaks
the agent**: when a run fails with an MCP-looking error (the server is down at the start) the servers are probed,
dead ones are left out (and stay out `MCP_DOWN_SECONDS`, with the reason), the run continues with the rest, and
the model is told in the run's `instructions` which servers are missing and why (`_unavailable_servers_note`), so
it can say so. **A failing tool call never ends the answer** (`ai/mcp_calls.py`, pydantic-ai's `process_tool_call`,
set by `build_mcp_server`): a tool that answered `isError` gives its text to the model at once (same arguments, same
result); a call that did not get through (connection, timeout, HTTP, MCP protocol error) is tried `MCP_TOOL_ATTEMPTS`
(3) times, the later ones over a new connection, then the model gets "could not be called: 3 attempts failed. Last
error: MCP error 408: ..." as the tool's result. Metric `omnixon_mcp_tool_errors_total{kind=refused|failed}`.
pydantic-ai raises `ModelRetry` for both an `isError` result and a protocol error; only the latter has an `McpError`
as `__context__` (`_refused`). Verified live: a 404 of a tool, a 2 s `read_timeout` (3 attempts, ~9 s, answer goes
on) and the MCP container stopped (answer names `ConnectError`). A retried call may run twice if the first got
through and only its answer was lost (Omnixon's own `/request` is cancelled with its client, so no duplicates there). `REQUEST_TIMEOUT_SECONDS` bounds a request
(504). **A request whose client has gone away is cancelled** (`_until_disconnect`): this required the
middleware to be plain ASGI, because `BaseHTTPMiddleware` hides the disconnect from the route; a
disconnect also ends a stream. Streaming uses `agent.iter` (NOT `run_stream_events`, whose background
task fails noisily on client disconnect) and yields text deltas, with a blank line between text parts of
different model turns. SSE protocol: `event: user`, (with `trace`: `event: trace` steps as they finish), `data:` chunks (JSON strings), then `event: done`
(or `event: error` with `{"detail"}`). Failures after the 200 header can only be reported as `event: error`.

**Trace** (`ai/trace.py`): with `trace: true` the response has `trace` (a list of `TraceStep`: `kind` model|tool,
`name`, `args`, `result`, `text`, tokens, `duration_ms`, `error`) and the stream sends `event: trace` per step. It is
built from the pydantic-ai messages of the run (`Tracer.feed` at each node of `agent.iter`), so it costs nothing;
results are clipped to 4000 characters. `agent_run` returns the steps, `agent_endpoint` is its text-only wrapper.

Errors: `core.errors.error_response` maps exceptions to a status. Provider/MCP failures (including
inside anyio `ExceptionGroup`s) are **502**, timeouts **504**, everything else 500. Known DB constraint
violations are mapped explicitly in routers (`asyncpg.ForeignKeyViolationError` -> 404/409).

## Database rules

- **Migrations**: files `app/database/migrations/<n>.sql`. Table `migrations` has ONE row with the last
  applied number (created by `0.sql`). On every start `PostgresPool.run_migrations` applies files with a
  number greater than the accumulator, in order, each in its own transaction, under a Postgres advisory
  lock (replicas can start together). **Never edit an applied migration; add the next number.** Then
  update `schema.reference.sql` by hand. Current head: **14** (0 baseline, 1 drop store_history, 2 tools,
  3 memories, 4 agents.config, 5 drop units.ip, 6 agent_versions + messages.agent_version, 7 message indexes,
  8 memories.embedding, 9 prefix index on users for the id suggestions, 10 nullable `name` on agents/models/mcp_servers/units, 11 roles + tokens (sha256) replace units, users belong to agents, usage tables, 12 `models.base_url/use_proxy/api_token`, 13 chats, 14 agent_connections).
- **A connection is taken per query**, not per request (a request spends its time waiting for the model;
  holding a connection used to freeze the service at 10 slow requests). Never hold a connection across
  an LLM call; use `self.fetch_one/fetch_all/execute` from the mixins.
- **Atomic work uses `async with db.transaction():`** (in `database/context.py`): one pooled connection for
  the block, commit at the end, rollback on any exception; nested blocks are savepoints. Keep blocks short
  and free of model/network calls. Inside it `await db.lock(key)` takes a Postgres advisory lock held to the
  end of the outermost transaction, which puts work on the same thing in line. The pinned connection is a
  `ContextVar`, so only the code running in the block uses it — other tasks sharing the same `db` object
  (an agent's concurrent tools) keep using their own connections. Used for: the question+answer pair of a
  request (`create_messages`, lock `messages:<user>`, so concurrent requests of one user never interleave),
  agent change + its version (lock `agent-versions:<agent>`, also makes `expected_version` race-free),
  `create_agent`, rollback (all or nothing), MCP attach/detach, model/MCP edits + versions of the agents they
  change, and look-then-save of a memory (lock `memories:<user>:<agent>`: no duplicate facts from two
  requests at once). New multi-statement writes should use it too.
- **`@async_logfire_class_decorator` wraps every public COROUTINE method of `PostgresDB`** (it awaits and
  logs the call). Non-coroutine members — like `transaction()`, an async context manager — are left alone;
  methods starting with `_` are never wrapped. A plain sync helper is therefore safe now, but forgetting
  `await` on a wrapped method still silently does nothing.
- `asyncpg` returns JSONB as text: models decode it in `field_validator(mode="before")`; `map_value`
  dumps dicts to JSON on the way in. `fetch_all` returns `None` for no rows in some paths — use `or []`.
- Pool uses `statement_cache_size=0`; pgvector codec registered per connection.

## Operations

`/healthz` (liveness), `/readyz` (DB answers and is at the last migration, else 503) and `/metrics`
(Prometheus, prefix `omnixon_`; labels are route templates, never ids) need no token and are not logged as
requests. The image has a `HEALTHCHECK` on `/readyz`; the test stack waits for it. Add metrics in
`core/metrics.py` and keep labels bounded. **Labelled series expire**: wrap a labelled metric with
`expiring(...)`; a series (label combination) untouched for `METRICS_TTL_DAYS` is removed from the registry
when `/metrics` is rendered (unlabelled metrics are single series and stay).

## Logging and secrets

- `setup_logging()` (called in `main.py`) writes **JSON lines to stdout**: logfire logs, finished spans
  and stdlib `logging` records (uvicorn, httpx, ...). Fields: `timestamp, level, message, trace_id,
  span_id, source, attributes, duration_ms (spans), exception{type,message,stacktrace}`. Nested attributes
  are real JSON. `LOG_LEVEL` (default `info`); `debug` also logs every route/DB call with arguments —
  masked, but still verbose. `LOGFIRE_TOKEN` additionally ships logs to logfire. The API is started with
  plain `uvicorn` so no banner precedes the JSON.
- `core/masking.py` masks secrets in every log line: values under sensitive names (token, password,
  api_key, authorization, ...), the deployment's secrets from env (`SECRET_ENV_VARS`), Bearer credentials,
  tokens, provider keys, URL passwords. Debug logging masks call arguments **by parameter name** and
  logs non-data objects by type. A token's secret is returned once, when it is made, and never again.
- Use `logfire.info/warning/exception(..., _exc_info=exc)`; never `print`. Upstream (502/504) failures log
  at **warn**, real server errors at **error**: an `error` line in a test run means a real bug — the JSON
  error log has repeatedly pointed at real defects, so check it after every test run.

## Configuration (env, see `.env.example`)

`APP_NAME, UPSTREAM_PORT, POSTGRES_{HOST,PORT,USER,PASSWORD,DB}`, `OPENROUTER_API_KEY` (pydantic-ai reads it
itself; `OPENROUTER_TOKEN` in config is effectively unused), `INITIAL_API_KEY`, optional `OPENROUTER_PROXY`
(`http(s)://` or `socks5://`, needs `httpx[socks]`; applies to LLM **and** embeddings; the tests route
everything through a SOCKS5 proxy container), `DEFAULT_MODEL` (JSON body or plain name),
`DEFAULT_MESSAGE_LIMIT`, `DEFAULT_MEMO_LIMIT`, `DEFAULT_AUTO_MEMORY` (true), `MESSAGE_TTL_DAYS` (7; 0 = forever),
`MESSAGE_CLEANUP_INTERVAL_SECONDS`, `USAGE_TTL_DAYS` (30; 0 = never fold), `USAGE_COMPACT_INTERVAL_SECONDS`, `METRICS_TTL_DAYS` (7; 0 = forever), `REQUEST_TIMEOUT_SECONDS` (600), `UPSTREAM_RETRIES` (2),
`UPSTREAM_RETRY_DELAY` (1), `MCP_PROBE_TIMEOUT` (5), `MCP_DOWN_SECONDS` (30), `MCP_TOOL_ATTEMPTS` (3) and `MCP_TOOL_RETRY_DELAY` (1,
doubling) for MCP tool calls that do not get through, `MCP_TOOL_RETRIES` (3: pydantic-ai's retries when the model writes a tool's
arguments badly, e.g. not valid JSON; its default 1 failed whole answers with "Tool ... exceeded max retries count of 1"; a server's
own `max_retries` wins), `REDIS_URL` (unset: one process), `AGENT_CALL_DEPTH` (3), `LOG_LEVEL`, `LOGFIRE_TOKEN`.

## Dependencies and running

Managed with **uv** (`pyproject.toml` = direct deps, pinned with `==`; `uv.lock` = everything). Python 3.11.

```bash
uv sync --group test                         # .venv with everything
uv add <pkg>                                 # add a dependency (updates pyproject + uv.lock)
uv run uvicorn --app-dir app main:app --reload   # needs Postgres (pgvector) and env vars
```

Docker images use `uv sync --frozen` into `/opt/venv` (outside `/app`, so the dev volume mount keeps it);
the uv image tag is pinned (`ghcr.io/astral-sh/uv:0.8.22`). `.dockerignore` keeps `.env` out of images.

## Testing

Always run the full stack before declaring something done. **Use an isolated compose project name** and an
override that unpublishes the DB port (the user's own Postgres/containers already use 5432/8000):

```bash
# override.yaml (kept outside the repo):  services: { db: { ports: !reset [] } }
cd docker
export APP_NAME=omnixon_verify
C="docker compose -p omnixon_verify -f docker-compose.test.yaml -f /path/to/override.yaml --env-file .env"
$C up --build --abort-on-container-exit --exit-code-from tests   # run tests (~90s, uses real OpenRouter)
$C down -v                                                       # ONLY with -p omnixon_verify
```

- The test stack: `api`, `db` (pgvector pg16), `socks5-proxy`, `mcp-calculator`, `tests`. `docker/.env` is
  what the API container reads (CI copies `.env` to it); pass `--env-file .env` from the **docker/**
  directory so the DB password matches. UPSTREAM_PORT in the local file is 8083.
- `tests/test_api_*.py` (HTTP, order-marked, **real LLM calls**, an LLM judge at temperature 0 for a few tests) and
  `tests/test_unit_*.py` (no API; scratch databases created on the test Postgres). Last full run: **391 passed** (~4 min; run the test stack with an override that also unpublishes the api port when the user's stack holds 8083). Tests that need the
  embedding service or a vision model call the real providers.
- Fast local loop for the unit tests: start `pgvector/pgvector:pg16` on a spare port and
  `POSTGRES_HOST=localhost POSTGRES_PORT=<p> POSTGRES_USER=postgres POSTGRES_PASSWORD=pw POSTGRES_DB=postgres
  INITIAL_API_KEY=x OPENROUTER_API_KEY=x uv run --group test pytest app/tests/test_unit_*.py
  --deselect app/tests/test_unit_migrations.py::test_api_database_is_at_the_latest_migration`.
- Live-probing the stack with a script (httpx) found most of the real bugs; do that for new features, and
  read the API container's JSON logs afterwards (`docker logs`, filter `"level": "error"`).
- Test pitfalls found: leaving `async for line in res.aiter_lines()` with `break` **closes the connection**
  (the server then cancels the stream), so assert on a live stream inside the loop; an LLM judge rejected
  correct "exactly two sentences" answers, so that check is in code; reasoning models give an empty answer with a
  tiny `max_tokens` (502).
- Prefer deterministic tests (history length, status codes, fake DB + pydantic-ai `TestModel`) over LLM-judged ones.

## Docker pitfalls (learned the hard way)

- **`docker compose down -v` without `-p`/`APP_NAME` override resolves the project name from
  `docker/.env` (`APP_NAME=unilink`) and deletes the user's `unilink-postgres-data` volume.** This
  happened once. Always `-p omnixon_verify`.
- `docker run --env-file` keeps literal quotes from `.env`; compose strips them.
- Compose project/volume names derive from `APP_NAME`; ports 5432/8000 on the host belong to other things.
- zsh does not word-split `$VAR`: use `${=VAR}` or a function when a variable holds a command.
- macOS BSD `sed -E` has no `\s` (use `[[:space:]]`) — a CI step once relied on it.

## Keeping omnixon-lib in sync

Changing a request/response model or a route means updating `../omnixon-library` (models, client methods,
README, tests) and bumping its version. The lib has a **contract test** against an OpenAPI snapshot:

```bash
uv run python scripts/dump_openapi.py ../omnixon-library/tests/server_openapi.json
cd ../omnixon-library && uv run pytest
```

Then verify the built wheel against the running stack (install `dist/*.whl` into a clean venv, drive every
method), as was done for each lib release.

## Status (update this section when it changes)

- Latest work (all committed, not pushed): agent versions, retries/timeouts/cancellation/dead-MCP handling,
  health + metrics, message TTL, smart memory + auto_memory, attachments; then: memory on by default and
  memories moved from the system prompt into the user's message.

- Branch `dev`; the user pushes themselves. `origin/dev` is at `f381ffe`; the commit "Fix bugs found by
  probing the running service" is local only.
- omnixon-lib is at **3.2.0** (not yet on PyPI from this session); the bot pins `omnixon-lib>=3.0.0` and has
  no `uv.lock` until the lib is published (then `uv lock` in the bot repo).
- Done in this line of work: models/MCP/SSE streaming/proxy, migrations, per-request `save_message`/`use_memo`,
  agent `config` (tools/limits), memory tool, user auto-creation, uv, JSON logs + masking, bug-hunt fixes.

## Ideas / not done

- Rate limits and token expiry/rotation were suggested and deliberately
  skipped: the service is internal and trusted ("everyone trusts everyone").
- Prompt versions have no canary/pinning yet (variant B: tokens pinned to a version) — the table is ready for it.

- `.github/workflows/test.yml` still sets up Python although only Docker is used.
- `requests` with an empty `request` string are forwarded to the model (works, wasteful).
- A retry after a provider failure re-runs tool calls the model already made (memory dedupe and idempotent
  tools make this harmless today).
- Documents (PDF) as attachments depend on the provider/model; only images are covered by tests.
- The `retries=2` argument in `ai/agent.py` triggers a pydantic-ai deprecation warning (`tool_retries`).

## Rename (Unilink -> Omnixon)

The product is called **Omnixon** now (omni = many services into one, xon = axon, one brain). Renamed in code: the Python package/import `omnixon`
(PyPI `omnixon-lib`, a NEW PyPI project: nothing of `unilink-lib` carries over), the Prometheus prefix `omnixon_`, env vars (`OMNIXON_*`), compose
project and container names, the default `APP_NAME`/database names, panel texts and localStorage keys (`omnixon.token`, `omnixon.baseUrl`: everybody is signed out once). NOT renamed on purpose:
the GitLab project path `unlink/unilink-api` and the GitHub mirror `europrom-injectors/unilink` (the user renames the remotes; the local folders are `omnixon-backend`, `omnixon-library`, `omnixon-frontend` now), the Swarm/CI deploy
files of the other team member (`.gitlab/`, `docker/docker-compose.*-deploy.yml`: stack `unilink`, service `unilink_api`, job `unilink_promote_job`), the GitHub secret names `UNILINK_TOKEN` / `UNILINK_BASE_URL` of the bot, and
statements about the user's real `.env` / Docker volume (`unilink-postgres-data`), which are still called as before until they change them.

---

# Library (omnixon-library)

Briefing for an agent working in this repository. `README.md` is the user-facing reference of the
methods; this file explains the project, its rules and its traps. The service this library talks to lives in
the sibling repository **`../omnixon-backend`** (read its `AGENTS.md` too); a Telegram bot that uses this library
lives in **`../../unlink-telegram-bot`**.

## What this is

`omnixon-lib` is the async Python client for the **Omnixon** service (an API that unifies LLM interaction:
history, memory, knowledge base, MCP tools, streaming). Published on PyPI as **`omnixon-lib`** (import name
`omnixon`). It is a thin, typed wrapper: one method per endpoint, pydantic models for every payload.

Current version: **4.2.0** (set in `pyproject.toml`; 4.1.0 `AgentConfig.rag_limit`, 4.2.0 agent connections: `get_agent_connections(agent_id=None)`, `create/get/update/delete_agent_connection`, `AgentConnection`). **Not published from this work**: PyPI's latest is
1.2.1 (as seen earlier); 2.x and 3.x only exist locally/in git. Publishing is done by the user through a
GitHub release (see below). The bot pins `omnixon-lib>=3.0.0`.

## Working agreements with the user (lixelv)

- The user writes **Russian**; answer in Russian. Code, comments, commit messages, docs: English.
- **One commit per step**, clear message, with the trailer
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. **Never push** unless asked.
- Ask before building when something is unclear; offer improvement suggestions.
- Report faithfully what was verified and what was not.
- Never delete files you did not create (the repo has git-ignored local files: `config.py`, `temp/`,
  `a.py`, `a.xml`, `dist/`).

## Layout

```
omnixon/
  __init__.py      public exports (Client, MessageStream, models)
  main.py          Client (all endpoints) and MessageStream (streamed answer)
  schemes.py       pydantic models: responses (User, Message, Agent, AgentConfig, Token, NewToken, Model, MCPServer,
                   Memory, RAG, MessageResponse) and request bodies (…Create/…Update, MessageRequest)
  exceptions.py    UnlinkError and subclasses
tests/
  test_client.py            unit tests: httpx.MockTransport, no network
  test_server_contract.py   the models must match the service (see below)
  server_openapi.json       SNAPSHOT of the service's OpenAPI schema (generated, do not edit by hand)
test.py            manual smoke script against a live server (needs git-ignored config.py: BASE_URL, TOKEN)
pyproject.toml, uv.lock     uv project; hatchling builds the wheel; dev group = pytest, pytest-asyncio
.github/workflows/publish.yml   on GitHub release: set version from tag, test, build, publish (all via uv)
```

## How the client works

- `Client(token, base_url)`; `base_url` is the service root WITHOUT `/api/v1` (the client appends
  `/api/v1/` and `/api/v1/admin/`). The constructor calls `check_connection()` synchronously (so creating
  a client needs a reachable server; a wrong token raises `NoAccess`).
- Every call goes through `Client._session(timeout)`: by default it opens its own `httpx.AsyncClient`; inside
  `async with Client(...)` (or after `__aenter__`) it reuses ONE shared pool (`self._http`), closed by
  `aclose()`/`__aexit__`; after closing, calls fall back to per-call clients. `_Session` injects the
  per-call default timeout (5 s plain, 120 s `LONG_TIMEOUT` for what waits for a model) so both modes
  behave the same. Never create `httpx.AsyncClient` directly in a method: use `_session`. Only
  `send_message`, `create_rag` and `update_rag` retry (`httpx.ReadError`, 3 times). Streams are **not**
  retried (a retry would restart a half-delivered answer). `send_message`/streams use a 120 s timeout.
- **Messages**: `send_message(user_id, message, retries=3, save_message=True, use_memo=True)`.
  `user_id=None` or `""` makes the service create a user, returned as `response.user`. `use_memo=False`
  skips the message history only (memory is controlled by the agent's `config["tools"]`).
  `stream_message(...)` returns a `MessageStream` (async iterator of text chunks; `.user` is set from the
  first `event: user`, so it is known even if the stream later fails; `StreamError` on `event: error`).
  `send_message_stream(...)` is the same as a plain async generator of strings. All three take
  `attachments` (list of `Attachment` or dicts: images/PDF/audio/video as `url` or base64 `data`;
  `Attachment.from_file/from_bytes/from_url`); the model must be able to handle them.
- **Agents**: `config` is `{"tools": [...], "message_limit": int, "memo_limit": int}`, every key optional,
  as a dict or `AgentConfigInput`. `create_agent`/`update_agent` build their models from the **given**
  values only (`_given`) and send `model_dump(exclude_unset=True)`, so a key set to `None` inside `config`
  is sent as `null` and **resets it to the default** on the service. Do not “simplify” this: it carries
  meaning. `Agent.config` is an `AgentConfig` (parsed, with defaults); config keys: `tools`, `message_limit`,
  `memo_limit`, `auto_memory`. `create_agent`/`update_agent` take `comment`; `update_agent` takes
  `expected_version` (Conflict when the agent moved on).
- **Agent versions**: `get_agent_versions`, `get_agent_version`, `diff_agent_versions(agent_id, number, to=None)`,
  `rollback_agent(agent_id, to, comment=None)`; `Message.agent_version`. **Memory**: `get_memories(..., query=)`
  searches by meaning. `ready()` asks `/readyz` without a token.
- **Errors** (all `UnlinkError`, with the service's `detail` as message when it gave one):
  `NoAccess` 401/403, `NotFound` 404, `Conflict` 409, `InvalidRequest` 422, `UpstreamError` 502/504
  (model provider or MCP server failed/timed out; the service is fine), `StreamError`,
  `ConnectionError`. Anything else falls through to `httpx.HTTPStatusError`.
- Admin methods need a token of a high enough role (user: its own agent; admin: any; owner: tokens of any role); the service refuses the rest with `NoAccess`. `Client(..., act_as_agent=)` sends `X-Act-As-Agent`.

## Tests and the contract with the service

```bash
uv sync            # .venv incl. the dev group
uv run pytest      # 81 tests: client behaviour + contract
uv build           # dist/*.whl and *.tar.gz
```

- `test_client.py` replaces `httpx.AsyncClient`/`httpx.Client` in `omnixon.main` with ones using
  `httpx.MockTransport`; add a test for every new method/parameter, including the exact JSON body sent.
- **`test_server_contract.py` compares every model with `tests/server_openapi.json`**: same fields, same
  types, same required-ness (`KNOWN_DIFFERENCES` lists the deliberate exceptions, e.g. `Agent.config`, which
  the service describes as a plain object but the lib parses into `AgentConfig`). A new service model must
  be added to `MODELS`. **When the service changes a model or route, regenerate the snapshot from the
  service repo and make the lib match:**
  `cd ../omnixon-backend && uv run python scripts/dump_openapi.py ../omnixon-library/tests/server_openapi.json`
- The unit tests prove the client builds correct requests; they do not prove the service accepts them.
  Verify real releases against a live stack: build the wheel, install it into a **clean venv** (run Python
  from outside the repo so the repo's `omnixon/` does not shadow the wheel), bring up the service's test
  stack (see `../omnixon-backend/AGENTS.md`, "Testing") and exercise every changed method. That was done for each
  release (user creation without id, flags, streaming + `.user`, memory, config partial updates and
  resets, error mapping, MCP through the stream).

## Versioning and releasing

Semantic versioning. Latest: **4.0.0** (also in 4.0.0: chats (`get_chats`, `create_chat`, `get_chat`, `rename_chat`, `delete_chat`, `get_chat_history`, `clear_chat_history`, `chat_id=` on the message calls, `MessageResponse.chat_id`, `Chat`), user ids are URL-quoted in paths; `get_recent_users(limit)` -> `RecentUser`, `update_token(role=)`, `interrupt(user_id)` -> `Interrupted`, `MessageStream.interrupted`, `Model.base_url/use_proxy/has_api_token`, `create_model`/`update_model` take `base_url`, `use_proxy`, `api_token`; units are gone: `Token`/`NewToken`/`Role`, `create_token` (secret once), `get_tokens`, `rename_token`, `update_token(id, name=None, role=None)` (a token's role can be changed again), `delete_token`, `get_self_token`, `get_usage`/`get_usage_monthly`, `act_as_agent`; `User.agent_id`; `create_mcp_server(agent_id=)`; names: `name` is required in `create_agent`/`create_model`/`create_mcp_server`/`create_token` as the FIRST argument and optional in the `update_*`; `Agent/Model/MCPServer/Unit.name`; `list_rag`; `get_self_unit`/`get_self_agent` use the main API; breaking), 3.5.0 (3.2.0 was: agent versions, attachments, memory search, `auto_memory`, shared
connection, `ready()`; additive). History of this line: 2.0 (models/MCP/streaming; breaking vs 1.2.1), 2.x (memory,
request flags, config), **3.0.0** (breaking: `Unit.ip` and the old agent fields removed, typed
`AgentConfigInput`, contract tests, uv), **3.1.0** (`UpstreamError`), **3.2.0** (see above), **3.5.0** (`search_users`: users of your unit by the start of their id, 3+ characters; additive), **3.4.0** (`trace=True` on `send_message`/`stream_message`: `MessageResponse.trace`, `MessageStream.trace`, `TraceStep`; additive), **3.3.0** (`Unit.is_initial`, `create_unit(is_admin=)`, `update_unit(is_admin=)`: only the initial unit may give or take admin rights; additive). Bump with `uv version X.Y.Z` (it
updates `pyproject.toml` and `uv.lock`). Publishing = create a GitHub **release with tag `vX.Y.Z`**:
the workflow runs `uv version "${TAG#v}"`, `uv run pytest`, `uv build`, `uv publish` (secret `PYPI_TOKEN`
as `UV_PUBLISH_TOKEN`). `uv publish --dry-run` checks the artifacts without uploading.
Gotcha: BSD `sed` has no `\s`, which is why the workflow uses `uv version` instead of `sed`.

After publishing, the **bot** needs `uv lock` (it has no `uv.lock` yet because 3.x was not on PyPI).

## Status

- Local commits exist beyond the original repo history; nothing from this work is pushed unless the user did it.
- Last verification: 81 tests pass; the 3.2.0 wheel was installed into a clean venv and driven against the live
  stack (versions + conflict + rollback, image attachments in normal and stream mode, history note,
  semantic memory search, auto_memory, shared pool, `ready()`).
- `README.md` documents the methods; keep it in step with `main.py` (it lists every method and the errors).

## Ideas / not done

- No sync wrapper; no automatic retry on `UpstreamError` (a retry may help for 502/504).
- `test.py` is a manual smoke script, not part of the automated suite.

## Rename (Unilink -> Omnixon)

The product is called **Omnixon** now (omni = many services into one, xon = axon, one brain). Renamed in code: the Python package/import `omnixon`
(PyPI `omnixon-lib`, a NEW PyPI project: nothing of `unilink-lib` carries over), the Prometheus prefix `omnixon_`, env vars (`OMNIXON_*`), compose
project and container names, the default `APP_NAME`/database names, panel texts and localStorage keys (`omnixon.token`, `omnixon.baseUrl`: everybody is signed out once). NOT renamed on purpose:
the GitLab project path `unlink/unilink-api` and the GitHub mirror `europrom-injectors/unilink` (the user renames the remotes; the local folders are `omnixon-backend`, `omnixon-library`, `omnixon-frontend` now), the Swarm/CI deploy
files of the other team member (`.gitlab/`, `docker/docker-compose.*-deploy.yml`: stack `unilink`, service `unilink_api`, job `unilink_promote_job`), the GitHub secret names `UNILINK_TOKEN` / `UNILINK_BASE_URL` of the bot, and
statements about the user's real `.env` / Docker volume (`unilink-postgres-data`), which are still called as before until they change them.

---

# Admin panel (omnixon-frontend)

Briefing for an agent working here. `README.md` is the user-facing description. The service this panel
talks to is `../omnixon-backend` (read its `AGENTS.md`); its Python client is `../omnixon-library`.

## Working agreements with the user (lixelv)

- The user writes **Russian**; answer in Russian. Code, comments, commit messages, docs: English.
- One commit per step, trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (use the attribution
  the harness gives). **Never push** unless asked.
- Ask before building when something is unclear. Report faithfully what was and was not verified.

## What this is

A React SPA, no backend of its own. Every route of the Omnixon API is reachable from it. An API change in
`../omnixon-backend` (routes in `app/routers/`) means changing `src/lib/api.ts`, `src/lib/types.ts` and the page.

## Docker files

All of them are in `docker/`, like in the backend: `Dockerfile.panel` (build + nginx), `Dockerfile.e2e` (Playwright), `nginx.conf.template`,
`docker-compose.{e2e,local}.yaml`, the host example `docker-compose.yaml` and `init-db/`. The build context is the repository root
(`context: ..`, `dockerfile: docker/Dockerfile.panel`), `.dockerignore` stays in the root, and relative paths inside a compose file
are relative to `docker/` (the sibling service is `../../omnixon-backend`).

## Logo

One drawing: `public/favicon.svg` (a white U on a black tile, nothing else). The sidebar and the sign-in page show it through
`components/logo.tsx`, which is an `<img>` of that same file, so the favicon and the in-app logo cannot drift apart.

## Conventions (keep the panel uniform)

- New list page: `Page` > `PageHeader` > (`QueryBar`) > `DataTable` with `idColumn`/`createdColumn`/`actionsColumn` and
  `rowAction.*`; no `max-w-*` wrappers, pages fill the window. A page that is not one table scrolls inside `PageScroll`.
- New form: `FormDialog` + `FieldGroup` + `FormField` (it passes `id` to its single child, so the control must accept it).
  Toggles are `SwitchField`/`CheckboxField`. Pick from a short enum with `OptionSelect`, from entities with
  `OptionCombobox`, free text with suggestions (user ids) with `SuggestInput`.
- Write ids without `#`. Delete is `Trash2Icon` (via `rowAction.remove`), edit is `PencilIcon`. lucide imports use the
  `...Icon` names. Empty states are `EmptyState`, loading is `LoadingRows`, spinners are `ui/spinner`.
- `ui/table.tsx` was edited to take `containerClassName` (the sticky header needs the table container not to scroll);
  re-apply it if `shadcn add table` overwrites the file.

- Long text in a table cell (Agents' Prompt, Models' Settings) goes through `clip()` (`lib/format.ts`): at most 40 characters, the first 37
  and `...`, the whole text in the span's `title`. No `max-w-*` box around it: cells do not wrap (`whitespace-nowrap`), so a capped box let
  the text run over the next column; the column now takes the clipped text's width. e2e: `layout.spec.ts` (long prompts and model settings).
- **Agent graph** (`pages/agent-graph.tsx`, `/agent-graph`, admin+): React Flow (`@xyflow/react`) with React Flow UI's `components/base-node.tsx`
  (added by `shadcn add https://ui.reactflow.dev/base-node`) for the agent cards, a bezier edge with an arrow and a clipped label (`edge-label-<id>`),
  a static dot background, dagre (`@dagrejs/dagre`) left-to-right layout (positions are not stored: "Arrange" lays out again). Top right: Arrange,
  Add connection; dragging from a card's right handle to another card or clicking an edge opens `ConnectionDialog` (create / description / delete).
  e2e `agent-graph.spec.ts`.
- Every page behind the sign-in is `React.lazy` (`App.tsx`, a `Suspense` around the `Outlet` in `layout.tsx`): the first load is ~780 kB, not 2.7 MB; the
  front page and the login stay eager. A new page: `const X = lazy(() => import('@/pages/x'))`.
- e2e only via `npm run test:e2e`: `docker compose ... run e2e` does NOT start `fake-llm` (it is no dependency of `e2e`: model calls then
  answer 500 "Connection error") and without `--build` runs the specs baked into the OLD image. Last full run: 110 passed. `memories` and the
  RAG search-error test wait for the (keyless) embedding call to OpenRouter: a slow network fails them once in a while; rerun before blaming code.
- Column headings and mono values are styled in `src/index.css` (`[data-slot=table-head]`, `.value-mono`), not per page;
  don't give a header button its own `text-*`. Dialog footers: `DialogFooter` pulls itself out by a `p-4` dialog's padding,
  so `FormDialog` resets it (`mx-0 mb-0`); `e2e/design.spec.ts` checks it stays inside the card.
- `InputGroup` has `has-disabled:opacity-50`: a disabled button inside dims the whole group (the Playground composer
  overrides it). The chain of calls comes from the service's `trace` (see README); `chain-of-thought.tsx` is AI Elements
  adapted to Base UI (no Radix hook, `data-closed` attributes).

- **Pickers**: entities (agent, model, MCP server, token, version, user) are `Option`s from `lib/options.ts` (`icon`, `label`, `id`, `to`, `attrs`) and
  go into `OptionCombobox`: a list of cards with a search, and a compact card in the field once chosen. `attrs` with a `to` are links to
  the related entity, without one they are chips; **never join attributes into a string with `·` or `—`**. A link inside a card must not
  pick it (`keepOut` stops the click). `?open=ID` on Models and MCP servers opens that editor (`lib/use-open-param.ts`). Short enums
  use `OptionSelect`. User ids use `UserSuggest`: `GET /users?query=` (3+ characters, debounced) in ONE agent (`actAs` prop), disabled
  until that agent is known. The wrapper `ui/combobox.tsx` sets `disabled={false}` on its input, so pass `disabled` to `ComboboxInput` too.
  Recent users are per agent (`lib/recent-users.ts`).
- **Design = Vercel Geist**, all of it in `src/index.css`: the shadcn variables hold Geist tokens (hex values in comments name the
  token), `@theme inline` sets the radii (6 / 12 / 16 px) and `@theme` the shadows (dark scheme overrides them). Status colours are
  `bg-success` / `text-warning` / `text-destructive`, never Tailwind's palette. Menus (`dropdown-menu`, `select`, `combobox`) were
  changed to `rounded-xl` to match Geist's 12px menus; re-apply if `shadcn add` overwrites them.

## Things that already cost time

- **Tables are `components/data-table.tsx`** (TanStack Table **v8**, pinned: npm's `latest` is v9 with another
  API). TanStack caches a cell's value per row by `data`, so a value that depends on another query (a model
  name, a count) must be put INTO the rows with `useMemo`, never looked up inside a column accessor
  (`agents.tsx`, `models.tsx`). `actionsColumn()` gives icon buttons with aria-labels; a row click opens the editor.
- **`npx shadcn add` keeps writing `import { cn } from "cn"`** (an unrelated npm package): after every `add`
  run `grep -rl 'from "cn"' src | xargs sed -i '' 's#from "cn"#from "@/lib/utils"#'` and `npm rm cn`.
- Tech Text (`components/TechText.tsx`) is the React Bits component from `https://reactbits.dev/r/TechText-TS-TW.json`
  (canvas, no dependencies, fills its parent; colors are hex, so re-key it on theme change as the login page does).
- A screenshot taken in the same browser batch as a click can show the page before the dialog is painted;
  take it in a separate call.

- **shadcn style is `base-nova` (Base UI), not Radix.** Use `render={<Link />}` instead of `asChild`, and add
  `nativeButton={false}` to a `Button` that renders a non-button. `Select` shows the raw value unless the
  options are passed as `items` — use `OptionSelect` from `components/common.tsx`.
- The shadcn CLI once generated `import { cn } from "cn"` (an unrelated npm package). `cn` lives in
  `src/lib/utils.ts` (clsx + tailwind-merge); fix imports if `shadcn add` writes `"cn"` again.
- **A disabled TanStack query has `isLoading === false` and no data.** Render on `!q.data`, never `q.data!`
  after an `isLoading` check (this crashed the version dialogs).
- `useEffect(() => something())` must not return a value; use a block body when the call returns anything.
- The SPA's `/metrics` route must not be proxied to the service: the proxy exposes `/healthz`, `/readyz`,
  `/metrics` as `/_ops/*` (`ops()` in `api.ts`, `vite.config.ts`, `docker/nginx.conf.template`).
- The service has no CORS: browser → same-origin proxy → service. Do not call it cross-origin.
- `Agent.config.tools` is always present in responses (defaults filled in), so "default" and "explicitly the
  default list" look the same; `agent-form.tsx` handles it and avoids sending `tools: null` needlessly.
- The API has no list endpoints for users, messages or RAG entries (see README).

## Verifying

**E2E:** `npm run test:e2e` (then `npm run test:e2e:down`). The compose project is `omnixon_admin_e2e`, nothing is
published and the DB is tmpfs, so `down -v` is safe. The `docker/Dockerfile.e2e` image tag must equal the
`@playwright/test` version. Selectors: `Field` renders `role=group` named by its label (`field(scope, 'Label')`
in `e2e/fixtures.ts`); a `Button` with `render={<Link/>}` has `role=button`, not `link`; scope to
`getByRole('main')` when the sidebar has a same-named link. Tests share one DB and run serially with unique names.

`npm run build` and `npm run lint` are the static checks. For behaviour, run the real service and drive the
panel (the Vite dev server proxies to `OMNIXON_URL`). Quick isolated backend: a `pgvector/pgvector:pg16`
container on a spare port with `CREATE EXTENSION vector`, then in `../omnixon-backend`
`POSTGRES_HOST=localhost POSTGRES_PORT=<p> POSTGRES_USER=postgres POSTGRES_PASSWORD=pw POSTGRES_DB=postgres
INITIAL_API_KEY=<token> OPENROUTER_API_KEY=x uv run uvicorn --app-dir app main:app --port <p2>`.
Without a real OpenRouter key, model calls and embeddings (RAG, memory search) answer 502 — the panel shows it.
Do not touch containers or volumes you did not create (the user's `unilink` Postgres volume lives in Docker).

## Status

- All pages and endpoints implemented; verified against a live service (CRUD, versions/diff/rollback, errors,
  SSE parser against a fake stream). **Not verified:** a successful LLM answer, RAG create/update/search and
  semantic memory search (they need a real OpenRouter key).
- Playwright e2e tests (`e2e/`), run in Docker by `docker/docker-compose.e2e.yaml`; last run: see the end of the section (the stack also has a `fake-llm` container, built from `../omnixon-backend/docker/Dockerfile.fake-llm`, so streams can run and be cut without a key).
- **Roles, not units** (the service has no units any more; see its AGENTS.md): `useAuth()` gives `token` (id, name, role, agent_id), `role`,
  `atLeast(role)`, `isAdmin` (admin or owner), `agentId`. `components/nav-items.tsx` is the one table of pages with `minRole`/`onlyRole`
  (`groupsFor(role)` for the sidebar and dashboard, `canOpen(role, path)` for `App.tsx`'s `<Gate>`). Data hooks in `lib/data.ts` are
  `enabled` only for the roles the service lets through (models: user+, agents/MCP list: admin+, tokens: user+). **regular**: Dashboard,
  Playground, Users & history (its agent's users and their chats), Settings; **user**: plus My agent (`/my-agent` -> `/agents/<own>`), Usage, Knowledge base, Memories, Users & history,
  Tokens; **admin/owner**: everything, plus Agents/Models/MCP/Metrics and a picker for the agent to work as. The panel only hides what the
  service would refuse; the service is the authority. e2e `access.spec.ts` signs in with a token of every role (and asserts a regular token
  makes no `/admin` call).
- **Acting as an agent**: `components/agent-field.tsx`: `useActingAgent()` (URL `?agent=`, admin+ only, starts on the own agent) gives `actAs`
  (a number only when it is not the own agent) which `api.ts` sends as `X-Act-As-Agent` (users, history, requests). `AgentField` is the
  card picker for admin+ and a static card of the own agent for everybody else. Knowledge base and Memories use `agent_id` params instead.
- **Tokens page** (`pages/tokens.tsx`): list/create/rename/delete. `MAY_HAND_OUT` mirrors the service's grants (it only decides what is
  offered). The secret is in the answer of `createToken` only: `SecretDialog` shows it once (`DecryptedText` from ReactBits; test id
  `new-token`); it is never put in a query cache or list. **Usage page** (`pages/usage.tsx`): shadcn `chart` (recharts), data from
  `/admin/usage` (by day, token, model) and `/admin/usage/monthly` (folded months); KPI test ids `kpi-*`.
- **Voice** (`components/voice-recorder.tsx`, `lib/voice.ts`): MediaRecorder + an AnalyserNode drawn on a canvas for the live waveform (react-audio-visualize bundles React 18 internals and breaks the app), decoded and
  encoded to a mono 16-bit **WAV** (`audiobuffer-to-wav`) and attached as `audio/wav` (`Send` sends at once, `Attach` keeps it in the message).
  The e2e browser has a fake microphone (`playwright.config.ts` launch args + permission).
- **Front page** (`pages/landing.tsx`, English): for visitors who are not signed in, at `/`; Login (top left of the header) goes to `/login`
  (`?next=` keeps where they were going; `App.tsx` builds the router for both states). Built from ReactBits components copied into
  `src/components/` (`shadcn add https://reactbits.dev/r/<Name>-TS-TW.json`; after adding, the CLI may write `from "cn"` imports and a `cn`
  dependency: change to `@/lib/utils` and `npm uninstall cn`; it also asks before overwriting `card.tsx`: keep ours). ReactBits is also used in
  the app: `CountUp` (dashboard and usage), `ShinyText` (thinking), `DecryptedText` (secret) and `DotField` (the dotted backgrounds of the front page and the login, flat colour: **no gradients in the panel**, the user does not want them; do not add `GradientText`/`Aurora`/coloured spotlights).
  Avoid text-splitting components (BlurText, SplitText) on pages whose text e2e tests read.
- **Names**: the service always returns `name`; the panel shows it everywhere (`nameColumn`, `options.ts`). Derived values (agent name in a unit row)
  go into the rows via `useMemo` because TanStack caches cell values per row.
- **Cards in pickers** are `h-16` (`cardItem` in `components/form.tsx`) and the list is `max-h-[min(20.5rem, ...)]` (`cardList`): five whole cards.
- **KB import/export**: `lib/kb-json.ts` (format + validation), `components/kb-transfer.tsx`; e2e fakes `/admin/rag` because the test stack has no embeddings.

## Ideas / not done

- An MSW-backed unit test of `api.ts`; e2e for a real LLM answer, RAG create/search and attachments (needs a real OpenRouter key).
- Route-level code splitting (the bundle is ~670 kB).
- Show which agents use a model / MCP server (needs a reverse lookup the API does not offer).

- **Simple choices are cards too**: `OptionSelect` shows a list of simple cards (icon, name, `description`), like the entity pickers but with nothing to search (roles with `lib/roles.ts` icons, period, transport, auto memory, theme).
- **Usage empties are played out** (`ChartEmpty`): a period without requests replaces each chart with an explanation; no folded months says why and when they appear; months in
  between that had no usage are listed as "No usage" instead of vanishing.

- **Markdown and code** (`components/markdown.tsx`, `code-block.tsx`, `lib/highlight.ts`): the answers of a model (Playground, and the assistant side of a user's history) are
  rendered with `react-markdown` + `remark-gfm`: tables, task lists, strikethrough, links that open in a new tab. Raw HTML is shown as text, images become links, `javascript:` links
  are dropped by react-markdown. Fenced code goes to `CodeBlock`: language label, copy button, coloured by **shiki** (fine-grained, JS regex engine, languages loaded on demand from
  `@shikijs/langs/<name>`; add a language and its aliases in `LOADERS`/`ALIASES`). The theme is GitHub's own scope-to-colour mapping where every colour is a CSS variable `--syn-*`
  (index.css, GitHub's light and dark palette) and text/background/borders come from the panel's tokens, so the code follows the theme switch. The front page's code uses the same
  `CodeBlock`. Do not add `react-audio-visualize`-like libraries that bundle React 18 internals; check `ReactCurrentOwner` errors in the browser console after adding a UI library.
  e2e `markdown.spec.ts` mocks `/api/v1/request` (and shims the clipboard: the test panel is plain http). Only the answer is markdown; what the user types stays as typed.
- **Formulas** (`lib/math.ts`, `markdown.tsx`): `remark-math` + `rehype-katex` (+ `katex/contrib/mhchem` for `\ce{}`; css imported in `markdown.tsx`; `throwOnError: false`, `trust: false`,
  errors shown quietly as source in the muted colour, a few macros like `\degree`). remark-math alone is too strict for what models write, so `prepareMath` finds the formulas itself by
  pandoc's rules before parsing (`$` opens only before a non-space, closes only after a non-space and before a non-digit, a `$` after a space ends the search so prices stay text) and writes each
  in the one form remark-math reads: `$$..$$` always as a block of its own (text before it becomes its own paragraph; inside a list, quote or table row it is `$\displaystyle ..$`),
  `\(..\)` and `\[..\]` converted, an unclosed `$$` (a streamed answer so far) left as plain text. Code is untouched. This was measured on real model answers: with remark-math alone
  a streamed answer was in an error state in ~8% of its prefixes and had errors at the end; with `prepareMath` 0 of ~1000 prefixes and 0 errors at the end (the one error left was a real extra brace of the model).
  If formulas go red again, take a real answer, replay it prefix by prefix through `unified().use(remarkMath).use(rehypeKatex)` in node, and count `katex-error`.
- **Copying an answer**: an assistant bubble (Playground and history) has a `Copy answer` button; it copies the markdown source as the model wrote it, not the rendered text.
- **The chain of calls does not repeat what the model wrote** (the `text` of a model step): only model/tool names, time, tokens, and the tools' arguments and results.
- **A `Card` (overflow-hidden) inside a scrolling grid can be squeezed to its header** when the page is taller than the window (the Usage page's last card did: "Earlier months" showed only its title). Give such a scroll area `auto-rows-max` and the card `overflow-visible`; e2e `usage.spec.ts` checks the card is whole. Usage's two tables use `grid-cols-[repeat(auto-fit,minmax(min(100%,46rem),1fr))]`: side by side only when each fits a row on one line.

- **External model settings** (`pages/models.tsx`): a `Collapsible` (closed every time the dialog opens) with Base URL (empty = OpenRouter; the field's placeholder is the default),
  Use proxy and API token (password input; the service never returns the key, only `has_api_token`; "Remove the key of this model" sends `api_token: ""`).
  On update only changed connection fields are sent; copies do not copy the key.
- **Stop in the Playground** calls `POST /users/{id}/interrupt` (the stream then ends with `event: interrupted`, handled by `onInterrupted`; the bubble gets an
  "interrupted" badge); with no user yet or a non-stream request it falls back to aborting the fetch. History bubbles show `content.interrupted`.

- **Tokens page**: the edit dialog changes the name AND the role (`PATCH /admin/tokens/{id}`); the role picker offers what the caller may hand out and is disabled for
  the token in use and the initial one (the service answers 409). Agent cards in pickers show no tool chips. The hero of the front page fills the screen
  (`min-h-[calc(100svh-3.5rem)]`, the name + tagline centred in what is left above the example). `PageScroll` has 1px of padding so the ring of a card is not cut.
The recent users of the Users page come from `GET /users/recent` (`useRecentUsers`, query key `recent-users`; invalidated by create/rename/delete/clear/chat), derived from the messages the service still keeps — nothing is stored in the browser any more (`main.tsx` drops the old `omnixon.recentUsers.*` keys; those were unit ids that collided with agent ids). Only the token and the theme live in localStorage. `JsonEditor` keeps `rows` as a minimum height (field-sizing would shrink an empty box to its placeholder).

## Rename (Unilink -> Omnixon)

The product is called **Omnixon** now (omni = many services into one, xon = axon, one brain). Renamed in code: the Python package/import `omnixon`
(PyPI `omnixon-lib`, a NEW PyPI project: nothing of `unilink-lib` carries over), the Prometheus prefix `omnixon_`, env vars (`OMNIXON_*`), compose
project and container names, the default `APP_NAME`/database names, panel texts and localStorage keys (`omnixon.token`, `omnixon.baseUrl`: everybody is signed out once). NOT renamed on purpose:
the GitLab project path `unlink/unilink-api` and the GitHub mirror `europrom-injectors/unilink` (the user renames the remotes; the local folders are `omnixon-backend`, `omnixon-library`, `omnixon-frontend` now), the Swarm/CI deploy
files of the other team member (`.gitlab/`, `docker/docker-compose.*-deploy.yml`: stack `unilink`, service `unilink_api`, job `unilink_promote_job`), the GitHub secret names `UNILINK_TOKEN` / `UNILINK_BASE_URL` of the bot, and
statements about the user's real `.env` / Docker volume (`unilink-postgres-data`), which are still called as before until they change them.

- **Where a role starts**: `/` is only a redirect (`Home` in App.tsx, `homePath` in nav-items): regular and user tokens open on the Playground (`/chat`), admin and owner on the
  dashboard; the dashboard is `/dashboard` and is in the sidebar for everyone. A page the role may not open goes to the start of the role. After signing out the visitor lands on the front
  page (`signedOut` in lib/auth.tsx tells `ToLogin` not to keep the page they were on as `?next=`).
- **Playground settings** are in a dialog (`FormDialog`, "Change settings" button beside "Clear transcript"); a strip of badges above the transcript (`aria-label="Current settings"`,
  `data-testid="chat-user"`) shows what the next message goes with. E2E: `openSettings` / `closeSettings` / `singleResponse` in e2e/fixtures.ts (closing clicks the title first: an open list of
  suggestions hides the dialog from the page). In `models.tsx` the form state is updated with the functional form of `setDraft`, never from a closure.

- **Connections graph** (`components/connections-graph.tsx`, bottom of the front page, above the closing call to action): channels (Telegram, WhatsApp, Discord, Avito, VK, a website) -> Omnixon -> agents -> models.
  Cards placed by percentages over one SVG drawn in a 100 x 100 box (`preserveAspectRatio="none"`, `vector-effect: non-scaling-stroke`), so the curves meet the cards at any width; the dashes that run
  along the lines are `.graph-flow` in index.css (off for `prefers-reduced-motion`). The figure scrolls sideways inside its box below 40rem instead of squeezing. e2e checks the nodes, the 15 edges and that no cards overlap.
- The Playground's chat card is `flex-1` in its column: without it the card is only as tall as its content (half the window).
- When the backend working tree does not start (someone's unfinished edit), e2e can be run against the last commit: `git -C ../omnixon-backend archive HEAD | tar -x -C <dir>` and `OMNIXON_REPO=<dir>`.

- **Connections graph** (`components/connections-graph.tsx`, bottom of the front page, above the closing call to action): channels (Telegram, WhatsApp, Discord, Avito, VK, a website) -> Omnixon -> agents -> models.
  Cards placed by percentages over one SVG drawn in a 100 x 100 box (`preserveAspectRatio="none"`, `vector-effect: non-scaling-stroke`), so the curves meet the cards at any width; the dashes that run
  along the lines are `.graph-flow` in index.css (off for `prefers-reduced-motion`). The figure scrolls sideways inside its box below 40rem instead of squeezing. e2e checks the nodes, the 15 edges and that no cards overlap.
- The Playground's chat card is `flex-1` in its column: without it the card is only as tall as its content (half the window).
- Folders: the three repositories are siblings `omnixon-backend`, `omnixon-library`, `omnixon-frontend` (the compose files default `OMNIXON_REPO` to `../../omnixon-backend`).
- The graph: only the messengers are coloured (a brand-coloured tile with a white mark, `data-brand`); four agents run one-to-one on four models, shuffled so the lines cross (14 lines in all).
  The hero's JSON shows only `response` and a line of dots. In the Playground an answer (`data-testid="answer"`) has no background, border or inset: it is text on the page of the chat; the user's own message keeps its bubble.

- **Chats** (service migration 13): the Playground is a list of the user's chats (`components/chat-panel.tsx`, shared with Users & history) beside the transcript. Who it talks as and which chat is remembered
  per agent in localStorage (`omnixon.playground.agent.<agentId>` = `{userId, chatId}`, `lib/playground-store.ts`); on open the user's chats are read, the remembered chat (or the latest) is opened and its
  messages are shown once (`shownKey`: a refetch must not wipe the screen). The first message of a Playground with no user makes one (`newUserId`: `crypto.randomUUID` does not exist on plain http) and a chat
  (the service names it after that message); "New chat" is a blank page, the chat is made by its first message. The user typed in the settings applies when the dialog closes. "Clear chat" asks, then empties the
  chat on the service. The chat list is disabled while an answer comes. Users & history: `?user=` and `?chat=`; chats can be started, renamed, cleared and deleted there too, for **regular** as well
  (`minRole` of the page is `regular`; no `/admin` call is made). E2E: `chats.spec.ts` (against the fake model server), `fakeAgent(request, prefix, role)`.

---

# MCP server (omnixon-mcp)

`README.md` there describes it for users. Omnixon as an MCP server for a model that manages it (low-level `mcp` SDK 1.30, stateless streamable
HTTP at `/mcp`), started by the root compose as `mcp` (port `MCP_PORT`, 8090; from an agent of the stack `http://mcp:8090/mcp`). Claude Code
connects through `.mcp.json` in this folder (`OMNIXON_TOKEN`, `OMNIXON_MCP_URL`).

- **The tools are written by hand** (since 2026-10-08; they used to be generated from `/openapi.json`, one per route, which gave a model
  57 tools named after routes, raw rows, and 4-5 calls per task). `tools/<topic>.py` (overview, agents, connections, mcp_servers, models,
  knowledge, memories, users, messages, tokens, usage): `@tool(name, group, role, description, props, required, routes, scoped)` + an async
  handler `(c: Ctx, **args)`. 52 tools for admin, 40 user, 14 regular. `get_agent` aggregates 5 calls; connections are addressed by the agents
  (`connect_agents(caller, called, description)`), not by connection id; answers are compact and name things.
- **The names must not collide with the built-in tools an agent gets**: `list_agents` and `ask_agent` are built into an agent that has
  connections (backend `ai/agent_calls.py`), so the MCP uses `find_agents` / `send_message`.
- **Declare the routes**: every tool lists the routes it calls (`routes`, and `admin_routes` for the ones it calls only for an admin token).
  `tests/test_contract.py` checks them against the OpenAPI snapshot (`../omnixon-library/tests/server_openapi.json`): a route of the service
  with no tool and no entry in `LEFT_OUT` (with a reason) FAILS, a tool naming a route the service lacks fails, and a tool offered to a role
  lower than its highest route needs fails (`ADMIN_ONLY` in `access.py` mirrors the backend's `require("admin")`: keep it in step).
  **When `sync-omnixon-lib` shows a new route, the MCP needs a tool for it.**
- **Roles**: the token's role comes from `GET /api/v1/tokens/self` (cached by the token's sha256, `OMNIXON_MCP_IDENTITY_SECONDS`). A tool is
  offered from `role` up; `scoped=True` tools work on one agent: the token's own, or for admin+ `agent_id` (main-API calls then carry
  `X-Act-As-Agent`, the admin API takes `agent_id` as a parameter). Descriptions get a note per role. The service is still the authority.
- **Messages** (`send_message`, admin+): the user is `agentmcp_<agent of the token>`, not an argument; the token's own agent is refused.
- **No token / rejected token**: one tool, `omnixon_connect`. No uvicorn access log: `?token=` would be in it. `?groups=` keeps groups
  (`registry.GROUPS`; `self` stays); an unknown group is an error.
- Secrets: header values of an MCP server read `<hidden>` in every answer (`tools/common.hide_headers`); a new token's secret is in the answer
  of `create_token` once. Answers have no embeddings (`api.without_embeddings`); the service's 422 is said as `config.tools: <msg>`; a 404 for a
  user of the own agent says to give `agent_id` (`Ctx._refusal`).
- The SDK's own input validation caches ONE tool list for all sessions, so `call_tool(validate_input=False)`; `registry.run` validates against
  the schema the caller's role was shown (jsonschema, `additionalProperties: false`).
- macOS: uv's `.pth` in `.venv` gets the `hidden` flag and Python 3.11.15+ skips hidden `.pth`: pytest has `pythonpath = ["src"]`; run locally
  with `PYTHONPATH=src` (the image is non-editable).
- Claude Code caches a tool's schema by NAME: after the rewrite `get_agent`/`delete_agent` kept their old schema in a running session until
  it reconnected. Reconnect (`/mcp`) after changing a tool.
- Tests: `uv run --group test pytest` (29: contract + behaviour against a `Service` table of answers). Verified live: Claude Code through the
  tools, and Agent manager (an agent with this MCP attached) creating an agent, connecting itself to it and asking it through `ask_agent`.
