"""Reaching the models: the HTTP clients (through the proxy or around it, both with retries), the model objects, and the embedder.

`ModelGateway` owns what used to be module-level clients; whoever needs a model is given the gateway."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

import httpx2
from pydantic_ai import Embedder as PydanticEmbedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.models.openrouter import OpenRouterModel, OpenRouterModelSettings, OpenRouterProvider
from pydantic_ai.providers.openai import OpenAIProvider

from config import Settings
from domain.models import DEFAULT_BASE_URL
from .transport import RetryingTransport

EMBEDDING_MODEL = "openai/text-embedding-3-small"


class ModelSettingsMapper:
    """A model is an OpenRouter request body ({"model": ..., ...}). Its keys reach the provider in three ways:
    - OpenRouter's own options map to OpenRouterModelSettings' `openrouter_<key>`;
    - the common sampling options map to pydantic-ai's model settings;
    - everything else (top_k, min_p, repetition_penalty, ...) is sent as it is."""

    OPENROUTER_KEYS = {"models", "provider", "preset", "transforms", "reasoning", "usage"}
    SAMPLING = {
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

    def settings(self, request_json: Dict[str, Any], openrouter: bool = True) -> Dict[str, Any]:
        """OpenRouter's options are only OpenRouter's: for another server they are sent as they are, with the rest."""
        settings: Dict[str, Any] = {}
        extra_body: Dict[str, Any] = {}
        for key, value in request_json.items():
            if key == "model":
                continue
            if key in self.OPENROUTER_KEYS and openrouter:
                settings[f"openrouter_{key}"] = value
            elif key in self.SAMPLING:
                settings[self.SAMPLING[key]] = value
            else:
                extra_body[key] = value
        if extra_body:
            settings["extra_body"] = extra_body
        return settings


class Embedder(Protocol):
    async def embed(self, text: str) -> List[float]: ...


class ModelGateway:
    def __init__(self, settings: Settings, mapper: Optional[ModelSettingsMapper] = None):
        self.settings = settings
        self.mapper = mapper or ModelSettingsMapper()
        self._clients: Dict[bool, httpx2.AsyncClient] = {}

    def client(self, use_proxy: bool = True) -> httpx2.AsyncClient:
        """The client that reaches a model: through OPENROUTER_PROXY (if there is one), or, with `use_proxy` off, around it. Shared.
        A 5 s default timeout would cut off slow answers: these have the ones pydantic-ai uses, and retry a request that fails in a way
        that passes."""
        if use_proxy not in self._clients:
            proxy = (self.settings.openrouter_proxy or None) if use_proxy else None
            inner = httpx2.AsyncHTTPTransport(proxy=proxy) if proxy else httpx2.AsyncHTTPTransport()
            transport = RetryingTransport(inner, self.settings.upstream_retries, self.settings.upstream_retry_delay)
            self._clients[use_proxy] = httpx2.AsyncClient(transport=transport, timeout=httpx2.Timeout(600, connect=5))
        return self._clients[use_proxy]

    @staticmethod
    def uses_openrouter(base_url: Optional[str]) -> bool:
        return not base_url or base_url.rstrip("/") == DEFAULT_BASE_URL

    def chat_model(self, request_json: Dict[str, Any], base_url: Optional[str] = None, use_proxy: bool = True, api_token: Optional[str] = None):
        """The pydantic-ai model of a model record: OpenRouter by default, with the key of the deployment and through its proxy. A
        `base_url` of another server makes it the plain OpenAI protocol there; `use_proxy` False goes around the proxy; `api_token` is the
        key for it (None: the key of the deployment)."""
        openrouter = self.uses_openrouter(base_url)
        settings = self.mapper.settings(request_json, openrouter)
        http_client = self.client(use_proxy)
        api_key = api_token or self.settings.openrouter_token

        if not openrouter:  # a server that is not OpenRouter: the plain OpenAI protocol (a local server takes any key)
            return OpenAIChatModel(
                request_json["model"],
                provider=OpenAIProvider(base_url=base_url.rstrip("/"), api_key=api_key or "none", http_client=http_client),
                settings=OpenAIChatModelSettings(**settings) if settings else None,
            )
        # ask OpenRouter for the cost of the call (usage accounting), unless the model says otherwise
        settings.setdefault("openrouter_usage", {"include": True})
        return OpenRouterModel(
            request_json["model"],
            provider=OpenRouterProvider(api_key=api_key, http_client=http_client),
            settings=OpenRouterModelSettings(**settings),
        )

    def embedder(self) -> "OpenRouterEmbedder":
        return OpenRouterEmbedder(self)

    async def aclose(self) -> None:
        clients, self._clients = list(self._clients.values()), {}
        for client in clients:
            await client.aclose()


class OpenRouterEmbedder:
    """text-embedding-3-small through OpenRouter, over the gateway's client."""

    def __init__(self, gateway: ModelGateway):
        self.gateway = gateway
        self._embedder: Optional[PydanticEmbedder] = None

    async def embed(self, text: str) -> List[float]:
        if self._embedder is None:
            model = OpenAIEmbeddingModel(
                EMBEDDING_MODEL,
                provider=OpenRouterProvider(api_key=self.gateway.settings.openrouter_token, http_client=self.gateway.client(True)),
            )
            self._embedder = PydanticEmbedder(model)
        result = await self._embedder.embed_query(text)
        return result.embeddings[0]
