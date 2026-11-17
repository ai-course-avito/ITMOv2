# Omnixon

Omnixon is a web service that unifies how automated systems talk to LLMs. A client sends a text request for a user; Omnixon builds the context (history, memory, knowledge base, tools), calls the model through OpenRouter, stores the exchange and returns the answer, optionally streamed.

## Concepts

* **Model**: an OpenRouter request body as JSON (`{"model": "...", "provider": {...}, ...}`). Model `0` is the default one, seeded from `DEFAULT_MODEL`. How a model is reached is set next to the body: `base_url` (another OpenAI-compatible server; default OpenRouter's), `use_proxy` (default `true`; `false` calls it without `OPENROUTER_PROXY`) and `api_token` (its key; default: the key of the deployment). The key is never returned (`has_api_token` says whether there is one); in `PATCH`, `""` clears `base_url` / `api_token`.
* **Agent**: a system prompt, a model and a `config` JSON (see below). Agents can use MCP servers. Every change of an agent is kept as a numbered **version** that can be compared and rolled back to.
* **Token**: the way in. A token is bound to an **agent** and has a **role**: `regular` (requests, users, history), `user` (plus everything about its own agent: prompt, knowledge base, MCP servers, memories, tokens for it), `admin` (every agent, models, every token up to `user`, usage of all, acting as another agent with `X-Act-As-Agent`) and `owner` (tokens of any role). Only the sha256 of a token is stored; the secret is shown once, when it is made. The token of `INITIAL_API_KEY` is the first owner.
* **User**: someone talking to an agent, identified by an external id. Users of different agents are separate.
* **Chat**: a conversation of a user with the agent. Each chat is its own thread of messages (the model is given the messages of the chat it is asked in), while the memories, what the agent knows about the user, are shared by all of them. A request without `chat_id` goes to the user's *default chat*, so clients that know nothing about chats (a bot) work as before.
* **Message**: the saved history of a chat.
* **Memory**: facts an agent remembers about a user (per user and agent). They are on by default: the model learns from conversations (`auto_memory`), can `remember`/`recall`/`forget` itself, and what it knows about the user is put in front of every message of theirs. With embeddings: `recall` and `GET /admin/memories?query=` find them by meaning. A message is forgotten after `MESSAGE_TTL_DAYS` (7); memories are not.
* **RAG**: a knowledge base of an agent, searched by embeddings.
* **MCP server**: an external tool server (`streamable_http` or `sse`) that can be attached to agents.

### Agent config

`agents.config` is one JSON with the settings of an agent. Default: `{"tools": ["rag", "memory"]}`.

| Key | Meaning | Default |
|---|---|---|
| `tools` | built-in tools: `rag` (knowledge base search), `memory` (`remember` / `recall` / `forget`) | `["rag", "memory"]` |
| `message_limit` | how many of the latest messages are given to the model | `DEFAULT_MESSAGE_LIMIT` (10) |
| `memo_limit` | how many memories are shown to the model at once (system prompt and `recall`) | `DEFAULT_MEMO_LIMIT` (20) |
| `auto_memory` | after every saved exchange the model is asked, in the background, what is worth remembering about the user | on (`DEFAULT_AUTO_MEMORY`) |

On `PATCH /admin/agents/{id}` only the given keys change, and a key set to `null` goes back to its default.

## API

Every request needs `Authorization: Bearer <token>`. The interactive documentation is at `/docs`. Paths are below `/api/v1`.

### Main API

* `POST /request`: body `{"user_id", "request", "chat_id", "save_message", "use_memo"}`. Returns `{"response", "user", "chat_id"}`. `chat_id` is one of the user's chats (404 otherwise); omitted: the default chat.
  * `user_id` empty or omitted: a new user is created for the agent and returned.
  * `trace=true`: the response also has `trace`, the chain of calls behind the answer: each call to the model and each tool it called (built-in or MCP), in order, with arguments, results, tokens and times.
  * `save_message=false`: the exchange is not stored. `use_memo=false`: the user's previous messages are not given to the model (memory is controlled by the agent's `tools`).
