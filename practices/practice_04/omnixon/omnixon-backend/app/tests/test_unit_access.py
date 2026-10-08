"""unit access tests"""

import json
import uuid
from types import SimpleNamespace
import asyncpg
import pytest
from core import DATABASE_CONFIG
from database import Agent
from database.models import Token, token_hash
from database.foundation import (
    MIGRATIONS_DIR,
    apply_migrations,
    list_migrations,
)

from shared import (
    NOW,
    scratch_database,
    scratch_pool,
)


def _row(**kw):
    return {"timestamp": NOW, **kw}


def test_fallback_names_of_rows_without_a_name():
    from database.models import MCPServer, Model

    assert MCPServer(**_row(id=5, config={"url": "http://x"})).name == "MCP 5"
    assert Model(**_row(id=3, request_json={"model": "a/b"})).name == "a/b"
    assert Model(**_row(id=3, request_json={})).name == "Model 3"  # no model inside
    assert Model(**_row(id=3, request_json='{"model": "c/d"}')).name == "c/d"
    for blank in (None, "", "   "):
        assert MCPServer(**_row(id=5, name=blank, config={"url": "u"})).name == "MCP 5"


def test_a_given_name_always_wins_over_the_fallback():
    from database.models import MCPServer, Model

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
    """Rows of a database that only knew migrations up to 9 get no name; after the
    migration they are shown with the fallbacks and can be named."""
    from database import Context, PostgresDB, PostgresPool

    name = f"names_test_{uuid.uuid4().hex[:8]}"
    admin = await scratch_pool(name)
    try:
        async with PostgresPool({**DATABASE_CONFIG, "database": name}) as pool:
            async with PostgresDB(
                pool, Context(agent=None, token=None, user=None)
            ) as db:
                # what an old row looks like: no name at all
                model_id = (
                    await db.fetch_one(
                        "INSERT INTO models (request_json) VALUES ($1) RETURNING id",
                        ({"model": "old/model"},),
                    )
                )["id"]
                mcp_id = (
                    await db.fetch_one(
                        "INSERT INTO mcp_servers (config) VALUES ($1) RETURNING id",
                        ({"url": "http://old"},),
                    )
                )["id"]
                agent_id = (
                    await db.fetch_one(
                        "INSERT INTO agents (prompt, model_id) VALUES ($1, $2) RETURNING id",
                        ("Old prompt\nmore", model_id),
                    )
                )["id"]
                bare_agent_id = (
                    await db.fetch_one(
                        "INSERT INTO agents (prompt, model_id) VALUES ('', $1) RETURNING id",
                        (model_id,),
                    )
                )["id"]
                assert (await db.get_model(model_id)).name == "old/model"
                assert (await db.get_mcp_server(mcp_id)).name == f"MCP {mcp_id}"
                assert (await db.get_agent(agent_id)).name == "Old prompt"
                assert (
                    await db.get_agent(bare_agent_id)
                ).name == f"Agent {bare_agent_id}"
                assert {a.id: a.name for a in await db.get_all_agents()}[
                    agent_id
                ] == "Old prompt"
                assert [m.name for m in await db.get_all_mcp_servers()] == [
                    f"MCP {mcp_id}"
                ]

                # naming them
                assert (await db.update_model(model_id, name="Old")).name == "Old"
                assert (
                    await db.update_mcp_server(mcp_id, name="Maths")
                ).name == "Maths"
                renamed = await db.update_agent(agent_id, name="Support")
                assert (
                    renamed.name == "Support" and renamed.prompt == "Old prompt\nmore"
                )
                # a change without a name keeps it; the content of a rename is untouched
                assert (await db.update_agent(agent_id, prompt="New")).name == "Support"
                assert (await db.get_model(model_id)).request_json == {
                    "model": "old/model"
                }
                assert (await db.update_model(model_id, {"model": "x/y"})).name == "Old"

                # a rollback makes copies without names: they show the fallbacks
                mcp2 = await db.create_mcp_server({"url": "http://c"})
                assert mcp2.name == f"MCP {mcp2.id}"
                assert (await db.create_model({"model": "p/q"})).name == "p/q"
    finally:
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


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


