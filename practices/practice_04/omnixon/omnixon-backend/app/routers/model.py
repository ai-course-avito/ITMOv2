from urllib.parse import urlparse

import asyncpg
from fastapi import APIRouter, Depends, Request, Body, HTTPException
from typing import Sequence
from typing import Annotated, Optional
from pydantic import AfterValidator, BaseModel, StringConstraints, field_validator
from database import PostgresDB, Model
from database.models import NAME_MAX
from access import require
from core import async_logfire_decorator

router = APIRouter()

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]


# How a model is reached is not part of its body: these are fields of the model (base_url, use_proxy, api_token)
CONNECTION_FIELDS = ("base_url", "use_proxy", "api_token", "api_key_env")


def _validate_request_json(value: dict) -> dict:
    if not isinstance(value.get("model"), str) or not value["model"]:
        raise ValueError('request_json must contain a non-empty "model" string')
    misplaced = [k for k in CONNECTION_FIELDS if k in value]
    if misplaced:
        raise ValueError(
            f"{', '.join(misplaced)} belong next to request_json, not inside it (they say how to reach the model, and are never sent to it)"
        )
    return value


def _validate_base_url(value: Optional[str]) -> Optional[str]:
    """None: not given. An empty string means the default. The trailing slash is dropped."""
    if value is None:
        return None
    value = value.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "base_url must be an http(s) address, e.g. https://openrouter.ai/api/v1"
        )
    return value


BaseUrl = Annotated[Optional[str], AfterValidator(_validate_base_url)]
# An empty string clears it (the key of the deployment is used again); None keeps what there is
ApiToken = Annotated[
    Optional[str], StringConstraints(strip_whitespace=True, max_length=512)
]


class ModelCreate(BaseModel):
    name: Name  # required
    request_json: dict
    base_url: BaseUrl = None  # default: OpenRouter (https://openrouter.ai/api/v1)
    use_proxy: bool = (
        True  # false: call the model directly, not through the proxy of the deployment
    )
    api_token: ApiToken = None  # default: the key of the deployment. Never returned.

    _check = field_validator("request_json")(_validate_request_json)


class ModelUpdate(BaseModel):
    name: Optional[Name] = None
    request_json: Optional[dict] = None
    base_url: BaseUrl = None  # "" or OpenRouter's address: back to the default
    use_proxy: Optional[bool] = None
    api_token: ApiToken = None  # "": back to the key of the deployment

    @field_validator("request_json")
    @classmethod
    def _check(cls, value):
        return None if value is None else _validate_request_json(value)


# Models


@router.get("/models", summary="List all models")
@async_logfire_decorator
async def get_models(request: Request) -> Sequence[Model]:
    db: PostgresDB = request.state.db
    return await db.get_all_models()


@router.post(
    "/models",
    summary="Create a new model",
    status_code=201,
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def create_model(request: Request, data: ModelCreate = Body(...)) -> Model:
    db: PostgresDB = request.state.db
    return await db.create_model(
        data.request_json, data.name, data.base_url, data.use_proxy, data.api_token
    )


@router.get("/models/{model_id}", summary="Get a model by ID")
@async_logfire_decorator
async def get_model(request: Request, model_id: int) -> Model:
    db: PostgresDB = request.state.db
    model = await db.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.patch(
    "/models/{model_id}",
    summary="Update a model",
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def update_model(
    request: Request, model_id: int, data: ModelUpdate = Body(...)
) -> Model:
    db: PostgresDB = request.state.db
    async with db.transaction():  # the model and the versions of the agents it changes
        model = await db.update_model(
            model_id,
            data.request_json,
            data.name,
            data.base_url,
            data.use_proxy,
            data.api_token,
        )
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        # a new name changes no behaviour; record_versions_of adds a version only if the snapshot differs
        await db.record_versions_of(
            await db.agent_ids_using_model(model_id),
            f"model {model_id} updated",
            db.context.token.id,
        )
    return model


@router.delete(
    "/models/{model_id}",
    summary="Delete a model",
    dependencies=[Depends(require("admin"))],
)
@async_logfire_decorator
async def delete_model(request: Request, model_id: int) -> Model:
    db: PostgresDB = request.state.db
    if model_id == 0:
        raise HTTPException(
            status_code=409, detail="The default model cannot be deleted"
        )
    try:
        model = await db.delete_model(model_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=409, detail="Model is used by an agent")
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model
