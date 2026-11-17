from __future__ import annotations

from ..registry import i, s, tool

M = "/api/v1/admin/memories"
USER = s("The person's id (as the client gave it; see find_users).", minLength=1)


def fact(x: dict) -> dict:
    return {"id": x["id"], "text": x["content"], "at": x["timestamp"]}


@tool(
    "list_memories",
    group="memories",
    role="user",
    description="What an agent remembers about a person: short facts the model keeps (it adds them itself with its 'memory' tool, or "
    "automatically after a chat). Newest first; with query, the ones that match it by meaning.",
    props={
        "user_id": USER,
        "query": s("Only memories about this."),
        "limit": i("How many (default 50).", minimum=1, maximum=1000),
    },
    required=("user_id",),
    scoped=True,
    routes=(("GET", M),),
)
async def list_memories(c, user_id, query=None, limit=50):
    found = await c.get(M, params={"user_id": user_id, "agent_id": c.agent, "query": query, "limit": limit})
    return [fact(x) for x in found]


@tool(
    "add_memory",
    group="memories",
    role="user",
    description="Tells an agent something to remember about a person (a lasting fact, one sentence: 'Prefers short answers').",
    props={"user_id": USER, "text": s("The fact (up to 2000 characters).", minLength=1, maxLength=2000)},
    required=("user_id", "text"),
    scoped=True,
    routes=(("POST", M),),
)
async def add_memory(c, user_id, text):
    return {
        "added": fact(await c.post(M, json_body={"user_id": user_id, "content": text, "agent_id": c.agent}))
    }


@tool(
    "edit_memory",
    group="memories",
    role="user",
    description="Rewrites a remembered fact.",
    props={
        "memory_id": i("The memory (from list_memories).", minimum=1),
        "text": s("The new text.", minLength=1, maxLength=2000),
    },
    required=("memory_id", "text"),
    routes=(("PATCH", M + "/{memory_id}"),),
)
async def edit_memory(c, memory_id, text):
    return {"updated": fact(await c.patch(f"{M}/{memory_id}", json_body={"content": text}))}


@tool(
    "delete_memory",
    group="memories",
    role="user",
    description="Makes an agent forget a fact about a person.",
    props={"memory_id": i("The memory to delete.", minimum=1)},
    required=("memory_id",),
    routes=(("DELETE", M + "/{memory_id}"),),
)
async def delete_memory(c, memory_id):
    await c.delete(f"{M}/{memory_id}")
    return {"deleted": memory_id}
