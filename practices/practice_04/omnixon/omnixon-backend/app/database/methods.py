from typing import Optional

from core import async_logfire_class_decorator
from .mixins import (
    AgentMethods,
    AgentVersionMethods,
    TokenMethods,
    UserMethods,
    MessageMethods,
    ChatMethods,
    RAGMethods,
    ModelMethods,
    MCPServerMethods,
    AgentConnectionMethods,
    MemoryMethods,
    UsageMethods,
)


@async_logfire_class_decorator
class PostgresDB(
    AgentMethods,
    AgentVersionMethods,
    TokenMethods,
    UserMethods,
    MessageMethods,
    ChatMethods,
    RAGMethods,
    ModelMethods,
    MCPServerMethods,
    AgentConnectionMethods,
    MemoryMethods,
    UsageMethods,
):
    async def insure_user(self, user_id: int) -> bool:
        self.context.user = await self.get_user(user_id)

        if self.context.user is None:
            self.context.user = await self.create_user(user_id)
            if self.context.user is None:  # another task made it first (two tools of one turn asking the same agent)
                self.context.user = await self.get_user(user_id)

        return True
