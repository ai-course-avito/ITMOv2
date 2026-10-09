"""unit tests of names, tokens and users as the database keeps them (and the migrations that made them so)"""

import json

import asyncpg
import pytest

from domain.entities import Agent, token_hash
from infrastructure.postgres import MIGRATIONS_DIR, apply_migrations, list_migrations
from repositories.agents import AgentRepository
from repositories.models import McpServerRepository, ModelRepository
from repositories.people import TokenRepository, UserRepository
from shared import NOW
from world import world


def _row(**kw):
    return {"timestamp": NOW, **kw}


def test_fallback_names_of_rows_without_a_name():
    from domain.entities import MCPServer, Model

    assert MCPServer(**_row(id=5, config={"url": "http://x"})).name == "MCP 5"
    assert Model(**_row(id=3, request_json={"model": "a/b"})).name == "a/b"
    assert Model(**_row(id=3, request_json={})).name == "Model 3"  # no model inside
    assert Model(**_row(id=3, request_json='{"model": "c/d"}')).name == "c/d"
    for blank in (None, "", "   "):
        assert MCPServer(**_row(id=5, name=blank, config={"url": "u"})).name == "MCP 5"


def test_a_given_name_always_wins_over_the_fallback():
    from domain.entities import MCPServer, Model

    agent = Agent(**_row(id=2, name="Support", prompt="You are a pirate.", model_id=0))
    assert agent.name == "Support"
    assert (
        Model(**_row(id=3, name="Fast", request_json={"model": "a/b"})).name == "Fast"
    )
    assert MCPServer(**_row(id=5, name="Maths", config={"url": "u"})).name == "Maths"


def test_an_agent_without_a_name_shows_the_start_of_its_prompt():
    def name(prompt, id=2):
        return Agent(**_row(id=id, prompt=prompt, model_id=0)).name

    assert name("You are a pirate.") == "You are a pirate."
    assert name("\n\n   Second thing  \nthird") == "Second thing"  # first real line
    long = name("w" * 200)
    assert len(long) == 60 and long.endswith("…")
    assert name("") == "Agent 2" and name("  \n ") == "Agent 2"  # nothing to quote


def test_the_name_goes_out_in_the_api_answer():
    agent = Agent(**_row(id=2, prompt="Hello there", model_id=0))
    assert agent.model_dump(mode="json")["name"] == "Hello there"


@pytest.mark.asyncio
async def test_rows_made_before_names_exist_are_served_with_fallbacks():
    """Rows of a database that only knew migrations up to 9 get no name; after the migration they are shown with the fallbacks and can be named."""
    async with world() as w:
        db, models, servers, agents = w.get(ModelRepository).db, w.get(ModelRepository), w.get(McpServerRepository), w.get(AgentRepository)
        # what an old row looks like: no name at all
        model_id = (await db.fetch_one("INSERT INTO models (request_json) VALUES ($1) RETURNING id", ({"model": "old/model"},)))["id"]
        mcp_id = (await db.fetch_one("INSERT INTO mcp_servers (config) VALUES ($1) RETURNING id", ({"url": "http://old"},)))["id"]
        agent_id = (await db.fetch_one("INSERT INTO agents (prompt, model_id) VALUES ($1, $2) RETURNING id", ("Old prompt\nmore", model_id)))["id"]
        bare_agent_id = (await db.fetch_one("INSERT INTO agents (prompt, model_id) VALUES ('', $1) RETURNING id", (model_id,)))["id"]
        assert (await models.get(model_id)).name == "old/model"
        assert (await servers.get(mcp_id)).name == f"MCP {mcp_id}"
        assert (await agents.get(agent_id)).name == "Old prompt"
        assert (await agents.get(bare_agent_id)).name == f"Agent {bare_agent_id}"
        assert {a.id: a.name for a in await agents.list()}[agent_id] == "Old prompt"
        assert [m.name for m in await servers.list()] == [f"MCP {mcp_id}"]

        # naming them
        assert (await models.update(model_id, name="Old")).name == "Old"
        assert (await servers.update(mcp_id, name="Maths")).name == "Maths"
        renamed = await agents.update(agent_id, name="Support")
        assert renamed.name == "Support" and renamed.prompt == "Old prompt\nmore"
        # a change without a name keeps it; the content of a rename is untouched
        assert (await agents.update(agent_id, prompt="New")).name == "Support"
        assert (await models.get(model_id)).request_json == {"model": "old/model"}
        assert (await models.update(model_id, {"model": "x/y"})).name == "Old"

        # a rollback makes copies without names: they show the fallbacks
        mcp2 = await servers.insert({"url": "http://c"})
        assert mcp2.name == f"MCP {mcp2.id}"
        assert (await models.insert({"model": "p/q"})).name == "p/q"


