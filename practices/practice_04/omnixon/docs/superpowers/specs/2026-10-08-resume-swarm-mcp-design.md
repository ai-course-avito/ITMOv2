# Resume after failure, Swarm-safe interrupts, a hand-written omnixon-mcp (design)

Approved in chat 2026-10-08 ("Вперед, хороший план"). Order of work: 1, 2, 3, then lazy pages of the panel (cheap, no design needed).

## 1. A retry continues where the run broke (backend, `ai/endpoint.py`, `ai/resilience.py`)
- A run collects its messages. After a failure that may pass (provider 5xx/429/timeout/empty answer) the next attempt starts from
  the messages that are complete (the question, finished model responses, tool results); an unfinished model response is dropped and that
  step is asked again. Tools that already returned are never called again.
- Usage, saved history and trace cover all attempts.
- A stream that already sent text to the client is not restarted (as now); tool work done before is kept.
- Test: a scripted model (FunctionModel) fails on its second step after a tool ran: the tool ran once, the answer arrives.

## 2. Swarm: interrupts across replicas (Redis)
- `REDIS_URL` optional. Unset: in-process registry as now (unit tests, local run unchanged).
- Set: a running stream holds key `omnixon:stream:<agent>:<user>` = instance id (TTL, renewed). Stop (endpoint or a new request of the same pair)
  publishes on channel `omnixon:stop`; the owner stops its stream, saves, publishes `omnixon:stopped:<stream id>`; the asker waits <= 15 s.
- Background jobs are already safe on several instances (usage folding is DELETE ... RETURNING, retention deletes are repeatable). The MCP-down
  cache and metrics stay per instance.
- Redis in the root compose, the test stack and the Swarm files. Test: two api instances; stream on one, Stop on the other.

## 3. omnixon-mcp by hand
- Modules by meaning (agents, connections, knowledge, memories, users and chats, models, mcp servers, tokens, usage, messages); tools named for
  actions, with descriptions saying when to use them, typed arguments, short answers; fewer calls per task (`get_agent` returns prompt, model,
  effective config, MCP servers, connections in and out, latest version).
- `about_omnixon` (what agent / connection / token / user / chat / memory / knowledge / version are, and what this role can do), `whoami`,
  server `instructions` pointing to `about_omnixon`.
- Kept: role-dependent tool sets and notes, `?groups=`, `agentmcp_` user and no self-messages, `omnixon_connect` without a token.
- Guard against drift: a test compares the backend's OpenAPI with a route -> tool map; a route without a tool (or a deliberate exclusion) fails it.
- Verified live from Claude Code and by Agent manager doing an agent-of-agents task.

## 4. Lazy pages (panel)
- `React.lazy` per page in `App.tsx` with a Suspense fallback; the front page and login stay eager.
