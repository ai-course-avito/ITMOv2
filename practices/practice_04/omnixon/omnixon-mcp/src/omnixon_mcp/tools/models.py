from __future__ import annotations

from ..registry import i, o, s, tool
from .common import without_none

MODELS = "/api/v1/admin/models"
MODEL = s("The OpenRouter model id, e.g. google/gemini-2.5-flash or openai/gpt-4o-mini.", minLength=1)
OPTIONS = o(
    "Options sent with every request to the model: temperature, top_p, max_tokens, seed, stop, reasoning, provider (OpenRouter routing) ... "
    "Give them whole (they replace the old ones). A tiny max_tokens on a reasoning model gives empty answers."
)
CONNECTION = {
    "base_url": s(
        "The address of an OpenAI-compatible API to use instead of OpenRouter. Omitted: OpenRouter. In edit_model, '' goes back to OpenRouter."
    ),
    "use_proxy": {
        "type": "boolean",
        "description": "Whether the service's outgoing proxy is used for this model (default true).",
    },
    "api_key": s("The key for that API. It is never shown back. In edit_model, '' removes it."),
}


def brief(m: dict) -> dict:
    request = m["request_json"]
    options = {k: v for k, v in request.items() if k != "model"}
    return {
        "id": m["id"],
        "name": m["name"],
        "model": request.get("model"),
        **({"options": options} if options else {}),
        "base_url": m["base_url"],
        "has_own_key": m.get("has_api_token", False),
    }


@tool(
    "list_models",
    group="models",
    role="user",
    description="The models agents can run on: id, name, the OpenRouter model id and its options. An agent's model is chosen with model_id in "
    "create_agent / update_agent.",
    routes=(("GET", MODELS),),
)
async def list_models(c):
    return [brief(m) for m in await c.get(MODELS)]


@tool(
    "create_model",
    group="models",
    role="admin",
    description="Adds a model agents can then be given (model_id of create_agent / update_agent).",
    props={
        "name": s("A name for it.", minLength=1, maxLength=120),
        "model": MODEL,
        "options": OPTIONS,
        **CONNECTION,
    },
    required=("name", "model"),
    routes=(("POST", MODELS),),
)
async def create_model(c, name, model, options=None, base_url=None, use_proxy=None, api_key=None):
    body = without_none(
        name=name,
        request_json={"model": model, **(options or {})},
        base_url=base_url,
        use_proxy=use_proxy,
        api_token=api_key,
    )
    return {"created": brief(await c.post(MODELS, json_body=body))}


@tool(
    "edit_model",
    group="models",
    role="admin",
    description="Changes a model: only what you give changes. Every agent that runs on it is changed too and gets a new version, so check "
    "who uses it before you change one that matters.",
    props={
        "model_id": i("The model (list_models).", minimum=0),
        "name": s("A new name.", minLength=1, maxLength=120),
        "model": MODEL,
        "options": OPTIONS,
        **CONNECTION,
    },
    required=("model_id",),
    routes=(("GET", MODELS + "/{model_id}"), ("PATCH", MODELS + "/{model_id}")),
)
async def edit_model(
    c, model_id, name=None, model=None, options=None, base_url=None, use_proxy=None, api_key=None
):
    request = None
    if model is not None or options is not None:
        current = await c.get(f"{MODELS}/{model_id}")
        request = {
            "model": model or current["request_json"]["model"],
            **(
                options
                if options is not None
                else {k: v for k, v in current["request_json"].items() if k != "model"}
            ),
        }
    body = without_none(
        name=name, request_json=request, base_url=base_url, use_proxy=use_proxy, api_token=api_key
    )
    return {"updated": brief(await c.patch(f"{MODELS}/{model_id}", json_body=body))}


@tool(
    "delete_model",
    group="models",
    role="admin",
    description="Deletes a model. Refused while an agent still runs on it, and model 0 (the default) cannot be deleted.",
    props={"model_id": i("The model to delete.", minimum=1)},
    required=("model_id",),
    routes=(("DELETE", MODELS + "/{model_id}"),),
)
async def delete_model(c, model_id):
    model = await c.delete(f"{MODELS}/{model_id}")
    return {"deleted": {"id": model["id"], "name": model["name"]}}
