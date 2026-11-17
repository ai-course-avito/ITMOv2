"""unit version recorder tests"""

import pytest

from repositories.agents import AgentRepository
from repositories.versions import VersionRepository
from services.versions import VersionRecorder
from world import world


@pytest.mark.asyncio
async def test_a_version_is_recorded_only_when_the_snapshot_changes():
    async with world() as w:
        recorder, versions, agents = w.get(VersionRecorder), w.get(VersionRepository), w.get(AgentRepository)
        agent = await w.agent()
        assert (await recorder.record(agent.id, "created", None)).number == 1
        assert await recorder.record(agent.id, "again", None) is None  # nothing changed
        await agents.update(agent.id, prompt="other")
        assert (await recorder.record(agent.id, "edited", None)).number == 2
        assert [v.comment for v in await versions.list(agent.id)] == ["edited", "created"]
        assert await recorder.record(99999, "nobody", None) is None


@pytest.mark.asyncio
async def test_two_recorders_at_once_number_the_versions_one_after_another():
    import asyncio

    async with w_ctx() as w:
        recorder, agents = w.get(VersionRecorder), w.get(AgentRepository)
        agent = await w.agent()

        async def change(i):
            await agents.update(agent.id, prompt=f"p{i}")
            return await recorder.record(agent.id, f"c{i}", None)

        made = [v for v in await asyncio.gather(*[change(i) for i in range(4)]) if v]
        numbers = sorted(v.number for v in made)
        assert numbers == list(range(1, len(numbers) + 1))


def w_ctx():
    return world()
