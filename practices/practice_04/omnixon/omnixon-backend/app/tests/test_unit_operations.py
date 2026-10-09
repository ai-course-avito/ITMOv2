"""unit operations tests: readiness and the metrics page"""

from types import SimpleNamespace

import pytest

from infrastructure.postgres import list_migrations


def controller(pool):
    from api.controllers.health import HealthController
    from repositories.database import Database

    return HealthController(Database(pool))


@pytest.mark.asyncio
async def test_readiness_is_503_without_a_pool_or_a_database():
    import json as _json

    res = await controller(None).readyz()
    assert res.status_code == 503 and _json.loads(res.body)["status"] == "starting"

    class BrokenPool:
        @staticmethod
        def acquire():
            raise ConnectionRefusedError("database is down")

    res = await controller(BrokenPool()).readyz()
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "database unavailable"
    assert body["detail"] == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_readiness_reports_a_database_that_is_behind():
    import json as _json

    class Connection:
        async def fetchval(self, query):
            return 2  # applied

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *exc):
            return None

    class Pool:
        @staticmethod
        def acquire():
            return Acquire()

    res = await controller(Pool()).readyz()
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "migrating"
    assert body["migration"] == 2 and body["expected"] == list_migrations()[-1][0]


def test_metrics_page_renders_the_families():
    from core import metrics

    body, content_type = metrics.render()
    assert content_type.startswith("text/plain")
    assert b"omnixon_http_requests_total" in body and b"omnixon_active_streams" in body
