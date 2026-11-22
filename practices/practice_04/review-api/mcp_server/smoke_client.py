"""Реальный вызов MCP-инструмента scan_diff через stdio-клиент SDK.

Запускает сервер так же, как OpenCode (команда из opencode.json), и вызывает
инструмент на корректном входе, на diff с секретом и на трёх ошибочных входах.
"""
import asyncio
import json
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    "samples/training_pr.diff",
    "samples/with_secret.diff",
    "samples/not_a_diff.txt",
    "samples/missing.diff",
    "../../../etc/passwd",
]


async def main() -> None:
    params = StdioServerParameters(command=str(ROOT / ".venv/bin/python"),
                                   args=["mcp_server/review_tools_server.py"], cwd=str(ROOT))
    async with Client(params) as client:
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools.tools])
        for diff_path in CASES:
            result = await client.call_tool("scan_diff", {"diff_path": diff_path})
            body = result.structured_content or [c.text for c in result.content]
            print(f"\n> scan_diff({diff_path!r}) isError={result.is_error}")
            print(json.dumps(body, ensure_ascii=False, indent=2)[:900])


asyncio.run(main())
