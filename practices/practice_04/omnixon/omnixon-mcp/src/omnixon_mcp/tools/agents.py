from __future__ import annotations

from ..api import ToolError
from ..registry import a, i, s, tool
from .common import CONFIG_KEYS, CONFIG_PROPS, clip, config_from, hide_headers, mcp_brief, without_none
from .overview import DEFAULTS

A = "/api/v1/admin/agents"
CONNS = "/api/v1/admin/agent-connections"
COMMENT = s("Why you are making this change: shown in the versions of the agent. Worth always giving.")


def brief(agent: dict) -> dict:
    tools = agent.get("config", {}).get("tools", DEFAULTS["tools"])
    return {
        "id": agent["id"],
        "name": agent["name"],
        "model_id": agent["model_id"],
        "prompt": clip(agent["prompt"]) or None,
        "tools": tools,
    }


@tool(
    "find_agents",
    group="agents",
    role="admin",
    description="Lists the agents of the service (id, name, model, the start of the prompt, tools), optionally only those whose name contains a text. "
    "Use get_agent for everything about one.",
    props={"name": s("Only agents whose name contains this (not case sensitive).")},
    routes=(("GET", A),),
)
async def find_agents(c, name: str | None = None):
    agents = await c.get(A)
    found = [x for x in agents if not name or name.lower() in x["name"].lower()]
    return {"count": len(found), "agents": [brief(x) for x in found]}


@tool(
    "get_agent",
    group="agents",
    role="user",
    description="Everything about an agent in one call: prompt, model, stored config (and the defaults of what is not set), MCP servers, "
    "the number of its latest version, and which agents it may call or is called by. Look at an agent with this before you change it.",
    scoped=True,
    routes=(
        ("GET", A + "/{agent_id}"),
        ("GET", A + "/{agent_id}/versions"),
        ("GET", A + "/{agent_id}/mcp-servers"),
        ("GET", "/api/v1/admin/models"),
    ),
    admin_routes=(("GET", A), ("GET", CONNS)),
)
async def get_agent(c):
    base = f"{A}/{c.agent}"
    agent = await c.get(base)
    versions = await c.get(base + "/versions")
    servers = await c.get(base + "/mcp-servers")
    models = await c.get("/api/v1/admin/models")
    model = next((m for m in models if m["id"] == agent["model_id"]), None)
    result = {
        "id": agent["id"],
        "name": agent["name"],
        "prompt": agent["prompt"],
        "model": {"id": agent["model_id"], "name": model["name"] if model else None},
        "config": agent["config"],
        "defaults_of_unset_config": DEFAULTS,
        "latest_version": versions[0]["number"] if versions else None,
        "mcp_servers": [mcp_brief(s_) for s_ in servers],
    }
    if c.who.is_admin:
        names = {x["id"]: x["name"] for x in await c.get(A)}
        connections = await c.get(CONNS)
        result["may_call"] = [
            {"agent_id": x["agent2_id"], "name": names.get(x["agent2_id"]), "description": x["description"]}
            for x in connections
            if x["agent1_id"] == c.agent
        ]
        result["called_by"] = [
            {"agent_id": x["agent1_id"], "name": names.get(x["agent1_id"])}
            for x in connections
            if x["agent2_id"] == c.agent
        ]
    return result


CREATE_PROPS = {
    "name": s("A name for the agent, shown everywhere (1-120 characters).", minLength=1, maxLength=120),
    "prompt": s(
        "The system prompt: who the agent is and how it answers. May be empty (then it sends no system message)."
    ),
    "model_id": i("The model it runs on: an id from list_models."),
    **CONFIG_PROPS,
    "comment": COMMENT,
}


@tool(
    "create_agent",
    group="agents",
    role="admin",
    description="Makes an agent. It starts with a first version. Afterwards: give it tokens (create_token) so a client can use it, "
    "knowledge (add_knowledge), MCP servers (add_mcp_server), or connect it to other agents (connect_agents); test it with send_message.",
    props=CREATE_PROPS,
    required=("name", "prompt", "model_id"),
    routes=(("POST", A),),
)
async def create_agent(c, name, prompt, model_id, comment=None, **config):
    body = without_none(
        name=name, prompt=prompt, model_id=model_id, config=config_from(config), comment=comment
    )
    agent = await c.post(A, json_body=body)
    return {"created": brief(agent)}


