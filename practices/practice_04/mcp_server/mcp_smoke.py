#!/usr/bin/env python3
"""Ручная проверка MCP-сервера без агента: рукопожатие, список инструментов, вызов.

Запуск (Python из окружения Hermes, там есть пакет mcp):

    /home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_smoke.py

Скрипт поднимает mcp_server/tetris_mcp.py как подпроцесс, выполняет initialize,
tools/list и один вызов sim, и печатает разбор. Полезно, когда нужно доказать,
что сервер живой, не запуская сессию агента.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

SERVER = Path(__file__).resolve().parent / "tetris_mcp.py"


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            server_info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
            protocol = getattr(init, "protocol_version", None) or getattr(init, "protocolVersion", "?")
            if server_info is not None:
                print("server:", server_info.name, server_info.version)
            print("protocol:", protocol)

            listing = await session.list_tools()
            names = [tool.name for tool in listing.tools]
            print(f"tools ({len(names)}):", ", ".join(names))

            spec = await session.call_tool("spec", {"section": "scoring"})
            spec_text = spec.content[0].text if spec.content else ""
            print("spec(scoring) →", spec_text.splitlines()[0] if spec_text else "(пусто)")
            print("  длина ответа:", len(spec_text), "символов")

            sim = await session.call_tool("sim", {"seed": 42, "script": "HD"})
            payload = json.loads(sim.content[0].text) if sim.content else {}
            if payload.get("ok"):
                state = payload["state"]
                print(
                    "sim(seed=42, script=HD) →",
                    f"score={state['score']} lines={state['lines']}",
                    f"board_hash={state['board_hash']}",
                )
            else:
                print("sim → ошибка (ожидаемо, если проект ещё не собран):", payload.get("error"))
                print("  подсказка:", payload.get("hint", "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
