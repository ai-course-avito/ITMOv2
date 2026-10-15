"""unit token service tests: who may make, change and delete which token, and the initial token"""

import pytest

from api.schemas.tokens import TokenCreate, TokenUpdate
from domain.errors import Conflict, Forbidden, NotFound
from repositories.people import TokenRepository
from services.tokens import TokenService
from world import world


@pytest.mark.asyncio
async def test_a_user_token_hands_out_regular_and_user_only_on_its_own_agent():
    async with world() as w:
        tokens = w.get(TokenService)
        user = await w.principal("user")
        made = await tokens.create(user, TokenCreate(name="n", role="regular"))
        assert made.agent_id == user.agent.id and made.token and made.token_sha256
        assert (await tokens.create(user, TokenCreate(name="n", role="user"))).role == "user"
        with pytest.raises(Forbidden, match="may not hand out the admin role"):
            await tokens.create(user, TokenCreate(name="n", role="admin"))
        other = await w.agent("other")
        with pytest.raises(Forbidden, match="only use its own agent"):
            await tokens.create(user, TokenCreate(name="n", role="regular", agent_id=other.id))
        with pytest.raises(NotFound, match="^Agent not found$"):
            await tokens.create(await w.principal("admin"), TokenCreate(name="n", role="regular", agent_id=99999))


@pytest.mark.asyncio
async def test_listing_is_scoped_by_role():
    async with world() as w:
        tokens = w.get(TokenService)
        user, admin = await w.principal("user"), await w.principal("admin")
        mine = [t.id for t in await tokens.list(user)]
        assert mine == [user.token.id]
        assert user.token.id in [t.id for t in await tokens.list(admin)] and len(await tokens.list(admin)) > 1
        with pytest.raises(Forbidden):
            await tokens.list(user, agent_id=admin.agent.id)


@pytest.mark.asyncio
async def test_the_texts_of_what_cannot_be_done_to_a_token():
    async with world() as w:
        tokens, repo = w.get(TokenService), w.get(TokenRepository)
        owner = await w.principal("owner")
        with pytest.raises(Conflict, match="^The token in use cannot delete itself$"):
            await tokens.delete(owner, owner.token.id)
        with pytest.raises(Conflict, match="^The token in use cannot change its own role$"):
            await tokens.update(owner, owner.token.id, TokenUpdate(role="admin"))
        initial = await tokens.ensure_initial("x")
        assert initial.is_initial and initial.role == "owner"
        with pytest.raises(Conflict, match="^The initial token cannot be deleted$"):
            await tokens.delete(owner, initial.id)
        with pytest.raises(Conflict, match="^The role of the initial token cannot be changed$"):
            await tokens.update(owner, initial.id, TokenUpdate(role="user"))
        with pytest.raises(NotFound, match="^Token not found$"):
            await tokens.delete(owner, 99999)
        other_agent_token = await repo.insert("x", (await w.agent("o")).id, "regular")
        user = await w.principal("user")
        with pytest.raises(Forbidden, match="may not manage a token of that role or agent"):
            await tokens.delete(user, other_agent_token.id)


@pytest.mark.asyncio
async def test_the_initial_token_is_made_once_with_an_agent_of_its_own_and_raised_to_owner_again():
    async with world() as w:
        tokens, repo = w.get(TokenService), w.get(TokenRepository)
        first = await tokens.ensure_initial("fresh-initial-secret")
        again = await tokens.ensure_initial("fresh-initial-secret")
        assert first.id == again.id and first.role == "owner" and first.is_initial is False  # the repository here knows another initial key
        await repo.update(first.id, role="user")
        assert (await tokens.ensure_initial("fresh-initial-secret")).role == "owner"
        from repositories.agents import AgentRepository

        assert (await w.get(AgentRepository).get(first.agent_id)).name == "Default agent"


@pytest.mark.asyncio
async def test_two_replicas_starting_together_make_one_initial_token():
    import asyncio

    async with world() as w:
        tokens = w.get(TokenService)
        made = await asyncio.gather(*[tokens.ensure_initial("racing-secret") for _ in range(5)])
        assert len({t.id for t in made}) == 1