def test_migration_10_adds_a_nullable_name_to_the_four_entities():
    sql = (MIGRATIONS_DIR / "10.sql").read_text()
    for table in (
        "agents",
        "models",
        "mcp_servers",
        "units",
    ):  # units were dropped later, by migration 11
        assert f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS name TEXT" in sql
    assert "NOT NULL" not in sql  # old rows have none

@pytest.mark.asyncio
async def test_a_token_is_stored_as_a_hash_and_its_secret_is_known_only_when_it_is_made():
    async with world() as w:
        tokens, agent = w.get(TokenRepository), await w.agent("a")
        made = await tokens.insert("bot", agent.id, "user")
        assert made.token and len(made.token) == 64 and made.role == "user" and made.name == "bot"

        # the database holds the hash, nowhere the secret
        row = await tokens.db.fetch_one("SELECT * FROM tokens WHERE id=$1", (made.id,))
        assert row["token_sha256"] == token_hash(made.token)
        assert made.token not in json.dumps({k: str(v) for k, v in row.items()})
        columns = {r["column_name"] for r in await tokens.db.fetch_all("SELECT column_name FROM information_schema.columns WHERE table_name='tokens'")}
        assert columns == {"id", "name", "agent_id", "role", "token_sha256", "timestamp"}

        # found by the secret; a wrong secret finds nothing; reading it back gives no secret
        found = await tokens.by_secret(made.token)
        assert found.id == made.id and found.agent_id == agent.id
        assert await tokens.by_secret(made.token + "x") is None
        assert "token" not in found.model_dump() and "token" not in (await tokens.get(made.id)).model_dump()

        other = await tokens.insert("bot2", agent.id, "regular")  # two tokens never share a secret
        assert other.token != made.token

        # rename, delete: a deleted token stops working at once
        assert (await tokens.update(made.id, name="renamed")).name == "renamed"
        changed = await tokens.update(made.id, role="user")  # the role may be changed; what is not given stays
        assert (changed.name, changed.role) == ("renamed", "user")
        assert (await tokens.update(made.id, role="regular")).name == "renamed"
        assert (await tokens.delete(made.id)).id == made.id
        assert await tokens.by_secret(made.token) is None and await tokens.delete(made.id) is None


@pytest.mark.asyncio
async def test_a_role_must_exist_and_an_agent_with_tokens_cannot_be_deleted():
    async with world() as w:
        tokens, agents, agent = w.get(TokenRepository), w.get(AgentRepository), await w.agent("a")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await tokens.insert("bad", agent.id, "superuser")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await tokens.insert("bad", 999999, "user")
        made = await tokens.insert("bot", agent.id, "user")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await agents.delete(agent.id)  # still has a token
        await tokens.delete(made.id)
        assert await agents.delete(agent.id) is not None


@pytest.mark.asyncio
async def test_users_belong_to_an_agent_and_are_separate_between_agents():
    async with world() as w:
        users, agents = w.get(UserRepository), w.get(AgentRepository)
        first, second = await w.agent("first"), await w.agent("second")
        mine = await users.insert(first.id, "shared-id")
        assert mine.agent_id == first.id and await users.insert(first.id, "shared-id") is None  # one per agent
        theirs = await users.insert(second.id, "shared-id")  # the same id in another agent is another user
        assert theirs.id != mine.id and theirs.agent_id == second.id
        assert (await users.get(second.id, "shared-id")).id == theirs.id and (await users.get(first.id, "shared-id")).id == mine.id
        assert [u.external_id for u in await users.search(second.id, "sha")] == ["shared-id"]
        await agents.delete(second.id)  # deleting an agent takes its users along
        assert (await users.db.fetch_one("SELECT count(*) AS n FROM users WHERE id=$1", (theirs.id,)))["n"] == 0


