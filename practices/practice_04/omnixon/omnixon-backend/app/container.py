"""The composition root: the one place that knows which class is made from which (GRASP Creator).

Everything else is given what it needs. A test builds a container with `overrides` to put a fake where a real thing would be made."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Type, TypeVar, Union

from config import Settings

T = TypeVar("T")
Closer = Callable[[], Union[None, Awaitable[None]]]


class Container:
    def __init__(
        self,
        settings: Settings,
        *,
        factories: Optional[Mapping[type, Callable[[], Any]]] = None,
        overrides: Optional[Mapping[type, Any]] = None,
    ) -> None:
        self.settings = settings
        self._factories: Dict[type, Callable[[], Any]] = dict(factories or {})
        self._overrides: Dict[type, Any] = dict(overrides or {})
        self._instances: Dict[type, Any] = {}
        self._closers: List[Closer] = []

    def register(self, cls: Type[T], factory: Callable[[], T]) -> None:
        self._factories[cls] = factory

    def get(self, cls: Type[T]) -> T:
        if cls in self._overrides:
            return self._overrides[cls]
        if cls not in self._instances:
            self._instances[cls] = self._factories[cls]()
        return self._instances[cls]

    def on_close(self, closer: Closer) -> None:
        """Something to undo at shutdown; closers run in the reverse order of their registration."""
        self._closers.append(closer)

    async def aclose(self) -> None:
        closers, self._closers = self._closers[::-1], []
        for closer in closers:
            result = closer()
            if inspect.isawaitable(result):
                await result


def wire_data_layer(container: Container) -> None:
    """What stands on the database: the repositories, the access policy and authentication. (The services are added below as they are built.)"""
    from domain.access import AccessPolicy
    from repositories.agents import AgentRepository
    from repositories.connections import ConnectionRepository
    from repositories.data import KnowledgeRepository, MemoryRepository, UsageRepository
    from repositories.database import Database
    from repositories.models import McpServerRepository, ModelRepository
    from repositories.people import ChatRepository, MessageRepository, TokenRepository, UserRepository
    from repositories.unit_of_work import UnitOfWork
    from repositories.versions import VersionRepository
    from services.auth import AuthService

    settings = container.settings
    container.register(Database, Database)
    container.register(UnitOfWork, lambda: UnitOfWork(container.get(Database)))
    container.register(AccessPolicy, AccessPolicy)
    container.register(TokenRepository, lambda: TokenRepository(container.get(Database), settings.initial_api_key))
    for repository in (AgentRepository, VersionRepository, UserRepository, ModelRepository, McpServerRepository, ConnectionRepository, MemoryRepository, KnowledgeRepository, UsageRepository):
        container.register(repository, lambda r=repository: r(container.get(Database)))
    container.register(ChatRepository, lambda: ChatRepository(container.get(Database), settings.message_ttl_days))
    container.register(MessageRepository, lambda: MessageRepository(container.get(Database), settings.message_ttl_days))
    container.register(
        AuthService,
        lambda: AuthService(container.get(TokenRepository), container.get(AgentRepository), container.get(ConnectionRepository), container.get(AccessPolicy)),
    )


def wire_services(container: Container) -> None:
    """The use cases, and the controllers that put them on HTTP."""
    from ai.factory import (
        AgentCallsProvider, AgentFactory, KnowledgeProvider, McpProvider, MemoryProvider, ParallelCallsProvider, ToolFailuresProvider,
    )
    from ai.interrupts import InterruptRegistry
    from ai.memory_extractor import MemoryExtractor
    from ai.prompts import PromptBuilder
    from ai.runner import AgentRunner
    from ai.usage import UsageMeter
    from api.controllers.conversations import ConversationController
    from infrastructure.jobs import TaskSupervisor
    from infrastructure.mcp_health import McpHealth, RedisHealthStore
    from infrastructure.redis import LocalStopBus, RedisStopBus, StopBus
    from repositories.database import Database
    from api.controllers.agents import AgentController, ConnectionController, VersionController
    from api.controllers.mcp_servers import McpServerController
    from api.controllers.data import KnowledgeController, MemoryController, UsageController
    from api.controllers.health import HealthController, RootController
    from api.controllers.models import ModelController
    from api.controllers.people import ChatController, UserController
    from api.controllers.tokens import SelfController, TokenController
    from infrastructure.llm import Embedder, ModelGateway
    from repositories.data import KnowledgeRepository, MemoryRepository, UsageRepository
    from services.knowledge import KnowledgeService
    from services.memories import MemoryService
    from services.usage import UsageService
    from repositories.people import ChatRepository, MessageRepository, UserRepository
    from services.users import ChatService, UserService
    from domain.access import AccessPolicy
    from repositories.connections import ConnectionRepository
    from services.agents import AgentService
    from services.connections import ConnectionService
    from services.versions import VersionService
    from services.tokens import TokenService
    from repositories.people import TokenRepository
    from repositories.models import McpServerRepository
    from services.mcp_servers import McpServerService
    from repositories.agents import AgentRepository
    from repositories.models import ModelRepository
    from repositories.unit_of_work import UnitOfWork
    from repositories.versions import VersionRepository
    from services.conversations import ConversationService
    from services.models import ModelService
    from services.versions import VersionRecorder

    get = container.get
    container.register(VersionRecorder, lambda: VersionRecorder(get(VersionRepository), get(UnitOfWork)))
    container.register(ModelService, lambda: ModelService(get(ModelRepository), get(AgentRepository), get(VersionRecorder), get(UnitOfWork)))
    container.register(ModelController, lambda: ModelController(get(ModelService)))
    container.register(
        McpServerService,
        lambda: McpServerService(get(McpServerRepository), get(AgentRepository), get(VersionRecorder), get(AccessPolicy), get(UnitOfWork)),
    )
    container.register(McpServerController, lambda: McpServerController(get(McpServerService)))
    container.register(
        TokenService, lambda: TokenService(get(TokenRepository), get(AgentRepository), get(VersionRecorder), get(AccessPolicy), get(UnitOfWork))
    )
    container.register(TokenController, lambda: TokenController(get(TokenService)))
    container.register(SelfController, lambda: SelfController(get(TokenService)))
    container.register(
        AgentService,
        lambda: AgentService(
            get(AgentRepository), get(VersionRepository), get(McpServerRepository), get(ConnectionRepository), get(VersionRecorder),
            get(AccessPolicy), get(UnitOfWork), container.settings.agent_defaults,
        ),
    )
    container.register(AgentController, lambda: AgentController(get(AgentService)))
    container.register(
        VersionService,
        lambda: VersionService(
            get(VersionRepository), get(AgentRepository), get(ModelRepository), get(McpServerRepository), get(ConnectionRepository),
            get(VersionRecorder), get(AccessPolicy), get(UnitOfWork),
        ),
    )
    container.register(VersionController, lambda: VersionController(get(VersionService)))
    container.register(
        ConnectionService, lambda: ConnectionService(get(ConnectionRepository), get(AgentRepository), get(VersionRecorder), get(UnitOfWork))
    )
    container.register(ConnectionController, lambda: ConnectionController(get(ConnectionService)))
    container.register(UserService, lambda: UserService(get(UserRepository), container.settings.message_ttl_days))
    container.register(
        ChatService, lambda: ChatService(get(UserService), get(ChatRepository), get(MessageRepository), container.settings.agent_defaults)
    )
    container.register(UserController, lambda: UserController(get(UserService)))
    container.register(ChatController, lambda: ChatController(get(ChatService)))
    container.register(ModelGateway, lambda: ModelGateway(container.settings))
    container.register(Embedder, lambda: get(ModelGateway).embedder())
    container.register(
        MemoryService,
        lambda: MemoryService(get(MemoryRepository), get(UserRepository), get(AgentRepository), get(Embedder), get(AccessPolicy), get(UnitOfWork)),
    )
    container.register(KnowledgeService, lambda: KnowledgeService(get(KnowledgeRepository), get(Embedder), get(AccessPolicy)))
    container.register(UsageService, lambda: UsageService(get(UsageRepository), get(AccessPolicy)))
    container.register(MemoryController, lambda: MemoryController(get(MemoryService)))
    container.register(KnowledgeController, lambda: KnowledgeController(get(KnowledgeService)))
    container.register(UsageController, lambda: UsageController(get(UsageService)))
    container.register(HealthController, lambda: HealthController(get(Database)))
    container.register(RootController, RootController)

    # -- running agents ------------------------------------------------------------------------------------------------------
    settings = container.settings
    container.register(StopBus, lambda: RedisStopBus.from_url(settings.redis_url) if settings.redis_url else LocalStopBus())
    container.register(InterruptRegistry, lambda: InterruptRegistry(get(StopBus)))
    container.register(
        McpHealth,
        lambda: McpHealth(settings.mcp_down_seconds, shared=RedisHealthStore(get(StopBus).client) if settings.redis_url else None),
    )
    container.register(TaskSupervisor, TaskSupervisor)
    container.register(UsageMeter, lambda: UsageMeter(get(UsageRepository)))
    container.register(PromptBuilder, lambda: PromptBuilder(get(MessageRepository), get(MemoryService)))
    container.register(
        AgentFactory,
        lambda: AgentFactory(
            get(ModelGateway),
            [
                ToolFailuresProvider(),
                KnowledgeProvider(),
                MemoryProvider(),
                AgentCallsProvider(get(ConnectionService), lambda: get(ConversationService)),  # (made after the factory: asked for when needed)
                McpProvider(get(McpServerRepository), get(McpHealth), settings.mcp_tool_attempts, settings.mcp_tool_retry_delay, settings.mcp_tool_retries),
                ParallelCallsProvider(),
            ],
        ),
    )
    container.register(
        AgentRunner,
        lambda: AgentRunner(get(AgentFactory), get(PromptBuilder), get(UsageMeter), get(MemoryService), get(KnowledgeService), settings.request_timeout_seconds),
    )
    container.register(MemoryExtractor, lambda: MemoryExtractor(get(ModelGateway), get(MemoryService), get(UsageMeter), get(TaskSupervisor)))
    container.register(
        ConversationService,
        lambda: ConversationService(
            get(UserService), get(ChatService), get(ChatRepository), get(MessageRepository), get(AgentRepository), get(ModelRepository),
            get(AgentRunner), get(InterruptRegistry), get(MemoryExtractor), get(ConnectionService), get(AccessPolicy), get(UnitOfWork),
            settings.agent_defaults, settings.agent_call_depth,
        ),
    )
    container.register(ConversationController, lambda: ConversationController(get(ConversationService)))


def controllers(container: Container) -> list:
    """Every controller, in the order their routes are registered (a fixed path before a path with a parameter)."""
    from api.controllers.agents import AgentController, ConnectionController, VersionController
    from api.controllers.mcp_servers import McpServerController
    from api.controllers.conversations import ConversationController
    from api.controllers.data import KnowledgeController, MemoryController, UsageController
    from api.controllers.health import HealthController, RootController
    from api.controllers.models import ModelController
    from api.controllers.people import ChatController, UserController
    from api.controllers.tokens import SelfController, TokenController

    return [
        container.get(c)
        for c in (
            AgentController, VersionController, ConnectionController, ModelController, McpServerController, TokenController, SelfController,
            UserController, ChatController, MemoryController, KnowledgeController, UsageController, HealthController, RootController, ConversationController,
        )
    ]
