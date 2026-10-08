"""What an agent remembers about a person: one implementation for the API and for the agent's own tools."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import logfire

from domain.memory import MAX_MEMORY_CHARS
from database.models import Memory
from domain.access import AccessPolicy, Conversation, Principal
from domain.errors import NotFound
from infrastructure.llm import Embedder
from repositories.agents import AgentRepository
from repositories.data import MemoryRepository
from repositories.people import UserRepository
from repositories.unit_of_work import UnitOfWork

# Cosine distance between embeddings (0: the same meaning), measured on text-embedding-3-small:
DUPLICATE_MAX_DISTANCE = 0.06
SIMILAR_MAX_DISTANCE = 0.25
RECALL_MAX_DISTANCE = 0.82

MEMORY_INSTRUCTIONS = (
    "You have a long-term memory about this user. Every message of the user starts "
    "with a <Memory> block that the system adds (the user did not write it): what "
    "you remember about them. Use it to personalise your answers, and answer "
    "questions about what you know of the user from it. Use the `remember` tool to "
    "save new, lasting facts the user tells you (name, preferences, circumstances), "
    "`recall` to search your memories by meaning when the block does not have what "
    "you need, and `forget` to delete outdated ones. Do not save trivia or things "
    "that only matter for this one message."
)


def format_memory_line(memory: Memory) -> str:
    return f"[{memory.id}] {memory.content}"


def format_memories(memories: Sequence[Memory], total: int) -> str:
    lines = [format_memory_line(memory) for memory in memories]
    hidden = total - len(memories)
    if hidden > 0:
        lines.append(f"({hidden} older memories are not shown, use the recall tool to search them)")
    return "\n".join(lines)


class MemoryService:
    def __init__(
        self,
        memories: MemoryRepository,
        users: UserRepository,
        agents: AgentRepository,
        embedder: Embedder,
        policy: AccessPolicy,
        uow: UnitOfWork,
    ):
        self.memories, self.users, self.agents = memories, users, agents
        self.embedder, self.policy, self.uow = embedder, policy, uow

    async def embed(self, text: str) -> Optional[List[float]]:
        """The embedding of a text, or None when the embedding service fails: memory still works then, only without meaning-based
        search for that memory."""
        try:
            return await self.embedder.embed(text)
        except Exception as exc:
            logfire.warning("Embedding a memory failed: {error}", error=str(exc)[:200])
            return None

    # -- the API --------------------------------------------------------------------------------------------------------------

    async def _scope(self, principal: Principal, external_id: str, agent_id: Optional[int]) -> Tuple[int, int]:
        agent_id = self.policy.agent_scope(principal, agent_id)  # first: what is not the token's to touch is not looked up
        user = await self.users.get(principal.agent.id, external_id)  # a user belongs to the agent in context, the memory to the agent asked for
        if not user:
            raise NotFound("User not found")
        if not await self.agents.get(agent_id):
            raise NotFound("Agent not found")
        return user.id, agent_id

    async def list(self, principal: Principal, external_id: str, agent_id: Optional[int], limit: int, query: Optional[str]) -> List[Memory]:
        scope = await self._scope(principal, external_id, agent_id)
        if query and query.strip():
            return await self.recall(scope, query, limit)
        return await self.memories.newest(*scope, limit=limit)

    async def create(self, principal: Principal, data) -> Memory:
        scope = await self._scope(principal, data.user_id, data.agent_id)
        return await self.memories.insert(*scope, data.content, await self.embed(data.content))

    async def get(self, principal: Principal, memory_id: int) -> Memory:
        memory = await self.memories.get(memory_id)
        if not memory:
            raise NotFound("Memory not found")
        self.policy.ensure_agent(principal, memory.agent_id)
        return memory

    async def _own(self, principal: Principal, memory_id: int) -> None:
        """A token may touch a memory only of an agent it may use (a missing one is left to the route's 404)."""
        memory = await self.memories.get(memory_id)
        if memory:
            self.policy.ensure_agent(principal, memory.agent_id)

    async def update(self, principal: Principal, memory_id: int, content: str) -> Memory:
        await self._own(principal, memory_id)
        memory = await self.memories.update(memory_id, content, await self.embed(content))
        if not memory:
            raise NotFound("Memory not found")
        return memory

    async def delete(self, principal: Principal, memory_id: int) -> Memory:
        await self._own(principal, memory_id)
        memory = await self.memories.delete(memory_id)
        if not memory:
            raise NotFound("Memory not found")
        return memory

    # -- search and saving ----------------------------------------------------------------------------------------------------

    async def recall(self, scope: Tuple[int, int], query: str, limit: int) -> List[Memory]:
        """What is remembered about `query`: by meaning first, then by the words it contains (which also finds memories that have no
        embedding yet). No query lists the newest memories."""
        if not query.strip():
            return list(await self.memories.newest(*scope, limit=limit))
        found: List[Memory] = []
        embedding = await self.embed(query)
        if embedding is not None:
            for memory, _ in await self.memories.nearest(*scope, embedding, limit, RECALL_MAX_DISTANCE):
                found.append(memory)
        seen = {memory.id for memory in found}
        for memory in await self.memories.newest(*scope, limit=limit, query=query):
            if memory.id not in seen:
                found.append(memory)
        return found[:limit]

    async def _find_existing(self, scope: Tuple[int, int], fact: str, embedding: Optional[List[float]]) -> Optional[Memory]:
        """The memory that already says this: the same words, or the same meaning."""
        for memory in await self.memories.newest(*scope, limit=50, query=fact):
            if memory.content.strip().lower() == fact.lower():
                return memory
        if embedding is not None:
            near = await self.memories.nearest(*scope, embedding, 1, DUPLICATE_MAX_DISTANCE)
            if near:
                return near[0][0]
        return None

    async def save(self, scope: Tuple[int, int], fact: str) -> Tuple[Memory, bool, List[Memory]]:
        """Remember a fact unless it is remembered already. Returns (the memory, whether it is new, similar memories that were there before)."""
        embedding = await self.embed(fact)  # (a call to the embedding service: outside the transaction)
        # Looking and saving is one step, one at a time per user and agent: two requests that learn the same fact together must not both save it.
        async with self.uow.transaction():
            await self.uow.lock(f"memories:{scope[0]}:{scope[1]}")
            existing = await self._find_existing(scope, fact, embedding)
            if existing is not None:
                return existing, False, []
            similar: List[Memory] = []
            if embedding is not None:
                similar = [memory for memory, _ in await self.memories.nearest(*scope, embedding, 3, SIMILAR_MAX_DISTANCE)]
            return await self.memories.insert(*scope, fact, embedding), True, similar

    async def backfill(self, batch: int = 100) -> int:
        """Give the memories made before embeddings existed one. Stops at the first failure (the embedding service may be down) and
        returns how many were done."""
        done = 0
        while True:
            memories = await self.memories.without_embedding(batch)
            if not memories:
                return done
            for memory in memories:
                embedding = await self.embed(memory.content)
                if embedding is None:
                    return done
                await self.memories.set_embedding(memory.id, embedding)
                done += 1

    # -- what an agent does with its memory -----------------------------------------------------------------------------------

    @staticmethod
    def _scope_of(conversation: Conversation) -> Tuple[int, int]:
        return conversation.user.id, conversation.agent.id

    async def block(self, conversation: Conversation) -> str:
        """The <Memory> block that goes in front of the user's message: the newest memories about the user (at most the agent's
        memo_limit). It is data that changes with every request, so it is part of the user prompt; the system prompt stays the same."""
        scope = self._scope_of(conversation)
        memories = await self.memories.newest(*scope, limit=conversation.settings.memo_limit)
        if not memories:
            return "<Memory>\nNothing is remembered about this user yet.\n</Memory>"
        total = await self.memories.count(*scope)
        return f"<Memory>\nWhat you remember about this user (newest first, id in brackets):\n{format_memories(memories, total)}\n</Memory>"

    async def remember(self, conversation: Conversation, fact: str) -> str:
        fact = fact.strip()
        if not fact or len(fact) > MAX_MEMORY_CHARS:
            return f"Not saved: a fact must be 1-{MAX_MEMORY_CHARS} characters long."
        memory, is_new, similar = await self.save(self._scope_of(conversation), fact)
        if not is_new:
            return f"Already remembered as memory [{memory.id}]: {memory.content}"
        reply = f"Saved as memory [{memory.id}]."
        if similar:
            reply += (
                " Similar memories exist; if this replaces one of them, delete the outdated one with `forget`:\n"
                + "\n".join(format_memory_line(m) for m in similar)
            )
        return reply

    async def recall_text(self, conversation: Conversation, query: str) -> str:
        memories = await self.recall(self._scope_of(conversation), query, conversation.settings.memo_limit)
        return "\n".join(format_memory_line(memory) for memory in memories) if memories else "No matching memories."

    async def forget(self, conversation: Conversation, memory_id: int) -> str:
        deleted = await self.memories.delete(memory_id, *self._scope_of(conversation))
        return f"Forgot memory [{memory_id}]." if deleted else "No such memory."