@tool(
    "update_agent",
    group="agents",
    role="user",
    description="Changes an agent: only what you give changes. A change of prompt, model or config makes a new version, so it can be rolled back. "
    "To put a config setting back to its default, name it in reset_config. Give expected_version (from get_agent) if someone else may be "
    "editing it too: the change is refused if the agent has moved on.",
    props={
        "name": s("A new name.", minLength=1, maxLength=120),
        "prompt": s("The new system prompt, whole (it replaces the old one)."),
        "model_id": i("Another model: an id from list_models."),
        **CONFIG_PROPS,
        "reset_config": a(
            "Config settings to put back to their default.", {"type": "string", "enum": list(CONFIG_KEYS)}
        ),
        "comment": COMMENT,
        "expected_version": i(
            "The version number you read; the change is refused if the agent has a newer one.", minimum=1
        ),
    },
    scoped=True,
    routes=(("PATCH", A + "/{agent_id}"),),
)
async def update_agent(
    c, name=None, prompt=None, model_id=None, reset_config=None, comment=None, expected_version=None, **config
):
    body = without_none(
        name=name,
        prompt=prompt,
        model_id=model_id,
        config=config_from(config, reset_config),
        comment=comment,
        expected_version=expected_version,
    )
    if not body or set(body) <= {"comment"}:
        raise ToolError(
            "Nothing to change: give at least one of name, prompt, model_id, a config setting or reset_config."
        )
    agent = await c.patch(f"{A}/{c.agent}", json_body=body)
    return {"updated": brief(agent), "config": agent["config"]}


@tool(
    "delete_agent",
    group="agents",
    role="admin",
    description="Deletes an agent for good, with its users, chats, memories, knowledge and connections. Refused while it still has tokens "
    "(delete them first with delete_token). Agents that could call it get a new version without that connection.",
    props={"agent_id": i("The agent to delete.", minimum=1)},
    required=("agent_id",),
    routes=(("DELETE", A + "/{agent_id}"),),
)
async def delete_agent(c, agent_id):
    agent = await c.delete(f"{A}/{agent_id}")
    return {"deleted": {"id": agent["id"], "name": agent["name"]}}


@tool(
    "list_versions",
    group="agents",
    role="user",
    description="The history of an agent, newest first: number, when, why (the comment), and who. Read one with show_version, undo with rollback_agent.",
    scoped=True,
    routes=(("GET", A + "/{agent_id}/versions"),),
)
async def list_versions(c):
    versions = await c.get(f"{A}/{c.agent}/versions")
    return [
        {
            "number": v["number"],
            "comment": v["comment"],
            "at": v["timestamp"],
            "by_token": v["created_by_token_id"],
        }
        for v in versions
    ]


@tool(
    "show_version",
    group="agents",
    role="user",
    description="One version of an agent as it was (prompt, model, config, MCP servers, connections), or with compare_with what changed between "
    "two versions.",
    props={
        "number": i("The version to show.", minimum=1),
        "compare_with": i(
            "Another version number (from list_versions): show what differs between `number` and it, instead.",
            minimum=1,
        ),
    },
    required=("number",),
    scoped=True,
    routes=(("GET", A + "/{agent_id}/versions/{number}"), ("GET", A + "/{agent_id}/versions/{number}/diff")),
)
async def show_version(c, number, compare_with=None):
    base = f"{A}/{c.agent}/versions/{number}"
    if compare_with is not None:
        diff = await c.get(base + "/diff", params={"to": compare_with})
        return {
            "from_version": diff["from_version"],
            "to_version": diff["to_version"],
            "changes": diff["changes"],
        }
    version = await c.get(base)
    snapshot = dict(version["snapshot"])
    snapshot["mcp_servers"] = [
        {"id": x.get("id"), "config": hide_headers(x.get("config", {}))}
        for x in snapshot.get("mcp_servers", [])
    ]
    return {
        "number": version["number"],
        "comment": version["comment"],
        "at": version["timestamp"],
        "snapshot": snapshot,
    }


@tool(
    "rollback_agent",
    group="agents",
    role="user",
    description="Makes an agent what an older version was (prompt, model, config, MCP servers and connections). Nothing is lost: the rollback is "
    "itself a new version.",
    props={"to": i("The version to go back to (from list_versions).", minimum=1), "comment": COMMENT},
    required=("to",),
    scoped=True,
    routes=(("POST", A + "/{agent_id}/rollback"),),
)
async def rollback_agent(c, to, comment=None):
    version = await c.post(f"{A}/{c.agent}/rollback", json_body=without_none(to=to, comment=comment))
    return {"now_version": version["number"] if version else None, "restored": to}