def fake_db(role: str, agent_id: int = 1, token_id: int = 10):
    """Enough of a database object for the checks of access.py: a context with a token."""
    token = Token(
        id=token_id,
        name="t",
        agent_id=agent_id,
        role=role,
        token_sha256="x",
        timestamp=NOW,
    )
    return SimpleNamespace(
        context=SimpleNamespace(token=token, agent=SimpleNamespace(id=agent_id))
    )


def a_token(role: str, agent_id: int = 1, token_id: int = 99) -> Token:
    return Token(
        id=token_id,
        name="other",
        agent_id=agent_id,
        role=role,
        token_sha256="y",
        timestamp=NOW,
    )


def test_roles_are_ranked_regular_user_admin_owner():
    from database import RANK, ROLES

    assert ROLES == ("regular", "user", "admin", "owner")
    assert [RANK[r] for r in ROLES] == [1, 2, 3, 4]


@pytest.mark.parametrize(
    "caller, grants",
    [
        ("regular", set()),
        ("user", {"regular", "user"}),
        ("admin", {"regular", "user"}),  # an admin cannot hand out admin
        ("owner", {"regular", "user", "admin", "owner"}),
    ],
)
def test_who_may_hand_out_which_role(caller, grants):
    from access import may_grant
    from database import ROLES

    db = fake_db(caller)
    assert {role for role in ROLES if may_grant(db, role)} == grants


def test_a_token_is_managed_only_up_to_what_the_caller_may_hand_out_and_on_agents_it_may_use():
    from access import can_manage_token

    # a user: regular and user tokens of its own agent only
    user = fake_db("user", agent_id=1)
    assert can_manage_token(user, a_token("regular", agent_id=1))
    assert can_manage_token(user, a_token("user", agent_id=1))
    assert not can_manage_token(user, a_token("admin", agent_id=1))
    assert not can_manage_token(user, a_token("regular", agent_id=2))  # another agent

    # an admin: any agent, but nothing from admin up
    admin = fake_db("admin", agent_id=1)
    assert can_manage_token(admin, a_token("user", agent_id=2))
    assert not can_manage_token(admin, a_token("admin", agent_id=2))
    assert not can_manage_token(admin, a_token("owner", agent_id=1))

    # an owner: everything
    owner = fake_db("owner", agent_id=1)
    assert all(
        can_manage_token(owner, a_token(r, agent_id=5))
        for r in ("regular", "user", "admin", "owner")
    )

    # a regular token manages nothing, not even its own kind
    assert not can_manage_token(fake_db("regular"), a_token("regular", agent_id=1))


def test_agents_outside_the_own_one_are_for_admins_only():
    from access import default_agent_id, ensure_agent_access
    from fastapi import HTTPException

    for role in ("regular", "user"):
        db = fake_db(role, agent_id=1)
        ensure_agent_access(db, 1)
        with pytest.raises(HTTPException) as e:
            ensure_agent_access(db, 2)
        assert e.value.status_code == 403
        assert default_agent_id(db, None) == 1
        with pytest.raises(HTTPException):
            default_agent_id(db, 2)
    for role in ("admin", "owner"):
        db = fake_db(role, agent_id=1)
        ensure_agent_access(db, 2)
        assert default_agent_id(db, 2) == 2


