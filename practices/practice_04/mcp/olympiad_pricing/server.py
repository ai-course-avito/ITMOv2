"""Olympiad Start pricing MCP server (stdio, JSON-RPC 2.0, standard library only).

One tool, `quote`: the canonical price for a program, duration and (optional) grade.
Programs, grades, prices and discounts are parsed from docs/requirements.md, so the
server and the page share one source of truth.

Run: python3 mcp/olympiad_pricing/server.py   (registered in .mcp.json)
"""

import json
import re
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "olympiad-pricing", "version": "1.0.0"}
REQUIREMENTS = Path(__file__).resolve().parents[2] / "docs" / "requirements.md"

PROGRAM_IDS = {"Старт": "start", "Основа": "base", "Интенсив": "intensive"}


class ToolError(Exception):
  """A problem with the tool input: reported to the model as isError, not as a protocol error."""


def load_contract(path=REQUIREMENTS):
  text = path.read_text(encoding="utf-8")
  programs = {}
  for name, grades, price in re.findall(r"- (\S+) \(([\d–]+) класс\) — (\d+) ₽ / month", text):
    low, _, high = grades.partition("–")
    grade_range = list(range(int(low), int(high or low) + 1))
    programs[PROGRAM_IDS.get(name, name.lower())] = {"name": name, "grades": grade_range, "price": int(price)}
  discounts = {1: 0}
  for months, percent in re.findall(r"(\d+) months — (\d+)% discount", text):
    discounts[int(months)] = int(percent)
  if len(programs) != 3 or set(discounts) != {1, 3, 6}:
    raise RuntimeError(f"cannot parse prices from {path}: programs={programs}, discounts={discounts}")
  return programs, discounts


def rub(value):
  # Same format as the page (script.js formatRub): 4410 ₽, 26 460 ₽ (NBSP separators).
  digits = f"{value:,}".replace(",", " ") if value >= 10000 else str(value)
  return digits + " ₽"


def quote(args, contract):
  programs, discounts = contract
  key = str(args.get("program", "")).strip()
  by_name = {p["name"].lower(): k for k, p in programs.items()}
  program_id = key if key in programs else by_name.get(key.lower())
  if not program_id:
    raise ToolError(f"Unknown program «{key}». Use one of: "
                    + ", ".join(f"{k} ({p['name']})" for k, p in programs.items()) + ".")

  months = args.get("months")
  if not isinstance(months, int) or isinstance(months, bool) or months not in discounts:
    raise ToolError(f"months must be one of {sorted(discounts)}, got {months!r}.")

  program = programs[program_id]
  grade = args.get("grade")
  if grade is not None:
    if not isinstance(grade, int) or isinstance(grade, bool) or not 5 <= grade <= 9:
      raise ToolError(f"grade must be an integer from 5 to 9, got {grade!r}.")
    if grade not in program["grades"]:
      right = next(p for p in programs.values() if grade in p["grades"])
      low, high = program["grades"][0], program["grades"][-1]
      fits = f"grade {low}" if low == high else f"grades {low}–{high}"
      raise ToolError(f"Grade {grade} does not match «{program['name']}» ({fits}). "
                      f"For grade {grade} the right program is «{right['name']}».")

  percent = discounts[months]
  monthly = program["price"] * (100 - percent) // 100
  total = monthly * months
  discount = program["price"] * months - total
  data = {
    "program": program_id,
    "program_name": program["name"],
    "grades": program["grades"],
    "months": months,
    "base_monthly_rub": program["price"],
    "discount_percent": percent,
    "monthly_rub": monthly,
    "discount_rub": discount,
    "total_rub": total,
    "display": {
      "monthly": rub(monthly),
      "discount": f"−{percent}% (−{rub(discount)})" if percent else f"0% ({rub(0)})",
      "total": rub(total),
    },
  }
  summary = (f"«{program['name']}», {months} мес.: {rub(monthly)} в месяц, "
             f"скидка {data['display']['discount']}, итого {rub(total)}.")
  return summary, data


TOOLS = [{
  "name": "quote",
  "title": "Olympiad Start price quote",
  "description": ("Canonical price for an Olympiad Start program from docs/requirements.md: monthly price after "
                  "discount, discount in % and ₽, and total, with the exact strings the page should display. "
                  "Optionally checks that the child's grade fits the program and names the right program if not. "
                  "Use it to verify the sign-up calculator."),
  "inputSchema": {
    "type": "object",
    "properties": {
      "program": {"type": "string", "description": "start | base | intensive (or Старт | Основа | Интенсив)"},
      "months": {"type": "integer", "enum": [1, 3, 6], "description": "Duration in months"},
      "grade": {"type": "integer", "minimum": 5, "maximum": 9, "description": "Optional child's grade"},
    },
    "required": ["program", "months"],
    "additionalProperties": False,
  },
}]


def handle(message, contract):
  method = message.get("method")
  if method == "initialize":
    requested = (message.get("params") or {}).get("protocolVersion")
    return {"protocolVersion": requested or PROTOCOL_VERSION, "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}
  if method == "ping":
    return {}
  if method == "tools/list":
    return {"tools": TOOLS}
  if method == "tools/call":
    params = message.get("params") or {}
    if params.get("name") != "quote":
      raise LookupError(f"Unknown tool: {params.get('name')}")
    try:
      summary, data = quote(params.get("arguments") or {}, contract)
    except ToolError as error:
      return {"content": [{"type": "text", "text": str(error)}], "isError": True}
    return {"content": [{"type": "text", "text": summary + "\n" + json.dumps(data, ensure_ascii=False)}],
            "structuredContent": data, "isError": False}
  raise NotImplementedError(method)


def main():
  contract = load_contract()
  for line in sys.stdin:
    if not line.strip():
      continue
    try:
      message = json.loads(line)
    except ValueError:
      reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
    else:
      if "id" not in message:
        continue  # notification, e.g. notifications/initialized
      reply = {"jsonrpc": "2.0", "id": message["id"]}
      try:
        reply["result"] = handle(message, contract)
      except LookupError as error:
        reply["error"] = {"code": -32602, "message": str(error)}
      except NotImplementedError as error:
        reply["error"] = {"code": -32601, "message": f"Method not found: {error}"}
    sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
  main()
