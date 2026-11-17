from typing import Annotated, Optional
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, StringConstraints, field_validator

from .common import Name

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
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("base_url must be an http(s) address, e.g. https://openrouter.ai/api/v1")
    return value


BaseUrl = Annotated[Optional[str], AfterValidator(_validate_base_url)]
# An empty string clears it (the key of the deployment is used again); None keeps what there is
ApiToken = Annotated[Optional[str], StringConstraints(strip_whitespace=True, max_length=512)]


class ModelCreate(BaseModel):
    name: Name  # required
    request_json: dict
    base_url: BaseUrl = None  # default: OpenRouter (https://openrouter.ai/api/v1)
    use_proxy: bool = True  # false: call the model directly, not through the proxy of the deployment
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
