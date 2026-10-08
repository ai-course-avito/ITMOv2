from typing import Optional, Sequence
from ..context import PostgresConnectionWithContext
from ..models import DEFAULT_BASE_URL, Model


class ModelMethods(PostgresConnectionWithContext):
    async def get_model(self, model_id: int) -> Optional[Model]:
        query = "SELECT * FROM models WHERE id=$1"
        return await self.fetch_one(query, (model_id,), Model)

    async def get_all_models(self) -> Sequence[Model]:
        query = "SELECT * FROM models ORDER BY id ASC"
        return (await self.fetch_all(query, (), Model)) or []

    async def create_model(
        self,
        request_json: dict,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        use_proxy: bool = True,
        api_token: Optional[str] = None,
    ) -> Model:
        """`base_url` None (or OpenRouter's own address) is stored as NULL; `api_token` None: the key of the deployment."""
        query = """
            INSERT INTO models (request_json, name, base_url, use_proxy, api_token)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        return await self.fetch_one(
            query,
            (request_json, name, None if base_url in (None, "", DEFAULT_BASE_URL) else base_url, use_proxy, api_token or None),
            Model,
        )

    async def update_model(
        self,
        model_id: int,
        request_json: Optional[dict] = None,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        use_proxy: Optional[bool] = None,
        api_token: Optional[str] = None,
    ) -> Optional[Model]:
        """Only what is given changes. For `base_url` and `api_token` an empty string goes back to the default (OpenRouter, the
        key of the deployment); None keeps what there is."""
        if base_url == DEFAULT_BASE_URL:
            base_url = ""
        query = """
            UPDATE models
            SET request_json=COALESCE($1, request_json),
                name=COALESCE($2, name),
                base_url=CASE WHEN $3::text IS NULL THEN base_url WHEN $3 = '' THEN NULL ELSE $3 END,
                use_proxy=COALESCE($4, use_proxy),
                api_token=CASE WHEN $5::text IS NULL THEN api_token WHEN $5 = '' THEN NULL ELSE $5 END
            WHERE id=$6
            RETURNING *
        """
        return await self.fetch_one(
            query, (request_json, name, base_url, use_proxy, api_token, model_id), Model
        )

    async def delete_model(self, model_id: int) -> Optional[Model]:
        query = "DELETE FROM models WHERE id=$1 RETURNING *"
        return await self.fetch_one(query, (model_id,), Model)
