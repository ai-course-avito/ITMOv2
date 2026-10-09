from __future__ import annotations

from ..registry import i, o, s, tool
from .common import mcp_brief, user_note, without_none

SERVERS = "/api/v1/admin/mcp-servers"
AGENTS = "/api/v1/admin/agents"

URL = s("The address of the server, e.g. http://tools:9100/mcp")
TRANSPORT = s("'streamable_http' (the usual) or 'sse'.", enum=["streamable_http", "sse"])
HEADERS = o(
    'Headers sent to the server with every call, e.g. {"Authorization": "Bearer ..."}. Their values are never shown back.',
    additionalProperties={"type": "string"},
)
OPTIONS = o(
    "Other options of the connection: timeout (seconds), read_timeout, tool_prefix, max_retries, allow_sampling, cache_tools, cache_resources, log_level, id.",
)


def config_of(url=None, transport=None, headers=None, options=None, base: dict | None = None) -> dict:
    config = dict(base or {})
    config.update(options or {})
    config.update(without_none(url=url, transport=transport, headers=headers))
    return config


@tool(
    "list_mcp_servers",
    group="mcp",
    role="user",
    description="The MCP servers (external tools) an agent may use: id, name, address. Admins and owners without agent_id get every server of the "
    "service, attached or not.",
    props={"agent_id": i("Only the servers attached to this agent.", minimum=1)},
    routes=(("GET", AGENTS + "/{agent_id}/mcp-servers"),),
    admin_routes=(("GET", SERVERS),),
    note=lambda who: "" if who.is_admin else f"Lists the servers of your own agent (id {who.agent_id}).",
)
async def list_mcp_servers(c, agent_id=None):
    if agent_id is None and c.who.is_admin:
        found = await c.get(SERVERS)
    else:
        found = await c.get(f"{AGENTS}/{agent_id or c.who.agent_id}/mcp-servers")
    return [mcp_brief(x) for x in found]


@tool(
    "add_mcp_server",
    group="mcp",
    role="user",
    description="Registers an MCP server and attaches it to an agent at once: the agent's model can then call the tools the server offers. "
    "A new version of the agent is recorded. If the server is down later the agent goes on without it and says so.",
    props={
        "name": s("A name for the server.", minLength=1, maxLength=120),
        "url": URL,
        "transport": TRANSPORT,
        "headers": HEADERS,
        "options": OPTIONS,
        "agent_id": i("The agent to attach it to (default: your own).", minimum=1),
    },
    required=("name", "url"),
    routes=(("POST", SERVERS),),
    note=user_note("It is attached to your own agent."),
)
async def add_mcp_server(c, name, url, transport=None, headers=None, options=None, agent_id=None):
    config = config_of(url, transport, headers, options)
    made = await c.post(
        SERVERS, json_body=without_none(name=name, config=config, agent_id=agent_id or c.who.agent_id)
    )
    return {"added": mcp_brief(made)}


@tool(
    "edit_mcp_server",
    group="mcp",
    role="user",
    description="Changes an MCP server: only what you give changes (headers replace the old ones as a whole). Every agent that has it attached gets a "
    "new version. A user token may change only servers attached to its own agent and to no other.",
    props={
        "mcp_server_id": i("The server (an id from list_mcp_servers).", minimum=1),
        "name": s("A new name.", minLength=1, maxLength=120),
        "url": URL,
        "transport": TRANSPORT,
        "headers": HEADERS,
        "options": OPTIONS,
    },
    required=("mcp_server_id",),
    routes=(("GET", SERVERS + "/{mcp_server_id}"), ("PATCH", SERVERS + "/{mcp_server_id}")),
)
async def edit_mcp_server(c, mcp_server_id, name=None, url=None, transport=None, headers=None, options=None):
    current = await c.get(f"{SERVERS}/{mcp_server_id}")
    config = config_of(url, transport, headers, options, base=current["config"])
    body = without_none(name=name, config=config if config != current["config"] else None)
    updated = await c.patch(f"{SERVERS}/{mcp_server_id}", json_body=body)
    return {"updated": mcp_brief(updated)}


@tool(
    "delete_mcp_server",
    group="mcp",
    role="user",
    description="Deletes an MCP server and detaches it from every agent (each gets a new version). To only stop one agent from using it, use detach_mcp_server.",
    props={"mcp_server_id": i("The server to delete.", minimum=1)},
    required=("mcp_server_id",),
    routes=(("DELETE", SERVERS + "/{mcp_server_id}"),),
)
async def delete_mcp_server(c, mcp_server_id):
    server = await c.delete(f"{SERVERS}/{mcp_server_id}")
    return {"deleted": {"id": server["id"], "name": server["name"]}}


@tool(
    "attach_mcp_server",
    group="mcp",
    role="admin",
    description="Gives an agent an MCP server that already exists (made for another agent, say). A new version of the agent is recorded.",
    props={
        "agent_id": i("The agent.", minimum=1),
        "mcp_server_id": i("The server (list_mcp_servers).", minimum=1),
    },
    required=("agent_id", "mcp_server_id"),
    routes=(("POST", AGENTS + "/{agent_id}/mcp-servers/{mcp_server_id}"),),
)
async def attach_mcp_server(c, agent_id, mcp_server_id):
    servers = await c.post(f"{AGENTS}/{agent_id}/mcp-servers/{mcp_server_id}")
    return {"agent_now_has": [mcp_brief(x) for x in servers]}


@tool(
    "detach_mcp_server",
    group="mcp",
    role="user",
    description="Stops an agent from using an MCP server (the server itself stays). A new version of the agent is recorded.",
    props={"mcp_server_id": i("The server to detach.", minimum=1)},
    required=("mcp_server_id",),
    scoped=True,
    routes=(("DELETE", AGENTS + "/{agent_id}/mcp-servers/{mcp_server_id}"),),
)
async def detach_mcp_server(c, mcp_server_id):
    servers = await c.delete(f"{AGENTS}/{c.agent}/mcp-servers/{mcp_server_id}")
    return {"agent_now_has": [mcp_brief(x) for x in servers]}
