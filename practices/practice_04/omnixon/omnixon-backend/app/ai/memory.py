import asyncio
from typing import List, Optional, Sequence, Set, Tuple

import asyncpg
import logfire
from core import TOOL_MEMORY
from pydantic_ai import Agent, RunContext
from pydantic_ai.toolsets import FunctionToolset

from core import metrics
from database import Memory, PostgresDB
from .deps import Dependencies
from .usage import track_usage
from .utils import generate_model, get_embedding_vector

MAX_MEMORY_CHARS = 2000

# Cosine distance between embeddings (0: the same meaning), measured on
# text-embedding-3-small:

DUPLICATE_MAX_DISTANCE = 0.06
SIMILAR_MAX_DISTANCE = 0.25
RECALL_MAX_DISTANCE = 0.82

# What the model may add to the memory after one exchange (auto_memory)
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


def format_memory_line(memory: Memory) -> str:
    return f"[{memory.id}] {memory.content}"


def format_memories(memories: Sequence[Memory], total: int) -> str:
    lines = [format_memory_line(memory) for memory in memories]
    hidden = total - len(memories)
    if hidden > 0:
        lines.append(
            f"({hidden} older memories are not shown, use the recall tool to search them)"
        )
    return "\n".join(lines)


def _scope(db: PostgresDB) -> Optional[tuple]:
    """(user_id, agent_id) of the current request, if there is one."""
    if db.context.user is None or db.context.agent is None:
        return None
    return db.context.user.id, db.context.agent.id


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


async def build_memory_block(db: PostgresDB) -> str:
    """The <Memory> block that goes in front of the user's message: the newest memories
    about the user (at most the agent's memo_limit). It is data that changes with every
    request, so it is part of the user prompt; the system prompt (MEMORY_INSTRUCTIONS)
    stays the same. Empty when there is no user or agent."""
    scope = _scope(db)
    if scope is None:
        return ""

    memories = await db.get_memories(*scope, limit=db.context.agent.memo_limit)
    if not memories:
        return "<Memory>\nNothing is remembered about this user yet.\n</Memory>"

    total = await db.count_memories(*scope)
    return (
        "<Memory>\nWhat you remember about this user (newest first, id in brackets):\n"
        f"{format_memories(memories, total)}\n</Memory>"
    )


async def embed(text: str) -> Optional[List[float]]:
    """The embedding of a text, or None when the embedding service fails: memory still
    works then, only without meaning-based search for that memory."""
    try:
        return await get_embedding_vector(text)
    except Exception as exc:
        logfire.warning("Embedding a memory failed: {error}", error=str(exc)[:200])
        return None


async def find_existing(
    db: PostgresDB, scope: tuple, fact: str, embedding: Optional[List[float]]
) -> Optional[Memory]:
    """The memory that already says this: the same words, or the same meaning."""
    for memory in await db.get_memories(*scope, limit=50, query=fact):
        if memory.content.strip().lower() == fact.lower():
            return memory
    if embedding is not None:
        near = await db.search_memories(*scope, embedding, 1, DUPLICATE_MAX_DISTANCE)
        if near:
            return near[0][0]
    return None


async def save_memory(
    db: PostgresDB, scope: tuple, fact: str
) -> Tuple[Memory, bool, List[Memory]]:
    """Remember a fact unless it is remembered already.

    Returns (the memory, whether it is new, similar memories that were there before)."""
    embedding = await embed(
        fact
    )  # (a call to the embedding service: outside the transaction)

    # Looking and saving is one step, one at a time per user and agent: two requests
    # that learn the same fact together must not both save it.
    async with db.transaction():
        await db.lock(f"memories:{scope[0]}:{scope[1]}")
        existing = await find_existing(db, scope, fact, embedding)
        if existing is not None:
            return existing, False, []

        similar: List[Memory] = []
        if embedding is not None:
            near = await db.search_memories(*scope, embedding, 3, SIMILAR_MAX_DISTANCE)
            similar = [memory for memory, _ in near]
        return await db.create_memory(*scope, fact, embedding), True, similar


async def recall_memories(
    db: PostgresDB, scope: tuple, query: str, limit: int
) -> List[Memory]:
    """What is remembered about `query`: by meaning first, then by the words it
    contains (which also finds memories that have no embedding yet). No query lists the
    newest memories."""
    if not query.strip():
        return list(await db.get_memories(*scope, limit=limit))

    found: List[Memory] = []
    embedding = await embed(query)
    if embedding is not None:
        for memory, _ in await db.search_memories(
            *scope, embedding, limit, RECALL_MAX_DISTANCE
        ):
            found.append(memory)
    seen = {memory.id for memory in found}
    for memory in await db.get_memories(*scope, limit=limit, query=query):
        if memory.id not in seen:
            found.append(memory)
    return found[:limit]


def wants_auto_memory(db: PostgresDB) -> bool:
    agent = db.context.agent
    return bool(
        agent and agent.auto_memory and TOOL_MEMORY in agent.tools and db.context.user
    )