@pytest.mark.asyncio
async def test_require_lets_through_the_role_and_above():
    from access import require
    from fastapi import HTTPException

    for needed, passes in {
        "user": {"user", "admin", "owner"},
        "admin": {"admin", "owner"},
        "owner": {"owner"},
    }.items():
        for role in ("regular", "user", "admin", "owner"):
            request = SimpleNamespace(state=SimpleNamespace(db=fake_db(role)))
            if role in passes:
                assert await require(needed)(request) is None
            else:
                with pytest.raises(HTTPException) as e:
                    await require(needed)(request)
                assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_a_token_is_stored_as_a_hash_and_its_secret_is_known_only_when_it_is_made():
    async with scratch_database("tokens_test") as (pool, db):
        made = await db.create_token("bot", db.context.agent.id, "user")
        assert (
            made.token
            and len(made.token) == 64
            and made.role == "user"
            and made.name == "bot"
        )

        # the database holds the hash, nowhere the secret
        row = await db.fetch_one("SELECT * FROM tokens WHERE id=$1", (made.id,))
        assert row["token_sha256"] == token_hash(made.token)
        assert made.token not in json.dumps({k: str(v) for k, v in row.items()})
        columns = {
            r["column_name"]
            for r in await pool.pool.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name='tokens'"
            )
        }
        assert columns == {
            "id",
            "name",
            "agent_id",
            "role",
            "token_sha256",
            "timestamp",
        }

        # found by the secret; a wrong secret finds nothing; reading it back gives no secret
        found = await db.get_token_by_secret(made.token)
        assert found.id == made.id and found.agent_id == db.context.agent.id
        assert await db.get_token_by_secret(made.token + "x") is None
        assert "token" not in found.model_dump()
        assert "token" not in (await db.get_token(made.id)).model_dump()

        # two tokens never share a secret
        other = await db.create_token("bot2", db.context.agent.id, "regular")
        assert other.token != made.token

        # rename, delete: a deleted token stops working at once
        assert (await db.update_token(made.id, name="renamed")).name == "renamed"
        changed = await db.update_token(
            made.id, role="user"
        )  # the role may be changed; what is not given stays
        assert (changed.name, changed.role) == ("renamed", "user")
        assert (await db.update_token(made.id, role="regular")).name == "renamed"
        assert (await db.delete_token(made.id)).id == made.id
        assert await db.get_token_by_secret(made.token) is None
        assert await db.delete_token(made.id) is None


@pytest.mark.asyncio
async def test_a_role_must_exist_and_an_agent_with_tokens_cannot_be_deleted():
    async with scratch_database("tokens_fk_test") as (pool, db):
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await db.create_token("bad", db.context.agent.id, "superuser")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await db.create_token("bad", 999999, "user")

        made = await db.create_token("bot", db.context.agent.id, "user")
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await db.delete_agent(db.context.agent.id)  # still has a token
        await db.delete_token(made.id)
        assert (await db.delete_agent(db.context.agent.id)) is not None


@pytest.mark.asyncio
async def test_the_initial_token_is_an_owner_with_an_agent_of_its_own_and_is_made_once():
    async with scratch_database("initial_test") as (pool, db):
        first = await db.get_token_by_secret("a-deployment-key")
        assert first is None
        made = await db.ensure_initial_token("a-deployment-key")
        assert made.role == "owner" and made.name == "initial"
        agent = await db.get_agent(made.agent_id)
        assert agent.name == "Default agent" and agent.prompt == ""
        assert (
            await db.get_latest_version_number(agent.id) == 1
        )  # recorded like any agent

        again = await db.ensure_initial_token("a-deployment-key")
        assert (
            again.id == made.id and again.agent_id == made.agent_id
        )  # a restart changes nothing

        # someone lowered it by hand: the next start makes it an owner again
        await db.execute("UPDATE tokens SET role='regular' WHERE id=$1", (made.id,))
        assert (await db.ensure_initial_token("a-deployment-key")).role == "owner"


@pytest.mark.asyncio
async def test_users_belong_to_an_agent_and_are_separate_between_agents():
    async with scratch_database("users_agent_test") as (pool, db):
        first = db.context.agent
        second = await db.create_agent("second", 0, name="b")

        mine = await db.create_user("shared-id")
        assert mine.agent_id == first.id
        assert await db.create_user("shared-id") is None  # one per agent

        db.context.agent = second
        theirs = await db.create_user(
            "shared-id"
        )  # the same id in another agent is another user
        assert theirs.id != mine.id and theirs.agent_id == second.id
        assert (await db.get_user("shared-id")).id == theirs.id
        assert [u.external_id for u in await db.search_users("sha")] == ["shared-id"]

        db.context.agent = first
        assert (await db.get_user("shared-id")).id == mine.id
        # deleting an agent takes its users along
        await db.delete_agent(second.id)
        assert (
            await pool.pool.fetchval(
                "SELECT count(*) FROM users WHERE id=$1", theirs.id
            )
            == 0
        )


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
