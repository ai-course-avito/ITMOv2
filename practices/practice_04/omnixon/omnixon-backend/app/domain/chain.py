from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

USER_ID_MAX = 64  # users.external_id


def caller_user_id(caller_agent_id: int, human: str) -> str:
    """The user a called agent talks to: one per (calling agent, person). A person's id that does not fit is replaced by a short fingerprint
    of it, which is still one per person."""
    user_id = f"agent_{caller_agent_id}:{human}"
    if len(user_id) <= USER_ID_MAX:
        return user_id
    return f"agent_{caller_agent_id}:{hashlib.sha256(human.encode()).hexdigest()[:16]}"


@dataclass(frozen=True)
class CallChain:
    """The agents a request went through when agents called each other (the tool `ask_agent`), and the person it started with. A chain is only
    ever extended (a new one is made)."""

    agents: Tuple[int, ...]  # the first is the agent the request came to, the last the one that is running
    human: str  # the external id of the person, a user of the first agent

    def then(self, agent_id: int) -> "CallChain":
        return CallChain(self.agents + (agent_id,), self.human)

    def refusal(self, target: int, depth: int) -> Optional[str]:
        """Why the chain may not go on to `target` (a loop, or too deep), in the tool's words; None if it may."""
        if target in self.agents:
            path = " -> ".join(str(a) for a in self.agents)
            return f"Refused: agent {target} is already in this chain of calls ({path}); an agent is not called twice."
        if len(self.agents) - 1 >= depth:
            return f"Refused: this request is already {depth} agents deep, the most that one request may go."
        return None
