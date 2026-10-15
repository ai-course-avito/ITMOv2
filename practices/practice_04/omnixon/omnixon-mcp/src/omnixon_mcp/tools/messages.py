from __future__ import annotations

from ..api import REQUEST_TIMEOUT, ToolError, q
from ..registry import b, i, s, tool
from .common import clip, without_none

USERS = "/api/v1/users"


def step(x: dict) -> dict:
    row = {"step": x["step"], "kind": x["kind"], "name": x["name"]}
    for key in ("args", "result", "error"):
        if x.get(key) is not None:
            row[key] = clip(str(x[key]), 300)
    if x.get("text"):
        row["text"] = clip(x["text"], 300)
    if x.get("duration_ms") is not None:
        row["ms"] = x["duration_ms"]
    return row


@tool(
    "send_message",
    group="messages",
    role="admin",
    description="Sends a message to another agent and returns its answer: the way to try an agent you made or changed. The message is written as the "
    "user `agentmcp_<your agent id>` (you cannot write as anyone else), so the agent keeps a conversation with you across calls; use start_chat "
    "and chat_id for a fresh one. You cannot message your own agent. With trace the answer also lists what the agent did (each model call and "
    "each tool it called, with arguments and results).",
    props={
        "agent_id": i("The agent to talk to (an id from find_agents), not your own.", minimum=1),
        "text": s("The message."),
        "chat_id": i(
            "A chat of your user with that agent (list_chats). Omitted: the default chat.", minimum=1
        ),
        "trace": b("Also return what the agent did to answer."),
    },
    required=("agent_id", "text"),
    routes=(("POST", "/api/v1/request"),),
    timeout=REQUEST_TIMEOUT,
)
async def send_message(c, agent_id, text, chat_id=None, trace=False):
    if agent_id == c.who.agent_id:
        raise ToolError(
            f"Refused: agent {agent_id} is the agent of this token, and an agent may not message itself."
        )
    c.agent = agent_id
    body = without_none(request=text, user_id=c.who.mcp_user, chat_id=chat_id, trace=trace or None)
    answer = await c.post(
        "/api/v1/request", json_body=body, acting=True, timeout=REQUEST_TIMEOUT, name="the agent"
    )
    result = {"answer": answer["response"], "chat_id": answer["chat_id"], "as_user": c.who.mcp_user}
    if trace:
        result["trace"] = [step(x) for x in answer.get("trace") or []]
    return result


@tool(
    "interrupt_answer",
    group="messages",
    role="regular",
    description="Stops an answer that is being streamed to a person right now: what was said so far is saved to their history (marked interrupted). "
    "Does nothing, and says so, if nothing is being said.",
    props={"user_id": s("The person's id.", minLength=1, maxLength=64)},
    required=("user_id",),
    scoped=True,
    routes=(("POST", USERS + "/{user_id}/interrupt"),),
)
async def interrupt_answer(c, user_id):
    stopped = await c.post(f"{USERS}/{q(user_id)}/interrupt", acting=True)
    return {"interrupted": stopped["interrupted"], "said_so_far": stopped["text"]}
