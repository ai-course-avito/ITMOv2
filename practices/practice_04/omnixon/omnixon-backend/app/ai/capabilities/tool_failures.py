"""A tool that fails does not end the run.

Whatever a tool raises (a bug, a database error, a server that went away) is turned into what the model reads as the tool's FAILED result,
with what happened, and the run goes on: the model can tell the user, try another way, or give up on that part. What is not a failure is left
alone: a request to the model to correct its call (`ModelRetry`), a result that is already a failure (`ToolFailed`), a deferred or
approval-gated call, and a cancelled run (which is no `Exception` at all).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import logfire
from pydantic_ai import ToolFailed
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ApprovalRequired, CallDeferred, ModelRetry

from core import metrics
from ..deps import RunDeps
from ..failures import describe_failure


@dataclass
class ToolFailures(AbstractCapability[RunDeps]):
    id: Optional[str] = "tool-failures"

    async def on_tool_execute_error(self, ctx, *, call, tool_def, args, error) -> Any:
        if isinstance(error, (ToolFailed, ModelRetry, ApprovalRequired, CallDeferred)):
            raise error
        metrics.TOOL_ERRORS.inc()
        logfire.warning("Tool {tool} failed: {why}", tool=call.tool_name, why=describe_failure(error), _exc_info=error)
        raise ToolFailed(f"The tool `{call.tool_name}` failed: {describe_failure(error)}")
