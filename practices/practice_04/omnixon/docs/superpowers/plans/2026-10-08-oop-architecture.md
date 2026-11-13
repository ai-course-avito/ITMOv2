# Omnixon OOP Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild omnixon-backend as layers of objects (domain, repositories, services, AI, controllers, a composition root) and the
library as an SDK of resources (5.0), without changing what the HTTP API does.

**Architecture:** Strangler migration in 7 stages: new classes are built next to the old modules (test first), routers are replaced
by controllers resource by resource, and the old `PostgresDB`/mixins/globals are deleted at the end. After every stage the service
works and the unchanged HTTP test suite is green.

**Tech Stack:** Python 3.11, FastAPI, asyncpg + pgvector, pydantic 2 + pydantic-settings, pydantic-ai 2.54, httpx2, redis, pytest
(+ pytest-asyncio, fakeredis), uv; library: httpx, pydantic.

**Spec:** `docs/superpowers/specs/2026-10-08-oop-architecture-design.md` (read it first; section numbers below refer to it).

## Global Constraints

- **TDD for every task:** write the test, run it and see it fail for the expected reason, write the code, see it pass, then refactor.
  Moved behaviour: port the old test to the new class first and see it fail before the class exists.
- The HTTP API does not change: URLs, methods, status codes, request/response bodies, `detail` texts, SSE events, headers.
- The OpenAPI schema does not change: `app.openapi()` must equal the golden file of Task 0 (component names, `operationId`s, summaries,
  descriptions, `x-min-role`). The golden file is updated only for a reason written in the commit message.
- `app/tests/test_api_*.py` are not edited, except the import `from core import DATABASE_CONFIG` (Task 1).
- Database schema and migrations: untouched. Start command stays `uvicorn --app-dir app main:app`.
- Only `Settings.from_env()` reads the environment (after Task 29). `domain/` imports nothing of the project but `domain/`.
- No module-level mutable state (after Task 29): no `_active`, `bus`, `_http_client`, `_embedder`, `health`, `_background`.
- Code, comments, docs, commit messages in English; replies to the user in Russian. Commit trailer:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. One commit per stage (Tasks 5, 13, 21, 28, 29, 34, 35). Never push.
- Unit test loop (from `omnixon-backend/`): once `docker run -d --name omnixon_unit_verify_db -e POSTGRES_PASSWORD=pw -p 55434:5432
  pgvector/pgvector:pg16`, then `UNIT="env POSTGRES_HOST=localhost POSTGRES_PORT=55434 POSTGRES_USER=postgres POSTGRES_PASSWORD=pw
  POSTGRES_DB=postgres INITIAL_API_KEY=x OPENROUTER_API_KEY=x uv run --group test pytest"`; run as `${=UNIT} app/tests/<file> -q`
  (zsh needs `${=...}`).
- Full stack (from `omnixon-backend/docker/`): `APP_NAME=omnixon_verify docker compose -p omnixon_verify -f docker-compose.test.yaml
  -f <scratchpad>/override.yaml --env-file .env up --build --abort-on-container-exit --exit-code-from tests`, then `down -v` with the
  same `-p`. Pass = only known real-model flakes fail (`test_ai_consistency_and_format`, `test_stream_use_memo_false_ignores_history`;
  rerun them) and `grep -c '"level": "error"'` on the output is 0.
- Panel e2e (from `omnixon-frontend/`): `npm run test:e2e` then `npm run test:e2e:down`; 111 pass.

## Review Focus

- A transaction opened by one task must not be used by other tasks sharing the same `Database` (an agent's parallel tools): Task 8
  pins this with a concurrency test.
- Every `detail` text and status of today must survive the move to domain errors (e.g. `Agent {id} not found` vs `Agent not found`,
  `The agent is at version {latest}, not {expected}`): Task 2 and each service task assert the exact texts.
- A client that disconnects mid-request still cancels the run and stores nothing; a stopped stream still saves its partial answer:
  Task 28 ports both behaviours with tests.
- Shutdown closes everything the `Container` made (jobs, supervised tasks, httpx clients, Redis, pool) without `"pool is closed"`
  warnings from tasks still running: Task 29 asserts the order of `Container.aclose()`.
- The OpenAPI schema drifts silently when a method or summary is renamed: Task 0's golden test catches it after every task.

---

## Stage 0. Baseline

### Task 0: Baseline commit and golden OpenAPI

**Files:**
- Create: `omnixon-backend/app/tests/golden_openapi.json`, `omnixon-backend/app/tests/test_unit_openapi_golden.py`

**Interfaces:**
- Produces: `golden_openapi.json` = `app.openapi()` of the code as it is now.

- [ ] **Step 1:** Ask the user to allow a baseline commit of the current uncommitted work (pydantic-ai 2 migration, Redis, parallel
  calls). Commit it only on a yes; otherwise stop here.
- [ ] **Step 2: Write the test** `test_the_openapi_schema_is_the_golden_one`: `json.loads(golden) == main.app.openapi()`; on failure
  print the JSON paths that differ.
- [ ] **Step 3:** Generate `golden_openapi.json` with `uv run python scripts/dump_openapi.py app/tests/golden_openapi.json`.
- [ ] **Step 4: Run** `${=UNIT} app/tests/test_unit_openapi_golden.py -q` → 1 passed. Run all unit tests → all pass (210).

## Stage 1. Skeleton

### Task 1: Settings

**Files:**
- Create: `app/config.py`, `app/tests/test_unit_settings.py`
- Modify: `app/core/config.py` (every constant becomes `settings.<field>` of one module-level `settings = Settings.from_env()`, kept
  until Task 29), `pyproject.toml`/`uv.lock` (`uv add "pydantic-settings==<latest>"`, pinned), `app/tests/test_api_*.py` that import
  `DATABASE_CONFIG` (use `Settings.from_env().database`)

**Interfaces:**
- Produces: `class Settings(BaseSettings)` (frozen, `extra="ignore"`), `Settings.from_env() -> Settings`; fields named as today's
  env vars in lower case with today's defaults (`request_timeout_seconds=600`, `upstream_retries=2`, `upstream_retry_delay=1`,
  `mcp_down_seconds=30`, `mcp_tool_attempts=3` (min 1), `mcp_tool_retry_delay=1`, `mcp_tool_retries=3`, `message_ttl_days=7`,
  `usage_ttl_days=30`, `metrics_ttl_days=7`, `agent_call_depth=3`, `redis_url=""`, `default_model: dict` (parsed as today),
  `initial_api_key`, `openrouter_api_key`, `openrouter_proxy`, `log_level="info"`, ...); `settings.database -> dict` (asyncpg kwargs);
  `settings.agent_defaults -> AgentDefaults` (frozen: `message_limit=10`, `memo_limit=20`, `rag_limit=8`, `auto_memory=True`,
  `parallel_tool_calls=True`, `tools=("rag","memory")`).

