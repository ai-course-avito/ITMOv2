"""unit model connection tests"""

import json
import httpx
import pytest
from ai import utils as ai_utils
from database import models as database_models
from database.foundation import (
    MIGRATIONS_DIR,
    apply_migrations,
    list_migrations,
)

from shared import (
    NOW,
    scratch_database,
)


def test_a_model_is_called_through_openrouter_unless_it_has_a_base_url(monkeypatch):
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.models.openrouter import OpenRouterModel

    monkeypatch.setattr(ai_utils, "OPENROUTER_TOKEN", "system-key")
    assert isinstance(ai_utils.generate_model({"model": "a/b"}), OpenRouterModel)
    assert isinstance(
        ai_utils.generate_model(
            {"model": "a/b"}, base_url=database_models.DEFAULT_BASE_URL + "/"
        ),
        OpenRouterModel,
    )
    plain = ai_utils.generate_model(
        {"model": "a/b", "provider": {"order": ["x"]}, "temperature": 0.3},
        base_url="http://llm:8000/v1/",
    )
    assert isinstance(plain, OpenAIChatModel) and not isinstance(plain, OpenRouterModel)
    assert plain.client.base_url.host == "llm" and str(
        plain.client.base_url
    ).startswith("http://llm:8000/v1")
    # OpenRouter's own options are only OpenRouter's: here they travel in the body with the rest
    assert plain.settings["temperature"] == 0.3 and plain.settings["extra_body"] == {
        "provider": {"order": ["x"]}
    }
    assert (
        "openrouter_provider" not in plain.settings
        and "openrouter_usage" not in plain.settings
    )


@pytest.mark.asyncio
async def test_the_key_of_a_model_goes_to_its_server_and_the_system_key_otherwise(
    monkeypatch,
):
    monkeypatch.setattr(ai_utils, "OPENROUTER_TOKEN", "system-key")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((str(request.url), request.headers.get("authorization")))
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "a/b",
                "provider": "Somebody",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "pong"},
                        "finish_reason": "stop",
                        "native_finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(ai_utils, "http_client_for", lambda use_proxy: client)
    from pydantic_ai import Agent

    async def ask(**connection):
        agent = Agent(ai_utils.generate_model({"model": "a/b"}, **connection))
        return (await agent.run("ping")).output

    assert await ask(base_url="http://llm:8000/v1", api_token="its-own-key") == "pong"
    assert (
        await ask(base_url="http://llm:8000/v1") == "pong"
    )  # no key of its own: the deployment's
    assert await ask(api_token="openrouter-own-key") == "pong"
    assert await ask() == "pong"
    assert seen == [
        ("http://llm:8000/v1/chat/completions", "Bearer its-own-key"),
        ("http://llm:8000/v1/chat/completions", "Bearer system-key"),
        ("https://openrouter.ai/api/v1/chat/completions", "Bearer openrouter-own-key"),
        ("https://openrouter.ai/api/v1/chat/completions", "Bearer system-key"),
    ]


@pytest.mark.asyncio
async def test_a_model_without_the_proxy_gets_a_client_that_goes_around_it(monkeypatch):
    monkeypatch.setattr(ai_utils, "_http_client", None)
    monkeypatch.setattr(ai_utils, "_direct_client", None)
    monkeypatch.setattr(ai_utils, "OPENROUTER_PROXY", None)
    # no proxy: nothing to avoid, but the clients are still there (they retry what the provider drops)
    assert ai_utils.http_client_for(True) is not None and ai_utils.http_client_for(False) is not None
    monkeypatch.setattr(ai_utils, "_http_client", None)
    monkeypatch.setattr(ai_utils, "_direct_client", None)

    monkeypatch.setattr(ai_utils, "OPENROUTER_PROXY", "socks5://proxy:1080")
    proxied, direct = ai_utils.http_client_for(True), ai_utils.http_client_for(False)
    try:
        assert proxied is not None and direct is not None and proxied is not direct
        assert (
            ai_utils.http_client_for(False) is direct
            and ai_utils.http_client_for(True) is proxied
        )  # both shared
        assert direct.timeout.read == 600 and direct.timeout.connect == 5
    finally:
        await proxied.aclose()
        await direct.aclose()


