"""
Официальный клиент к удаленному MCP-серверу ВкусВилл (https://mcp.vkusvill.ru/mcp).
Реализован на стандартной библиотеке Python (urllib.request) без внешних зависимостей.
Выполняет JSON-RPC 2.0 вызовы инструментов:
- vkusvill_products_search
- vkusvill_products_discount
- vkusvill_product_details
- vkusvill_product_analogs
- vkusvill_cart_link_create
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

VKUSVILL_MCP_URL = "https://mcp.vkusvill.ru/mcp"
logger = logging.getLogger("vkusvill-client")

DEFAULT_HEADERS = {
    "User-Agent": "OpenCode/2.0.20 (VkusMart Assistant)",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

def call_vkusvill_remote_tool(tool_name: str, arguments: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
    """
    Отправляет JSON-RPC tools/call на удаленный сервер ВкусВилл MCP.
    Возвращает унифицированный словарь с результатом (успех или ошибка).
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        VKUSVILL_MCP_URL,
        data=data_bytes,
        headers=DEFAULT_HEADERS,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")

        res_json = json.loads(resp_body)
        if "error" in res_json:
            return {"ok": False, "error": res_json["error"], "raw_jsonrpc": res_json}

        content_list = res_json.get("result", {}).get("content", [])
        if content_list and "text" in content_list[0]:
            try:
                parsed_text = json.loads(content_list[0]["text"])
                is_ok = parsed_text.get("ok", True)
                err_data = parsed_text.get("error") if not is_ok else None
                items = parsed_text.get("data", {}).get("items", []) if is_ok else []
                return {
                    "ok": is_ok,
                    "error": err_data,
                    "items": items,
                    "data": parsed_text,
                    "raw_jsonrpc": res_json
                }
            except Exception:
                return {
                    "ok": True,
                    "text": content_list[0]["text"],
                    "raw_jsonrpc": res_json
                }

        return {"ok": True, "raw_jsonrpc": res_json}

    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8") if he.fp else ""
        try:
            err_json = json.loads(err_body)
            return {"ok": False, "http_status": he.code, "error": err_json.get("error", err_json), "raw_jsonrpc": err_json}
        except Exception:
            return {"ok": False, "http_status": he.code, "error": err_body}
    except Exception as e:
        logger.error(f"Error calling remote VkusVill MCP: {e}")
        return {"ok": False, "error": str(e)}

def search_vkusvill_products(q: str, limit: int = 10) -> Dict[str, Any]:
    """Поиск реальных продуктов ВкусВилл через официальный MCP."""
    return call_vkusvill_remote_tool("vkusvill_products_search", {"q": q, "limit": limit})

def get_vkusvill_discounts(q: str = "молоко", limit: int = 10) -> Dict[str, Any]:
    """Получение скидок и акционных товаров ВкусВилл через официальный MCP."""
    return call_vkusvill_remote_tool("vkusvill_products_discount", {"q": q, "limit": limit})
