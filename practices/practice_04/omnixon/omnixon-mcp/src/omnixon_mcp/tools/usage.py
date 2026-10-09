from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..registry import i, tool

U = "/api/v1/admin/usage"
FIELDS = ("requests", "errors", "input_tokens", "output_tokens", "cost")
PROPS = {
    "token_id": i("Only this token.", minimum=1),
    "agent_id": i("Only the tokens of this agent.", minimum=1),
}


def total(rows: Iterable[dict]) -> dict:
    out = {f: 0 for f in FIELDS}
    for r in rows:
        for f in FIELDS:
            out[f] += r[f] or 0
    out["cost"] = round(out["cost"], 6)
    return out


def grouped(rows: list[dict], key: str, label: str) -> list[dict]:
    groups: dict = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return sorted(({label: k, **total(v)} for k, v in groups.items()), key=lambda x: -x["cost"])


def report(rows: list[dict], by_day: bool) -> dict:
    result = {
        "total": total(rows),
        "by_model": grouped(rows, "model", "model"),
        "by_token": grouped(rows, "token_name", "token"),
    }
    if by_day:
        result["by_day"] = sorted(grouped(rows, "day", "day"), key=lambda x: x["day"])
    return result


@tool(
    "usage_report",
    group="usage",
    role="user",
    description="What was spent on the models over the last days: requests, errors, tokens and cost (in dollars, as OpenRouter reports it), in "
    "total and by model, by token and by day. Texts are never stored, only counts.",
    props={
        "days": i("How many days back, today included (1-366, default 30).", minimum=1, maximum=366),
        **PROPS,
    },
    routes=(("GET", U),),
    note=lambda who: (
        "Usage of every token."
        if who.is_admin
        else f"Usage of the tokens of your own agent (id {who.agent_id}) only."
    ),
)
async def usage_report(c, days=30, token_id=None, agent_id=None):
    rows = await c.get(U, params={"days": days, "token_id": token_id, "agent_id": agent_id})
    return {"days": days, **report(rows, by_day=True)}


@tool(
    "usage_report_monthly",
    group="usage",
    role="user",
    description="Older usage, which the service folds into one row per token, model and month once it is a month old: the same figures by month.",
    props=PROPS,
    routes=(("GET", U + "/monthly"),),
)
async def usage_report_monthly(c, token_id=None, agent_id=None):
    rows = await c.get(U + "/monthly", params={"token_id": token_id, "agent_id": agent_id})
    result = report(rows, by_day=False)
    result["by_month"] = sorted(grouped(rows, "month", "month"), key=lambda x: x["month"])
    return result