def test_the_secret_of_a_model_is_not_in_what_it_says_about_itself():
    model = database_models.Model(
        id=3,
        request_json={"model": "a/b"},
        api_token="sk-very-secret",
        timestamp=NOW,
        base_url="http://llm/v1/",
        use_proxy=False,
    )
    dumped = model.model_dump()
    assert "api_token" not in dumped and "sk-very-secret" not in model.model_dump_json()
    assert (
        dumped["has_api_token"] is True
        and dumped["base_url"] == "http://llm/v1"
        and dumped["use_proxy"] is False
    )
    assert model.connection == {
        "base_url": "http://llm/v1",
        "use_proxy": False,
        "api_token": "sk-very-secret",
    }
    default = database_models.Model(
        id=4, request_json={"model": "a/b"}, timestamp=NOW, base_url=None
    )
    assert (
        default.base_url == database_models.DEFAULT_BASE_URL
        and default.use_proxy is True
        and default.has_api_token is False
    )


@pytest.mark.asyncio
async def test_the_connection_of_a_model_is_stored_and_changed_field_by_field():
    async with scratch_database("conn_test") as (pool, db):
        made = await db.create_model({"model": "a/b"}, "plain")
        assert (made.base_url, made.use_proxy, made.api_token) == (
            database_models.DEFAULT_BASE_URL,
            True,
            None,
        )
        own = await db.create_model(
            {"model": "a/b"},
            "own",
            base_url="http://llm/v1",
            use_proxy=False,
            api_token="k1",
        )
        assert (own.base_url, own.use_proxy, own.api_token) == (
            "http://llm/v1",
            False,
            "k1",
        )

        kept = await db.update_model(own.id, name="renamed")  # not given: kept
        assert (kept.base_url, kept.use_proxy, kept.api_token, kept.name) == (
            "http://llm/v1",
            False,
            "k1",
            "renamed",
        )
        changed = await db.update_model(own.id, use_proxy=True, api_token="k2")
        assert (changed.use_proxy, changed.api_token, changed.base_url) == (
            True,
            "k2",
            "http://llm/v1",
        )
        cleared = await db.update_model(
            own.id, base_url="", api_token=""
        )  # "" goes back to the defaults
        assert (cleared.base_url, cleared.api_token) == (
            database_models.DEFAULT_BASE_URL,
            None,
        )
        assert (
            await pool.pool.fetchval("SELECT base_url FROM models WHERE id=$1", own.id)
            is None
        )
        assert (
            await db.update_model(own.id, base_url=database_models.DEFAULT_BASE_URL)
        ).base_url == database_models.DEFAULT_BASE_URL
        assert (
            await pool.pool.fetchval("SELECT base_url FROM models WHERE id=$1", own.id)
            is None
        )  # the default is stored as NULL


@pytest.mark.asyncio
async def test_migration_12_gives_old_models_the_default_connection(
    scratch_db, tmp_path
):
    for number, path in list_migrations(MIGRATIONS_DIR):
        if number <= 11:
            (tmp_path / path.name).write_text(path.read_text())
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db, tmp_path) == 11
    await scratch_db.execute(
        'INSERT INTO models (id, request_json) VALUES (0, \'{"model": "a/b"}\')'
    )

    (tmp_path / "12.sql").write_text((MIGRATIONS_DIR / "12.sql").read_text())
    assert await apply_migrations(scratch_db, tmp_path) == 12
    row = await scratch_db.fetchrow(
        "SELECT base_url, use_proxy, api_token FROM models WHERE id=0"
    )
    assert (row["base_url"], row["use_proxy"], row["api_token"]) == (None, True, None)
    old = database_models.Model(
        id=0, request_json={"model": "a/b"}, timestamp=NOW, **dict(row)
    )
    assert (
        old.base_url == database_models.DEFAULT_BASE_URL and old.has_api_token is False
    )


