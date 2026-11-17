from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domain.access import Conversation

if TYPE_CHECKING:
    from services.knowledge import KnowledgeService
    from services.memories import MemoryService


@dataclass
class RunDeps:
    """What the tools of an agent are given: the conversation they run in, and the services they use (never SQL)."""

    conversation: Conversation
    memory: "MemoryService"
    knowledge: "KnowledgeService"
