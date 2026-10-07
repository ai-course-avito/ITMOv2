#!/usr/bin/env python3
"""Снимает сырой протокол MCP-сервера Tetris по stdio: JSON-RPC-кадры как есть.

Запуск (Python из окружения Hermes — там есть пакет `mcp`, но этот скрипт его не
использует: он говорит по протоколу напрямую, чтобы кадры были видно целиком):

    /home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_transcript.py docs/evidence/mcp-transcript.jsonl

Пишет по одной паре «запрос → ответ» на строку:

    {"label": "...", "request": {...}, "response": {...}}

Никакой обработки: в файл попадает ровно то, что ушло серверу в stdin и пришло из его
stdout. Этот файл — источник данных для `docs/mcp-evidence.md`.
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SERVER = PROJECT / "mcp_server" / "tetris_mcp.py"

CALLS: list[tuple[str, str, dict]] = [
    ("sim: корректный вход", "sim", {"seed": 42, "script": "HD HD"}),
    ("sim: неизвестный токен сценария", "sim", {"seed": 42, "script": "XX HD"}),
    ("sim: seed не число", "sim", {"seed": "сорок два", "script": "HD"}),
    ("spec: неизвестный раздел", "spec", {"section": "нет-такого"}),
    ("render: ASCII-поле", "render", {"seed": 42, "script": "L3 CW HD T30 HOLD HD HD"}),
    ("test: прогон ctest", "test", {}),
    ("info: состояние проекта", "info", {}),
]


class Client:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=str(PROJECT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.put(line)

    def send(self, message: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def wait(self, msg_id: int, timeout: float = 180.0) -> dict:
        while True:
            try:
                line = self.lines.get(timeout=timeout).strip()
            except queue.Empty:
                raise SystemExit(f"нет ответа на id={msg_id} за {timeout} с")
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("id") == msg_id:
                return payload

    def call(self, msg_id: int, method: str, params: dict | None = None) -> tuple[dict, dict]:
        request: dict = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            request["params"] = params
        self.send(request)
        return request, self.wait(msg_id)

    def notify(self, method: str) -> None:
        self.send({"jsonrpc": "2.0", "method": method})

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def main() -> int:
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else PROJECT / "docs/evidence/mcp-transcript.jsonl")
    client = Client()
    records: list[dict] = []
    msg_id = 1

    def record(label: str, method: str, params: dict | None = None) -> dict:
        nonlocal msg_id
        request, response = client.call(msg_id, method, params)
        msg_id += 1
        records.append({"label": label, "request": request, "response": response})
        return response

    init = record("initialize", "initialize", {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "mcp-transcript", "version": "0.1.0"},
    })
    client.notify("notifications/initialized")
    listing = record("tools/list", "tools/list")
    for label, tool, args in CALLS:
        record(f"{label} [{tool}]", "tools/call", {"name": tool, "arguments": args})
    client.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for item in records:
            out.write(json.dumps(item, ensure_ascii=False) + "\n")

    print("сервер:", init.get("result", {}).get("serverInfo"))
    print("протокол:", init.get("result", {}).get("protocolVersion"))
    print("инструментов:", len(listing.get("result", {}).get("tools", [])))
    print("записано пар:", len(records), "→", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
