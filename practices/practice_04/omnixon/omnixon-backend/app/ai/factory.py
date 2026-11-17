"""Making the pydantic-ai agent of a conversation: its model, its prompt as the instructions, and what it can do.

What it can do is decided by the capability providers (Strategy): each looks at the conversation and gives its capability, or nothing. A new
capability is a new provider handed to the factory; the factory does not change."""

from __future__ import annotations

from typing import Callable, List, Optional, Protocol, Sequence

from pydantic_ai import Agent
from pydantic_ai.capabilities import AbstractCapability

from domain.tools import TOOL_MEMORY, TOOL_RAG
from domain.entities import Model
from domain.access import Conversation
from infrastructure.llm import ModelGateway
from infrastructure.mcp_health import McpHealth
from repositories.models import McpServerRepository
from services.connections import ConnectionService
from .capabilities import AgentAsker, AgentCalls, KnowledgeBase, McpServers, Memory, ParallelCalls, ToolFailures
from .deps import RunDeps


class CapabilityProvider(Protocol):
    async def provide(self, conversation: Conversation, built: Sequence[AbstractCapability]) -> Optional[AbstractCapability]:
        """The capability this conversation's agent has, or None. `built` are the ones the providers before this one gave."""


class ToolFailuresProvider:
    async def provide(self, conversation, built):
        return ToolFailures()  # first: what the others raise, it turns into a failed result


class KnowledgeProvider:
    async def provide(self, conversation, built):
        return KnowledgeBase() if TOOL_RAG in conversation.settings.tools else None


class MemoryProvider:
    async def provide(self, conversation, built):
        return Memory() if TOOL_MEMORY in conversation.settings.tools else None


class AgentCallsProvider:
    """The built-in tools of an agent that has outgoing connections, whatever `config.tools` says. The asker is given as a getter: whoever
    runs agents is made after the factory."""

    def __init__(self, connections: ConnectionService, asker: Callable[[], AgentAsker]):
        self.connections, self.asker = connections, asker

    async def provide(self, conversation, built):
        connected = await self.connections.connected_agents(conversation.agent.id)
        return AgentCalls(agents=connected, asker=self.asker()) if connected else None


class McpProvider:
    def __init__(self, servers: McpServerRepository, health: McpHealth, attempts: int, retry_delay: float, tool_retries: int):
        self.servers, self.health = servers, health
        self.attempts, self.retry_delay, self.tool_retries = attempts, retry_delay, tool_retries

    async def provide(self, conversation, built):
        servers = await self.servers.of_agent(conversation.agent.id)
        if not servers:
            return None
        return McpServers(
            servers=[(server.name, server.config) for server in servers],
            health=self.health,
            attempts=self.attempts,
            retry_delay=self.retry_delay,
            tool_retries=self.tool_retries,
        )


class ParallelCallsProvider:
    """Last: tells the model it may call independent tools together, if there are tools to call."""

    async def provide(self, conversation, built):
        return ParallelCalls() if conversation.settings.parallel_tool_calls and len(built) > 1 else None


class AgentFactory:
    def __init__(self, gateway: ModelGateway, providers: Sequence[CapabilityProvider]):
        self.gateway, self.providers = gateway, list(providers)

    async def capabilities(self, conversation: Conversation) -> List[AbstractCapability]:
        built: List[AbstractCapability] = []
        for provider in self.providers:
            capability = await provider.provide(conversation, built)
            if capability is not None:
                built.append(capability)
        return built

    async def build(self, conversation: Conversation, model: Model) -> Agent:
        """An agent with an empty prompt has no instructions of its own (an empty system message is refused by some providers)."""
        prompt = conversation.agent.prompt.strip()
        return Agent(
            self.gateway.chat_model(model.request_json, **model.connection),
            deps_type=RunDeps,
            instructions=prompt or None,
            capabilities=await self.capabilities(conversation),
            # sent only when it is off (an OpenAI-compatible server may not know it); a model's own `parallel_tool_calls` still wins
            model_settings=None if conversation.settings.parallel_tool_calls else {"parallel_tool_calls": False},
            retries={"tools": 2},
        )
