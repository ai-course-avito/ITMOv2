"""MCP-сервер review-tools: проверка diff по правилам проекта до отправки в LLM.

Запуск (stdio): .venv/bin/python mcp_server/review_tools_server.py
"""
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diff_scan import DiffError, scan_diff_text  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_FILE_BYTES = 2_000_000

server = MCPServer("review-tools", instructions="Project rules checker for review-api diffs (API-1, SEC-1).")


@server.tool()
def scan_diff(diff_path: str) -> dict:
    """Check a unified diff file against project rules before it is sent to an LLM.

    Reports API-1 (diff longer than 20 000 chars must be rejected with HTTP 413) and
    SEC-1 (tokens, passwords and private keys in added lines) with file and new-file
    line numbers. `diff_path` is relative to the project root, e.g. `samples/training_pr.diff`.
    Returns verdict "ok" or "blocked" and the reasons.
    """
    target = (PROJECT_ROOT / diff_path).resolve()
    if not target.is_relative_to(PROJECT_ROOT):
        raise ToolError(f"diff_path must stay inside the project root, got {diff_path!r}")
    if not target.is_file():
        raise ToolError(f"file not found: {diff_path}")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ToolError(f"file is larger than {MAX_FILE_BYTES} bytes: {diff_path}")
    try:
        result = scan_diff_text(target.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ToolError(f"file is not UTF-8 text: {diff_path}") from exc
    except DiffError as exc:
        raise ToolError(str(exc)) from exc
    return {"diff_path": diff_path, **result}


if __name__ == "__main__":
    server.run()
