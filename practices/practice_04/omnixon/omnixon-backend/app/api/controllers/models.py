from typing import Sequence

from fastapi import Body, Depends

from api.controller import Controller, current_principal, endpoint
from api.schemas.models import ModelCreate, ModelUpdate
from database.models import Model
from domain.access import Principal
from services.models import ModelService


class ModelController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, models: ModelService):
        self.models = models
        super().__init__()

    @endpoint.get("/models", summary="List all models")
    async def get_models(self) -> Sequence[Model]:
        return await self.models.list()

    @endpoint.post("/models", summary="Create a new model", status_code=201, min_role="admin")
    async def create_model(self, data: ModelCreate = Body(...)) -> Model:
        return await self.models.create(data)

    @endpoint.get("/models/{model_id}", summary="Get a model by ID")
    async def get_model(self, model_id: int) -> Model:
        return await self.models.get(model_id)

    @endpoint.patch("/models/{model_id}", summary="Update a model", min_role="admin")
    async def update_model(self, model_id: int, data: ModelUpdate = Body(...), principal: Principal = Depends(current_principal)) -> Model:
        return await self.models.update(principal, model_id, data)

    @endpoint.delete("/models/{model_id}", summary="Delete a model", min_role="admin")
    async def delete_model(self, model_id: int) -> Model:
        return await self.models.delete(model_id)