- [ ] **Step 1: Write tests** `test_defaults_are_todays`, `test_booleans_read_like_today` (`"0","false","no","off",""` → False),
  `test_default_model_accepts_a_name_or_a_json_body`, `test_agent_defaults_come_from_the_settings`.
- [ ] **Step 2: Run** → fail (`ModuleNotFoundError: config`).
- [ ] **Step 3:** Implement `Settings`; rewrite `core/config.py` on top of it (the old names stay importable).
- [ ] **Step 4: Run** the new tests and all unit tests → pass; golden test passes.

### Task 2: Domain errors and their HTTP answers

**Files:**
- Create: `app/domain/__init__.py`, `app/domain/errors.py`, `app/api/__init__.py`, `app/api/errors.py`, `app/tests/test_unit_errors.py`
- Modify: `app/main.py` (register the handler)

**Interfaces:**
- Produces: `DomainError(detail: str)` with `status: ClassVar[int]`; `NotFound` 404, `Conflict` 409, `Forbidden` 403, `Invalid` 422.
  `install_error_handlers(app: FastAPI) -> None` answers `{"detail": exc.detail}` with `exc.status`, logs at warn.
- [ ] **Step 1: Tests** `test_each_domain_error_has_its_status_and_detail` (TestClient on a tiny app: raising `NotFound("Agent not
  found")` → 404 `{"detail": "Agent not found"}`, same for 409/403/422); `test_upstream_failures_keep_502_and_504`.
- [ ] **Step 2–4:** fail → implement → pass; golden test passes.

### Task 3: Controller base and `@endpoint`

