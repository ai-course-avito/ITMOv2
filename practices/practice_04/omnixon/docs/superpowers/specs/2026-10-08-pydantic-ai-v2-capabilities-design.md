# pydantic-ai 2.x and a capabilities-based `ai/` (design)

Asked for on 2026-10-08: update pydantic-ai (1.58 -> 2.54), make `agent_calls` a design to be proud of, a tool that fails never ends the run, one path to
run an agent (not two), roles in OpenAPI, coordination in Redis. pydantic-ai 2 has what these needed: **capabilities** (tools + instructions + hooks
bundled), **tool error hooks / `ToolFailed`**, **`MCPToolset`** and **transport retries** (tenacity on the provider's httpx2 client).

## Shape

`ai/capabilities/` - one capability per thing an agent can have; `build_capabilities(db)` reads the agent row and returns the list:

| capability | gives the agent |
|---|---|
| `KnowledgeBase` | `retrieve` (rag_limit) |
| `Memory` | `remember`/`recall`/`forget` + the static instructions (the per-request `<Memory>` block stays in the user prompt) |
| `AgentCalls` | `list_agents`/`ask_agent` over `agent_connections` (+ the call chain) |
| `McpServers` | one `MCPToolset` per attached server, each behind a wrapper that isolates it: a server that cannot be reached gives no tools and a note in the instructions, a call that does not get through is tried 3 times then reported |
| `ToolFailures` | `on_tool_execute_error`: any tool that raises (not a cancel, not a request to the model to retry) becomes a failed tool result with what happened; the run goes on |

`generate_agent` becomes `Agent(model, capabilities=[...])`. Nothing registers tools on an agent by hand.

## Retries are where they belong
- Provider failures (429/5xx/connection): a tenacity transport on the provider's httpx2 client (`wait_retry_after`, 3 attempts). Nothing re-runs a run;
  `ai/resume.py`, the provider half of `ai/resilience.py` and `Progress` go away.
- A tool that fails: `ToolFailed` (does not use the retry budget of the tool); transport errors of MCP tools are tried 3 times first.
- The down-cache of MCP servers (don't try a dead server for 30 s) and the interrupt registry live in Redis when REDIS_URL is set (all replicas).

## One way to run an agent
`ai/runner.py`: `run_agent(db, request, ...)` is an async generator of events (`Text`, `Step`, `Done(output)`), over `agent.iter`; the JSON endpoint reads it
to the end, the SSE endpoint forwards it. Persisting the exchange, usage, auto-memory and the interrupt hand-off happen once, in the runner. The two
HTTP routes stay (they are the public API), as thin adapters.

## Roles in OpenAPI
`require(role)` marks its dependency; `custom_openapi()` walks each route's dependencies and writes `x-min-role` on every operation. omnixon-mcp
reads it (tests) instead of a hand-kept `ADMIN_ONLY`.

## Tests
Coverage of the unit tests is measured (coverage.py) and the gaps closed; agent connections get an end-to-end test over HTTP with a scripted model.

## As built (differences from the plan above)
- Provider retries are `ai/transport.py` (`RetryingTransport` on our own httpx2 client), not tenacity: `wrap_model_request` may call its handler only once,
  and the client also has to keep the proxy / no-proxy choice and the 600 s read timeout. Same effect: the run never notices.
- `run_agent` yields `str | TraceStep | Finished` (not `Text/Step/Done`) and takes `stream`: the JSON route runs the same code with `stream=False`, so the
  provider is asked for whole answers there (as before) and for pieces on the SSE route.
- The call chain of `ask_agent` is `db.context.chain` (explicit, derived with `db.with_context(...)`), not a ContextVar; "how to run an agent" is injected into
  `AgentCalls` (`answer=`), so the capability does not import the runner.
- `AbstractCapability` is a dataclass with `id` first: capabilities with fields are `kw_only`.
- `x-min-role` is written by `openapi.add_roles` (and a Bearer security scheme); omnixon-mcp keeps its table (`ADMIN_ONLY`) but a contract test compares it with the schema.
- `ToolFailures` also catches pydantic-ai's own `UnexpectedModelBehavior` for exhausted tool retries (raised inside the same hook), which is what used to end answers.