async def extract_memories(
    db: PostgresDB, scope: tuple, model, user_text: str, answer: str
) -> List[Memory]:
    """Ask the model what is worth remembering about the user after this exchange
    and remember it. Returns the memories that were created."""
    known = await db.get_memories(*scope, limit=db.context.agent.memo_limit)
    known_text = "\n".join(f"- {memory.content}" for memory in known) or "(nothing yet)"
    prompt = (
        f"Already known about the user:\n{known_text}\n\n"
        f"The user said:\n{user_text}\n\nThe assistant answered:\n{answer}"
    )

    extractor = Agent(
        model, output_type=List[str], instructions=EXTRACTION_INSTRUCTIONS
    )
    async with track_usage(
        db, "auto_memory", str(getattr(model, "model_name", "?"))
    ) as usage:
        async with asyncio.timeout(EXTRACTION_TIMEOUT_SECONDS):
            result = await extractor.run(prompt)
        usage.add(result.new_messages())

    created = []
    for fact in result.output[:MAX_FACTS_PER_EXCHANGE]:
        fact = fact.strip()
        if not fact or len(fact) > MAX_MEMORY_CHARS:
            continue
        memory, is_new, _ = await save_memory(db, scope, fact)
        if is_new:
            created.append(memory)
    metrics.MEMORIES_EXTRACTED.inc(len(created))
    return created


_background: Set[asyncio.Task] = set()  # tasks must be referenced, or they may vanish


def schedule_extraction(
    db: PostgresDB,
    request_json: dict,
    user_text: str,
    answer: str,
    connection: Optional[dict] = None,
) -> None:
    """After an exchange: if the agent has auto_memory, learn from it in the background
    (the user is not kept waiting, and a failure only costs the extraction)."""
    if not wants_auto_memory(db):
        return
    scope = _scope(db)

    async def work() -> None:
        try:
            created = await extract_memories(
                db,
                scope,
                generate_model(request_json, **(connection or {})),
                user_text,
                answer,
            )
            if created:
                logfire.info(
                    "Remembered {count} new facts from the exchange", count=len(created)
                )
        except asyncpg.ForeignKeyViolationError:
            logfire.debug(
                "The user or agent was deleted before its memories were saved"
            )
        except Exception as exc:
            logfire.warning(
                "Extracting memories failed: {error}",
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
                _exc_info=exc,
            )

    task = asyncio.create_task(work())
    _background.add(task)
    task.add_done_callback(_background.discard)


async def backfill_embeddings(db: PostgresDB, batch: int = 100) -> int:
    """Give the memories made before embeddings existed one. Stops at the first
    failure (the embedding service may be down) and returns how many were done."""
    done = 0
    while True:
        memories = await db.memories_without_embedding(batch)
        if not memories:
            return done
        for memory in memories:
            embedding = await embed(memory.content)
            if embedding is None:
                return done
            await db.set_memory_embedding(memory.id, embedding)
            done += 1


async def run_backfill(db: PostgresDB) -> None:
    """backfill_embeddings for the start of the service: it must never fail it. Of several replicas that start together one does it."""
    try:
        async with db.foundation.pool.acquire() as connection:
            if not await connection.fetchval("SELECT pg_try_advisory_lock(7411001)"):
                return  # another replica is at it
            try:
                done = await backfill_embeddings(db)
            finally:
                await connection.execute("SELECT pg_advisory_unlock(7411001)")
        if done:
            logfire.info("Added embeddings to {count} memories", count=done)
    except asyncio.CancelledError:
        raise
    except Exception:
        logfire.exception("Adding embeddings to old memories failed")


memory_tools = FunctionToolset[Dependencies]()  # remember / recall / forget; given to an agent by capabilities.Memory


@memory_tools.tool
async def remember(context: RunContext[Dependencies], fact: str) -> str:
    """Save a lasting fact about the user so it can be recalled in later conversations.

    Args:
        context: The call context.
        fact: One short, self-contained fact, e.g. "Prefers answers in Russian".
    """
    db = context.deps.db
    scope = _scope(db)
    fact = fact.strip()
    if scope is None:
        return "Memory is not available."
    if not fact or len(fact) > MAX_MEMORY_CHARS:
        return f"Not saved: a fact must be 1-{MAX_MEMORY_CHARS} characters long."

    memory, is_new, similar = await save_memory(db, scope, fact)
    if not is_new:
        return f"Already remembered as memory [{memory.id}]: {memory.content}"
    reply = f"Saved as memory [{memory.id}]."
    if similar:
        reply += (
            " Similar memories exist; if this replaces one of them, delete the "
            "outdated one with `forget`:\n"
            + "\n".join(format_memory_line(m) for m in similar)
        )
    return reply

@memory_tools.tool
async def recall(context: RunContext[Dependencies], query: str = "") -> str:
    """Search the memories saved about the user, by meaning.

    Args:
        context: The call context.
        query: What to look for, in a few words. Leave empty to list the newest memories.
    """
    db = context.deps.db
    scope = _scope(db)
    if scope is None:
        return "Memory is not available."

    memories = await recall_memories(db, scope, query, db.context.agent.memo_limit)
    if not memories:
        return "No matching memories."
    return "\n".join(format_memory_line(memory) for memory in memories)

@memory_tools.tool
async def forget(context: RunContext[Dependencies], memory_id: int) -> str:
    """Delete a memory that is outdated or wrong.

    Args:
        context: The call context.
        memory_id: The id shown in brackets next to the memory.
    """
    db = context.deps.db
    scope = _scope(db)
    if scope is None:
        return "Memory is not available."

    deleted = await db.delete_memory(memory_id, *scope)
    return f"Forgot memory [{memory_id}]." if deleted else "No such memory."
