"""MCP-сервер diff-inspector (stdio). Один tool: inspect_diff.

Запуск вручную: python mcp_server/server.py  (ждет JSON-RPC на stdin)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.fastmcp.exceptions import ToolError  # noqa: E402

from diff_parser import DEFAULT_MAX_BYTES, DiffInspectError  # noqa: E402
from diff_parser import inspect_diff as _inspect_diff  # noqa: E402

mcp = FastMCP("diff-inspector")


@mcp.tool()
def inspect_diff(diff: str, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """Разобрать unified diff (вывод git diff) и вернуть сводку.

    Возвращает JSON: files (path, status, added, removed, binary), total_files,
    total_added, total_removed, size_bytes (utf-8), too_large (size_bytes > max_bytes)
    и would_be_accepted (diff годится для ai-review-api). Пустой diff, текст без признаков
    diff и max_bytes <= 0 дают ошибку tool (isError=true) с пояснением.
    """
    try:
        return _inspect_diff(diff, max_bytes)
    except DiffInspectError as e:
        raise ToolError(str(e)) from e


if __name__ == "__main__":
    mcp.run(transport="stdio")
