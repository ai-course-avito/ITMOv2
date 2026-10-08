from typing import Sequence, Optional, List

import httpx2
from pydantic_ai import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.messages import (
    ModelRequest,
    UserPromptPart,
    ModelResponse,
    TextPart,
    ModelMessage,
)
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openrouter import (
    OpenRouterModel,
    OpenRouterModelSettings,
    OpenRouterProvider,
)

from database import PostgresDB
from .attachments import describe as describe_attachments
from core import OPENROUTER_TOKEN, OPENROUTER_PROXY
from .transport import RetryingTransport

_http_client: Optional[httpx2.AsyncClient] = None
_direct_client: Optional[httpx2.AsyncClient] = None

# Where a model is called when it says nothing else. A model's own `base_url` (see the `models` table) points it at another
# OpenAI-compatible server: a local vLLM or Ollama, a Russian provider ...
from database.models import DEFAULT_BASE_URL  # noqa: E402


# A model is an OpenRouter request body ({"model": ..., ...}). Its keys reach the
# provider in three ways:
# - OpenRouter's own options map to OpenRouterModelSettings' `openrouter_<key>`;
_OPENROUTER_SETTINGS_KEYS = {
    "models",
    "provider",
    "preset",
    "transforms",
    "reasoning",
    "usage",
}
# - the common sampling options map to pydantic-ai's model settings (key -> setting);
_SAMPLING_SETTINGS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_tokens": "max_tokens",
    "seed": "seed",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
    "logit_bias": "logit_bias",
    "parallel_tool_calls": "parallel_tool_calls",
    "stop": "stop_sequences",
}
# - everything else (top_k, min_p, repetition_penalty, ...) is sent as it is.


def _client(proxy: Optional[str]) -> httpx2.AsyncClient:
    """A client for a model provider: the same timeouts pydantic-ai uses for its own (a 5 s default would cut off slow answers), and
    the retries of `transport.RetryingTransport` for a request that fails in a way that passes."""
    inner = httpx2.AsyncHTTPTransport(proxy=proxy) if proxy else httpx2.AsyncHTTPTransport()
    return httpx2.AsyncClient(transport=RetryingTransport(inner), timeout=httpx2.Timeout(600, connect=5))


def _get_http_client() -> httpx2.AsyncClient:
    """The client that reaches a model: through OPENROUTER_PROXY if there is one."""
    global _http_client
    if _http_client is None:
        _http_client = _client(OPENROUTER_PROXY or None)
    return _http_client


def _get_direct_client() -> httpx2.AsyncClient:
    """A client that does not use the proxy (for a model with `use_proxy: false`)."""
    global _direct_client
    if _direct_client is None:
        _direct_client = _client(None)
    return _direct_client


def uses_openrouter(base_url: Optional[str]) -> bool:
    return not base_url or base_url.rstrip("/") == DEFAULT_BASE_URL


def model_settings(request_json: dict, openrouter: bool = True) -> dict:
    """Settings for pydantic-ai from the body of a model (see above). OpenRouter's own options are only OpenRouter's: for another
    server they are sent as they are, with the rest."""
    settings: dict = {}
    extra_body: dict = {}

    for key, value in request_json.items():
        if key == "model":
            continue
        if key in _OPENROUTER_SETTINGS_KEYS and openrouter:
            settings[f"openrouter_{key}"] = value
        elif key in _SAMPLING_SETTINGS:
            settings[_SAMPLING_SETTINGS[key]] = value
        else:
            extra_body[key] = value

    if extra_body:
        settings["extra_body"] = extra_body
    return settings


def http_client_for(use_proxy: bool) -> httpx2.AsyncClient:
    """The client that reaches a model: through OPENROUTER_PROXY (if there is one), or, for a model with `use_proxy` off, around it."""
    return _get_http_client() if use_proxy else _get_direct_client()


def generate_model(
    request_json: dict,
    base_url: Optional[str] = None,
    use_proxy: bool = True,
    api_token: Optional[str] = None,
):
    """The pydantic-ai model of a model record: OpenRouter by default, with the key of the deployment and through its proxy. A `base_url`
    of another server makes it the plain OpenAI protocol there; `use_proxy` False goes around the proxy; `api_token` is the key for it
    (None: the key of the deployment)."""
    openrouter = uses_openrouter(base_url)
    settings = model_settings(request_json, openrouter)
    http_client = http_client_for(use_proxy)
    api_key = api_token or OPENROUTER_TOKEN

    if not openrouter:
        # a server that is not OpenRouter: the plain OpenAI protocol (a local server takes any key)
        return OpenAIChatModel(
            request_json["model"],
            provider=OpenAIProvider(
                base_url=base_url.rstrip("/"),
                api_key=api_key or "none",
                http_client=http_client,
            ),
            settings=OpenAIChatModelSettings(**settings) if settings else None,
        )

    # ask OpenRouter for the cost of the call (usage accounting), unless the model says otherwise
    settings.setdefault("openrouter_usage", {"include": True})
    return OpenRouterModel(
        request_json["model"],
        provider=OpenRouterProvider(api_key=api_key, http_client=http_client),
        settings=OpenRouterModelSettings(**settings),
    )


_embedder: Optional[Embedder] = None


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        embedding_model = OpenAIEmbeddingModel(
            "openai/text-embedding-3-small",
            provider=OpenRouterProvider(
                api_key=OPENROUTER_TOKEN, http_client=_get_http_client()
            ),
        )
        _embedder = Embedder(embedding_model)
    return _embedder


async def get_embedding_vector(text: str) -> List[float]:
    result = await _get_embedder().embed_query(text)
    return result.embeddings[0]


async def store_exchange(
    db: PostgresDB, user_text: str, answer: str, **user_extra
) -> None:
    """Save a question and its answer together (see MessageMethods.create_messages)."""
    await db.create_messages(
        [
            {"type": "user", "content": user_text, **user_extra},
            {"type": "assistant", "content": answer},
        ]
    )


async def get_conversation_history(db: PostgresDB, use_memo: bool = True) -> Sequence[ModelMessage]:
    """The stored messages of the chat as what the model is given before the new one. (The agent's prompt is not among them: it is the
    agent's `instructions`.)"""
    raw_messages = (await db.get_all_messages() or []) if use_memo else []
    # The window of the latest N messages can begin with an answer whose question
    # fell out of it; a conversation must begin with the user.
    while raw_messages and raw_messages[0].content.get("type") != "user":
        raw_messages = raw_messages[1:]

    messages: List[ModelMessage] = []
    for msg in raw_messages:
        m_type = msg.content["type"]
        m_content = msg.content["content"]

        if m_type == "user":
            notes = msg.content.get("attachments")
            if notes:  # the file itself is not kept, only the fact that it was there
                m_content = f"{m_content}\n{describe_attachments(notes)}".strip()
            messages.append(ModelRequest(parts=[UserPromptPart(content=m_content)]))
        elif m_type == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=m_content)]))

    return messages
