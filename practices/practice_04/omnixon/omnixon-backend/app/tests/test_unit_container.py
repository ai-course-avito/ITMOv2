"""unit container tests: the composition root makes each thing once and lets a test replace any of them"""

import pytest

from config import Settings
from container import Container


class Thing:
    pass


def test_get_returns_one_instance():
    container = Container(Settings(), factories={Thing: Thing})
    assert container.get(Thing) is container.get(Thing)


def test_overrides_replace_a_dependency():
    fake = Thing()
    container = Container(Settings(), factories={Thing: Thing}, overrides={Thing: fake})
    assert container.get(Thing) is fake


def test_an_unknown_type_is_an_error():
    with pytest.raises(KeyError):
        Container(Settings()).get(Thing)


@pytest.mark.asyncio
async def test_aclose_runs_the_closers_in_reverse_order_once():
    order = []
    container = Container(Settings())
    container.on_close(lambda: order.append("first"))
    container.on_close(lambda: order.append("second"))
    await container.aclose()
    await container.aclose()
    assert order == ["second", "first"]
