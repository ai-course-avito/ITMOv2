# Omnixon backend and library: an object-oriented architecture (design)

Asked for on 2026-10-08: the code grew by "vibe coding" and has no clear shape; restructure it by SOLID and GRASP, largely in the OOP
paradigm. Behaviour and endpoints stay as they are. Tests that a change is known in advance to break are rewritten on purpose. The
library becomes 5.0 and its public API may change. Work is test-driven (TDD).

Scope (decided): **omnixon-backend** (everything) and **omnixon-library** (5.0, resources like an SDK). omnixon-mcp and the admin panel
change only where the backend or the library forces it (they should not need to: the HTTP API and the OpenAPI schemas stay). The
Telegram bot is outside this folder and is updated by the user.

## 1. What is wrong now (the reasons for each decision below)

| # | Problem | Where | Principle broken |
|---|---|---|---|
| P1 | `PostgresDB` is one class of 12 mixins plus the request context (`self.context`); routers write `db.context.user = ...` and later calls read it: hidden temporal coupling | `database/methods.py`, `database/mixins/*`, `database/context.py`, every router | SRP, ISP, DIP; GRASP Low Coupling |
| P2 | Business rules live in route handlers: transactions, advisory locks, `expected_version`, recording versions, 404/409 mapping of DB errors | `routers/agent.py`, `routers/model.py`, `routers/mcp_server.py`, `routers/token.py`, `routers/request.py`, ... | SRP; GRASP Controller, Information Expert |
| P3 | Rollback, "record a version if the snapshot changed", `insure_user` are business logic inside the data layer | `mixins/agent_version.py`, `methods.py` | SRP; GRASP Information Expert |
| P4 | Module-level state: `interrupt._active/bus/current`, `ai.utils._http_client/_direct_client/_embedder`, `mcp_health.health`, `memory._background`; 40 config constants imported from anywhere; tests patch modules | `ai/*`, `core/config.py` | DIP; GRASP Protected Variations; testability |
| P5 | Domain models read the environment: `Agent.message_limit` etc. read `DEFAULT_*`, `Token.is_initial` reads `INITIAL_API_KEY` | `database/models.py` | DIP; GRASP Pure Fabrication missing |
| P6 | Access rules are free functions over `db` (`require`, `ensure_agent_access`, `default_agent_id`, `may_grant`, `can_manage_token`, `may_act_as`, `_check_use` in a router) | `access.py`, `routers/mcp_server.py` | SRP; GRASP Information Expert |
| P7 | Memory logic exists twice: the API (`routers/memory.py` + mixin) and the agent's tools (`ai/memory.py`) | | DRY; GRASP Information Expert |
| P8 | The library is one `Client` class of 1078 lines and ~80 methods; its constructor does synchronous network I/O | `omnixon-library/omnixon/main.py` | SRP, ISP |

## 2. Layers

```
omnixon-backend/app/
  main.py              create_app(settings) -> FastAPI; the ASGI entry `app = create_app(Settings.from_env())`
  config.py            Settings (pydantic-settings BaseSettings, frozen; Settings.from_env()), AgentDefaults
  container.py         Container: the composition root (GRASP Creator); lifespan starts/stops what it made
  domain/              entities with behaviour, value objects, AccessPolicy, domain errors (no I/O, no env)
  repositories/        Database, UnitOfWork, one repository per aggregate (SQL and row mapping only)
  services/            use cases (GRASP Controller): one class per resource area
  ai/                  AgentFactory, AgentRunner, capability providers, MemoryExtractor, InterruptRegistry, StreamGuard, Tracer
  infrastructure/      postgres (pool, migrations, seed), redis (StopBus, McpHealth store), llm (ModelGateway, Embedder,
                       RetryingTransport), logging, masking, metrics, jobs (PeriodicJob, TaskSupervisor)
  api/                 Controller base + @endpoint, controllers/, schemas/, middleware (auth + request log), errors, sse, openapi
```

Dependencies point down only: `api -> services -> (domain, repositories, ai) -> infrastructure`. `domain` imports nothing of the
project. Nothing reads the environment except `Settings.from_env()`.

**No `PostgresDB`, no mixins, no `Context`, no `request.state.db`.** The state of a request is an immutable `Principal`; the user and
chat a call is about are explicit arguments or a `Conversation` value.

## 3. Domain (`domain/`)

Pydantic models stay the entities, because they are also the response schemas (the OpenAPI schema must not change). They lose every
read of the environment and gain behaviour.

- `Role` (enum `regular < user < admin < owner`): `rank`, `grants` (the highest role it may hand out: regular none, user user, admin
  user, owner owner), `at_least(other)`. Replaces `ROLES`, `RANK`, `GRANTS`.
