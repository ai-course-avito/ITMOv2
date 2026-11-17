"""unit model service tests: the rules of models and the versions their change leaves"""

import pytest

from api.schemas.models import ModelCreate, ModelUpdate
from domain.errors import Conflict, NotFound
from repositories.versions import VersionRepository
from services.models import ModelService
from world import world


@pytest.mark.asyncio
async def test_a_model_is_created_read_and_listed():
    async with world() as w:
        models = w.get(ModelService)
        made = await models.create(ModelCreate(name="m", request_json={"model": "a/b"}, base_url="http://llm/v1/", use_proxy=False))
        assert made.base_url == "http://llm/v1" and not made.use_proxy
        assert (await models.get(made.id)).id == made.id and made.id in [m.id for m in await models.list()]
        with pytest.raises(NotFound, match="^Model not found$"):
            await models.get(99999)


@pytest.mark.asyncio
async def test_editing_a_model_records_a_version_of_each_agent_using_it_but_a_rename_records_none():
    async with world() as w:
        models, versions = w.get(ModelService), w.get(VersionRepository)
        admin = await w.principal("admin")
        model = await models.create(ModelCreate(name="m", request_json={"model": "a/b"}))
        agent = await w.agent("user of m")
        from repositories.agents import AgentRepository
        from services.versions import VersionRecorder

        await w.get(AgentRepository).update(agent.id, model_id=model.id)
        await w.get(VersionRecorder).record(agent.id, "start", None)
        await models.update(admin, model.id, ModelUpdate(request_json={"model": "a/b", "temperature": 0}))
        assert [v.comment for v in await versions.list(agent.id)] == [f"model {model.id} updated", "start"]
        await models.update(admin, model.id, ModelUpdate(name="renamed"))
        assert await versions.latest_number(agent.id) == 2  # a name is not behaviour


@pytest.mark.asyncio
async def test_the_default_model_and_a_used_model_cannot_be_deleted():
    async with world() as w:
        models = w.get(ModelService)
        with pytest.raises(Conflict, match="^The default model cannot be deleted$"):
            await models.delete(0)
        model = await models.create(ModelCreate(name="m", request_json={"model": "a/b"}))
        from repositories.agents import AgentRepository

        agent = await w.agent()
        await w.get(AgentRepository).update(agent.id, model_id=model.id)
        with pytest.raises(Conflict, match="^Model is used by an agent$"):
            await models.delete(model.id)
        with pytest.raises(NotFound):
            await models.delete(99999)
