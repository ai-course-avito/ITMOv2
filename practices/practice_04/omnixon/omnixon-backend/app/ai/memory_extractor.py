"""auto_memory: after an exchange that was saved, ask the model what is worth remembering about the person, in the background."""

from __future__ import annotations

import asyncio
from typing import List

import asyncpg
import logfire
from pydantic_ai import Agent

from core import metrics
from core.tools import TOOL_MEMORY
from database.models import Memory, Model
from domain.access import Conversation
from domain.memory import MAX_MEMORY_CHARS
from infrastructure.jobs import TaskSupervisor
from infrastructure.llm import ModelGateway
from services.memories import MemoryService
from .usage import UsageMeter

# What the model may add to the memory after one exchange
MAX_FACTS_PER_EXCHANGE = 5
EXTRACTION_TIMEOUT_SECONDS = 120

EXTRACTION_INSTRUCTIONS = (
    "You keep the long-term memory about a user. From the exchange below, list the NEW "
    "lasting facts about the user that will be useful in future conversations: name, "
    "preferences, circumstances, plans, relationships, how they want to be answered. "
    "Leave out what is already known, trivia that only matters for this message, "
    "guesses, and anything about the assistant. Write every fact as one short sentence "
    "about the user, in the language of the conversation. Return an empty list when "
    "there is nothing new."
)


class MemoryExtractor:
    def __init__(self, gateway: ModelGateway, memory: MemoryService, meter: UsageMeter, supervisor: TaskSupervisor, timeout: float = EXTRACTION_TIMEOUT_SECONDS):
        self.gateway, self.memory, self.meter, self.supervisor, self.timeout = gateway, memory, meter, supervisor, timeout

    @staticmethod
    def wanted(conversation: Conversation) -> bool:
        return conversation.settings.auto_memory and TOOL_MEMORY in conversation.settings.tools

    def schedule(self, conversation: Conversation, model: Model, user_text: str, answer: str) -> None:
        """After an exchange: if the agent has auto_memory, learn from it in the background (the user is not kept waiting, and a failure only
        costs the extraction)."""
        if not self.wanted(conversation):
            return
        self.supervisor.spawn(self._learn(conversation, model, user_text, answer), "auto_memory")

    async def _learn(self, conversation: Conversation, model: Model, user_text: str, answer: str) -> None:
        try:
            created = await self.extract(conversation, model, user_text, answer)
            if created:
                logfire.info("Remembered {count} new facts from the exchange", count=len(created))
        except asyncpg.ForeignKeyViolationError:
            logfire.debug("The user or agent was deleted before its memories were saved")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logfire.warning(
                "Extracting memories failed: {error}", error=f"{type(exc).__name__}: {str(exc)[:300]}", _exc_info=exc
            )

    async def extract(self, conversation: Conversation, model: Model, user_text: str, answer: str) -> List[Memory]:
        """Ask the model what is worth remembering about the user after this exchange and remember it; the memories that were created."""
        scope = (conversation.user.id, conversation.agent.id)
        known = await self.memory.memories.newest(*scope, limit=conversation.settings.memo_limit)
        known_text = "\n".join(f"- {memory.content}" for memory in known) or "(nothing yet)"
        prompt = f"Already known about the user:\n{known_text}\n\nThe user said:\n{user_text}\n\nThe assistant answered:\n{answer}"
        chat_model = self.gateway.chat_model(model.request_json, **model.connection)
        extractor = Agent(chat_model, output_type=List[str], instructions=EXTRACTION_INSTRUCTIONS)
        async with self.meter.track(conversation.principal, "auto_memory", str(getattr(chat_model, "model_name", "?"))) as usage:
            async with asyncio.timeout(self.timeout):
                result = await extractor.run(prompt)
            usage.add(result.new_messages())

        created = []
        for fact in result.output[:MAX_FACTS_PER_EXCHANGE]:
            fact = fact.strip()
            if not fact or len(fact) > MAX_MEMORY_CHARS:
                continue
            memory, is_new, _ = await self.memory.save(scope, fact)
            if is_new:
                created.append(memory)
        metrics.MEMORIES_EXTRACTED.inc(len(created))
        return created