- `Token`: as now; `is_initial` is a plain field set by `TokenRepository` (which knows the initial hash from `Settings`), still a
  computed-looking field in the answer. `role: Role`. Methods `may_hand_out(role)`, `may_manage(other: Token)`.
- `Agent`: the stored row only. `agent.settings(defaults: AgentDefaults) -> AgentSettings` (frozen: `tools`, `message_limit`,
  `memo_limit`, `rag_limit`, `auto_memory`, `parallel_tool_calls`). The five env-reading properties go.
- `AgentConfig` / `AgentConfigInput`: as now (`AgentConfigInput` moves to `domain` because services merge it).
- `AgentSnapshot`: what a version holds; `AgentSnapshot.normal(raw)`, `snapshot.diff(other)`, equality = "nothing changed".
- `ModelConnection` (`base_url`, `use_proxy`, `api_token`, `fingerprint()`), `Model.connection -> ModelConnection`.
- `CallChain` (moves from `database/context.py`): `then(agent_id)`, `refusal(target, depth) -> Optional[str]`, `caller_user_id(...)`
  (the `agent_<caller>:<person>` id, shortened by sha256 over 64 characters).
- `Principal` (frozen): `token: Token`, `agent: Agent` (the token's or the acted-as one), `chain: Optional[CallChain]`;
  `role`, `acting_as_other` properties; `continued_as(agent, chain)` for an agent asking another.
- `Conversation` (frozen): `principal`, `user: User`, `chat: Chat`, `settings: AgentSettings`.
- `AccessPolicy` (GRASP Information Expert for permissions): `require(principal, role)`, `agent_scope(principal, agent_id|None) ->
  int`, `ensure_agent(principal, agent_id)`, `may_act_as(principal, agent_id, connections) -> bool`, `ensure_may_hand_out(principal,
  role)`, `ensure_may_manage(principal, token)`, `ensure_mcp_use(principal, agents_using, change: bool)`. Raises `Forbidden`.
- Domain errors: `DomainError` -> `NotFound(what)`, `Conflict(detail)`, `Forbidden(detail)`, `Invalid(detail)`. The detail texts are
  the ones the API sends today (tests and the panel match on them).

## 4. Data (`repositories/`)

- `Database`: the pool; `fetch_one/fetch_all/execute` take a connection per query (as today); `transaction()` pins one connection to
  the current task through a ContextVar, nested blocks are savepoints (today's `PostgresConnectionWithContext` without the context).
  `fetch_all` returns `[]`, never `None`.
- `UnitOfWork(database)`: `async with uow:` = one transaction; `await uow.lock(key)` = advisory lock to the end of it. Services use it
  for every multi-statement write (the same places as today: agent change + version, message pair, rollback, MCP attach/detach, model/
  MCP edits + versions, look-then-save of a memory, create agent + first version).
- `Repository` base: holds `Database`; one place logs calls (replaces `@async_logfire_class_decorator` on a god class).
- Repositories (methods take every id explicitly; no business rules):
  `AgentRepository`, `VersionRepository` (incl. `snapshot_of(agent_id)` query and `latest`), `TokenRepository` (secret creation stays
  in `TokenService`), `UserRepository`, `ChatRepository`, `MessageRepository`, `ModelRepository`, `McpServerRepository` (incl.
  attachments), `ConnectionRepository`, `MemoryRepository`, `KnowledgeRepository` (RAG, partitions), `UsageRepository` (logs, reports,
  folding used by the job).
- `infrastructure/postgres.py`: `PostgresPool` (vector check, pool, migrations under the advisory lock, seed of model 0), unchanged
  behaviour. `MessageRetention` and `UsageCompaction` keep their SQL.

## 5. Services (`services/`)

Each service gets its collaborators in the constructor and the `Principal` (or a `Conversation`) as an argument; raises domain errors.

| Service | Takes over |
|---|---|
| `AuthService` | token lookup by secret, `X-Act-As-Agent` (via `AccessPolicy.may_act_as`), building the `Principal` |
| `VersionRecorder` | "record a version of agent X if its snapshot changed", for every service that changes behaviour |
| `AgentService` | list/get/self/create/update (`expected_version` under the lock)/delete (+ versions of callers), MCP attach/detach/list |
| `VersionService` | list/get/diff/rollback (copies of model and MCP when changed, connections) |
| `ModelService` | CRUD, `request_json`/connection validation, versions of the agents using it |
| `McpServerService` | CRUD, config validation (`MCP_OPTIONS`), use rules for user tokens, versions of the agents using it |
| `ConnectionService` | CRUD of agent connections + versions of the caller |
| `TokenService` | self/list/create (secret)/update (name, role)/delete, `ensure_initial(secret)` |
| `UserService` | search/recent/create/get/rename/delete, `ensure(external_id) -> User` (race-safe; today's `insure_user`) |
| `ChatService` | chats, default chat, history, clear (today's `chat.py` and `history.py`) |
| `MemoryService` | one implementation for the API and the agent's tools: save with near-duplicate rules, recall by meaning then words, CRUD, the `<Memory>` block, embedding backfill |
| `KnowledgeService` | RAG CRUD, list, search (with `Embedder`) |
| `UsageService` | daily/monthly reports scoped by the token's role |
| `ConversationService` | `/request` and `/request-stream`: resolve user and chat, stop the previous stream of the pair, run `AgentRunner`, store the exchange or the interrupted part, schedule auto_memory; `ask_as_agent(...)` for `ask_agent` (implements the `AgentAsker` protocol) |

## 6. AI (`ai/` and `infrastructure/llm.py`)

- `ModelGateway`: owns the two httpx2 clients (through `OPENROUTER_PROXY` and direct), both with `RetryingTransport`; `chat_model(model:
  Model) -> pydantic-ai model`; `ModelSettingsMapper` (the `request_json` -> settings mapping of today's `model_settings`).
- `Embedder` (Protocol `embed(text) -> list[float]`), `OpenRouterEmbedder`. Tests use a fake.
- `AgentFactory(gateway, providers: Sequence[CapabilityProvider])`: `build(conversation) -> pydantic_ai.Agent` (instructions = prompt,
  capabilities, `parallel_tool_calls: False` only when off, retries).
- `CapabilityProvider` (Strategy, OCP): `applies(conversation) -> bool`, `build(conversation) -> AbstractCapability`. Providers:
  `ToolFailuresProvider`, `KnowledgeProvider`, `MemoryProvider`, `AgentCallsProvider`, `McpProvider`, `ParallelCallsProvider` (last;
  only when another one gave tools). The capability classes stay (`ToolFailures`, `KnowledgeBase`, `Memory`, `AgentCalls`,
  `McpServers` + `GuardedServer`, `ParallelCalls`).
- `RunDeps` (the pydantic-ai deps): `conversation`, `memory: MemoryService`, `knowledge: KnowledgeService`. Tools call services, never
  SQL.
- `AgentRunner(factory, prompts: PromptBuilder, usage: UsageMeter, settings)`: `run(conversation, request: RunRequest) ->
  AsyncIterator[RunEvent]`; `RunEvent` = `TextChunk | TraceStep | Finished`. It does not store anything (storing is
  `ConversationService`'s job). One task drives it from start to end; it is stopped by cancelling that task.
- `PromptBuilder`: history (`MessageRepository`, `use_memo`, the window), the `<Memory>` block (`MemoryService`), attachments.
- `UsageMeter` (today's `track_usage`): writes through `UsageRepository`.
- `MemoryExtractor` (today's `schedule_extraction`/`extract_memories`): runs through `TaskSupervisor`, model from `ModelGateway`, saves
  through `MemoryService`.
- `InterruptRegistry(bus: StopBus)`: `start/end/stop/stop_for_replica`, `current` stream; `StopBus` Protocol with `RedisStopBus`
  (today's `InterruptBus`) and `LocalStopBus` (one process). `StreamGuard` = today's `until_stopped`.
- `McpHealth(store)` with `RedisHealthStore` / `LocalHealthStore`; injected into `McpProvider` -> `GuardedServer`.

Behaviour is kept: the same instructions, tool names and descriptions, retries, failure texts, SSE protocol, trace, usage rows.

## 7. API (`api/`)

- `Controller` base + `@endpoint.get/post/patch/delete(path, *, min_role=None, status_code=200, summary=..., response_model=...)`.
  A controller collects its marked methods at construction and registers the bound methods on its `APIRouter`; `min_role` becomes
  `Depends(require_role(role))`, so `openapi.add_roles` still writes `x-min-role`.
- Controllers get services in the constructor (made by the `Container`); only per-request things come through `Depends`:
  `principal: Principal = Depends(current_principal)`, `request: Request` (disconnects, SSE).
- **Method names = today's function names** (`get_agents`, `update_agent`, ...) and the same summaries, so the OpenAPI `operationId`s
  and descriptions stay, and the library's snapshot does not change.
- Controllers: `HealthController`, `ConversationController`, `SelfController`, `UserController`, `ChatController` (with the default
  chat's `/history` routes), `AgentController`, `VersionController`, `ConnectionController`, `ModelController`,
  `McpServerController`, `TokenController`, `MemoryController`, `KnowledgeController`, `UsageController`.
- `api/schemas/`: the request bodies of today (same names, so the OpenAPI component names stay).
- `api/errors.py`: `DomainError` -> status + `{"detail"}`; `asyncpg.ForeignKeyViolationError` and friends are translated by the
  repositories into domain errors (the routers' try/except go). Upstream failures keep today's `error_response` mapping (502/504).
- `api/middleware.py`: plain ASGI as today (disconnects must stay visible): request log line, metrics, `AuthService.authenticate` ->
  `request.state.principal`; the same 403/404 answers and texts.
- `api/sse.py`: `SseStream(conversation_service, ...)` turns run events into `event: user | trace | data | done | interrupted |
  error`.

## 8. Background work

`PeriodicJob` (interval, `run_once()`, logging, clean stop): `MessageRetentionJob`, `UsageCompactionJob`, `EmbeddingBackfillJob`
(once, under `pg_try_advisory_lock`). `TaskSupervisor` keeps fire-and-forget tasks (auto_memory) and cancels them at shutdown. The
`Container` starts and stops them in `lifespan`.

## 9. Library 5.0 (`omnixon-library`)

- `Omnixon(token, base_url, act_as_agent=None, *, timeout=5, long_timeout=120, retry=RetryPolicy())`; no I/O in the constructor;
  `async with Omnixon(...) as client`; `await client.ping()` (token check), `await client.ready()`.
- `Transport`: one `httpx.AsyncClient`, headers, timeouts, `RetryPolicy` (which calls retry `httpx.ReadError`, how many times),
  `ErrorMapper` (status -> `NoAccess`/`NotFound`/`Conflict`/`InvalidRequest`/`UpstreamError`). Base exception `OmnixonError`
  (was `UnlinkError`); `StreamError` stays; `UnlinkConnectionError` becomes `OmnixonConnectionError` (raised by `ping()`).
- `Endpoint(method, path)` class attributes on resources; `Resource._call(endpoint, **path_params, json=..., params=...)`; every
  endpoint the library calls is found by reflection (`omnixon.endpoints()`), which the contract test and `check_sync.py` use.
- Resources: `client.messages` (`send`, `stream` -> `MessageStream`, `interrupt`), `client.users` (+ `.chats`, `.history`),
  `client.agents` (+ `.versions`, `.mcp_servers`; `self()`), `client.connections`, `client.models`, `client.mcp_servers`,
  `client.memories`, `client.knowledge`, `client.tokens` (`self()`), `client.usage` (`daily`, `monthly`).
- `SseReader` parses the stream; `MessageStream` uses it (same `.user`, `.interrupted`, `.trace`).
- Models: the same fields, split by area under `omnixon/types/`; the contract test against the snapshot stays.
- README: every method, and a v4 -> v5 table. Version 5.0.0.

## 10. Tests (TDD) and order of work

- **TDD for every new class**: write its test first (red), make it pass (green), then refactor; for moved behaviour, the old test is
  ported first and must fail against the new class before it exists.
- **The HTTP tests (`test_api_*.py`) are the safety net and do not change**, except `from core import DATABASE_CONFIG` (it becomes
  `Settings`). After every stage: the full test stack with two replicas green (only the known real-model flakes may fail, and are
  rerun), no `"level": "error"` in the JSON logs, the library's OpenAPI snapshot unchanged except descriptions, panel e2e green.
- **Unit tests break on purpose and are rewritten** where they reach into what moves: `FakeDB` (a duck-typed `PostgresDB`) becomes
  fake repositories/services passed to constructors; `monkeypatch` of module globals becomes constructor injection; scratch-database
  tests stay and target repositories/services.
- **Stages** (strangler: the service works after each; one commit per stage when the user agrees):
  1. Skeleton: `Settings`, `Container`, `Controller`/`@endpoint`, domain errors + `api/errors.py`, `Principal` + `AuthService` in the
     middleware (`PostgresDB` still exists behind it).
  2. Data and domain: `Database`, `UnitOfWork`, the 12 repositories, `Role`, `AgentSettings`, `AgentSnapshot`, `CallChain`,
     `AccessPolicy`.
  3. Services + controllers, resource by resource (models, MCP servers -> tokens, self -> agents, versions, connections -> users,
     chats, history -> memories, knowledge, usage); each old router is deleted when its controller is in.
  4. AI: `ModelGateway`/`Embedder` -> `InterruptRegistry`/`StopBus` -> `MemoryService`/`MemoryExtractor` -> capability providers and
     `RunDeps` -> `AgentRunner`, `ConversationService`, `SseStream`.
  5. Cleanup: delete `PostgresDB`, mixins, `Context`, `access.py`, `ai/utils.py`, the module globals; jobs on `PeriodicJob`/
     `TaskSupervisor`; AGENTS.md.
  6. Library 5.0.
  7. Final verification and the user's stack rebuilt.

## 11. Not changed

The database schema and migrations, URLs/methods/status codes/bodies/SSE protocol, the OpenAPI schema (component names, operation
ids, `x-min-role`), the docker files and deploy files (the start command `uvicorn --app-dir app main:app` stays), omnixon-mcp, the
panel, the bot.
