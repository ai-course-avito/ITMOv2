# omnixon-mcp

Omnixon as an MCP server, for a model that has to manage it: make and change agents, connect them to each other, fill their knowledge,
read chats, hand out tokens, read what was spent, and try an agent by sending it a message. The tools are written by hand, around tasks
(not one per route of the API): descriptions say when to use each, arguments are typed and explained, answers are short and keep only
what a model needs. `get_agent` is one call for what would take five requests.

Start with `about_omnixon`: it explains what an agent, a version, a connection, a token, a user and a chat are, and what the token you
connected with may do.

## Roles

What a model is offered depends on the role of the token the server was connected with (the service stays the authority and refuses the rest):

| Role | Tools | What it can do |
|---|---|---|
| regular | 14 | talk to the people and chats of its own agent (find, read, clear, interrupt) |
| user | 40 | plus manage its own agent: config, versions, knowledge, memories, MCP servers, tokens (up to user), usage, read models |
| admin | 52 | plus every agent: make/delete agents and models, connect agents, `agent_id` on everything, `send_message` |
| owner | 52 | as admin; may hand out tokens of any role |

Descriptions change with the role too ("works on your own agent (id 5)" for a user token, `agent_id` offered to admins only).

## The tools

| Group | Tools |
|---|---|
| `self` | `about_omnixon`, `whoami` |
| `agents` | `find_agents` (admin), `get_agent`, `create_agent` (admin), `update_agent`, `delete_agent` (admin), `list_versions`, `show_version`, `rollback_agent`, `list_connections`, `connect_agents`, `change_connection`, `disconnect_agents` (these four admin) |
| `messages` | `send_message` (admin), `interrupt_answer` |
| `users` | `find_users`, `recent_users`, `create_user`, `rename_user`, `delete_user`, `list_chats`, `read_chat`, `start_chat`, `rename_chat`, `clear_chat`, `delete_chat` |
| `knowledge` | `add_knowledge`, `search_knowledge`, `list_knowledge`, `edit_knowledge`, `delete_knowledge` |
| `memories` | `list_memories`, `add_memory`, `edit_memory`, `delete_memory` |
| `models` | `list_models`, `create_model` (admin), `edit_model` (admin), `delete_model` (admin) |
| `mcp` | `list_mcp_servers`, `add_mcp_server`, `edit_mcp_server`, `delete_mcp_server`, `attach_mcp_server` (admin), `detach_mcp_server` |
| `tokens` | `list_tokens`, `create_token`, `edit_token`, `delete_token` |
| `usage` | `usage_report`, `usage_report_monthly` |

`?groups=` on the URL keeps only some groups (`self` always stays), e.g. `http://mcp:8090/mcp?groups=agents,messages`: fewer tools, fewer
tokens on every model call (all of them are about 8k tokens).

## The token

Set once in the connection; no tool takes a token, so a model never sees or repeats it: the header `Authorization: Bearer <token>`
(preferred) or `?token=<token>` in the URL (for clients that take only a URL; the server writes no access log for this reason).
Without a token, or with one the service rejects, the server lists one tool, `omnixon_connect`, which tells the model to ask for the token
in the connection, not in the chat.

## Messages: an agent never speaks for a person

`send_message` (admin and owner) is written as the user `agentmcp_<agent id of the token>`; it takes no user id. It refuses the token's
own agent, so an agent cannot call itself in a loop.

## Agent of agents

Attach the server to an agent in Omnixon, with a token of that agent in the headers (an admin token to let it manage agents):

```json
{"name": "omnixon-mcp", "agent_id": 2,
 "config": {"url": "http://mcp:8090/mcp?groups=agents,messages",
            "headers": {"Authorization": "Bearer <admin token of agent 2>"}, "timeout": 30}}
```

Asked "make a pirate agent, connect yourself to it and ask it to say hello", such an agent called `create_agent`, `connect_agents` and
`ask_agent` (the built-in tool a connection gives it) and reported the answer. Headers of an MCP server are not shown by `get_agent`,
`list_mcp_servers` and the like (their values read `<hidden>`).

## Running

```bash
uv sync --group test
OMNIXON_URL=http://localhost:8083 uv run omnixon-mcp     # http://0.0.0.0:8090/mcp
uv run --group test pytest                               # no service needed
```

In the stack: `docker compose up -d --build` in the folder above starts it as `mcp` (port `MCP_PORT`, 8090). Claude Code: `.mcp.json` there reads
`OMNIXON_TOKEN` (and `OMNIXON_MCP_URL`), or `claude mcp add --transport http omnixon http://localhost:8090/mcp --header "Authorization: Bearer <token>"`.

Settings (env): `OMNIXON_URL` (the service, default `http://localhost:8083`), `OMNIXON_MCP_HOST` (`0.0.0.0`), `OMNIXON_MCP_PORT` (`8090`),
`OMNIXON_MCP_IDENTITY_SECONDS` (how long a token's role is cached, `30`).

## Layout and keeping up with the API

```
src/omnixon_mcp/
  server.py      low-level MCP server, stateless streamable HTTP at /mcp, token from header or ?token=, /healthz
  registry.py    Tool, @tool, the schema/description of a tool for a role, `run` (validates, calls the handler, compact JSON)
  access.py      roles, Identity, ADMIN_ONLY (the routes that need admin) and the lowest role of a route
  api.py         Ctx: the calls of one tool call (token, acting agent, X-Act-As-Agent, errors a model can act on)
  tools/         overview, agents, connections, mcp_servers, models, knowledge, memories, users, messages, tokens, usage
tests/test_contract.py    the tools against the service's OpenAPI (omnixon-library/tests/server_openapi.json)
tests/test_behaviour.py   what each important tool sends and returns, against a service that is a table of answers
```

Every tool declares the routes it calls. The contract test fails when the service has a route no tool uses (write a tool, or add the route
to `LEFT_OUT` with the reason), when a tool names a route that is not there, and when a tool is offered to a role lower than its routes need.
