from __future__ import annotations

from ..api import q
from ..registry import i, s, tool

USERS = "/api/v1/users"
USER = s(
    "The person's id, as the client gave it (find_users finds ids by their start).", minLength=1, maxLength=64
)
CHAT = i(
    "A chat of this person with this agent (from list_chats). Omitted: their default chat, where messages go that name no chat.",
    minimum=1,
)


def chat_row(x: dict) -> dict:
    return {
        "id": x["id"],
        "title": x["title"],
        "default": x["is_default"],
        "messages": x["messages"],
        "last_message_at": x["updated_at"],
    }


def message_row(m: dict) -> dict:
    content = m["content"]
    row = {"who": content.get("type"), "text": content.get("content"), "at": m["timestamp"]}
    if content.get("interrupted"):
        row["interrupted"] = True
    if content.get("attachments"):
        row["attachments"] = content["attachments"]
    return row


@tool(
    "find_users",
    group="users",
    role="regular",
    description="Finds the people who talked to an agent by the start of their id (at least 3 characters). People are known by the id the client gave "
    "(a Telegram id, a session id, ...).",
    props={
        "prefix": s("The start of the id (3 characters at least).", minLength=3),
        "limit": i("How many (1-50, default 10).", minimum=1, maximum=50),
    },
    required=("prefix",),
    scoped=True,
    routes=(("GET", USERS),),
)
async def find_users(c, prefix, limit=10):
    found = await c.get(USERS, params={"query": prefix, "limit": limit}, acting=True)
    return [x["external_id"] for x in found]


@tool(
    "recent_users",
    group="users",
    role="regular",
    description="The people of an agent who wrote lately (their messages are still kept), latest first, with how many messages they have.",
    props={"limit": i("How many (default 20).", minimum=1, maximum=100)},
    scoped=True,
    routes=(("GET", USERS + "/recent"),),
)
async def recent_users(c, limit=20):
    found = await c.get(USERS + "/recent", params={"limit": limit}, acting=True)
    return [
        {"user_id": x["external_id"], "messages": x["messages"], "last_active": x["last_active"]}
        for x in found
    ]


@tool(
    "create_user",
    group="users",
    role="regular",
    description="Registers a person with an agent. Rarely needed: a person is made by their first message.",
    props={"user_id": USER},
    required=("user_id",),
    scoped=True,
    routes=(("POST", USERS),),
)
async def create_user(c, user_id):
    made = await c.post(USERS, json_body={"external_id": user_id}, acting=True)
    return {"created": made["external_id"]}


@tool(
    "rename_user",
    group="users",
    role="regular",
    description="Changes the id of a person (their chats and memories stay with them).",
    props={"user_id": USER, "new_user_id": s("The new id.", minLength=1, maxLength=64)},
    required=("user_id", "new_user_id"),
    scoped=True,
    routes=(("PATCH", USERS + "/{user_id}"),),
)
async def rename_user(c, user_id, new_user_id):
    made = await c.patch(f"{USERS}/{q(user_id)}", json_body={"external_id": new_user_id}, acting=True)
    return {"renamed_to": made["external_id"]}


@tool(
    "delete_user",
    group="users",
    role="regular",
    description="Deletes a person from an agent with all their chats and messages (their memories are deleted too).",
    props={"user_id": USER},
    required=("user_id",),
    scoped=True,
    routes=(("DELETE", USERS + "/{user_id}"),),
)
async def delete_user(c, user_id):
    await c.delete(f"{USERS}/{q(user_id)}", acting=True)
    return {"deleted": user_id}


@tool(
    "list_chats",
    group="users",
    role="regular",
    description="The chats of a person with an agent, latest first: id, title, how many messages are kept.",
    props={"user_id": USER},
    required=("user_id",),
    scoped=True,
    routes=(("GET", USERS + "/{user_id}/chats"),),
)
async def list_chats(c, user_id):
    return [chat_row(x) for x in await c.get(f"{USERS}/{q(user_id)}/chats", acting=True)]


@tool(
    "read_chat",
    group="users",
    role="regular",
    description="The messages of a chat, oldest first: who said it (user or assistant), the text, when. Only messages from the last days are kept.",
    props={"user_id": USER, "chat_id": CHAT},
    required=("user_id",),
    scoped=True,
    routes=(("GET", USERS + "/{user_id}/chats/{chat_id}/history"), ("GET", USERS + "/{user_id}/history")),
)
async def read_chat(c, user_id, chat_id=None):
    path = f"{USERS}/{q(user_id)}" + (f"/chats/{chat_id}/history" if chat_id else "/history")
    return [message_row(m) for m in await c.get(path, acting=True)]


@tool(
    "start_chat",
    group="users",
    role="regular",
    description="Opens a new, empty chat for a person with an agent (messages sent with its chat_id go into it). Without a title it is named after its first message.",
    props={"user_id": USER, "title": s("A title.", minLength=1, maxLength=120)},
    required=("user_id",),
    scoped=True,
    routes=(("POST", USERS + "/{user_id}/chats"),),
)
async def start_chat(c, user_id, title=None):
    made = await c.post(f"{USERS}/{q(user_id)}/chats", json_body={"title": title}, acting=True)
    return {"created": chat_row(made)}


@tool(
    "rename_chat",
    group="users",
    role="regular",
    description="Gives a chat a new title.",
    props={
        "user_id": USER,
        "chat_id": i("The chat.", minimum=1),
        "title": s("The title.", minLength=1, maxLength=120),
    },
    required=("user_id", "chat_id", "title"),
    scoped=True,
    routes=(("PATCH", USERS + "/{user_id}/chats/{chat_id}"),),
)
async def rename_chat(c, user_id, chat_id, title):
    return {
        "renamed": chat_row(
            await c.patch(f"{USERS}/{q(user_id)}/chats/{chat_id}", json_body={"title": title}, acting=True)
        )
    }


@tool(
    "clear_chat",
    group="users",
    role="regular",
    description="Deletes the messages of a chat and keeps the chat (the agent then starts that conversation afresh). Memories are not touched.",
    props={"user_id": USER, "chat_id": CHAT},
    required=("user_id",),
    scoped=True,
    routes=(
        ("DELETE", USERS + "/{user_id}/chats/{chat_id}/history"),
        ("DELETE", USERS + "/{user_id}/history"),
    ),
)
async def clear_chat(c, user_id, chat_id=None):
    path = f"{USERS}/{q(user_id)}" + (f"/chats/{chat_id}/history" if chat_id else "/history")
    await c.delete(path, acting=True)
    return {"cleared": chat_id or "default chat"}


@tool(
    "delete_chat",
    group="users",
    role="regular",
    description="Deletes a chat with its messages.",
    props={"user_id": USER, "chat_id": i("The chat to delete.", minimum=1)},
    required=("user_id", "chat_id"),
    scoped=True,
    routes=(("DELETE", USERS + "/{user_id}/chats/{chat_id}"),),
)
async def delete_chat(c, user_id, chat_id):
    await c.delete(f"{USERS}/{q(user_id)}/chats/{chat_id}", acting=True)
    return {"deleted": chat_id}
