"""A small world for service tests: the real object graph on a scratch database (no HTTP, no model)."""

import contextlib
from types import SimpleNamespace

from config import Settings
from container import Container, controllers, wire_data_layer, wire_services
from domain.access import Principal
from repositories.database import Database
from services.auth import AuthService
from shared import scratch_database


class FakeEmbedder:
    """Meaning as a number: a text embeds to a unit vector at the angle its `angles` entry says (default: from the length of the text)."""

    def __init__(self, angles=None):
        self.angles, self.calls, self.fail = dict(angles or {}), [], False

    async def embed(self, text):
        import math

        self.calls.append(text)
        if self.fail:
            raise RuntimeError("the embedding service is down")
        angle = self.angles.get(text, len(text) / 10)
        vector = [0.0] * 1536
        vector[0], vector[1] = math.cos(angle), math.sin(angle)
        return vector


class FakeGateway:
    """Every model of every agent is the one given (a pydantic-ai FunctionModel or TestModel); `models_asked` says which were asked for."""

    def __init__(self, model):
        self.model, self.models_asked = model, []

    def chat_model(self, request_json, **connection):
        self.models_asked.append((request_json, connection))
        return self.model

    async def aclose(self):
        return None


@contextlib.asynccontextmanager
async def world(embedder=None, model=None, **settings):
    """Yields `w`: `w.get(Class)` from the container, `w.principal(role, agent=None)` (a token of that role on an agent, default a fresh one),
    `w.agent(name)`."""
    async with scratch_database("service") as (pool, _):
        from infrastructure.llm import Embedder, ModelGateway

        overrides = {Embedder: embedder or FakeEmbedder()}
        if model is not None:
            overrides[ModelGateway] = FakeGateway(model)
        container = Container(Settings(initial_api_key="x", **settings), overrides=overrides)
        wire_data_layer(container)
        wire_services(container)
        container.get(Database).bind(pool.pool)

        async def make_agent(name="agent", prompt="p", **config):
            from repositories.agents import AgentRepository

            return await container.get(AgentRepository).insert(name, prompt, 0, {"tools": ["rag", "memory"], **config})

        async def principal(role="user", agent=None, acting_as=None):
            from repositories.people import TokenRepository

            agent = agent or await make_agent(f"{role} agent")
            token = await container.get(TokenRepository).insert(f"{role} token", agent.id, role)
            return Principal(token, acting_as or agent)

        async def conversation(role="user", agent=None, user_id="u", acting_as=None):
            from domain.access import Conversation
            from services.users import ChatService, UserService

            p = await principal(role, agent, acting_as)
            user = await container.get(UserService).ensure(p.agent.id, user_id)
            chat = await container.get(ChatService).resolve(user, None)
            return Conversation(p, user, chat, p.agent.settings(container.settings.agent_defaults))

        yield SimpleNamespace(gateway=overrides.get(ModelGateway), conversation=conversation, container=container, get=container.get, agent=make_agent, principal=principal, auth=lambda: container.get(AuthService), controllers=lambda: controllers(container))
