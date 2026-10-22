from __future__ import annotations

from ..api import ToolError
from ..registry import i, s, tool

CONNS = "/api/v1/admin/agent-connections"
AGENTS = "/api/v1/admin/agents"
DESCRIPTION = s(
    "What the called agent is for, written for the calling agent: it reads this in list_agents to decide when to ask it (1-1000 characters).",
    minLength=1,
    maxLength=1000,
)
FROM = i("The agent that will do the calling (an id from find_agents).", minimum=1)
TO = i("The agent that will be called.", minimum=1)


async def names(c) -> dict[int, str]:
    return {x["id"]: x["name"] for x in await c.get(AGENTS)}


async def find(c, caller: int, called: int) -> dict:
    for x in await c.get(CONNS):
        if x["agent1_id"] == caller and x["agent2_id"] == called:
            return x
    raise ToolError(
        f"Agent {caller} is not connected to agent {called}. list_connections shows the connections there are."
    )


@tool(
    "list_connections",
    group="agents",
    role="admin",
    description="Which agent may call which: every connection with the names of both agents and the description the caller reads. "
    "With agent_id only those that go out of that agent.",
    props={"agent_id": i("Only the connections where this agent is the caller.", minimum=1)},
    routes=(("GET", CONNS), ("GET", AGENTS)),
)
async def list_connections(c, agent_id=None):
    label = await names(c)
    found = await c.get(CONNS, params={"agent_id": agent_id})
    return [
        {
            "caller": {"id": x["agent1_id"], "name": label.get(x["agent1_id"])},
            "called": {"id": x["agent2_id"], "name": label.get(x["agent2_id"])},
            "description": x["description"],
        }
        for x in found
    ]


@tool(
    "connect_agents",
    group="agents",
    role="admin",
    description="Lets one agent call another: from then on the caller has the tools list_agents (the agents it may call, with this description) and "
    "ask_agent(agent_id, request). The called agent sees only the request text. A new version of the caller is recorded. A connection is one way: "
    "to let B call A as well, connect them again the other way round. An agent cannot be connected to itself, nor twice to the same agent.",
    props={"caller": FROM, "called": TO, "description": DESCRIPTION},
    required=("caller", "called", "description"),
    routes=(("POST", CONNS), ("GET", AGENTS)),
)
async def connect_agents(c, caller, called, description):
    made = await c.post(
        CONNS, json_body={"agent1_id": caller, "agent2_id": called, "description": description}
    )
    label = await names(c)
    return {
        "connected": f"{label.get(caller)} ({caller}) may now call {label.get(called)} ({called})",
        "description": made["description"],
    }


@tool(
    "change_connection",
    group="agents",
    role="admin",
    description="Changes what the caller reads about the called agent in list_agents. A new version of the caller is recorded.",
    props={"caller": FROM, "called": TO, "description": DESCRIPTION},
    required=("caller", "called", "description"),
    routes=(("GET", CONNS), ("PATCH", CONNS + "/{connection_id}")),
)
async def change_connection(c, caller, called, description):
    found = await find(c, caller, called)
    updated = await c.patch(f"{CONNS}/{found['id']}", json_body={"description": description})
    return {"description": updated["description"]}


@tool(
    "disconnect_agents",
    group="agents",
    role="admin",
    description="Stops one agent from calling another (only that direction). A new version of the caller is recorded.",
    props={"caller": FROM, "called": TO},
    required=("caller", "called"),
    routes=(("GET", CONNS), ("DELETE", CONNS + "/{connection_id}")),
)
async def disconnect_agents(c, caller, called):
    found = await find(c, caller, called)
    await c.delete(f"{CONNS}/{found['id']}")
    return {"disconnected": f"agent {caller} may no longer call agent {called}"}
