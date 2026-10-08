from __future__ import annotations

from typing import List

import asyncpg

from database.models import Model
from domain.access import Principal
from domain.errors import Conflict, NotFound
from repositories.agents import AgentRepository
from repositories.models import ModelRepository
from repositories.unit_of_work import UnitOfWork
from .versions import VersionRecorder


class ModelService:
    def __init__(self, models: ModelRepository, agents: AgentRepository, recorder: VersionRecorder, uow: UnitOfWork):
        self.models, self.agents, self.recorder, self.uow = models, agents, recorder, uow

    async def list(self) -> List[Model]:
        return await self.models.list()

    async def get(self, model_id: int) -> Model:
        model = await self.models.get(model_id)
        if not model:
            raise NotFound("Model not found")
        return model

    async def create(self, data) -> Model:
        return await self.models.insert(data.request_json, data.name, data.base_url, data.use_proxy, data.api_token)

    async def update(self, principal: Principal, model_id: int, data) -> Model:
        async with self.uow.transaction():  # the model and the versions of the agents it changes
            model = await self.models.update(model_id, data.request_json, data.name, data.base_url, data.use_proxy, data.api_token)
            if not model:
                raise NotFound("Model not found")
            # a new name changes no behaviour; the recorder adds a version only if the snapshot differs
            await self.recorder.record_many(await self.agents.ids_using_model(model_id), f"model {model_id} updated", principal.token.id)
        return model

    async def delete(self, model_id: int) -> Model:
        if model_id == 0:
            raise Conflict("The default model cannot be deleted")
        try:
            model = await self.models.delete(model_id)
        except asyncpg.ForeignKeyViolationError:
            raise Conflict("Model is used by an agent")
        if not model:
            raise NotFound("Model not found")
        return model
