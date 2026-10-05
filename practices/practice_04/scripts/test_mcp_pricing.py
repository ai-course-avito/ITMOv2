"""Self-test for the olympiad-pricing MCP server over real stdio JSON-RPC.

Usage: python3 scripts/test_mcp_pricing.py [project_dir]
Expected numbers are written out by hand from docs/requirements.md, not computed by the server code.
"""

import json
import subprocess
import sys
from pathlib import Path

project_dir = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
server = project_dir / "mcp" / "olympiad_pricing" / "server.py"

# program, months -> (monthly, discount %, discount ₽, total)
EXPECTED = {
  ("start", 1): (4900, 0, 0, 4900), ("start", 3): (4655, 5, 735, 13965), ("start", 6): (4410, 10, 2940, 26460),
  ("base", 1): (5900, 0, 0, 5900), ("base", 3): (5605, 5, 885, 16815), ("base", 6): (5310, 10, 3540, 31860),
  ("intensive", 1): (6900, 0, 0, 6900), ("intensive", 3): (6555, 5, 1035, 19665),
  ("intensive", 6): (6210, 10, 4140, 37260),
}

ERRORS = [
  ({"program": "olymp", "months": 1}, "Unknown program"),
  ({"program": "start", "months": 2}, "months must be one of [1, 3, 6]"),
  ({"program": "start", "months": "6"}, "months must be one of"),
  ({"program": "start", "months": 1, "grade": 4}, "grade must be an integer from 5 to 9"),
  ({"program": "intensive", "months": 1, "grade": 6}, "(grade 9). For grade 6 the right program is «Старт»"),
  ({"program": "base", "months": 3, "grade": 9}, "the right program is «Интенсив»"),
]

results = []


def expect(ok, label):
  results.append((bool(ok), label))


proc = subprocess.Popen([sys.executable, str(server)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding="utf-8")
next_id = 0


def rpc(method, params=None):
  global next_id
  next_id += 1
  proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": next_id, "method": method, "params": params or {}}) + "\n")
  proc.stdin.flush()
  return json.loads(proc.stdout.readline())


try:
  init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "self-test", "version": "0"}})
  expect(init.get("result", {}).get("serverInfo", {}).get("name") == "olympiad-pricing", "initialize returns serverInfo")
  proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

  tools = rpc("tools/list")["result"]["tools"]
  expect([t["name"] for t in tools] == ["quote"], "tools/list exposes exactly one tool: quote")

  for (program, months), (monthly, percent, discount, total) in EXPECTED.items():
    r = rpc("tools/call", {"name": "quote", "arguments": {"program": program, "months": months}})["result"]
    d = r.get("structuredContent", {})
    expect(not r["isError"] and (d.get("monthly_rub"), d.get("discount_percent"), d.get("discount_rub"),
                                 d.get("total_rub")) == (monthly, percent, discount, total),
           f"quote {program} × {months}: {monthly}/мес, −{percent}% (−{discount}), итого {total}")

  example = rpc("tools/call", {"name": "quote", "arguments": {"program": "Старт", "months": 6, "grade": 5}})["result"]
  expect(example["structuredContent"]["display"] == {"monthly": "4410 ₽", "discount": "−10% (−2940 ₽)",
                                                     "total": "26 460 ₽"},
         "requirements example (Старт, 6 мес., 5 класс) has the page's display strings")

  for args, fragment in ERRORS:
    r = rpc("tools/call", {"name": "quote", "arguments": args})["result"]
    expect(r["isError"] and fragment in r["content"][0]["text"], f"error input {json.dumps(args, ensure_ascii=False)}")

  unknown = rpc("tools/call", {"name": "price", "arguments": {}})
  expect(unknown.get("error", {}).get("code") == -32602, "unknown tool name is a JSON-RPC error")
finally:
  proc.stdin.close()
  proc.wait(timeout=5)

failed = [label for ok, label in results if not ok]
for ok, label in results:
  print(f"{'PASS' if ok else 'FAIL'}  {label}")
if proc.returncode not in (0, None) or proc.stderr.read().strip():
  print("FAIL  server exited cleanly without stderr output")
  failed.append("server exit")
print(f"\n{len(results) - len(failed)}/{len(results)} MCP checks passed")
sys.exit(1 if failed else 0)
