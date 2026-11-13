"""unit controller tests: a class of endpoints becomes a router that looks like the functions it replaces"""

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from api.controller import Controller, endpoint, require_role
from api.errors import install_error_handlers
from domain.entities import Agent, Token
from domain.access import Principal
from shared import NOW
from openapi import add_roles


class Things(Controller):
    prefix = "/api/v1"

    def __init__(self, greeting: str):
        self.greeting = greeting
        super().__init__()

    @endpoint.get("/things", summary="List the things")
    async def get_things(self) -> list[str]:
        return [self.greeting]

    @endpoint.post("/things", summary="Make a thing", status_code=201, min_role="admin")
    async def create_thing(self, request: Request, name: str = "x") -> dict:
        return {"name": name, "role": request.state.principal.role.rank}

    @endpoint.get("/things/{thing_id}", summary="One thing", min_role="user")
    async def get_thing(self, thing_id: int, who: str = Depends(lambda: "me")) -> dict:
        return {"id": thing_id, "who": who}


def app_with(greeting="hi", rank=4):
    app = FastAPI()

    @app.middleware("http")
    async def fake_auth(request: Request, call_next):
        token = Token(id=1, name="t", agent_id=1, role=("regular", "user", "admin", "owner")[rank - 1], timestamp=NOW)
        request.state.principal = Principal(token, Agent(id=1, prompt="", model_id=0, timestamp=NOW))
        return await call_next(request)

    install_error_handlers(app)
    app.include_router(Things(greeting).router)
    add_roles(app)
    return app


def test_marked_methods_become_routes_in_order():
    paths = [(r.path, sorted(r.methods)) for r in Things("hi").router.routes]
    assert paths == [("/api/v1/things", ["GET"]), ("/api/v1/things", ["POST"]), ("/api/v1/things/{thing_id}", ["GET"])]


def test_the_state_of_the_controller_is_used_and_the_status_is_kept():
    c = TestClient(app_with("hello"))
    assert c.get("/api/v1/things").json() == ["hello"]
    res = c.post("/api/v1/things?name=a")
    assert res.status_code == 201 and res.json() == {"name": "a", "role": 4}


def test_the_operation_id_is_the_method_name():
    ops = app_with().openapi()["paths"]
    assert ops["/api/v1/things"]["get"]["operationId"] == "get_things_api_v1_things_get"
    assert ops["/api/v1/things"]["post"]["summary"] == "Make a thing"


def test_min_role_shows_as_x_min_role():
    ops = app_with().openapi()["paths"]
    assert [ops["/api/v1/things"]["get"]["x-min-role"], ops["/api/v1/things"]["post"]["x-min-role"], ops["/api/v1/things/{thing_id}"]["get"]["x-min-role"]] == ["regular", "admin", "user"]


def test_a_route_below_its_role_answers_403_with_todays_text():
    res = TestClient(app_with(rank=2)).post("/api/v1/things")
    assert res.status_code == 403 and res.json() == {"detail": "Forbidden: needs the admin role"}
    assert TestClient(app_with(rank=2)).get("/api/v1/things/3").json() == {"id": 3, "who": "me"}


def test_require_role_carries_its_role():
    assert require_role("admin").min_role == "admin"
