"""What the model is given besides the agent's own prompt: the history of the chat, the memories about the person, the new message and its files."""

from __future__ import annotations

from typing import List, Sequence

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from domain.tools import TOOL_MEMORY
from domain.access import Conversation
from repositories.people import MessageRepository
from services.memories import MemoryService
from .attachments import Attachment, contents_of
from .attachments import describe as describe_attachments


class PromptBuilder:
    def __init__(self, messages: MessageRepository, memory: MemoryService):
        self.messages, self.memory = messages, memory

    async def history(self, conversation: Conversation, use_memo: bool = True) -> Sequence[ModelMessage]:
        """The stored messages of the chat as what the model is given before the new one. (The agent's prompt is not among them: it is the
        agent's `instructions`.)"""
        raw = await self.messages.window_of(conversation.chat.id, conversation.settings.message_limit) if use_memo else []
        # The window of the latest N messages can begin with an answer whose question fell out of it; a conversation must begin with the user.
        while raw and raw[0].content.get("type") != "user":
            raw = raw[1:]
        history: List[ModelMessage] = []
        for message in raw:
            kind, content = message.content["type"], message.content["content"]
            if kind == "user":
                notes = message.content.get("attachments")
                if notes:  # the file itself is not kept, only the fact that it was there
                    content = f"{content}\n{describe_attachments(notes)}".strip()
                history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
            elif kind == "assistant":
                history.append(ModelResponse(parts=[TextPart(content=content)]))
        return history

    async def memory_block(self, conversation: Conversation) -> str:
        """What the model knows about the user, to be put in front of their message (when the agent has the memory tool)."""
        if TOOL_MEMORY in conversation.settings.tools:
            return await self.memory.block(conversation)
        return ""

    @staticmethod
    def prompt(text: str, attachments: Sequence[Attachment], memory_block: str = ""):
        """What the model is asked: the memories about the user, the text, then the files. (Only the user's own text is stored in the history,
        not the memory block.)"""
        asked = f"{memory_block}\n\n{text}" if memory_block else text
        return [asked, *contents_of(attachments)] if attachments else asked

    @staticmethod
    def stored(attachments: Sequence[Attachment]) -> dict:
        """What is kept of the files with the user's message: a note of each, never the data or the url."""
        return {"attachments": [a.note() for a in attachments]} if attachments else {}
