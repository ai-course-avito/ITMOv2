from ..access import HANDS_OUT, Identity
from ..registry import tool

DEFAULTS = {
    "tools": ["rag", "memory"],
    "message_limit": 10,
    "memo_limit": 20,
    "rag_limit": 8,
    "auto_memory": True,
}

CONCEPTS = """\
Omnixon runs LLM agents and keeps what they need. A client (a bot, a site) sends a text request for a person (a "user" of the agent); Omnixon builds the context, calls the model and stores the exchange.

THINGS
- Agent: a prompt + a model + settings (config) + the MCP servers it may use. Everything an agent does is decided by these. Every change to them is a numbered VERSION of the agent (list_versions, show_version, rollback_agent): nothing is lost, so changing an agent is safe.
- Model: a record naming an OpenRouter model (and options like temperature) that agents run on. Shared: changing one changes every agent that uses it.
- Config of an agent (only what is set is stored; null resets a key to the default): tools (built-in: "rag" searches the knowledge base, "memory" lets the model remember facts about a person; default both), message_limit (latest messages the model gets, default 10), memo_limit (memories shown at once, default 20), rag_limit (knowledge entries per search, default 8), auto_memory (after each saved exchange a second model call extracts lasting facts; default on). Defaults can be changed by whoever runs the service.
- Knowledge base (per agent): entries of text found by meaning when the agent searches. Memory (per person and agent): short facts about a person.
- User: a person who talks to an agent, known by an id the client chooses (the same id on two agents is two users). Chat: a thread of messages of one user with one agent; messages without a chat go to the user's default chat. Messages older than a week are forgotten; memories are not.
- MCP server: an external server of tools an agent may call. Token: the secret a client (or this server) uses; it belongs to ONE agent and has a role.
- Connection (agent A -> agent B): lets A call B. A then gets the tools list_agents and ask_agent(agent_id, request); B sees only the request text, as a user "agent_<A>:<person>". The description of a connection is what A reads about B, so write it for A.

HOW TO WORK
- Look before you change: get_agent shows everything about an agent in one call. To change one, update_agent with a comment saying why (it is shown in the versions).
- To test an agent, send it a message (send_message) and read the answer; with trace=true you also see the tools it called.
"""

ROLE_TEXT = {
    "regular": "You can only talk to the users and chats of your own agent: find users, read and manage chats, interrupt an answer.",
    "user": "Besides that you manage your own agent: its prompt, model, config, versions, knowledge base, memories, MCP servers and tokens, and you can read usage.",
    "admin": "You manage every agent: make and delete agents and models, connect agents to each other, read everything. Most tools take agent_id to work on an agent other than your own. You can send messages to other agents.",
    "owner": "Like admin, and you can also hand out tokens of any role (admins and owners too).",
}


def about(who: Identity) -> str:
    return (
        CONCEPTS
        + f'\nYOU: token {who.token_id} "{who.name}", role {who.role}, agent {who.agent_id}. {ROLE_TEXT[who.role]}'
        + f" Tokens you may hand out: {HANDS_OUT[who.role]}."
    )


@tool(
    "about_omnixon",
    group="self",
    role="regular",
    description="Explains what Omnixon is (agents, models, versions, knowledge base, memory, users, chats, tokens, connections between agents) "
    "and what your token may do. Call it first when you do not know the service; it costs nothing.",
)
async def about_omnixon(c):
    return about(c.who)


@tool(
    "whoami",
    group="self",
    role="regular",
    description="Which token you are connected with (its role) and which agent it belongs to, with that agent's name.",
    routes=(("GET", "/api/v1/tokens/self"), ("GET", "/api/v1/agents/self")),
)
async def whoami(c):
    token = await c.get("/api/v1/tokens/self")
    agent = await c.get("/api/v1/agents/self", acting=True)
    return {
        "token": {k: token[k] for k in ("id", "name", "role", "agent_id", "is_initial")},
        "agent": {"id": agent["id"], "name": agent["name"], "model_id": agent["model_id"]},
        "may_hand_out_tokens": HANDS_OUT[token["role"]],
    }
