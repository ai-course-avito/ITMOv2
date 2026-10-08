"""A run that fails and is tried again goes on from where it broke instead of starting over.

pydantic-ai keeps the messages of a run (the question, the answers of the model, the results of the tools). When a provider fails, the messages
that are complete are kept here and the next attempt starts from them: the tools that already returned are not called again, and only the step
that broke is asked of the model again. What is complete: everything up to the last request to the model (a request holds the question or the
results of the tools; a response of the model that is the last message has tool calls whose results never came, so it is dropped).
"""

from typing import Any, List, Optional, Sequence

from pydantic_ai.messages import ModelMessage, ModelRequest


class Progress:
    def __init__(self, history: Sequence[ModelMessage]):
        self.history = list(history)  # what the run was given: not part of its work
        self.kept: List[
            ModelMessage
        ] = []  # the complete messages of the attempts that failed

    def message_history(self) -> List[ModelMessage]:
        return self.history + self.kept

    def prompt(self, user_prompt: Any) -> Optional[Any]:
        """The question goes in once: after a failure it is already in the kept messages."""
        return None if self.kept else user_prompt

    def remember(self, run) -> None:
        """Keep the complete messages of a run that failed (`run`: the pydantic-ai run, which may be None if it never started)."""
        if run is None:
            return
        done = list(run.ctx.state.message_history[len(self.history) :])
        while done and not isinstance(done[-1], ModelRequest):
            done.pop()
        self.kept = done

    def new_messages(self, result) -> List[ModelMessage]:
        """Everything the run did, over all attempts."""
        return self.kept + list(result.new_messages())
