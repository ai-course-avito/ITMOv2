"""unit error tests: a domain error is an answer, and an upstream failure keeps its status"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import install_error_handlers
from domain.errors import Conflict, Forbidden, Invalid, NotFound


def client_raising(error):
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/x")
    async def x():
        raise error

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("error, status", [(NotFound("Agent not found"), 404), (Conflict("Agent still has tokens"), 409), (Forbidden("Forbidden: nope"), 403), (Invalid("bad"), 422)])
def test_each_domain_error_has_its_status_and_detail(error, status):
    res = client_raising(error).get("/x")
    assert res.status_code == status and res.json() == {"detail": error.detail}


def test_upstream_failures_keep_502_and_504():
    import httpx

    assert client_raising(httpx.ConnectError("refused")).get("/x").status_code == 502
    assert client_raising(httpx.ReadTimeout("slow")).get("/x").status_code == 504