@pytest.mark.asyncio
async def test_migration_11_turns_units_into_tokens_and_users_follow_their_agent(
    scratch_db, tmp_path
):
    for number, path in list_migrations(MIGRATIONS_DIR):
        if number <= 10:
            (tmp_path / path.name).write_text(path.read_text())
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db, tmp_path) == 10

    await scratch_db.execute(
        'INSERT INTO models (id, request_json) VALUES (0, \'{"model": "a/b"}\')'
    )
    agent_a = await scratch_db.fetchval(
        "INSERT INTO agents (prompt, model_id) VALUES ('a', 0) RETURNING id"
    )
    agent_b = await scratch_db.fetchval(
        "INSERT INTO agents (prompt, model_id) VALUES ('b', 0) RETURNING id"
    )
    admin = await scratch_db.fetchval(
        "INSERT INTO units (name, agent_id, token, is_admin) VALUES ('boss', $1, 'tok-admin', true) RETURNING id",
        agent_a,
    )
    plain = await scratch_db.fetchval(
        "INSERT INTO units (name, agent_id, token) VALUES ('bot', $1, 'tok-plain') RETURNING id",
        agent_a,
    )  # shares agent a
    other = await scratch_db.fetchval(
        "INSERT INTO units (agent_id, token) VALUES ($1, 'tok-other') RETURNING id",
        agent_b,
    )
    nobody = await scratch_db.fetchval(
        "INSERT INTO units (token) VALUES ('tok-noagent') RETURNING id"
    )  # made no agent yet

    # users: the same external id in two units that share an agent, and in a unit of another agent
    u_admin = await scratch_db.fetchval(
        "INSERT INTO users (unit_id, external_id) VALUES ($1, 'ann') RETURNING id",
        admin,
    )
    u_plain = await scratch_db.fetchval(
        "INSERT INTO users (unit_id, external_id) VALUES ($1, 'ann') RETURNING id",
        plain,
    )
    u_plain2 = await scratch_db.fetchval(
        "INSERT INTO users (unit_id, external_id) VALUES ($1, 'bob') RETURNING id",
        plain,
    )
    u_other = await scratch_db.fetchval(
        "INSERT INTO users (unit_id, external_id) VALUES ($1, 'ann') RETURNING id",
        other,
    )
    for user in (u_admin, u_plain):
        await scratch_db.execute(
            'INSERT INTO messages (user_id, content) VALUES ($1, \'{"type": "user", "content": "hi"}\')',
            user,
        )
        await scratch_db.execute(
            "INSERT INTO memories (user_id, agent_id, content) VALUES ($1, $2, 'likes tea')",
            user,
            agent_a,
        )
    await scratch_db.execute(
        "INSERT INTO agent_versions (agent_id, number, snapshot, created_by_unit_id) VALUES ($1, 1, '{}', $2)",
        agent_a,
        plain,
    )

    (tmp_path / "11.sql").write_text((MIGRATIONS_DIR / "11.sql").read_text())
    assert await apply_migrations(scratch_db, tmp_path) == 11

    # a token per unit: admin units admin, others regular; named like the unit; only the hash is kept
    tokens = {r["name"]: r for r in await scratch_db.fetch("SELECT * FROM tokens")}
    assert set(tokens) == {"boss", "bot", f"unit {other}", f"unit {nobody}"}
    assert tokens["boss"]["role"] == "admin" and tokens["bot"]["role"] == "regular"
    assert tokens["boss"]["token_sha256"] == token_hash("tok-admin")
    assert (
        tokens["bot"]["agent_id"] == agent_a
        and tokens[f"unit {other}"]["agent_id"] == agent_b
    )
    assert tokens[f"unit {nobody}"]["agent_id"] is not None  # it got an agent
    assert "token" not in {
        r["column_name"]
        for r in await scratch_db.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_name='tokens'"
        )
    }
    assert (
        await scratch_db.fetchval("SELECT to_regclass('units')") is None
    )  # the table is gone

    # users of one agent with one external id are one user now, with the messages and memories of both
    users = await scratch_db.fetch("SELECT * FROM users ORDER BY id")
    assert {(u["agent_id"], u["external_id"]) for u in users} == {
        (agent_a, "ann"),
        (agent_a, "bob"),
        (agent_b, "ann"),
    }
    ann = next(
        u for u in users if u["agent_id"] == agent_a and u["external_id"] == "ann"
    )
    assert (
        await scratch_db.fetchval(
            "SELECT count(*) FROM messages WHERE user_id=$1", ann["id"]
        )
        == 2
    )
    assert (
        await scratch_db.fetchval(
            "SELECT count(*) FROM memories WHERE user_id=$1", ann["id"]
        )
        == 2
    )
    assert u_other in {u["id"] for u in users} and u_plain2 in {u["id"] for u in users}

    # who made a version: the token of that unit
    made_by = await scratch_db.fetchval(
        "SELECT created_by_token_id FROM agent_versions"
    )
    assert made_by == tokens["bot"]["id"]

    # the same secret still opens the door
    assert (
        await scratch_db.fetchval(
            "SELECT role FROM tokens WHERE token_sha256 = encode(sha256(convert_to('tok-plain','UTF8')), 'hex')"
        )
        == "regular"
    )
