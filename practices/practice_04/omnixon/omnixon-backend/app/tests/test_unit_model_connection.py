"""unit model connection tests: where a model is reached and with which key, how that is stored, versioned and rolled back"""

import json

import httpx2
import pytest

from config import Settings
from database import models as database_models
from domain.models import DEFAULT_BASE_URL
from infrastructure.llm import ModelGateway
from infrastructure.postgres import MIGRATIONS_DIR, apply_migrations, list_migrations
from repositories.models import ModelRepository
from services.models import ModelService
from services.versions import VersionRecorder, VersionService
from shared import NOW
from world import world


def test_a_model_is_called_through_openrouter_unless_it_has_a_base_url():
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.models.openrouter import OpenRouterModel

    gateway = ModelGateway(Settings(openrouter_token="system-key"))
    assert isinstance(gateway.chat_model({"model": "a/b"}), OpenRouterModel)
    assert isinstance(gateway.chat_model({"model": "a/b"}, base_url=DEFAULT_BASE_URL + "/"), OpenRouterModel)
    plain = gateway.chat_model({"model": "a/b", "provider": {"order": ["x"]}, "temperature": 0.3}, base_url="http://llm:8000/v1/")
    assert isinstance(plain, OpenAIChatModel) and not isinstance(plain, OpenRouterModel)
    assert plain.client.base_url.host == "llm" and str(plain.client.base_url).startswith("http://llm:8000/v1")
    # OpenRouter's own options are only OpenRouter's: here they travel in the body with the rest
    assert plain.settings["temperature"] == 0.3 and plain.settings["extra_body"] == {"provider": {"order": ["x"]}}
    assert "openrouter_provider" not in plain.settings and "openrouter_usage" not in plain.settings


