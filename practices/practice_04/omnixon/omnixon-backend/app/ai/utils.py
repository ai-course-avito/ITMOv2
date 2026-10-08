from typing import Sequence, Optional, List
import httpx
from pydantic_ai import Embedder, SystemPromptPart
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
from pydantic_ai.mcp import MCPServer, MCPServerSSE, MCPServerStreamableHTTP

from database import PostgresDB
from .attachments import describe as describe_attachments
from core import MCP_TOOL_RETRIES, OPENROUTER_TOKEN, OPENROUTER_PROXY
from .mcp_calls import safe_tool_calls

_http_client: Optional[httpx.AsyncClient] = None
_direct_client: Optional[httpx.AsyncClient] = None

# Where a model is called when it says nothing else. A model's own `base_url` (see the `models` table) points it at another
# OpenAI-compatible server: a local vLLM or Ollama, a Russian provider ...
from database.models import DEFAULT_BASE_URL  # noqa: E402


def _count_tokens_the_provider_reports() -> None:
    """pydantic-ai takes the token counts of a response from its price tables, and leaves them at 0 for a
    model it has no prices for (most OpenRouter models). The response itself says how many tokens it
    used, so use that when the tables did not tell. A test (a real request writes tokens > 0) guards this."""
    from pydantic_ai.models import openai as openai_models

    original = openai_models._map_usage
    if getattr(original, "_counts_reported_tokens", False):
        return

    def map_usage(response, *args, **kwargs):
        usage = original(response, *args, **kwargs)
        reported = getattr(response, "usage", None)
        if reported is not None and not (usage.input_tokens or usage.output_tokens):
            usage.input_tokens = getattr(reported, "prompt_tokens", 0) or 0
            usage.output_tokens = getattr(reported, "completion_tokens", 0) or 0
        return usage

    map_usage._counts_reported_tokens = True
    openai_models._map_usage = map_usage


_count_tokens_the_provider_reports()


def _accept_any_service_tier() -> None:
    """OpenRouter reports `service_tier: "provisioned"` for some providers, which the OpenAI types that pydantic-ai builds on
    refuse (they list auto, default, flex, scale, priority and fast), failing the whole answer with a validation error. The tier
    is of no use to us, so take any text."""
    from pydantic_ai.models import openrouter

    for cls in (
        openrouter._OpenRouterChatCompletion,
        openrouter._OpenRouterChatCompletionChunk,
    ):
        cls.model_fields["service_tier"].annotation = Optional[str]
        cls.model_rebuild(force=True)


_accept_any_service_tier()

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


def _get_http_client() -> Optional[httpx.AsyncClient]:
    global _http_client
    if not OPENROUTER_PROXY:
        return None
    if _http_client is None:
        # Same timeouts pydantic-ai uses for its own provider clients; httpx's
        # 5s default would cut off slow LLM responses.
        _http_client = httpx.AsyncClient(
            proxy=OPENROUTER_PROXY, timeout=httpx.Timeout(600, connect=5)
        )
    return _http_client


def _get_direct_client() -> Optional[httpx.AsyncClient]:
    """A client that does not use the proxy (for a model with `use_proxy: false`). Without a proxy configured there is nothing to
    avoid, and the default client of the provider is used."""
    global _direct_client
    if not OPENROUTER_PROXY:
        return None
    if _direct_client is None:
        _direct_client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5))
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


def http_client_for(use_proxy: bool) -> Optional[httpx.AsyncClient]:
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


# Options of an MCP server config (besides url and transport) that are passed to
# pydantic-ai's server classes; callbacks and clients cannot come from JSON.
MCP_OPTIONS = frozenset(
    {
        "headers",
        "id",
        "tool_prefix",
        "log_level",
        "timeout",
        "read_timeout",
        "max_retries",
        "cache_tools",
        "cache_resources",
        "allow_sampling",
    }
)


def build_mcp_server(config: dict) -> MCPServer:
    transport = config.get("transport", "streamable_http")
    url = config["url"]
    kwargs = {
        key: value for key, value in config.items() if key not in ("url", "transport")
    }
    kwargs.setdefault("max_retries", MCP_TOOL_RETRIES)
    # a failed tool call becomes the tool's result instead of failing the answer
    kwargs["process_tool_call"] = safe_tool_calls(config, build_mcp_server)

    if transport == "sse":
        return MCPServerSSE(url, **kwargs)

    return MCPServerStreamableHTTP(url, **kwargs)


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


async def get_conversation_history(
    db: PostgresDB, system_prompt: str, use_memo: bool = True
) -> Sequence[ModelMessage]:
    raw_messages = (await db.get_all_messages() or []) if use_memo else []
    # The window of the latest N messages can begin with an answer whose question
    # fell out of it; a conversation must begin with the user.
    while raw_messages and raw_messages[0].content.get("type") != "user":
        raw_messages = raw_messages[1:]

    # no system message at all when there is nothing to say (an empty one is refused by some providers)
    messages: List[ModelMessage] = (
        [ModelRequest(parts=[SystemPromptPart(content=system_prompt)])]
        if system_prompt.strip()
        else []
    )

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
