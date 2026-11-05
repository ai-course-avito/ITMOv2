#!/usr/bin/env python3
"""
Minimal MCP stdio server exposing a single tool: file_summary

Implements required MCP JSON-RPC methods:
- initialize -> capabilities
- tools/list -> describe tools
- tools/call -> execute tool

Tool: file_summary(path: string) -> { path, size_bytes, line_count, sha256 }
"""
import hashlib
import json
import os
import sys


def file_summary(path: str):
    if not isinstance(path, str) or not path:
        raise ValueError("path must be a non-empty string")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    size = os.path.getsize(path)
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    with open(path, "rb") as f:
        line_count = sum(1 for _ in f)
    return {
        "path": path,
        "size_bytes": size,
        "line_count": line_count,
        "sha256": sha256.hexdigest(),
    }


def mcp_tools_list():
    return {
        "tools": [
            {
                "name": "file_summary",
                "description": "Summarize a file: size, line count, sha256",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"],
                },
            }
        ]
    }


def handle_request(req):
    rid = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    try:
        if method == "initialize":
            # Respond with protocolVersion and serverInfo per MCP spec
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "file-summary", "version": "0.1.0"}
                }
            }
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rid, "result": mcp_tools_list()}
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {}) or {}
            if name != "file_summary":
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Tool not found"}}
            try:
                res = file_summary(args.get("path"))
            except FileNotFoundError as e:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32004, "message": f"File not found: {e}"}}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}
            # MCP tool result format: array of content parts
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "json", "json": res}]}}
        # Unknown method
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": f"Internal error: {e}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue
        resp = handle_request(req)
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
