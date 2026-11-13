"""MCP-сервер для чтения .pptx файлов.

Tool'ы:
- count_slides(path): число слайдов
- get_slide_title(path, index): заголовок слайда по индексу
"""

from __future__ import annotations

import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NAMESPACES = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}


def _load_slides(path: str) -> list[str]:
    """Возвращает список XML-содержимого слайдов или бросает исключение."""
    pptx_path = Path(path)
    if not pptx_path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    if not pptx_path.suffix == ".pptx":
        raise ValueError(f"Ожидался .pptx, получено: {pptx_path.suffix}")

    with zipfile.ZipFile(pptx_path) as zf:
        slide_names = sorted(
            [n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")],
            key=lambda n: int("".join(filter(str.isdigit, Path(n).stem)) or 0),
        )
        return [zf.read(name).decode("utf-8") for name in slide_names]


def count_slides(path: str) -> dict:
    """Считает количество слайдов в .pptx."""
    try:
        slides = _load_slides(path)
        return {"ok": True, "count": len(slides), "path": path}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e), "code": "FILE_NOT_FOUND"}
    except ValueError as e:
        return {"ok": False, "error": str(e), "code": "INVALID_FORMAT"}
    except zipfile.BadZipFile as e:
        return {"ok": False, "error": f"Повреждённый .pptx: {e}", "code": "BAD_ZIP"}


def get_slide_title(path: str, index: int) -> dict:
    """Возвращает заголовок слайда по индексу (0-based)."""
    try:
        slides = _load_slides(path)
        if index < 0 or index >= len(slides):
            return {
                "ok": False,
                "error": f"Индекс {index} вне диапазона (всего слайдов: {len(slides)})",
                "code": "INDEX_OUT_OF_RANGE",
            }

        root = ET.fromstring(slides[index])
        title_el = root.find(".//p:cSld//p:sp//p:txBody//a:t", NAMESPACES)
        if title_el is None or not title_el.text:
            return {"ok": False, "error": "Заголовок не найден", "code": "NO_TITLE"}
        return {"ok": True, "title": title_el.text.strip(), "index": index}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e), "code": "FILE_NOT_FOUND"}
    except (ValueError, ET.ParseError) as e:
        return {"ok": False, "error": str(e), "code": "PARSE_ERROR"}


# --- MCP protocol (stdio) ---

TOOLS = {
    "count_slides": {
        "description": "Считает количество слайдов в .pptx файле",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Путь к .pptx"}},
            "required": ["path"],
        },
        "fn": lambda args: count_slides(args["path"]),
    },
    "get_slide_title": {
        "description": "Возвращает заголовок слайда по индексу",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "index": {"type": "integer", "description": "Индекс слайда (0-based)"},
            },
            "required": ["path", "index"],
        },
        "fn": lambda args: get_slide_title(args["path"], args["index"]),
    },
}


def _respond(msg_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def main() -> None:
    """Простой stdio MCP-сервер."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            _respond(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pptx-reader", "version": "1.0.0"},
            })
        elif method == "tools/list":
            tools = [
                {"name": name, "description": spec["description"], "inputSchema": spec["input_schema"]}
                for name, spec in TOOLS.items()
            ]
            _respond(msg_id, {"tools": tools})
        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            if tool_name not in TOOLS:
                _respond(msg_id, error={"code": -32601, "message": f"Tool не найден: {tool_name}"})
                continue
            result = TOOLS[tool_name]["fn"](args)
            _respond(msg_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
        elif method == "notifications/initialized":
            continue
        else:
            _respond(msg_id, error={"code": -32601, "message": f"Метод не поддержан: {method}"})


if __name__ == "__main__":
    main()
