"""unit gateway tests: models, settings and clients, built from settings (no module globals to patch)"""

import httpx2
import pytest

from config import Settings
from infrastructure.llm import ModelGateway, ModelSettingsMapper, OpenRouterEmbedder


def gateway(**settings):
    return ModelGateway(Settings(openrouter_token="test-key", **settings))


def test_chat_model_maps_openrouter_options():
    model = gateway().chat_model({"model": "a/b", "provider": {"order": ["x"]}, "reasoning": {"effort": "low"}, "not_a_setting": 1})
    assert model.model_name == "a/b"
    assert model.settings["openrouter_provider"] == {"order": ["x"]}
    assert model.settings["openrouter_reasoning"] == {"effort": "low"}
    assert model.settings["extra_body"] == {"not_a_setting": 1}  # sent as it is
    # the cost is always asked for (OpenRouter usage accounting), unless the model says otherwise
    assert gateway().chat_model({"model": "a/b"}).settings == {"openrouter_usage": {"include": True}}
    assert gateway().chat_model({"model": "a/b", "usage": {"include": False}}).settings["openrouter_usage"] == {"include": False}


def test_every_key_of_the_body_goes_on():
    settings = ModelSettingsMapper().settings(
        {"model": "a/b", "temperature": 0.2, "max_tokens": 12, "top_p": 0.9, "seed": 7, "stop": ["END"], "provider": {"order": ["x"]}, "top_k": 40, "min_p": 0.05}
    )
    assert settings == {
        "temperature": 0.2, "max_tokens": 12, "top_p": 0.9, "seed": 7, "stop_sequences": ["END"],
        "openrouter_provider": {"order": ["x"]}, "extra_body": {"top_k": 40, "min_p": 0.05},
    }
    assert ModelSettingsMapper().settings({"model": "a/b"}) == {}
    # for another server OpenRouter's options are not special
    assert ModelSettingsMapper().settings({"model": "a/b", "provider": 1}, openrouter=False) == {"extra_body": {"provider": 1}}


@pytest.mark.asyncio
async def test_a_model_of_another_server_is_the_plain_openai_protocol_with_its_own_key():
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.models.openrouter import OpenRouterModel

    g = gateway()
    other = g.chat_model({"model": "m"}, base_url="http://llm:8000/v1/", api_token="its-own-key")
    assert type(other) is OpenAIChatModel and str(other.client.base_url).rstrip("/") == "http://llm:8000/v1"
    assert isinstance(g.chat_model({"model": "x/m"}), OpenRouterModel)
    await g.aclose()


@pytest.mark.asyncio
async def test_the_clients_are_shared_patient_and_follow_the_proxy_setting():
    g = gateway()
    client = g.client(True)
    try:
        assert g.client(True) is client and g.client(False) is not client  # shared; the direct one is its own
        assert client.timeout.read == 600 and client.timeout.connect == 5  # not the 5 s that would cut off slow answers
    finally:
        await g.aclose()
    assert g._clients == {}


@pytest.mark.asyncio
async def test_a_gateway_with_a_proxy_builds_its_client_through_it():
    g = gateway(openrouter_proxy="socks5://proxy:1080")
    try:
        assert g.client(True) is not g.client(False)
    finally:
        await g.aclose()


@pytest.mark.asyncio
async def test_the_embedder_asks_for_the_small_embedding_model_through_the_gateway():
    seen = []

    def handler(request: httpx2.Request):
        seen.append(request.url.path)
        return httpx2.Response(200, json={"object": "list", "data": [{"object": "embedding", "index": 0, "embedding": [0.5, 0.25]}], "model": "m", "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    g = gateway()
    g._clients[True] = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    assert await OpenRouterEmbedder(g).embed("hello") == [0.5, 0.25] and seen == ["/api/v1/embeddings"]