* `POST /request-stream`: the same, as server-sent events: `event: user`, then one `data:` event per text chunk (a JSON string), then `event: done` (or `event: interrupted`, or `event: error`). With `trace=true`, `event: trace` events (one step each) come in between, as the steps finish.
* `POST /users`, `GET|PATCH|DELETE /users/{user_id}`, and `GET /users?query=abc&limit=10`: the users of your agent whose external id starts with `query` (at least 3 characters; there is no list of all users), for suggestions
* `GET /users/recent?limit=20`: the users of your agent that wrote lately, latest first, with `last_active` and the number of their `messages` that are still kept (the window is `MESSAGE_TTL_DAYS`, 7 by default; a user with no kept messages is not in it, use the search). For suggestions in clients, so they need no list of their own.
* `GET|DELETE /users/{user_id}/history`: the history of the default chat.
* Chats: `GET|POST /users/{user_id}/chats` (the latest first, with `messages` kept; a new chat may be given a `title`, else it is named after the first message), `GET|PATCH|DELETE /users/{user_id}/chats/{chat_id}` (rename; delete takes its messages), `GET|DELETE /users/{user_id}/chats/{chat_id}/history` (read or clear). A chat of one user is not found through another.
* `POST /users/{user_id}/interrupt`: stops the answer being streamed to that user (with the agent of the token). The stream ends with `event: interrupted`, what was said so far is saved to the history (the answer marked `interrupted`) and to the memory, and `{"interrupted": true, "text": "..."}` is returned (`false` when nothing was streaming). A new `/request` or `/request-stream` of the same user does this by itself first, so the new request starts from a history that has the cut answer. Streams are tracked in the process: with several replicas an interrupt only reaches streams of the replica that gets the call.

### Admin API (`/admin`)

