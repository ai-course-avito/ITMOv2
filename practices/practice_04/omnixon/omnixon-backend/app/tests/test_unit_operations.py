"""unit operations tests: readiness and the metrics page"""

from types import SimpleNamespace

import pytest

from database.foundation import list_migrations


class FakeApp:
    def __init__(self, pool):
        self.state = SimpleNamespace(db_pool=pool)


class FakeRequest:
    def __init__(self, pool):
        self.app = FakeApp(pool)


@pytest.mark.asyncio
async def test_readiness_is_503_without_a_pool_or_a_database():
    import json as _json
    from routers.health import readyz

    res = await readyz(FakeRequest(None))
    assert res.status_code == 503 and _json.loads(res.body)["status"] == "starting"

    class BrokenPool:
        class pool:  # noqa: N801
            @staticmethod
            def acquire():
                raise ConnectionRefusedError("database is down")

    res = await readyz(FakeRequest(BrokenPool()))
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "database unavailable"
    assert body["detail"] == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_readiness_reports_a_database_that_is_behind(monkeypatch):
    import json as _json
    from routers import health

    class Connection:
        async def fetchval(self, query):
            return 2  # applied

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *exc):
            return None

    class Pool:
        class pool:  # noqa: N801
            @staticmethod
            def acquire():
                return Acquire()

    res = await health.readyz(FakeRequest(Pool()))
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "migrating"
    assert body["migration"] == 2 and body["expected"] == list_migrations()[-1][0]


def test_metrics_page_renders_the_families():
    from core import metrics

    body, content_type = metrics.render()
    assert content_type.startswith("text/plain")
    assert b"omnixon_http_requests_total" in body and b"omnixon_active_streams" in body
