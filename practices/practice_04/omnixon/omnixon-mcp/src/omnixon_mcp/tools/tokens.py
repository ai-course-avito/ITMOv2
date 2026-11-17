from __future__ import annotations

from ..access import HANDS_OUT
from ..registry import i, s, tool
from .common import without_none

T = "/api/v1/admin/tokens"
ROLE = s(
    "regular: talks to the agent only. user: also manages that agent. admin: manages every agent. owner: also hands out tokens of any role.",
    enum=["regular", "user", "admin", "owner"],
)
HANDS = lambda who: (
    f"Your role is {who.role}: the roles you may hand out and manage are {HANDS_OUT[who.role]}."
    + ("" if who.is_admin else " Tokens of other agents are not visible to you.")
)


def row(t: dict) -> dict:
    return {
        "id": t["id"],
        "name": t["name"],
        "role": t["role"],
        "agent_id": t["agent_id"],
        **({"initial": True} if t.get("is_initial") else {}),
    }


@tool(
    "list_tokens",
    group="tokens",
    role="user",
    description="The tokens of an agent (the secrets are never shown again after they are made): id, name, role. Admins and owners without agent_id see the tokens of every agent.",
    props={"agent_id": i("Only the tokens of this agent.", minimum=1)},
    routes=(("GET", T),),
    note=HANDS,
)
async def list_tokens(c, agent_id=None):
    return [
        row(t)
        for t in await c.get(T, params={"agent_id": agent_id or (None if c.who.is_admin else c.who.agent_id)})
    ]


@tool(
    "create_token",
    group="tokens",
    role="user",
    description="Makes a token for an agent: the secret a client uses to talk to it. THE SECRET IS IN THE ANSWER ONCE and can never be read again: "
    "give it to whoever needs it and do not write it anywhere else.",
    props={
        "name": s("What the token is for (shown in lists and in usage).", minLength=1, maxLength=120),
        "role": ROLE,
        "agent_id": i("The agent it belongs to (default: your own).", minimum=1),
    },
    required=("name", "role"),
    routes=(("POST", T),),
    note=HANDS,
)
async def create_token(c, name, role, agent_id=None):
    made = await c.post(T, json_body=without_none(name=name, role=role, agent_id=agent_id or c.who.agent_id))
    return {**row(made), "secret": made["token"], "note": "Shown once. Pass it to its user now."}


@tool(
    "edit_token",
    group="tokens",
    role="user",
    description="Renames a token or changes its role (up to what you may hand out). A token cannot change its own role; the initial token stays an owner.",
    props={
        "token_id": i("The token (list_tokens).", minimum=1),
        "name": s("A new name.", minLength=1, maxLength=120),
        "role": ROLE,
    },
    required=("token_id",),
    routes=(("PATCH", T + "/{token_id}"),),
    note=HANDS,
)
async def edit_token(c, token_id, name=None, role=None):
    return {"updated": row(await c.patch(f"{T}/{token_id}", json_body=without_none(name=name, role=role)))}


@tool(
    "delete_token",
    group="tokens",
    role="user",
    description="Deletes a token: it stops working at once. The initial token and the token you are using cannot be deleted.",
    props={"token_id": i("The token to delete.", minimum=1)},
    required=("token_id",),
    routes=(("DELETE", T + "/{token_id}"),),
)
async def delete_token(c, token_id):
    await c.delete(f"{T}/{token_id}")
    return {"deleted": token_id}