* `agents`, `models`, `mcp-servers`, `tokens`, `rag`, `memories`: create, list, read, update and delete, as far as the role allows (see the roles above; `/api/v1/tokens/self` and `/api/v1/agents/self` read the caller's own token and agent). `POST /admin/tokens` answers with the secret, once. `PATCH /admin/tokens/{id}` renames a token and/or changes its `role` (up to what the caller may hand out; not its own, and the initial token stays an owner).
* `GET /admin/usage` and `/admin/usage/monthly`: what each token spent on the models (requests, errors, tokens, cost, time; never the texts). Detail is kept for `USAGE_TTL_DAYS` (30), then folded into one row per token, month and model that stays.
* **Names**: agents, models, MCP servers and tokens have a required `name` (1-120 characters, trimmed) on create and an optional one on update. Responses always carry a non-empty `name`; an entity made before names existed gets a fallback: model -> its own model name, MCP server -> `MCP <id>`, agent -> the start of its prompt (first line, 60 characters), else `Agent <id>`.
* `GET /rag` without `query` lists every entry of the agent (in the order made; `limit` up to 1000, `offset`); with `query` it searches by meaning (`limit` up to 100).
* `agents/{id}/mcp-servers/{mcp_server_id}`: attach (`POST`) or detach (`DELETE`) an MCP server; `GET agents/{id}/mcp-servers` lists them.
* Agent versions: `GET agents/{id}/versions` (newest first), `GET agents/{id}/versions/{n}`, `GET agents/{id}/versions/{n}/diff?to=` (what changed), `POST agents/{id}/rollback {"to": n}` (the agent becomes what it was, recorded as a new version). A version is a snapshot with copies of the model and MCP configs, so a rollback restores the behaviour of that time. `PATCH agents/{id}` takes a `comment` and `expected_version` (409 if the agent has moved on). Messages carry the `agent_version` that produced them.
* `memories`: `GET ?user_id=&agent_id=&query=` (newest first, or by meaning with `query`), `POST`, `GET|PATCH|DELETE /{id}`.

### Attachments

`POST /request` and `/request-stream` accept `attachments`: files for the model, each with a `url` (http/https) or base64 `data`, a `media_type` (guessed from a URL) and an optional `name`. Images, audio, video, PDF and text are accepted. The model must be able to handle them (for images it must see); otherwise the provider's error comes back as a 502. The history keeps only a note that a file was there.

### Operations (no token)

`GET /healthz` (liveness), `GET /readyz` (the database answers and is migrated, 503 otherwise), `GET /metrics` (Prometheus: requests by route template, durations, in-flight requests, active streams, retries, dropped MCP servers, cancelled requests, expired messages, database pool).

### Reliability

* A failure of the model provider that is likely to pass (5xx, 429, timeouts) is retried twice more with growing pauses; a bad model name or other 4xx is not.
* An MCP server that is down is left out (for 30 s) and the request is answered with the rest.
* `REQUEST_TIMEOUT_SECONDS` bounds every request (504). A request whose client has gone away is cancelled.
* Provider and MCP failures are 502 (504 for timeouts) with the reason.

## Configuration

See `.env.example`: database, `OPENROUTER_API_KEY`, `INITIAL_API_KEY` (the first owner token), optional `OPENROUTER_PROXY` (`http://`, `https://` or `socks5://`), `DEFAULT_MODEL`, `DEFAULT_MESSAGE_LIMIT`, `DEFAULT_MEMO_LIMIT`, `DEFAULT_AUTO_MEMORY`, `MESSAGE_TTL_DAYS`, `MESSAGE_CLEANUP_INTERVAL_SECONDS`, `METRICS_TTL_DAYS`, `REQUEST_TIMEOUT_SECONDS`, `UPSTREAM_RETRIES`, `UPSTREAM_RETRY_DELAY`, `MCP_DOWN_SECONDS`, `REDIS_URL`, `LOG_LEVEL`, `LOGFIRE_TOKEN`.

## Database and migrations

PostgreSQL with pgvector. The schema is built by the files in `app/database/migrations/` (`0.sql`, `1.sql`, ...). The `migrations` table has one row with the number of the last applied migration; on every start the service applies the files with a higher number, in order. To change the schema add the next numbered file; never edit an applied one. `app/database/schema.reference.sql` shows the current state for readers and is not used for migrating, so keep it in sync.

## Logs

Logs are JSON lines on stdout (secrets such as tokens, passwords and API keys are masked): one object per log, finished span or standard `logging` record, with `timestamp`, `level`, `message`, `trace_id`, `span_id`, `source`, `attributes` and, for errors, `exception`. Each request is logged with method, path, status, duration and unit id. `LOG_LEVEL` sets the lowest level; `debug` also logs arguments and results of every route and database call, including tokens and message texts.

## Development

Dependencies are managed with [uv](https://docs.astral.sh/uv/): `pyproject.toml` lists the direct ones and `uv.lock` pins everything. Docker images install from the lock (`uv sync --frozen`).

```bash
uv sync --group test        # create .venv with everything, tests included
uv add <package>            # add a dependency (updates pyproject.toml and uv.lock)
uv run uvicorn --app-dir app main:app --reload
```

The service is started with `uvicorn` directly (see `docker/Dockerfile.api`), so every line of the output is a JSON log.

## Tests

`app/tests/` has a file per aspect: `test_api_*.py` run against the API, `test_unit_*.py` test the logic and migrations directly; `conftest.py` and `shared.py` hold what they share. Both run in Docker:

```bash
cd docker && docker compose -f docker-compose.test.yaml --env-file .env up --build --abort-on-container-exit --exit-code-from tests
```

The stack contains the API, Postgres, a SOCKS5 proxy (all OpenRouter traffic of the API goes through it) an MCP calculator server and a fake OpenAI-compatible server (`docker/fake-llm`) that stands in for a provider for models with their own `base_url` (and for streams that can be interrupted).

## omnixon-lib

The Python client lives in the `omnixon-lib` repository. Its tests compare its models with a snapshot of this API's OpenAPI schema. After you change a request or response model, regenerate the snapshot:

```bash
uv run python scripts/dump_openapi.py ../omnixon-library/tests/server_openapi.json
```
