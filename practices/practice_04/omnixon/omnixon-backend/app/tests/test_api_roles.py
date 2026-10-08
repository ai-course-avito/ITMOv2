"""api roles tests"""

import pytest

from shared import (
    MCP_CALCULATOR_URL,
    RANK,
    ROLES,
    as_token,
    make_token,
    role_clients,
    versions_of,
)


# the highest role each role may hand out (written out here on purpose: the test must not share the code's table)
MAY_HAND_OUT = {"regular": 0, "user": 2, "admin": 2, "owner": 4}


def _cases(x):
    """(what, the lowest role that may, the call). A call below that role must be refused with 403, and
    from that role up it must not be (404, 422 and so on are fine: the door was open)."""
    a, b = x.a["id"], x.b["id"]
    return [
        (
            "search users",
            "regular",
            lambda c: c.get("/api/v1/users", params={"query": "abc"}),
        ),
        ("chats of a user", "regular", lambda c: c.get("/api/v1/users/nobody_streams/chats")),
        ("start a chat", "regular", lambda c: c.post("/api/v1/users/nobody_streams/chats")),
        ("rename a chat", "regular", lambda c: c.patch("/api/v1/users/nobody_streams/chats/1", json={"title": "x"})),
        ("delete a chat", "regular", lambda c: c.delete("/api/v1/users/nobody_streams/chats/1")),
        ("the history of a chat", "regular", lambda c: c.get("/api/v1/users/nobody_streams/chats/1/history")),
        ("recent users", "regular", lambda c: c.get("/api/v1/users/recent")),
        ("who am I", "regular", lambda c: c.get("/api/v1/tokens/self")),
        ("my agent", "regular", lambda c: c.get("/api/v1/agents/self")),
        ("list agents", "admin", lambda c: c.get("/api/v1/admin/agents")),
        ("create an agent", "admin", lambda c: c.post("/api/v1/admin/agents", json={})),
        (
            "delete an agent",
            "admin",
            lambda c: c.delete("/api/v1/admin/agents/999999999"),
        ),
        ("read the own agent", "user", lambda c: c.get(f"/api/v1/admin/agents/{a}")),
        (
            "change the own agent",
            "user",
            lambda c: c.patch(f"/api/v1/admin/agents/{a}", json={"comment": "c"}),
        ),
        (
            "versions of the own agent",
            "user",
            lambda c: c.get(f"/api/v1/admin/agents/{a}/versions"),
        ),
        (
            "MCP servers of the own agent",
            "user",
            lambda c: c.get(f"/api/v1/admin/agents/{a}/mcp-servers"),
        ),
        (
            "the knowledge of the own agent",
            "user",
            lambda c: c.get("/api/v1/admin/rag", params={"agent_id": a, "limit": 1}),
        ),
        (
            "the knowledge of the default agent",
            "user",
            lambda c: c.get("/api/v1/admin/rag", params={"limit": 1}),
        ),
        (
            "memories of the own agent",
            "user",
            lambda c: c.get("/api/v1/admin/memories", params={"user_id": "nobody"}),
        ),
        ("tokens of the own agent", "user", lambda c: c.get("/api/v1/admin/tokens")),
        (
            "change the role of a token",
            "user",
            lambda c: c.patch(
                "/api/v1/admin/tokens/999999999", json={"role": "regular"}
            ),
        ),
        ("usage", "user", lambda c: c.get("/api/v1/admin/usage")),
        ("monthly usage", "user", lambda c: c.get("/api/v1/admin/usage/monthly")),
        ("list models", "user", lambda c: c.get("/api/v1/admin/models")),
        ("read a model", "user", lambda c: c.get("/api/v1/admin/models/0")),
        ("create a model", "admin", lambda c: c.post("/api/v1/admin/models", json={})),
        (
            "change a model",
            "admin",
            lambda c: c.patch("/api/v1/admin/models/999999999", json={}),
        ),
        (
            "delete a model",
            "admin",
            lambda c: c.delete("/api/v1/admin/models/999999999"),
        ),
        ("list all MCP servers", "admin", lambda c: c.get("/api/v1/admin/mcp-servers")),
        (
            "attach an existing MCP server",
            "admin",
            lambda c: c.post(f"/api/v1/admin/agents/{a}/mcp-servers/999999999"),
        ),
        ("read another agent", "admin", lambda c: c.get(f"/api/v1/admin/agents/{b}")),
        (
            "change another agent",
            "admin",
            lambda c: c.patch(f"/api/v1/admin/agents/{b}", json={"comment": "c"}),
        ),
        (
            "versions of another agent",
            "admin",
            lambda c: c.get(f"/api/v1/admin/agents/{b}/versions"),
        ),
        (
            "roll back another agent",
            "admin",
            lambda c: c.post(f"/api/v1/admin/agents/{b}/rollback", json={"to": 1}),
        ),
        (
            "MCP servers of another agent",
            "admin",
            lambda c: c.get(f"/api/v1/admin/agents/{b}/mcp-servers"),
        ),
        (
            "detach from another agent",
            "admin",
            lambda c: c.delete(f"/api/v1/admin/agents/{b}/mcp-servers/999999999"),
        ),
        (
            "the knowledge of another agent",
            "admin",
            lambda c: c.get("/api/v1/admin/rag", params={"agent_id": b, "limit": 1}),
        ),
        (
            "memories of another agent",
            "admin",
            lambda c: c.get(
                "/api/v1/admin/memories", params={"user_id": "x", "agent_id": b}
            ),
        ),
        (
            "tokens of another agent",
            "admin",
            lambda c: c.get("/api/v1/admin/tokens", params={"agent_id": b}),
        ),
        (
            "usage of another agent",
            "admin",
            lambda c: c.get("/api/v1/admin/usage", params={"agent_id": b}),
        ),
        ("list connections between agents", "admin", lambda c: c.get("/api/v1/admin/agent-connections")),
        (
            "connect two agents",
            "admin",
            lambda c: c.post(
                "/api/v1/admin/agent-connections",
                json={"agent1_id": a, "agent2_id": a, "description": "x"},  # to itself: 409 past the door
            ),
        ),
        ("read a connection", "admin", lambda c: c.get("/api/v1/admin/agent-connections/999999999")),
        (
            "change a connection",
            "admin",
            lambda c: c.patch("/api/v1/admin/agent-connections/999999999", json={"description": "x"}),
        ),
        ("delete a connection", "admin", lambda c: c.delete("/api/v1/admin/agent-connections/999999999")),
        (
            "interrupt a user",
            "regular",
            lambda c: c.post("/api/v1/users/nobody_streams/interrupt"),
        ),
        (
            "act as another agent",
            "admin",
            lambda c: c.get(
                "/api/v1/users",
                params={"query": "abc"},
                headers={"X-Act-As-Agent": str(b)},
            ),
        ),
        (
            "act as the own agent",
            "admin",
            lambda c: c.get(
                "/api/v1/users",
                params={"query": "abc"},
                headers={"X-Act-As-Agent": str(a)},
            ),
        ),
        (
            "act as an agent that is not there",
            "admin",
            lambda c: c.get(
                "/api/v1/users",
                params={"query": "abc"},
                headers={"X-Act-As-Agent": "999999999"},
            ),
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_every_role_is_stopped_at_the_door_it_may_not_pass(client):
    async with role_clients(client) as x:
        for what, lowest, call in _cases(x):
            for role in ROLES:
                res = await call(x.clients[role])
                if RANK[role] >= RANK[lowest]:
                    assert res.status_code != 403, (
                        f"{role} should be let in: {what} -> {res.status_code} {res.text[:200]}"
                    )
                    assert res.status_code < 500, (
                        f"{role}: {what} -> {res.status_code} {res.text[:200]}"
                    )
                else:
                    assert res.status_code == 403, (
                        f"{role} must be refused: {what} -> {res.status_code} {res.text[:200]}"
                    )


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_acting_as_another_agent_is_for_admins_and_unknown_agents_are_not_found(
    client,
):
    async with role_clients(client) as x:
        for role in ("regular", "user"):
            res = await x.clients[role].get(
                "/api/v1/agents/self", headers={"X-Act-As-Agent": str(x.b["id"])}
            )
            assert res.status_code == 403 and "admin" in res.text
        for role in ("admin", "owner"):
            c = x.clients[role]
            res = await c.get(
                "/api/v1/agents/self", headers={"X-Act-As-Agent": str(x.b["id"])}
            )
            assert res.status_code == 200 and res.json()["id"] == x.b["id"]
            assert (
                await c.get(
                    "/api/v1/agents/self", headers={"X-Act-As-Agent": "999999999"}
                )
            ).status_code == 404
            assert (
                await c.get(
                    "/api/v1/agents/self", headers={"X-Act-As-Agent": "not a number"}
                )
            ).status_code == 404
            # an empty header means no acting as
            res = await c.get("/api/v1/agents/self", headers={"X-Act-As-Agent": ""})
            assert res.json()["id"] == x.a["id"]
            # the token itself is still the caller's own
            res = await c.get(
                "/api/v1/tokens/self", headers={"X-Act-As-Agent": str(x.b["id"])}
            )
            assert res.json()["id"] == x.tokens[role]["id"]


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_users_belong_to_the_agent_and_an_admin_reaches_them_by_acting_as_it(
    client,
):
    async with role_clients(client) as x:
        regular = x.clients["regular"]
        assert (
            await regular.post("/api/v1/users", json={"external_id": "ann"})
        ).status_code == 201
        # the same id on another agent is another user
        async with as_token(x.tokens["admin"]["token"], act_as=x.b["id"]) as admin_on_b:
            assert (await admin_on_b.get("/api/v1/users/ann")).status_code == 404
            made = await admin_on_b.post("/api/v1/users", json={"external_id": "ann"})
            assert made.status_code == 201 and made.json()["agent_id"] == x.b["id"]
        # the user of A is seen when acting as A, or as the token of A itself
        res = await client.get(
            "/api/v1/users/ann", headers={"X-Act-As-Agent": str(x.a["id"])}
        )
        assert res.status_code == 200 and res.json()["agent_id"] == x.a["id"]
        assert (
            await client.get("/api/v1/users/ann")
        ).status_code == 404  # the owner's own agent has no ann
        assert (await regular.get("/api/v1/users/ann")).json()["agent_id"] == x.a["id"]
        # history and deletion follow the same scope
        assert (await regular.get("/api/v1/users/ann/history")).json() == []
        assert (await regular.delete("/api/v1/users/ann")).status_code == 200
        assert (await regular.get("/api/v1/users/ann")).status_code == 404
        async with as_token(x.tokens["admin"]["token"], act_as=x.b["id"]) as admin_on_b:
            assert (
                await admin_on_b.get("/api/v1/users/ann")
            ).status_code == 200  # B's ann is untouched
            await admin_on_b.delete("/api/v1/users/ann")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_which_roles_a_token_may_hand_out(client):
    async with role_clients(client) as x:
        made = []
        try:
            for caller in ROLES:
                for role in ROLES:
                    res = await x.clients[caller].post(
                        "/api/v1/admin/tokens",
                        json={"name": "grant", "role": role, "agent_id": x.a["id"]},
                    )
                    allowed = RANK[role] <= MAY_HAND_OUT[caller]
                    if allowed:
                        assert res.status_code == 201, (
                            f"{caller} should hand out {role}: {res.text[:200]}"
                        )
                        made.append(res.json())
                        assert res.json()["role"] == role and res.json()["token"]
                    else:
                        assert res.status_code == 403, (
                            f"{caller} must not hand out {role}: {res.status_code}"
                        )
            # a regular token and a user token never reach another agent; an admin does, up to user
            for caller in ROLES:
                res = await x.clients[caller].post(
                    "/api/v1/admin/tokens",
                    json={
                        "name": "elsewhere",
                        "role": "regular",
                        "agent_id": x.b["id"],
                    },
                )
                if RANK[caller] >= RANK["admin"]:
                    assert res.status_code == 201, caller
                    made.append(res.json())
                else:
                    assert res.status_code == 403, caller
            # the nameless and role-less are refused for everybody
            for caller in ROLES:
                assert (
                    await x.clients[caller].post(
                        "/api/v1/admin/tokens", json={"role": "regular"}
                    )
                ).status_code in (403, 422)
        finally:
            for t in made:
                await client.delete(f"/api/v1/admin/tokens/{t['id']}")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_which_tokens_a_token_may_rename_and_delete(client):
    async with role_clients(client) as x:
        targets = []
        try:
            for agent in (x.a, x.b):
                for role in ROLES:
                    targets.append(
                        (
                            agent["id"],
                            role,
                            await make_token(
                                client, agent["id"], role, name=f"target {role}"
                            ),
                        )
                    )
            for caller in ROLES:
                for agent_id, role, target in targets:
                    own_or_admin = (
                        RANK[caller] >= RANK["admin"] or agent_id == x.a["id"]
                    )
                    allowed = own_or_admin and RANK[role] <= MAY_HAND_OUT[caller]
                    res = await x.clients[caller].patch(
                        f"/api/v1/admin/tokens/{target['id']}",
                        json={"name": f"by {caller}"},
                    )
                    expected = 200 if allowed else 403
                    assert res.status_code == expected, (
                        f"{caller} renaming a {role} token of agent {agent_id}: {res.status_code}"
                    )

            # deleting follows the same rule (the targets that were allowed are really deleted, the rest stay)
            for caller in ROLES:
                for agent_id, role, target in targets:
                    own_or_admin = (
                        RANK[caller] >= RANK["admin"] or agent_id == x.a["id"]
                    )
                    if not (own_or_admin and RANK[role] <= MAY_HAND_OUT[caller]):
                        res = await x.clients[caller].delete(
                            f"/api/v1/admin/tokens/{target['id']}"
                        )
                        assert res.status_code == 403, (
                            f"{caller} deleting a {role} token of agent {agent_id}: {res.status_code}"
                        )
            still = {t["id"] for t in (await client.get("/api/v1/admin/tokens")).json()}
            assert all(
                target["id"] in still for _, _, target in targets
            )  # nothing was removed by the refused ones
            # an admin removes a user token but not an admin or an owner token
            by_role = {(agent_id, role): target for agent_id, role, target in targets}
            admin = x.clients["admin"]
            assert (
                await admin.delete(
                    f"/api/v1/admin/tokens/{by_role[(x.b['id'], 'admin')]['id']}"
                )
            ).status_code == 403
            assert (
                await admin.delete(
                    f"/api/v1/admin/tokens/{by_role[(x.b['id'], 'owner')]['id']}"
                )
            ).status_code == 403
            assert (
                await admin.delete(
                    f"/api/v1/admin/tokens/{by_role[(x.b['id'], 'user')]['id']}"
                )
            ).status_code == 200
            # a user removes a regular token of its own agent
            assert (
                await x.clients["user"].delete(
                    f"/api/v1/admin/tokens/{by_role[(x.a['id'], 'regular')]['id']}"
                )
            ).status_code == 200
            # and the token it deletes stops working
            gone = by_role[(x.a["id"], "regular")]
            async with as_token(gone["token"]) as c:
                assert (await c.get("/api/v1/tokens/self")).status_code == 403
        finally:
            for _, _, target in targets:
                await client.delete(f"/api/v1/admin/tokens/{target['id']}")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_a_user_token_lists_only_the_tokens_of_its_own_agent(client):
    async with role_clients(client) as x:
        other = await make_token(client, x.b["id"], "regular", name="on B")
        try:
            listed = (await x.clients["user"].get("/api/v1/admin/tokens")).json()
            assert {t["agent_id"] for t in listed} == {x.a["id"]}
            assert other["id"] not in {t["id"] for t in listed}
            assert (
                await x.clients["user"].get(
                    "/api/v1/admin/tokens", params={"agent_id": x.b["id"]}
                )
            ).status_code == 403
            everything = (await x.clients["admin"].get("/api/v1/admin/tokens")).json()
            assert other["id"] in {t["id"] for t in everything}
            assert all("token" not in t and "token_sha256" not in t for t in everything)
        finally:
            await client.delete(f"/api/v1/admin/tokens/{other['id']}")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_a_user_changes_its_own_agent_and_may_pick_a_model_but_not_make_one(
    client,
):
    async with role_clients(client) as x:
        user = x.clients["user"]
        res = await user.patch(
            f"/api/v1/admin/agents/{x.a['id']}",
            json={
                "name": "renamed by user",
                "prompt": "You are a poet.",
                "config": {"memo_limit": 5},
                "comment": "by the user",
            },
        )
        assert res.status_code == 200
        assert (
            res.json()["prompt"] == "You are a poet."
            and res.json()["config"]["memo_limit"] == 5
        )
        version = (await versions_of(client, x.a["id"]))[0]
        assert (
            version["comment"] == "by the user"
            and version["created_by_token_id"] == x.tokens["user"]["id"]
        )
        # it picks one of the models there are
        assert len((await user.get("/api/v1/admin/models")).json()) >= 1
        assert (
            await user.patch(f"/api/v1/admin/agents/{x.a['id']}", json={"model_id": 0})
        ).status_code == 200
        assert (
            await user.patch(
                f"/api/v1/admin/agents/{x.a['id']}", json={"model_id": 999999999}
            )
        ).status_code == 404
        # but it makes and changes none, and it cannot touch the agent next door
        assert (
            await user.post(
                "/api/v1/admin/models",
                json={"name": "mine", "request_json": {"model": "a/b"}},
            )
        ).status_code == 403
        assert (
            await user.patch("/api/v1/admin/models/0", json={"name": "mine"})
        ).status_code == 403
        assert (
            await user.patch(
                f"/api/v1/admin/agents/{x.b['id']}", json={"prompt": "hijacked"}
            )
        ).status_code == 403
        assert (await client.get(f"/api/v1/admin/agents/{x.b['id']}")).json()[
            "prompt"
        ] == ""
        # rollback of its own agent works, and goes no further
        assert (
            await user.post(
                f"/api/v1/admin/agents/{x.a['id']}/rollback", json={"to": 1}
            )
        ).status_code == 200
        assert (
            await user.post(
                f"/api/v1/admin/agents/{x.b['id']}/rollback", json={"to": 1}
            )
        ).status_code == 403
        assert (
            await user.delete(f"/api/v1/admin/agents/{x.a['id']}")
        ).status_code == 403


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_mcp_servers_of_a_user_are_tied_to_its_agent_and_it_changes_only_its_own(
    client,
):
    async with role_clients(client) as x:
        user, regular = x.clients["user"], x.clients["regular"]
        url = {"url": MCP_CALCULATOR_URL}
        made: list = []
        try:
            # made by a user: tied to its agent at once
            res = await user.post(
                "/api/v1/admin/mcp-servers", json={"name": "mine", "config": url}
            )
            assert res.status_code == 201
            mine = res.json()
            made.append(mine["id"])
            assert [
                m["id"]
                for m in (
                    await user.get(f"/api/v1/admin/agents/{x.a['id']}/mcp-servers")
                ).json()
            ] == [mine["id"]]
            assert "created" in (await versions_of(client, x.a["id"]))[0]["comment"]
            # it reads and changes it, and may delete it as nothing else uses it
            assert (
                await user.get(f"/api/v1/admin/mcp-servers/{mine['id']}")
            ).status_code == 200
            res = await user.patch(
                f"/api/v1/admin/mcp-servers/{mine['id']}", json={"name": "renamed"}
            )
            assert res.status_code == 200 and res.json()["name"] == "renamed"
            # a regular token has no part in it
            assert (
                await regular.get(f"/api/v1/admin/mcp-servers/{mine['id']}")
            ).status_code == 403
            assert (
                await regular.post(
                    "/api/v1/admin/mcp-servers", json={"name": "x", "config": url}
                )
            ).status_code == 403

            # it cannot give one to another agent, nor take an existing one for its own
            assert (
                await user.post(
                    "/api/v1/admin/mcp-servers",
                    json={"name": "x", "config": url, "agent_id": x.b["id"]},
                )
            ).status_code == 403
            theirs = (
                await client.post(
                    "/api/v1/admin/mcp-servers",
                    json={"name": "of B", "config": url, "agent_id": x.b["id"]},
                )
            ).json()
            made.append(theirs["id"])
            assert (
                await user.post(
                    f"/api/v1/admin/agents/{x.a['id']}/mcp-servers/{theirs['id']}"
                )
            ).status_code == 403
            # what belongs to another agent is not its to read, change or delete
            for call in (
                lambda: user.get(f"/api/v1/admin/mcp-servers/{theirs['id']}"),
                lambda: user.patch(
                    f"/api/v1/admin/mcp-servers/{theirs['id']}",
                    json={"name": "hijacked"},
                ),
                lambda: user.delete(f"/api/v1/admin/mcp-servers/{theirs['id']}"),
            ):
                assert (await call()).status_code == 403
            assert (
                await client.get(f"/api/v1/admin/mcp-servers/{theirs['id']}")
            ).json()["name"] == "of B"
            assert (
                await user.get("/api/v1/admin/mcp-servers")
            ).status_code == 403  # no list of everybody's

            # a server shared with another agent: it may read it, not change it (that would change the other agent)
            assert (
                await client.post(
                    f"/api/v1/admin/agents/{x.b['id']}/mcp-servers/{mine['id']}"
                )
            ).status_code == 201
            assert (
                await user.get(f"/api/v1/admin/mcp-servers/{mine['id']}")
            ).status_code == 200
            assert (
                await user.patch(
                    f"/api/v1/admin/mcp-servers/{mine['id']}",
                    json={"name": "shared edit"},
                )
            ).status_code == 403
            assert (
                await user.delete(f"/api/v1/admin/mcp-servers/{mine['id']}")
            ).status_code == 403
            # but it can let go of it
            assert (
                await user.delete(
                    f"/api/v1/admin/agents/{x.a['id']}/mcp-servers/{mine['id']}"
                )
            ).status_code == 200
            assert (
                await user.get(f"/api/v1/admin/mcp-servers/{mine['id']}")
            ).status_code == 403  # no longer its own
            # a server only its agent uses can be deleted by it
            alone = (
                await user.post(
                    "/api/v1/admin/mcp-servers", json={"name": "alone", "config": url}
                )
            ).json()
            assert (
                await user.delete(f"/api/v1/admin/mcp-servers/{alone['id']}")
            ).status_code == 200
            assert (
                await client.get(f"/api/v1/admin/mcp-servers/{alone['id']}")
            ).status_code == 404

            # an admin may make one that belongs to nobody
            loose = (
                await client.post(
                    "/api/v1/admin/mcp-servers", json={"name": "loose", "config": url}
                )
            ).json()
            made.append(loose["id"])
            assert (
                await client.get(f"/api/v1/admin/agents/{x.a['id']}/mcp-servers")
            ).json() == []
        finally:
            for mcp_id in made:
                await client.delete(f"/api/v1/admin/mcp-servers/{mcp_id}")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_the_knowledge_of_an_agent_is_the_users_but_not_another_agents(client):
    async with role_clients(client) as x:
        user = x.clients["user"]
        created = await user.post(
            "/api/v1/admin/rag", json={"content": "A fact of agent A."}
        )
        assert created.status_code == 201 and created.json()["agent_id"] == x.a["id"]
        entry = created.json()
        try:
            listed = (
                await user.get("/api/v1/admin/rag", params={"limit": 1000})
            ).json()
            assert [e["content"] for e in listed] == ["A fact of agent A."]
            assert (
                await user.patch(
                    f"/api/v1/admin/rag/{entry['id']}", json={"content": "Changed."}
                )
            ).status_code == 200
            # another agent's knowledge is out of reach, whichever way it is asked for
            assert (
                await user.get("/api/v1/admin/rag", params={"agent_id": x.b["id"]})
            ).status_code == 403
            assert (
                await user.post(
                    "/api/v1/admin/rag",
                    params={"agent_id": x.b["id"]},
                    json={"content": "planted"},
                )
            ).status_code == 403
            assert (
                await user.get(
                    f"/api/v1/admin/rag/{entry['id']}", params={"agent_id": x.b["id"]}
                )
            ).status_code == 403
            assert (
                await user.delete(
                    f"/api/v1/admin/rag/{entry['id']}", params={"agent_id": x.b["id"]}
                )
            ).status_code == 403
            assert (
                await client.get(
                    "/api/v1/admin/rag", params={"agent_id": x.b["id"], "limit": 10}
                )
            ).json() == []
        finally:
            await user.delete(f"/api/v1/admin/rag/{entry['id']}")
        # a regular token has no knowledge base access at all
        assert (await x.clients["regular"].get("/api/v1/admin/rag")).status_code == 403


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_memories_of_a_user_follow_the_agent_scope(client):
    async with role_clients(client) as x:
        user = x.clients["user"]
        await user.post("/api/v1/users", json={"external_id": "mem_user"})
        made = await user.post(
            "/api/v1/admin/memories",
            json={"user_id": "mem_user", "content": "Likes tea."},
        )
        assert made.status_code == 201
        memory = made.json()
        try:
            assert [
                m["id"]
                for m in (
                    await user.get(
                        "/api/v1/admin/memories", params={"user_id": "mem_user"}
                    )
                ).json()
            ] == [memory["id"]]
            assert (
                await user.get(
                    "/api/v1/admin/memories",
                    params={"user_id": "mem_user", "agent_id": x.b["id"]},
                )
            ).status_code == 403
            assert (
                await user.post(
                    "/api/v1/admin/memories",
                    json={"user_id": "mem_user", "content": "x", "agent_id": x.b["id"]},
                )
            ).status_code == 403
            # a memory of an agent next door cannot be reached by its id either
            async with as_token(x.tokens["admin"]["token"], act_as=x.b["id"]) as on_b:
                await on_b.post("/api/v1/users", json={"external_id": "mem_user"})
                theirs = (
                    await on_b.post(
                        "/api/v1/admin/memories",
                        json={"user_id": "mem_user", "content": "B only."},
                    )
                ).json()
                for call in (
                    lambda: user.get(f"/api/v1/admin/memories/{theirs['id']}"),
                    lambda: user.patch(
                        f"/api/v1/admin/memories/{theirs['id']}", json={"content": "x"}
                    ),
                    lambda: user.delete(f"/api/v1/admin/memories/{theirs['id']}"),
                ):
                    assert (await call()).status_code == 403
                assert (
                    await on_b.get(f"/api/v1/admin/memories/{theirs['id']}")
                ).json()["content"] == "B only."
                await on_b.delete("/api/v1/users/mem_user")
        finally:
            await user.delete("/api/v1/users/mem_user")


@pytest.mark.asyncio
@pytest.mark.order(24)
async def test_the_role_of_a_token_can_be_changed_up_to_what_the_caller_may_hand_out(
    client,
):
    async with role_clients(client) as x:
        owner_id = (await client.get("/api/v1/tokens/self")).json()["id"]
        target = await make_token(client, x.a["id"], "regular", name="to be promoted")
        url = f"/api/v1/admin/tokens/{target['id']}"
        try:
            # a user token may make it a user, and back, but not an admin
            user = x.clients["user"]
            res = await user.patch(url, json={"role": "user"})
            assert (
                res.status_code == 200
                and res.json()["role"] == "user"
                and res.json()["name"] == "to be promoted"
            )
            assert (await user.patch(url, json={"role": "admin"})).status_code == 403
            assert (
                await user.patch(url, json={"role": "regular", "name": "demoted"})
            ).json() == {**res.json(), "role": "regular", "name": "demoted"}
            # something has to be given
            assert (await user.patch(url, json={})).status_code == 422
            assert (await user.patch(url, json={"role": "boss"})).status_code == 422
            # the new role is the real one: the secret works with it
            async with as_token(target["token"]) as c:
                assert (await c.get("/api/v1/tokens/self")).json()["role"] == "regular"
                assert (await c.get("/api/v1/admin/tokens")).status_code == 403
            assert (await client.patch(url, json={"role": "user"})).status_code == 200
            async with as_token(target["token"]) as c:
                assert (
                    await c.get("/api/v1/admin/tokens")
                ).status_code == 200  # a user token now

            # an admin may not hand out admin either; the owner may, and may take it back
            assert (
                await x.clients["admin"].patch(url, json={"role": "admin"})
            ).status_code == 403
            assert (await client.patch(url, json={"role": "admin"})).json()[
                "role"
            ] == "admin"
            # a token above what the caller may hand out is not the caller's to change
            assert (await user.patch(url, json={"role": "regular"})).status_code == 403
            assert (
                await x.clients["admin"].patch(url, json={"role": "regular"})
            ).status_code == 403
            assert (await client.patch(url, json={"role": "regular"})).json()[
                "role"
            ] == "regular"

            # a token does not change its own role; the initial token keeps being an owner
            res = await x.clients["owner"].patch(
                f"/api/v1/admin/tokens/{x.tokens['owner']['id']}", json={"role": "user"}
            )
            assert res.status_code == 409
            res = await x.clients["owner"].patch(
                f"/api/v1/admin/tokens/{owner_id}", json={"role": "user"}
            )
            assert res.status_code == 409
            assert (await client.get("/api/v1/tokens/self")).json()["role"] == "owner"
        finally:
            await client.delete(url)
