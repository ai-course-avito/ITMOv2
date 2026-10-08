from typing import Optional, Sequence

from fastapi import Body, Depends, Query

from api.controller import Controller, current_principal, endpoint
from api.schemas.tokens import TokenCreate, TokenUpdate
from database.models import Agent, NewToken, Token
from domain.access import Principal
from services.tokens import TokenService


class TokenController(Controller):
    prefix = "/api/v1/admin"
    tags = ["Admin API"]
    default_role = "user"

    def __init__(self, tokens: TokenService):
        self.tokens = tokens
        super().__init__()

    @endpoint.get("/tokens", summary="List tokens (of one agent, or of all for an admin)")
    async def get_tokens(
        self,
        agent_id: Optional[int] = Query(None, description="Only the tokens of this agent. Below admin: always the own agent"),
        principal: Principal = Depends(current_principal),
    ) -> Sequence[Token]:
        return await self.tokens.list(principal, agent_id)

    @endpoint.post("/tokens", summary="Make a token. Its secret is in the answer, and only there", status_code=201)
    async def create_token(self, data: TokenCreate = Body(...), principal: Principal = Depends(current_principal)) -> NewToken:
        return await self.tokens.create(principal, data)

    @endpoint.patch("/tokens/{token_id}", summary="Rename a token and/or change its role")
    async def update_token(self, token_id: int, data: TokenUpdate = Body(...), principal: Principal = Depends(current_principal)) -> Token:
        return await self.tokens.update(principal, token_id, data)

    @endpoint.delete("/tokens/{token_id}", summary="Delete a token (it stops working at once)")
    async def delete_token(self, token_id: int, principal: Principal = Depends(current_principal)) -> Token:
        return await self.tokens.delete(principal, token_id)


class SelfController(Controller):
    """What a token may know about itself, whatever its role (the admin panel signs in with it)."""

    prefix = "/api/v1"
    tags = ["Main API"]

    def __init__(self, tokens: TokenService):
        self.tokens = tokens
        super().__init__()

    @endpoint.get("/tokens/self", summary="Get the token in use: its role and its agent")
    async def get_self_token(self, principal: Principal = Depends(current_principal)) -> Token:
        return await self.tokens.self_token(principal)

    @endpoint.get("/agents/self", summary="Get the agent of the token (or the one acted as)")
    async def get_self_agent(self, principal: Principal = Depends(current_principal)) -> Agent:
        return principal.agent