**Files:**
- Create: `app/api/controller.py`, `app/api/dependencies.py`, `app/tests/test_unit_controller.py`
- Modify: `app/openapi.py` (unchanged logic; must read `min_role` from `require_role`'s dependency)

**Interfaces:**
- Produces: `endpoint.get/post/patch/delete(path: str, *, min_role: str | None = None, status_code: int = 200, summary: str,
  response_model=Default, **route_kwargs)` marking a method; `class Controller` with `prefix: ClassVar[str]` (`"/api/v1"` or
  `"/api/v1/admin"` or `""`), `router: APIRouter` built in `__init__` from the marked methods in definition order;
  `require_role(role: str) -> Callable` (FastAPI dependency carrying `min_role`); `current_principal(request) -> Principal` (reads
  `request.state.principal`, added in Task 13; until then raise if absent).
- [ ] **Step 1: Tests** `test_marked_methods_become_routes_in_order`, `test_the_operation_id_is_the_method_name` (FastAPI's
  `generate_unique_id` gives `<method>_<path>_<verb>` exactly as for a function of that name), `test_min_role_shows_as_x_min_role`,
  `test_a_route_below_its_role_answers_403_with_todays_text` (`"Forbidden: needs the admin role"`),
  `test_dependencies_of_a_bound_method_are_resolved` (a method taking `principal: Principal = Depends(current_principal)`).
- [ ] **Step 2–4:** fail → implement → pass.

### Task 4: Container and `create_app`

**Files:**
- Create: `app/container.py`, `app/tests/test_unit_container.py`
- Modify: `app/main.py` (`create_app(settings: Settings) -> FastAPI`; module-level `app = create_app(Settings.from_env())`; today's
  lifespan body moves into `Container.start()`/`aclose()`)

**Interfaces:**
- Produces: `class Container` with `__init__(settings, *, overrides: Mapping[type, object] = {})`, `async start()`, `async aclose()`,
  `get(cls: type[T]) -> T` (singletons made lazily by explicit factory methods, `overrides` win), `controllers() -> list[Controller]`
  (empty for now). `app.state.container`.
- [ ] **Step 1: Tests** `test_overrides_replace_a_dependency`, `test_get_returns_one_instance`, `test_start_and_aclose_are_idempotent`.
- [ ] **Step 2–4:** fail → implement → pass; all unit tests and golden test pass.

### Task 5: Stage 1 verification

- [ ] **Step 1:** Run all unit tests → pass. Run the full stack → pass (see Global Constraints).
- [ ] **Step 2: Commit** `Introduce settings, domain errors, controllers and the container (stage 1)`.

## Stage 2. Data and domain

### Task 6: Roles and tokens

**Files:**
- Create: `app/domain/roles.py`, `app/tests/test_unit_roles.py`
- Modify: `app/database/models.py` (`Token.role: Role`; `ROLES`, `RANK` derived from `Role` until Task 29)

**Interfaces:**
- Produces: `class Role(str, Enum)` `REGULAR="regular" < USER < ADMIN < OWNER` with `rank: int` (1..4), `grants: int` (0, 2, 2, 4),
  `at_least(other: Role) -> bool`, `may_hand_out(other: Role) -> bool`. `Token.may_manage(other: Token) -> bool` (rank of other ≤
  grants and (admin+ or same agent)).
- [ ] **Step 1: Tests** port the matrix part of `test_unit_access.py` (who may hand out what, who may manage which token) to
  `Role`/`Token`; serialisation of `Token.role` stays the string.
- [ ] **Step 2–4:** fail → implement → pass; golden test passes (the schema of `role` stays `string`).

### Task 7: Agent settings, snapshots, model connection, call chain

**Files:**
- Create: `app/domain/agents.py` (`AgentSettings`, `AgentSnapshot`), `app/domain/models.py` (`ModelConnection`), `app/domain/chain.py`
  (`CallChain`), `app/tests/test_unit_domain_agents.py`
- Modify: `app/database/models.py` (`Agent.settings(defaults)`; the five env-reading properties delegate to it with
  `settings.agent_defaults` until Task 29), `database/context.py` and `ai/capabilities/agent_calls.py` (import `CallChain`,
  `caller_user_id` from `domain.chain`)

**Interfaces:**
- Produces: `Agent.settings(defaults: AgentDefaults) -> AgentSettings` (frozen; config value or default per key);
  `AgentSnapshot.from_raw(raw: dict) -> AgentSnapshot` (applies today's `normal()` defaults), `.raw -> dict`,
  `.diff(other) -> dict[str, {"from","to"}]`, `==` compares normalised raw; `ModelConnection(base_url, use_proxy, api_token)` with
  `fingerprint() -> str | None` (8 hex of sha256); `CallChain(agents: tuple[int, ...], human: str)`, `.then(agent_id)`,
  `.refusal(target: int, depth: int) -> str | None` (today's texts), `caller_user_id(caller_agent_id: int, human: str) -> str`.
- [ ] **Step 1: Tests** port `test_a_version_made_before_connections_existed_is_not_a_change`, the diff tests and
  `test_the_user_of_a_called_agent_is_the_caller_and_the_person_and_never_too_long`; add `test_settings_fall_back_to_the_defaults`.
- [ ] **Step 2–4:** fail → implement → pass; all unit tests pass.

### Task 8: Database and UnitOfWork

**Files:**
- Create: `app/repositories/__init__.py`, `app/repositories/database.py`, `app/repositories/unit_of_work.py`,
  `app/tests/test_unit_database_layer.py`

**Interfaces:**
- Produces: `class Database(pool: asyncpg.Pool)`: `fetch_one(query, values=(), model: type[T] | None = None) -> T | dict | None`,
  `fetch_all(...) -> list[T | dict]` (never `None`), `execute(query, values=()) -> None`, `transaction() -> AsyncContextManager`
  (ContextVar pin owned by this `Database`, nested = savepoint), `lock(key: str)` (needs a transaction, else `RuntimeError("lock()
  needs a transaction")`); value mapping as today's `map_value`. `class UnitOfWork(database)`: `async with uow:` = `transaction()`,
  `await uow.lock(key)`. `class Repository(database: Database)`: the base of every repository; logs each public call once
  (name, duration, masked arguments by parameter name, as `@async_logfire_class_decorator` does today).
- [ ] **Step 1: Tests** (scratch DB) `test_a_failed_block_rolls_back`, `test_a_failed_inner_block_undoes_only_itself`,
  `test_other_tasks_do_not_use_the_pinned_connection` (inside a transaction, `asyncio.gather` of 5 `fetch_one("SELECT
  pg_backend_pid()")` from new tasks created before the block see other pids than the block), `test_lock_puts_work_in_line`,
  `test_fetch_all_of_nothing_is_an_empty_list`.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 9: Repositories of agents, versions, models, MCP servers, connections

**Files:**
- Create: `app/repositories/{agents,versions,models,mcp_servers,connections}.py`, `app/tests/test_unit_repositories_agents.py`

**Interfaces:**
- Consumes: `Database` (Task 8); entities from `database/models.py` (moved to `domain/` in Task 29).
- Produces (every id explicit, no rules, FK violations become `NotFound`/`Conflict` with today's texts where a router mapped them):
  - `AgentRepository`: `get(id) -> Agent | None`, `list() -> list[Agent]`, `insert(name, prompt, model_id, config: dict) -> Agent`,
    `update(id, *, name=None, prompt=None, model_id=None, config_changes: dict | None = None) -> Agent | None` (merge with
    `jsonb_strip_nulls`), `set_behaviour(id, prompt, model_id, config) -> None` (rollback), `delete(id) -> Agent | None` (drops
    `rag_<id>`), `ids_using_model(model_id) -> list[int]`.
  - `VersionRepository`: `snapshot_of(agent_id) -> AgentSnapshot | None` (today's query), `latest(agent_id) -> AgentVersion | None`,
    `latest_number(agent_id) -> int | None`, `list(agent_id)` (newest first), `get(agent_id, number)`, `insert(agent_id, snapshot,
    comment, token_id) -> AgentVersion` (next number).
  - `ModelRepository`: `get`, `list`, `insert(name, request_json, base_url, use_proxy, api_token) -> Model`, `update(id, ...)`,
    `delete(id)`; `McpServerRepository`: `get`, `list`, `insert(name, config)`, `update(id, name, config)`, `delete`,
    `of_agent(agent_id) -> list[MCPServer]`, `attach(agent_id, server_id)`, `detach(agent_id, server_id)`,
    `agents_using(server_id) -> list[int]`; `ConnectionRepository`: `list(agent_id=None)`, `get(id)`, `find(agent1, agent2)`,
    `insert(agent1, agent2, description)`, `update(id, description)`, `delete(id)`, `callers_of(agent_id) -> list[int]`,
    `replace_of(agent_id, connections: list[dict])`.
- [ ] **Step 1: Tests** (scratch DB, one per repository): round trip of each method; `test_a_snapshot_has_copies_and_a_fingerprint`;
  `test_deleting_an_agent_drops_its_knowledge_partition`; `test_an_unknown_model_id_is_not_found`.
- [ ] **Step 2–4:** fail → implement (copy today's SQL from the mixins) → pass.

### Task 10: Repositories of tokens, users, chats, messages

**Files:**
- Create: `app/repositories/{tokens,users,chats,messages}.py`, `app/tests/test_unit_repositories_people.py`

**Interfaces:**
- Produces:
  - `TokenRepository(database, initial_secret_hash: str | None)`: `by_secret(secret) -> Token | None`, `get(id)`, `list(agent_id=None)`,
    `insert(name, agent_id, role, secret) -> Token`, `update(id, name=None, role=None)`, `delete(id)`, `upsert_owner(secret, agent_id)
    -> Token`; every token read gets `is_initial` set from the hash (constant-time compare).
  - `UserRepository`: `get(agent_id, external_id)`, `search(agent_id, prefix, limit)` (`%`, `_`, `\` literal), `recent(agent_id,
    limit, ttl_days)`, `insert(agent_id, external_id) -> User | None` (None on conflict), `rename(user_id, agent_id, external_id) ->
    User | None`, `delete(user_id)`.
  - `ChatRepository(database, ttl_days)`: `list(user_id)`, `get(user_id, chat_id)`, `default(user_id)`, `ensure_default(user_id) ->
    Chat`, `insert(user_id, title)`, `rename(user_id, chat_id, title)`, `delete(user_id, chat_id)`, `touch(chat_id, first_text)`.
  - `MessageRepository(database, ttl_days)`: `window(chat_id, limit) -> list[Message]` (oldest first), `append(user_id, chat_id,
    agent_id, content) -> Message`, `clear(chat_id)`.
- [ ] **Step 1: Tests** port `test_unit_chats.py` to the repositories; `test_a_token_read_knows_if_it_is_the_initial_one`;
  `test_search_takes_percent_and_underscore_literally`; `test_two_inserts_of_one_user_give_one_row_and_one_none`.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 11: Repositories of memories, knowledge, usage

**Files:**
- Create: `app/repositories/{memories,knowledge,usage}.py`, `app/tests/test_unit_repositories_data.py`

**Interfaces:**
- Produces: `MemoryRepository`: `newest(user_id, agent_id, limit, query=None)`, `nearest(user_id, agent_id, embedding, limit,
  max_distance) -> list[tuple[Memory, float]]`, `count(user_id, agent_id)`, `get(id)`, `insert(user_id, agent_id, content,
  embedding=None)`, `update(id, content, embedding)`, `delete(id, user_id=None, agent_id=None)`, `without_embedding(limit)`,
  `set_embedding(id, embedding)`. `KnowledgeRepository`: today's RAG methods with `agent_id` explicit (`ensure_partition`,
  `insert`, `get`, `nearest`, `list(agent_id, limit, offset)`, `update`, `delete`). `UsageRepository`: `record(row: UsageRow)`,
  `daily(days, token_id=None, agent_id=None, only_agent=None)`, `monthly(...)`, `fold(older_than_days, batch)`.
- [ ] **Step 1: Tests** port the SQL-level parts of `test_unit_memory.py` and `test_unit_usage.py`; `test_knowledge_of_two_agents_
  stays_apart`.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 12: AccessPolicy

**Files:**
- Create: `app/domain/access.py`, `app/tests/test_unit_access_policy.py`

**Interfaces:**
- Consumes: `Role`, `Token` (Task 6), `Principal` (defined here).
- Produces: `Principal(token: Token, agent: Agent, chain: CallChain | None = None)` (frozen) with `role`, `continued_as(agent,
  chain)`; `Conversation(principal: Principal, user: User, chat: Chat, settings: AgentSettings)` (frozen, `domain/conversation.py`); `class AccessPolicy` (stateless): `require(principal, role: Role)`, `agent_scope(principal, agent_id: int | None) -> int`,
  `ensure_agent(principal, agent_id)`, `may_act_as(principal, agent_id, has_connection: bool) -> bool`, `ensure_may_hand_out(principal,
  role)`, `ensure_may_manage(principal, token)`, `ensure_mcp_use(principal, agents_using: set[int], change: bool)`. Raises
  `Forbidden` with today's texts (`"Forbidden: this token may only use its own agent"`, `"Forbidden: this MCP server is not
  attached to the token's agent"`, `"Forbidden: this MCP server is shared with another agent, so it cannot be changed here"`,
  `"Forbidden: needs the {role} role"`).
- [ ] **Step 1: Tests** port the remaining matrix of `test_unit_access.py` (every role × every rule) and the may-act-as cases of
  `test_unit_agent_calls.py` (`test_a_token_below_admin_may_act_as_an_agent_only_through_a_connection`).
- [ ] **Step 2–4:** fail → implement → pass.

### Task 13: AuthService, Principal in the middleware; stage 2 verification

**Files:**
- Create: `app/services/__init__.py`, `app/services/auth.py`, `app/api/middleware.py`, `app/tests/test_unit_auth.py`
- Modify: `app/main.py`/`app/middlewares/postgres.py` (the middleware calls `AuthService` and sets `request.state.principal`; it still
  sets `request.state.db = PostgresDB(pool, Context(...from principal))` for the old routers), `app/container.py` (factories for
  Database, UnitOfWork, all repositories, `AccessPolicy`, `AuthService`)

**Interfaces:**
- Produces: `AuthService(tokens, agents, connections, policy)`: `authenticate(secret: str | None, act_as: str | None) -> Principal`;
  raises `AuthError(status, body, as_json: bool)` reproducing today's three answers exactly: 403 text `Authentication failed: API
  token is missing`, 403 text `Authentication failed: wrong token`, 403 JSON `Forbidden: X-Act-As-Agent needs the admin role`, 404
  JSON `Agent not found`.
- [ ] **Step 1: Tests** one per answer above plus `test_an_admin_acting_as_another_agent_gets_that_agent`,
  `test_a_non_numeric_act_as_is_refused_like_an_unknown_agent` (today: `-1` → 403 below admin, 404 for admin).
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** All unit tests, golden test, full stack → pass.
- [ ] **Step 6: Commit** `Add the domain, repositories, access policy and authentication (stage 2)`.

## Stage 3. Services and controllers

Each task: write the service tests first against fake or scratch repositories, then the controller; then delete the router it replaces
and its `include_router`; then run that area's HTTP tests by name in the full stack (or the whole stack at the stage's end). The
controller methods keep today's function names, summaries, docstrings and `min_role`s; the golden test must pass after each task.

### Task 14: VersionRecorder, ModelService, ModelController

**Files:**
- Create: `app/services/versions.py` (`VersionRecorder` only here), `app/services/models.py`, `app/api/schemas/models.py` (bodies and
  validators moved from `routers/model.py`), `app/api/controllers/models.py`, `app/tests/test_unit_service_models.py`
- Delete: `app/routers/model.py`

**Interfaces:**
- Produces: `VersionRecorder(versions: VersionRepository, uow)`: `record(agent_id, comment, token_id) -> AgentVersion | None` (under
  lock `agent-versions:<id>`; inserts only when `snapshot_of` differs from `latest`); `record_many(agent_ids, comment, token_id)`.
  `ModelService(models, agents, recorder, uow)`: `list(principal)`, `get(principal, id)`, `create(principal, ModelCreate) -> Model`,
  `update(principal, id, ModelUpdate) -> Model` (versions of `agents.ids_using_model`), `delete(principal, id)` (texts `"The default
  model cannot be deleted"`, `"Model is used by an agent"`, `"Model not found"`). `ModelController(models: ModelService)`, prefix
  `/api/v1/admin`.
- [ ] **Step 1: Tests** `test_a_version_is_recorded_only_when_the_snapshot_changes`, `test_editing_a_model_records_a_version_of_each_
  agent_using_it`, `test_the_default_model_cannot_be_deleted`, `test_a_used_model_cannot_be_deleted`.
- [ ] **Step 2–4:** fail → implement → pass; golden passes; `test_api_models.py`, `test_api_model_connection.py` pass.

### Task 15: McpServerService, McpServerController

**Files:**
- Create: `app/services/mcp_servers.py`, `app/api/schemas/mcp_servers.py`, `app/api/controllers/mcp_servers.py`,
  `app/tests/test_unit_service_mcp_servers.py`
- Delete: `app/routers/mcp_server.py`

**Interfaces:**
- Produces: `McpServerService(servers, recorder, policy, uow)`: `list(principal)`, `create(principal, McpServerCreate)` (user tokens
  attach to their own agent at once), `get`, `update` (versions of the agents using it), `delete`. Validation of `config` stays a
  validator of `McpServerCreate`/`Update` using `MCP_OPTIONS` (from `ai/capabilities/mcp.py`).
- [ ] **Step 1: Tests** port the rule cases of `_check_use` (read when attached, change only when attached to the own agent only).
- [ ] **Step 2–4:** fail → implement → pass; `test_api_mcp_servers.py` passes.

### Task 16: TokenService, TokenController, SelfController

**Files:**
- Create: `app/services/tokens.py`, `app/api/schemas/tokens.py`, `app/api/controllers/tokens.py`, `app/api/controllers/self.py`,
  `app/tests/test_unit_service_tokens.py`
- Modify: `app/container.py` (`start()` calls `TokenService.ensure_initial(settings.initial_api_key)` under the advisory lock of today)
- Delete: `app/routers/token.py`, `app/routers/self.py`

**Interfaces:**
- Produces: `TokenService(tokens, agents, policy, uow)`: `self_token(principal)`, `list(principal, agent_id=None)`,
  `create(principal, TokenCreate) -> NewToken` (secret `<3>_<60>` as today), `update(principal, id, TokenUpdate)`, `delete(principal,
  id)`, `ensure_initial(secret) -> Token` (owner, own "Default agent" with an empty prompt). Texts: `"The initial token cannot be
  deleted"`, `"The role of the initial token cannot be changed"`, `"The token in use cannot change its own role"`, `"The token in use
  cannot delete itself"`, `"Token not found"`. `SelfController`: `get_self_token`, `get_self_agent` (prefix `/api/v1`).
- [ ] **Step 1: Tests** one per text above; `test_a_user_token_hands_out_regular_and_user_only`; `test_the_initial_token_is_raised_
  to_owner_at_start`.
- [ ] **Step 2–4:** fail → implement → pass; `test_api_tokens.py`, `test_api_roles.py`, `test_api_auth.py` pass.

### Task 17: AgentService, AgentController

**Files:**
- Create: `app/services/agents.py`, `app/api/schemas/agents.py` (`AgentCreate`, `AgentUpdate`; `AgentConfigInput` → `domain/agents.py`),
  `app/api/controllers/agents.py`, `app/tests/test_unit_service_agents.py`
- Delete: `app/routers/agent.py`

**Interfaces:**
- Produces: `AgentService(agents, servers, connections, recorder, policy, uow, defaults: AgentDefaults)`: `list`, `get(principal, id)`,
  `create(principal, AgentCreate) -> Agent` (+ version 1 `"created"`), `update(principal, id, AgentUpdate) -> Agent` (lock, `expected_
  version` → `Conflict("The agent is at version {latest}, not {expected}")`, version `"updated"`), `delete(principal, id)` (versions of
  callers `"agent {id} deleted: may no longer call it"`, `Conflict("Agent still has tokens")`), `mcp_servers(principal, id)`,
  `attach(principal, id, server_id)`, `detach(principal, id, server_id)` (versions `"MCP server {n} attached/detached"`).
- [ ] **Step 1: Tests** `test_expected_version_conflict_changes_nothing`, `test_null_in_config_resets_a_key`,
  `test_deleting_an_agent_records_a_version_of_each_caller`, `test_an_agent_with_tokens_cannot_be_deleted`.
- [ ] **Step 2–4:** fail → implement → pass; `test_api_agents.py`, `test_api_agent_versions.py` pass.

### Task 18: VersionService, VersionController

**Files:**
- Modify: `app/services/versions.py` (add `VersionService`)
- Create: `app/api/controllers/versions.py`, `app/tests/test_unit_service_versions.py`
- Delete: `app/routers/agent_version.py`, the rollback/snapshot code in `database/mixins/agent_version.py` (the mixin stays only with
  what old callers still use until Task 29)

**Interfaces:**
- Produces: `VersionService(versions, agents, models, servers, connections, recorder, policy, uow)`: `list(principal, agent_id)`,
  `get(principal, agent_id, number)`, `diff(principal, agent_id, number, to: int | None)`, `rollback(principal, agent_id, to: int,
  comment) -> AgentVersion` (one transaction: reuse or copy the model (keeping the key of the record it replaces) and MCP servers,
  replace connections, set behaviour, record `"rolled back to version {n}"`).
- [ ] **Step 1: Tests** port `test_connections_are_part_of_the_callers_versions_and_come_back_with_a_rollback`,
  `test_a_rollback_skips_a_connection_to_an_agent_that_is_gone`, the model-copy key test from `test_unit_model_connection.py`, and
  `test_a_rollback_that_fails_halfway_changes_nothing`.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 19: ConnectionService, ConnectionController

**Files:**
- Create: `app/services/connections.py`, `app/api/schemas/connections.py`, `app/api/controllers/connections.py`,
  `app/tests/test_unit_service_connections.py`
- Delete: `app/routers/agent_connection.py`

**Interfaces:**
- Produces: `ConnectionService(connections, agents, recorder, uow)`: `list(principal, agent_id=None)`, `get`, `create(principal,
  ConnectionCreate)` (texts `"An agent cannot be connected to itself"`, `"Agent {id} not found"`, `"Agent {a} is already connected
  to agent {b}"`), `update`, `delete` (versions of the caller); `connected_of(agent_id) -> list[dict]` (id, name, description) used by
  the AI in Task 26. Router-level `min_role="admin"`.
- [ ] **Step 1–4:** tests (one per text + versions) → fail → implement → pass; `test_api_agent_connections.py` passes.

### Task 20: UserService, ChatService, their controllers

**Files:**
- Create: `app/services/users.py`, `app/services/chats.py`, `app/api/schemas/users.py`, `app/api/controllers/{users,chats}.py`,
  `app/tests/test_unit_service_people.py`
- Delete: `app/routers/user.py` (except `interrupt_user`, moved in Task 28; until then keep it in a temporary module),
  `app/routers/chat.py`, `app/routers/history.py`

**Interfaces:**
- Produces: `UserService(users, defaults, ttl_days)`: `search(principal, query, limit)`, `recent(principal, limit)`, `create(principal,
  external_id)` (`Conflict("User already exists")`), `get(principal, external_id)` (`NotFound("User not found")`), `rename`,
  `delete`, `ensure(agent_id, external_id) -> User` (insert; on `None` read again). `ChatService(users, chats, messages)`:
  `list(principal, external_id)`, `create`, `get`, `rename`, `delete`, `history(principal, external_id, chat_id: int | None)` (None =
  default chat; today's window of `message_limit` from `agent.settings(defaults)`), `clear(...)`, `resolve(principal, user, chat_id:
  int | None) -> Chat` (`NotFound("Chat not found")`). `UserController` keeps `/users/recent` declared before `/users/{user_id}`.
- [ ] **Step 1: Tests** port the `test_two_tools_that_ask_the_same_agent_at_once_both_get_its_user` race to `UserService.ensure`;
  `test_the_default_chat_is_made_once`; `test_history_of_an_unknown_user_is_not_found`.
- [ ] **Step 2–4:** fail → implement → pass; `test_api_users.py`, `test_api_chats.py` pass.

### Task 21: Memories, knowledge and usage controllers; stage 3 verification

**Files:**
- Create: `app/services/memories.py` (CRUD and search part of `MemoryService`), `app/services/knowledge.py`, `app/services/usage.py`,
  `app/api/schemas/{memories,knowledge}.py`, `app/api/controllers/{memories,knowledge,usage}.py`,
  `app/tests/test_unit_service_data.py`
- Delete: `app/routers/{memory,rag,usage}.py`

**Interfaces:**
- Consumes: `Embedder` protocol (Task 22 defines it; here use a temporary adapter over `ai.utils.get_embedding_vector`).
- Produces: `MemoryService(memories, users, embedder, policy, uow)`: `list(principal, external_id, agent_id, query=None, limit)`,
  `create`, `get`, `update`, `delete` (texts `"Memory not found"`, `"User not found"`); `KnowledgeService(knowledge, embedder,
  policy)`: `list`, `search` (`Invalid("limit above 100 is allowed without a query only")`), `create`, `get`, `update` (`"RAG entry not
  found or update failed"`), `delete`; `UsageService(usage, policy)`: `daily(principal, days, token_id, agent_id)`,
  `monthly(...)`.
- [ ] **Step 1–4:** tests → fail → implement → pass.
- [ ] **Step 5:** `routers/` keeps only `request.py`, `health.py` and the temporary interrupt route; move `/healthz /readyz /metrics`
  into `HealthController`; golden passes; all unit tests; full stack → pass; panel e2e → pass.
- [ ] **Step 6: Commit** `Move every resource but the agent runs to services and controllers (stage 3)`.

## Stage 4. AI

### Task 22: ModelGateway and Embedder

**Files:**
- Create: `app/infrastructure/__init__.py`, `app/infrastructure/llm.py` (`ModelGateway`, `ModelSettingsMapper`, `Embedder`,
  `OpenRouterEmbedder`; `RetryingTransport` moves here from `ai/transport.py`), `app/tests/test_unit_llm.py`
- Modify: callers of `ai.utils.generate_model/get_embedding_vector/http_client_for` get them from the gateway (container)

**Interfaces:**
- Produces: `ModelGateway(settings)`: `chat_model(model: Model) -> pydantic_ai.models.Model`, `client(use_proxy: bool) ->
  httpx2.AsyncClient` (two shared clients, read timeout 600, connect 5), `aclose()`; `ModelSettingsMapper.settings(request_json,
  openrouter: bool) -> dict` (today's `model_settings`); `class Embedder(Protocol): async def embed(text: str) -> list[float]`.
- [ ] **Step 1: Tests** port `test_generate_model_maps_openrouter_options`, `test_model_settings_pass_every_key_of_the_body_on`,
  the client tests of `test_unit_ai.py`/`test_unit_model_connection.py` and `test_unit_transport.py` to the new classes (no
  monkeypatch of module globals: construct `ModelGateway(settings)` with test settings).
- [ ] **Step 2–4:** fail → implement → pass.

### Task 23: InterruptRegistry, StopBus, StreamGuard

**Files:**
- Create: `app/ai/interrupts.py` (`ActiveStream`, `InterruptRegistry`, `StreamGuard`), `app/infrastructure/redis.py` (`StopBus`
  Protocol, `RedisStopBus` = today's `InterruptBus`, `LocalStopBus`), `app/tests/test_unit_interrupts.py`
- Delete: `app/ai/interrupt.py`, `app/ai/interrupt_bus.py` (callers switch to the registry from the container)

**Interfaces:**
- Produces: `InterruptRegistry(bus: StopBus, stop_timeout: float = 15)`: `start(key) -> ActiveStream`, `end(stream)`, `stop(agent_id,
  user_id) -> ActiveStream | None` (here or on another replica, waits until saved), `serve()` (the bus loop),
  `current: ContextVar[ActiveStream | None]` as an attribute; `StreamGuard.items(source: AsyncIterator[T], stream) -> AsyncIterator[T]`
  (today's `until_stopped`: one producer task, queue, stop cancels).
- [ ] **Step 1: Tests** port `test_unit_interrupt.py` and `test_unit_interrupt_bus.py` (two registries on one fakeredis server).
- [ ] **Step 2–4:** fail → implement → pass.

### Task 24: McpHealth with stores

**Files:**
- Modify: `app/ai/mcp_health.py` → `app/infrastructure/mcp_health.py` (`McpHealth(store, down_seconds)`, `HealthStore` Protocol,
  `RedisHealthStore`, `LocalHealthStore`), `app/ai/capabilities/mcp.py` (`GuardedServer`/`McpServers` take `health` in the
  constructor; no global `health`)
- Test: `app/tests/test_unit_mcp_servers.py` (rewrite the fixtures: no `health._local`, no `monkeypatch` of `mcp_module`)

**Interfaces:**
- Produces: `McpHealth.why_down(key) -> str | None`, `mark_down(key, why)`; `McpServers(servers=..., health=..., attempts=...,
  retry_delay=...)`.
- [ ] **Step 1–4:** port the tests → fail → implement → pass.

### Task 25: MemoryService for agents, MemoryExtractor, TaskSupervisor

**Files:**
- Modify: `app/services/memories.py` (add `remember`, `recall`, `forget`, `block(conversation) -> str`, `backfill(batch)`)
- Create: `app/ai/memory_extractor.py`, `app/infrastructure/jobs.py` (`TaskSupervisor`, `PeriodicJob`), `app/tests/test_unit_memory_
  service.py`
- Delete: from `app/ai/memory.py` everything but `MEMORY_INSTRUCTIONS`, `EXTRACTION_INSTRUCTIONS` and the thresholds (moved to
  `services/memories.py`)

**Interfaces:**
- Produces: `MemoryService.remember(conversation, fact) -> str` (today's tool answer texts; duplicate ≤ 0.06, similar ≤ 0.25 shown),
  `recall(conversation, query) -> str` (meaning ≤ 0.82, then words; empty query = newest), `forget(conversation, memory_id) -> str`,
  `block(conversation) -> str` (`<Memory>…</Memory>`, newest `memo_limit`, "Nothing is remembered…" text, the "N older memories are not
  shown" line). `TaskSupervisor`: `spawn(coro, name) -> asyncio.Task`, `aclose()` (cancel and wait). `MemoryExtractor(gateway,
  models, memories, supervisor, metrics)`: `schedule(conversation, model: Model, user_text, answer)` (no-op unless `auto_memory`
  and the memory tool are on).
- [ ] **Step 1: Tests** port `test_unit_memory.py` (formatting, dedupe, recall, extraction, backfill) to the service with a fake
  `Embedder` and `TestModel`; `test_extraction_tasks_are_cancelled_at_close`.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 26: Capability providers, RunDeps, AgentFactory

**Files:**
- Create: `app/ai/deps.py` (replace: `RunDeps`), `app/ai/factory.py` (`AgentFactory`, `CapabilityProvider` Protocol, the six
  providers), `app/tests/test_unit_agent_factory.py`
- Modify: `app/ai/capabilities/{knowledge,memory,agent_calls,parallel}.py` (tools call `ctx.deps.knowledge`/`ctx.deps.memory`/
  `AgentAsker`; no SQL, no `db`), `app/ai/capabilities/__init__.py` (drop `build_capabilities`)

**Interfaces:**
- Produces: `RunDeps(conversation: Conversation, memory: MemoryService, knowledge: KnowledgeService)`;
  `class CapabilityProvider(Protocol): def applies(self, conversation) -> bool; async def build(self, conversation) ->
  AbstractCapability`; `class AgentAsker(Protocol): async def ask_as_agent(self, conversation: Conversation, agent_id: int, request:
  str) -> str`; `AgentFactory(gateway, providers, settings)`: `build(conversation, model: Model) -> pydantic_ai.Agent` (instructions =
  prompt or none, `retries={"tools": 2}`, `model_settings={"parallel_tool_calls": False}` only when off, `ParallelCallsProvider` last
  and only when another provider gave tools). `Conversation` is Task 12's.
- [ ] **Step 1: Tests** port `test_agent_registers_only_the_enabled_tools`, the memory/knowledge tool tests, `test_only_an_agent_with_
  tools_is_told_to_call_them_together` and the instruction-order tests of `test_unit_prompts.py` to the factory with fake services.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 27: AgentRunner, PromptBuilder, UsageMeter

**Files:**
- Create: `app/ai/runner.py` (replace), `app/ai/prompts.py` (`PromptBuilder`), `app/ai/usage.py` (`UsageMeter` replaces
  `track_usage`), `app/ai/events.py` (`TextChunk`, `Finished`; `TraceStep` stays in `ai/trace.py`), `app/tests/test_unit_runner.py`

**Interfaces:**
- Produces: `RunRequest(text, attachments=(), use_memo=True, trace=False, stream=True, kind="request")`; `AgentRunner(factory,
  prompts, usage, models, settings)`: `run(conversation, request) -> AsyncIterator[TextChunk | TraceStep | Finished]` (no storing;
  timeout `request_timeout_seconds`; `parallel_tool_call_execution_mode("sequential")` when off; blank line between text parts of
  different turns; `stream=False` runs nodes without streaming). `PromptBuilder(messages, memories)`: `history(conversation,
  use_memo) -> list[ModelMessage]`, `prompt(conversation, text, attachments) -> str | list`. `UsageMeter(usage)`: `async with
  meter.track(principal, kind, model_name) as spent: spent.add(messages)` (statuses ok / HTTP status / cancelled / interrupted).
- [ ] **Step 1: Tests** port `test_unit_prompts.py` (runs, trace, stream steps, stop), `test_unit_parallel.py` (timing, sequential
  when off) and `test_unit_usage.py` (meter statuses) to the runner with `FunctionModel`/`TestModel` and fakes.
- [ ] **Step 2–4:** fail → implement → pass.

### Task 28: ConversationService, ConversationController, SseStream; stage 4 verification

**Files:**
- Create: `app/services/conversations.py`, `app/api/sse.py`, `app/api/controllers/conversations.py`, `app/tests/test_unit_
  conversations.py`
- Modify: `app/api/controllers/users.py` (gains `interrupt_user`)
- Delete: `app/routers/` (all), `app/ai/endpoint`-era leftovers

**Interfaces:**
- Produces: `ConversationService(users, chats, messages, runner, interrupts, extractor, policy, agents, connections, defaults,
  settings)`: `answer(principal, MessageRequest) -> MessageResponse` (stops the pair's stream first; stores the exchange unless
  `save_message` is false; schedules auto_memory), `stream(principal, MessageRequest) -> AsyncIterator[SseEvent]` (registers in
  `InterruptRegistry`, `StreamGuard`, saves the interrupted part with `"interrupted": true`), `interrupt(principal, external_id) ->
  Interrupted`, `ask_as_agent(conversation, agent_id, request) -> str` (implements `AgentAsker`: chain refusals, `may_act_as`,
  user `caller_user_id(...)` via `UserService.ensure`, default chat, kind `agent_call`, failures as `"Agent {id} could not answer
  (HTTP {status}): {detail}"`). `SseStream.encode(event) -> str` (same lines as today). The controller keeps `_until_disconnect`
  (cancel on client disconnect → 499 body `Client closed the request`).
- [ ] **Step 1: Tests** port `test_unit_agent_calls.py` (scripted model, chains, refusals, usage kinds),
  `test_an_interrupted_exchange_is_saved_with_what_was_said_and_remembered`, `test_a_cut_answer_is_given_to_the_model_as_an_answer_of_
  its_own`; add `test_a_disconnected_client_stores_nothing`.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5:** All unit tests, golden, full stack (with `test_api_agent_calls.py`, `test_api_interrupt.py`, `test_api_replicas.py`),
  panel e2e → pass; `grep -rn "request.state.db\|PostgresDB" app --include=*.py` lists only `database/` and old tests.
- [ ] **Step 6: Commit** `Run agents through the runner, conversation service and SSE stream (stage 4)`.

## Stage 5. Cleanup

### Task 29: Delete the old layer, jobs, docs

**Files:**
- Delete: `app/database/{methods,context}.py`, `app/database/mixins/`, `app/access.py`, `app/ai/utils.py`, `app/middlewares/`,
  `app/core/config.py` constants (keep `Settings` only), `app/core/decorators.py` if unused; move `database/models.py` entities to
  `domain/` (`domain/entities.py` or per area) and `database/foundation.py`, `retention.py`, `usage_compaction.py` to
  `infrastructure/postgres.py` + `infrastructure/jobs.py` as `MessageRetentionJob`, `UsageCompactionJob`, `EmbeddingBackfillJob`
  (`PeriodicJob` subclasses)
- Modify: `app/container.py` (start order: pool → initial token → bus/serve → jobs; `aclose()` order: jobs → supervisor → bus/Redis →
  gateway clients → pool), `app/tests/shared.py` (`FakeDB` deleted; fakes per repository/service), `AGENTS.md` (repository map, request
  flow, database rules, configuration, testing sections rewritten for the new layout), `README.md` of the backend
- Test: `app/tests/test_unit_container.py` (`test_aclose_stops_jobs_before_the_pool`), `app/tests/test_unit_architecture.py`

**Interfaces:**
- Produces: `PeriodicJob(name, interval)`: `run_once() -> None` (abstract), `start()`, `aclose()`.
- [ ] **Step 1: Tests** `test_aclose_stops_jobs_before_the_pool` (fake job records the order); architecture rules as tests:
  `test_domain_imports_nothing_of_the_project`, `test_only_settings_reads_the_environment` (no `os.getenv` outside `config.py`),
  `test_no_module_keeps_mutable_state` (scan for module-level `_active`, `bus =`, `_http_client`, `_embedder`, `_background`, `health =`),
  `test_controllers_do_not_import_repositories`.
- [ ] **Step 2–4:** fail → delete/move → pass; all unit tests; golden.
- [ ] **Step 5:** Full stack, panel e2e → pass; ruff `--select F` clean on `app/`.
- [ ] **Step 6: Commit** `Remove PostgresDB, the mixins and the module globals (stage 5)`.

## Stage 6. Library 5.0

### Task 30: Transport, errors, endpoints

**Files:**
- Create: `omnixon-library/omnixon/transport.py` (`Transport`, `RetryPolicy`, `ErrorMapper`), `omnixon/endpoints.py` (`Endpoint`,
  `endpoints()`), `tests/test_transport.py`
- Modify: `omnixon/exceptions.py` (`OmnixonError` base; `NoAccess`, `NotFound`, `Conflict`, `InvalidRequest`, `UpstreamError(status_
  code)`, `StreamError`, `OmnixonConnectionError`)

**Interfaces:**
- Produces: `Endpoint(method: str, path: str)` (frozen; `path` with `{name}` parameters, full path from `/api/v1`), `endpoints() ->
  set[tuple[str, str]]` (every `Endpoint` attribute of every resource class); `RetryPolicy(attempts=3, on=(httpx.ReadError,))`;
  `Transport(base_url, token, act_as_agent=None, timeout=5.0, long_timeout=120.0)`: `request(endpoint, *, path: dict, json=None,
  params=None, long=False, retry: RetryPolicy | None = None) -> httpx.Response` (user ids URL-quoted with `safe=""`), `stream(...)`,
  `aclose()`; `ErrorMapper.raise_for(response)` (today's status → exception mapping and `detail` extraction, 422 lists joined by
  `"; "`).
- [ ] **Step 1: Tests** port the error-mapping and retry tests of `tests/test_client.py`; `test_a_user_id_with_a_slash_is_quoted`;
  `test_no_network_in_the_constructor`.
- [ ] **Step 2–4:** fail → implement → pass (`uv run pytest tests/test_transport.py`).

### Task 31: Messages, users, chats

**Files:**
- Create: `omnixon/resources/{base,messages,users}.py` (`Resource`, `MessagesResource`, `UsersResource`, `ChatsResource`,
  `HistoryResource`), `omnixon/sse.py` (`SseReader`, `MessageStream`), `tests/test_resources_messages.py`

**Interfaces:**
- Produces: `client.messages.send(user_id, text, *, chat_id=None, save_message=True, use_memo=True, attachments=(), trace=False) ->
  MessageResponse` (retried by `RetryPolicy`), `.stream(...) -> MessageStream` (not retried), `.interrupt(user_id) -> Interrupted`;
  `client.users.search(query, limit=10)`, `.recent(limit=20)`, `.create(external_id)`, `.get(external_id)`, `.rename(external_id,
  new_id)`, `.delete(external_id)`; `client.users.chats.list(user_id)`, `.create(user_id, title=None)`, `.get`, `.rename`,
  `.delete`, `.history(user_id, chat_id)`, `.clear(user_id, chat_id)`; `client.users.history.get(user_id)`, `.clear(user_id)`.
- [ ] **Step 1: Tests** port the message, stream (`.user` before chunks, `.interrupted`, `.trace`, `StreamError`), user and chat tests
  of `tests/test_client.py` (method, path, exact JSON body).
- [ ] **Step 2–4:** fail → implement → pass.

### Task 32: Agents, versions, connections, models, MCP servers

**Files:**
- Create: `omnixon/resources/{agents,connections,models,mcp_servers}.py`, `tests/test_resources_agents.py`

**Interfaces:**
- Produces: `client.agents.list()`, `.get(id)`, `.self()`, `.create(name, prompt, model_id, *, config=None, comment=None)` (body from
  given values only; `config` dumped with `exclude_unset=True` so `None` resets a key), `.update(id, *, name, prompt, model_id, config,
  comment, expected_version)`, `.delete(id)`; `client.agents.versions.list(agent_id)`, `.get(agent_id, number)`, `.diff(agent_id,
  number, to=None)`, `.rollback(agent_id, to, comment=None)`; `client.agents.mcp_servers.list(agent_id)`, `.attach(agent_id,
  server_id)`, `.detach(agent_id, server_id)`; `client.connections.list(agent_id=None)`, `.create(agent1_id, agent2_id,
  description)`, `.get`, `.update(id, description)`, `.delete`; `client.models.list/get/create(name, request_json, *, base_url,
  use_proxy, api_token)/update/delete`; `client.mcp_servers.list/get/create(name, config, agent_id=None)/update/delete`.
- [ ] **Step 1–4:** port tests → fail → implement → pass.

### Task 33: Memories, knowledge, tokens, usage; the facade

**Files:**
- Create: `omnixon/resources/{memories,knowledge,tokens,usage}.py`, `omnixon/client.py` (`Omnixon`), `omnixon/types/` (models split by
  area, same fields), `tests/test_resources_data.py`, `tests/test_endpoints_cover_the_service.py`
- Modify: `omnixon/__init__.py` (exports `Omnixon`, `MessageStream`, every model, the exceptions), `tests/test_server_contract.py`
  (imports from `omnixon.types`)
- Delete: `omnixon/main.py`, `omnixon/schemes.py`, `tests/test_client.py` (all ported by now)

**Interfaces:**
- Produces: `client.memories.list(user_id, *, agent_id=None, query=None, limit=...)`, `.create`, `.get`, `.update`, `.delete`;
  `client.knowledge.list(*, agent_id=None, limit, offset)`, `.search(query, ...)`, `.create(content, ...)`, `.get`, `.update`, `.delete`;
  `client.tokens.self()`, `.list(agent_id=None)`, `.create(name, role, agent_id) -> NewToken`, `.update(id, *, name=None, role=None)`,
  `.delete`; `client.usage.daily(*, days, token_id, agent_id)`, `.monthly(...)`. `Omnixon(token, base_url, act_as_agent=None, *,
  timeout=5.0, long_timeout=120.0, retry=RetryPolicy())`, `async with`, `ping() -> Token` (raises `NoAccess`/`OmnixonConnectionError`),
  `ready() -> bool`, `aclose()`.
- [ ] **Step 1: Tests** port the rest of `tests/test_client.py`; `test_every_route_of_the_service_is_called_or_left_out` (snapshot
  paths vs `endpoints()`, `LEFT_OUT` = `/api/v1/`, `/healthz`, `/readyz` with reasons); the contract test unchanged in substance.
- [ ] **Step 2–4:** fail → implement → pass (`uv run pytest`).

### Task 34: Sync tooling, docs, version; stage 6 verification

**Files:**
- Modify: `.claude/skills/sync-omnixon-lib/scripts/check_sync.py` (client routes from `omnixon.endpoints()` instead of regexes over
  `main.py`), `.claude/skills/sync-omnixon-lib/SKILL.md` (the table: "a new route = an `Endpoint` + a method on its resource"),
  `omnixon-library/README.md` (every resource method, errors, a v4 → v5 table), `omnixon-library/test.py`, `pyproject.toml`
  (`uv version 5.0.0`), `AGENTS.md` (library section)

- [ ] **Step 1:** `python3 .claude/skills/sync-omnixon-lib/scripts/check_sync.py` → `RESULT: in sync`.
- [ ] **Step 2:** `uv build`; install the wheel into a clean venv outside the repo; against the running test stack drive: ping, send,
  stream (+ `.user`), interrupt, agents create/update(reset a config key)/versions/rollback, connections, tokens, knowledge list,
  memories search, usage; every call answers as expected.
- [ ] **Step 3: Commit** `Rebuild the library as resources (5.0.0) (stage 6)`.

## Stage 7. Final

### Task 35: Final verification

- [ ] **Step 1:** All backend unit tests; golden OpenAPI; full stack with two replicas (≥ today's 417 tests; only known flakes,
  rerun); no `"level": "error"` lines; panel e2e (111); library tests; MCP tests (`omnixon-mcp`: `uv run --group test pytest`, 30).
- [ ] **Step 2:** Rebuild the user's stack (`docker compose up -d --build api` in `omnixon/`), `/readyz` ok, `/openapi.json` has
  `x-min-role`.
- [ ] **Step 3:** Remove `omnixon_unit_verify_db`; update the `Status` sections of `AGENTS.md`.
- [ ] **Step 4: Commit** `Final verification of the OOP architecture (stage 7)`; report to the user in Russian (what was verified,
  what failed and why, the bot needs the v5 migration).
