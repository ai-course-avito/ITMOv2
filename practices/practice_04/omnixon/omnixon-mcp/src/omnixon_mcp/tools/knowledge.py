from __future__ import annotations

from ..registry import i, o, s, tool
from .common import clip, without_none

RAG = "/api/v1/admin/rag"
TEXT = s("The text of the entry: what the agent will read when this entry is found.")
SEARCH_TEXT = s(
    "What the entry is found by, when that should differ from its text (e.g. the question it answers). Omitted: the text itself."
)
METADATA = o("Anything to keep with the entry (a source, a date); not searched.")


def entry(x: dict, whole: bool = True) -> dict:
    return {
        "id": x["id"],
        "text": x["content"] if whole else clip(x["content"], 300),
        **({"metadata": x["metadata"]} if x.get("metadata") else {}),
    }


@tool(
    "add_knowledge",
    group="knowledge",
    role="user",
    description="Adds an entry to the knowledge base of an agent. When the agent has the 'rag' tool it searches these by meaning and reads the best "
    "matches (rag_limit of them). One fact or one topic per entry works best: short entries are found more precisely. To load a document, cut it "
    "into parts and add each.",
    props={"text": TEXT, "search_text": SEARCH_TEXT, "metadata": METADATA},
    required=("text",),
    scoped=True,
    routes=(("POST", RAG),),
)
async def add_knowledge(c, text, search_text=None, metadata=None):
    made = await c.post(
        RAG,
        params={"agent_id": c.agent},
        json_body=without_none(content=text, embedding_content=search_text, metadata=metadata),
    )
    return {"added": entry(made, whole=False)}


@tool(
    "search_knowledge",
    group="knowledge",
    role="user",
    description="Searches the knowledge base of an agent by meaning, the way the agent itself does: the best matches first. Use it to check what an agent "
    "would find for a question.",
    props={
        "query": s("What to look for, in words."),
        "limit": i("How many entries (1-100, default 8).", minimum=1, maximum=100),
    },
    required=("query",),
    scoped=True,
    routes=(("GET", RAG),),
)
async def search_knowledge(c, query, limit=8):
    return [entry(x) for x in await c.get(RAG, params={"agent_id": c.agent, "query": query, "limit": limit})]


@tool(
    "list_knowledge",
    group="knowledge",
    role="user",
    description="Lists the entries of the knowledge base of an agent in the order they were added (long ones are cut to 300 characters; "
    "search_knowledge gives them whole).",
    props={
        "limit": i("How many (1-1000, default 50).", minimum=1, maximum=1000),
        "offset": i("How many to skip (default 0).", minimum=0),
    },
    scoped=True,
    routes=(("GET", RAG),),
)
async def list_knowledge(c, limit=50, offset=0):
    found = await c.get(RAG, params={"agent_id": c.agent, "limit": limit, "offset": offset})
    return {"count": len(found), "offset": offset, "entries": [entry(x, whole=False) for x in found]}


@tool(
    "edit_knowledge",
    group="knowledge",
    role="user",
    description="Replaces an entry of the knowledge base (its text, and what it is found by, are searched again).",
    props={
        "entry_id": i("The entry (from list_knowledge or search_knowledge).", minimum=1),
        "text": TEXT,
        "search_text": SEARCH_TEXT,
        "metadata": METADATA,
    },
    required=("entry_id", "text"),
    scoped=True,
    routes=(("PATCH", RAG + "/{rag_id}"),),
)
async def edit_knowledge(c, entry_id, text, search_text=None, metadata=None):
    made = await c.patch(
        f"{RAG}/{entry_id}",
        params={"agent_id": c.agent},
        json_body=without_none(content=text, embedding_content=search_text, metadata=metadata),
    )
    return {"updated": entry(made, whole=False)}


@tool(
    "delete_knowledge",
    group="knowledge",
    role="user",
    description="Deletes an entry of the knowledge base.",
    props={"entry_id": i("The entry to delete.", minimum=1)},
    required=("entry_id",),
    scoped=True,
    routes=(("DELETE", RAG + "/{rag_id}"),),
)
async def delete_knowledge(c, entry_id):
    await c.delete(f"{RAG}/{entry_id}", params={"agent_id": c.agent})
    return {"deleted": entry_id}