@pytest.mark.asyncio
async def test_a_version_knows_the_connection_of_its_model_but_only_a_fingerprint_of_its_key():
    async with scratch_database("conn_version_test") as (pool, db):
        agent_id = db.context.agent.id
        model = await db.create_model(
            {"model": "a/b"}, "m", base_url="http://llm/v1", api_token="sk-secret-one"
        )
        await db.fetch_one(
            "UPDATE agents SET model_id=$1 WHERE id=$2 RETURNING id",
            (model.id, agent_id),
        )
        assert await db.record_agent_version(agent_id, "own model") is not None
        versions = await db.get_agent_versions(agent_id)
        assert "sk-secret-one" not in json.dumps([v.snapshot for v in versions])
        connection = versions[0].snapshot["model_connection"]
        assert (
            connection["base_url"] == "http://llm/v1"
            and connection["use_proxy"] is True
        )
        assert connection["own_api_token"] == database_models.fingerprint(
            "sk-secret-one"
        )

        # nothing changed: no new version
        assert await db.record_agent_version(agent_id, "again") is None
        # each part of the connection is a change of behaviour
        for change in (
            {"use_proxy": False},
            {"api_token": "sk-secret-two"},
            {"base_url": "http://other/v1"},
        ):
            await db.update_model(model.id, **change)
            assert await db.record_agent_version(agent_id, str(change)) is not None, (
                change
            )
        assert "sk-secret-two" not in json.dumps(
            [v.snapshot for v in await db.get_agent_versions(agent_id)]
        )


@pytest.mark.asyncio
async def test_a_rollback_brings_back_the_connection_and_keeps_the_current_key():
    async with scratch_database("conn_rollback_test") as (pool, db):
        agent_id = db.context.agent.id
        model = await db.create_model(
            {"model": "a/b"},
            "m",
            base_url="http://old/v1",
            use_proxy=False,
            api_token="sk-current",
        )
        await db.fetch_one(
            "UPDATE agents SET model_id=$1 WHERE id=$2 RETURNING id",
            (model.id, agent_id),
        )
        await db.record_agent_version(agent_id, "old connection")
        number = (await db.get_agent_versions(agent_id))[0].number
        await db.update_model(
            model.id, base_url="http://new/v1", use_proxy=True, api_token="sk-rotated"
        )
        await db.record_agent_version(agent_id, "new connection")

        await db.rollback_agent(agent_id, number, None, db.context.token.id)
        agent = await db.get_agent(agent_id)
        restored = await db.get_model(agent.model_id)
        assert (restored.base_url, restored.use_proxy) == ("http://old/v1", False)
        assert (
            restored.api_token == "sk-rotated"
        )  # keys are not in versions: the copy keeps the key of the record it replaced
        assert restored.id != model.id  # a copy: the shared record is never edited


def test_a_version_from_before_connections_is_the_default_connection_not_a_change():
    from database.mixins.agent_version import diff_snapshots, normal

    old = {
        "prompt": "p",
        "model_id": 0,
        "model": {"model": "a/b"},
        "config": {},
        "mcp_servers": [],
    }
    new = {
        **old,
        "model_connection": {
            "base_url": database_models.DEFAULT_BASE_URL,
            "use_proxy": True,
            "own_api_token": None,
        },
        "connections": [],  # nor had it connections to other agents (migration 14)
    }
    assert normal(old) == new and normal(new) is new
    assert diff_snapshots(old, new) == {}
    changed = {
        **new,
        "model_connection": {**new["model_connection"], "use_proxy": False},
    }
    assert list(diff_snapshots(old, changed)) == ["model_connection"]


def test_the_secret_of_a_model_is_masked_in_logs():
    from core.masking import mask_value

    assert "sk-abc" not in str(
        mask_value({"api_token": "sk-abc-123", "base_url": "http://x/v1"})
    )
