"""unit openapi tests: the schema says which role every route needs, read from the routes themselves (openapi.py)"""

import pytest
from fastapi import Depends, FastAPI

from api.controller import require_role as require
from domain.roles import Role
from openapi import NO_TOKEN, add_roles, required_role

RANK = {role.value: role.rank for role in Role}


@pytest.fixture(scope="module")
def schema():
    from main import app

    return app.openapi()


def operations(schema):
    return [(m.upper(), p, op) for p, item in schema["paths"].items() for m, op in item.items()]


def test_every_operation_says_its_role(schema):
    for method, path, op in operations(schema):
        assert op["x-min-role"] in (*RANK, NO_TOKEN), (method, path)
    assert {(m, p) for m, p, op in operations(schema) if op["x-min-role"] == NO_TOKEN} == {("GET", "/healthz"), ("GET", "/readyz")}


def test_the_role_is_the_one_the_route_enforces(schema):
    role = {(m, p): op["x-min-role"] for m, p, op in operations(schema)}
    assert role[("POST", "/api/v1/request")] == "regular"
    assert role[("GET", "/api/v1/tokens/self")] == "regular"
    assert role[("GET", "/api/v1/admin/agents/{agent_id}")] == "user"  # the router needs `user`
    assert role[("GET", "/api/v1/admin/agents")] == "admin"  # the route needs more than its router
    assert role[("POST", "/api/v1/admin/models")] == "admin"
    assert role[("GET", "/api/v1/admin/models")] == "user"
    assert role[("PATCH", "/api/v1/admin/agent-connections/{connection_id}")] == "admin"  # a whole router with require("admin")


def test_a_token_is_asked_for_on_every_route_that_needs_one(schema):
    assert "BearerToken" in schema["components"]["securitySchemes"]
    for method, path, op in operations(schema):
        if op["x-min-role"] == NO_TOKEN:
            assert op["security"] == []
        else:
            assert op["security"] == [{"BearerToken": []}], (method, path)
            assert "Needs " in op["description"]


def test_the_role_of_a_route_is_the_highest_of_its_dependencies():
    app = FastAPI(dependencies=[])

    async def ok():
        return {}

    app.get("/low", dependencies=[Depends(require("user"))])(ok)
    app.get("/both", dependencies=[Depends(require("user")), Depends(require("owner"))])(ok)
    app.get("/open")(ok)
    add_roles(app)
    paths = app.openapi()["paths"]
    assert [paths[p]["get"]["x-min-role"] for p in ("/low", "/both", "/open")] == ["user", "owner", "regular"]
    assert required_role(app.routes[-1].dependant) is None