@pytest.mark.asyncio
async def test_the_key_of_a_model_goes_to_its_server_and_the_system_key_otherwise():
    from pydantic_ai import Agent

    seen = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((str(request.url), request.headers.get("authorization")))
        return httpx2.Response(
            200,
            json={
                "id": "x", "object": "chat.completion", "created": 0, "model": "a/b", "provider": "Somebody",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop", "native_finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    gateway = ModelGateway(Settings(openrouter_token="system-key"))
    gateway._clients[True] = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    async def ask(**connection):
        return (await Agent(gateway.chat_model({"model": "x/b"}, **connection)).run("ping")).output

    assert await ask(base_url="http://llm:8000/v1", api_token="its-own-key") == "pong"
    assert await ask(base_url="http://llm:8000/v1") == "pong"  # no key of its own: the deployment's
    assert await ask(api_token="openrouter-own-key") == "pong"
    assert await ask() == "pong"
    assert seen == [
        ("http://llm:8000/v1/chat/completions", "Bearer its-own-key"),
        ("http://llm:8000/v1/chat/completions", "Bearer system-key"),
        ("https://openrouter.ai/api/v1/chat/completions", "Bearer openrouter-own-key"),
        ("https://openrouter.ai/api/v1/chat/completions", "Bearer system-key"),
    ]
    await gateway.aclose()


def test_the_secret_of_a_model_is_not_in_what_it_says_about_itself():
    model = database_models.Model(id=3, request_json={"model": "a/b"}, api_token="sk-very-secret", timestamp=NOW, base_url="http://llm/v1/", use_proxy=False)
    dumped = model.model_dump()
    assert "api_token" not in dumped and "sk-very-secret" not in model.model_dump_json()
    assert dumped["has_api_token"] is True and dumped["base_url"] == "http://llm/v1" and dumped["use_proxy"] is False
    assert model.connection == {"base_url": "http://llm/v1", "use_proxy": False, "api_token": "sk-very-secret"}
    default = database_models.Model(id=4, request_json={"model": "a/b"}, timestamp=NOW, base_url=None)
    assert default.base_url == DEFAULT_BASE_URL and default.use_proxy is True and default.has_api_token is False


@pytest.mark.asyncio
async def test_the_connection_of_a_model_is_stored_and_changed_field_by_field():
    async with world() as w:
        models = w.get(ModelRepository)
        made = await models.insert({"model": "a/b"}, "plain")
        assert (made.base_url, made.use_proxy, made.api_token) == (DEFAULT_BASE_URL, True, None)
        own = await models.insert({"model": "a/b"}, "own", base_url="http://llm/v1", use_proxy=False, api_token="k1")
        assert (own.base_url, own.use_proxy, own.api_token) == ("http://llm/v1", False, "k1")
        kept = await models.update(own.id, name="renamed")  # not given: kept
        assert (kept.base_url, kept.use_proxy, kept.api_token, kept.name) == ("http://llm/v1", False, "k1", "renamed")
        changed = await models.update(own.id, use_proxy=True, api_token="k2")
        assert (changed.use_proxy, changed.api_token, changed.base_url) == (True, "k2", "http://llm/v1")
        cleared = await models.update(own.id, base_url="", api_token="")  # "" goes back to the defaults
        assert (cleared.base_url, cleared.api_token) == (DEFAULT_BASE_URL, None)
        stored = lambda: models.db.fetch_one("SELECT base_url FROM models WHERE id=$1", (own.id,))  # noqa: E731
        assert (await stored())["base_url"] is None
        assert (await models.update(own.id, base_url=DEFAULT_BASE_URL)).base_url == DEFAULT_BASE_URL
        assert (await stored())["base_url"] is None  # the default is stored as NULL


@pytest.mark.asyncio
async def test_migration_12_gives_old_models_the_default_connection(scratch_db, tmp_path):
    for number, path in list_migrations(MIGRATIONS_DIR):
        if number <= 11:
            (tmp_path / path.name).write_text(path.read_text())
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db, tmp_path) == 11
    await scratch_db.execute('INSERT INTO models (id, request_json) VALUES (0, \'{"model": "a/b"}\')')
    (tmp_path / "12.sql").write_text((MIGRATIONS_DIR / "12.sql").read_text())
    assert await apply_migrations(scratch_db, tmp_path) == 12
    row = await scratch_db.fetchrow("SELECT base_url, use_proxy, api_token FROM models WHERE id=0")
    assert (row["base_url"], row["use_proxy"], row["api_token"]) == (None, True, None)
    old = database_models.Model(id=0, request_json={"model": "a/b"}, timestamp=NOW, **dict(row))
    assert old.base_url == DEFAULT_BASE_URL and old.has_api_token is False


@pytest.mark.asyncio
async def test_a_version_knows_the_connection_of_its_model_but_only_a_fingerprint_of_its_key():
    async with world() as w:
        models, recorder, versions = w.get(ModelRepository), w.get(VersionRecorder), w.get(VersionService)
        admin = await w.principal("admin")
        agent = await w.agent("a")
        model = await models.insert({"model": "a/b"}, "m", base_url="http://llm/v1", api_token="sk-secret-one")
        await models.db.execute("UPDATE agents SET model_id=$1 WHERE id=$2", (model.id, agent.id))
        assert await recorder.record(agent.id, "own model", None) is not None
        listed = await versions.list(admin, agent.id)
        assert "sk-secret-one" not in json.dumps([v.snapshot for v in listed])
        connection = listed[0].snapshot["model_connection"]
        assert connection["base_url"] == "http://llm/v1" and connection["use_proxy"] is True
        from domain.models import ModelConnection

        assert connection["own_api_token"] == ModelConnection(api_token="sk-secret-one").fingerprint()
        assert await recorder.record(agent.id, "again", None) is None  # nothing changed: no new version
        for change in ({"use_proxy": False}, {"api_token": "sk-secret-two"}, {"base_url": "http://other/v1"}):  # each part is a change of behaviour
            await models.update(model.id, **change)
            assert await recorder.record(agent.id, str(change), None) is not None, change
        assert "sk-secret-two" not in json.dumps([v.snapshot for v in await versions.list(admin, agent.id)])


@pytest.mark.asyncio
async def test_a_rollback_brings_back_the_connection_and_keeps_the_current_key():
    async with world() as w:
        models, recorder, versions = w.get(ModelRepository), w.get(VersionRecorder), w.get(VersionService)
        admin = await w.principal("admin")
        agent = await w.agent("a")
        model = await models.insert({"model": "a/b"}, "m", base_url="http://old/v1", use_proxy=False, api_token="sk-current")
        await models.db.execute("UPDATE agents SET model_id=$1 WHERE id=$2", (model.id, agent.id))
        await recorder.record(agent.id, "old connection", None)
        number = (await versions.list(admin, agent.id))[0].number
        await models.update(model.id, base_url="http://new/v1", use_proxy=True, api_token="sk-rotated")
        await recorder.record(agent.id, "new connection", None)
        await versions.rollback(admin, agent.id, number, None)
        from repositories.agents import AgentRepository

        restored = await models.get((await w.get(AgentRepository).get(agent.id)).model_id)
        assert (restored.base_url, restored.use_proxy) == ("http://old/v1", False)
        assert restored.api_token == "sk-rotated"  # keys are not in versions: the copy keeps the key of the record it replaced
        assert restored.id != model.id  # a copy: the shared record is never edited


def test_a_version_from_before_connections_is_the_default_connection_not_a_change():
    from domain.agents import AgentSnapshot

    old = {"prompt": "p", "model_id": 0, "model": {"model": "a/b"}, "config": {}, "mcp_servers": []}
    new = {
        **old,
        "model_connection": {"base_url": DEFAULT_BASE_URL, "use_proxy": True, "own_api_token": None},
        "connections": [],  # nor had it connections to other agents (migration 14)
    }
    assert AgentSnapshot.from_raw(old).raw == new and AgentSnapshot.from_raw(new).raw == new
    assert AgentSnapshot.from_raw(old).diff(AgentSnapshot.from_raw(new)) == {}
    changed = {**new, "model_connection": {**new["model_connection"], "use_proxy": False}}
    assert list(AgentSnapshot.from_raw(old).diff(AgentSnapshot.from_raw(changed))) == ["model_connection"]


def test_the_secret_of_a_model_is_masked_in_logs():
    from core.masking import mask_value

    assert "sk-abc" not in str(mask_value({"api_token": "sk-abc-123", "base_url": "http://x/v1"}))
