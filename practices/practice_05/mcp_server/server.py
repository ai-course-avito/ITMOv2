#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Server for VkusMart.
Реализует спецификацию MCP (JSON-RPC 2.0 stdio) для предоставления инструментов:
- get_theme_bundles
- search_products
- calculate_cart_nutrition
"""

import sys
import json
import logging
from typing import Any, Dict, Optional, List

from app.services import (
    search_products,
    get_theme_bundles,
    calculate_cart_nutrition,
    ServiceError
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger("vkusmart-mcp")

PROTOCOL_VERSION = "2024-11-05"

TOOLS_METADATA = [
    {
        "name": "get_theme_bundles",
        "description": "Получить готовые тематические подборки продуктов (ПП-рацион, студенческий ужин, кето и др.) с фильтрацией по бюджету и аллергенам.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme_id": {
                    "type": "string",
                    "description": "ID конкретной темы (например, 'theme-pp', 'theme-student', 'theme-keto'). Если не указан, возвращаются все темы."
                },
                "max_budget": {
                    "type": "number",
                    "description": "Максимальный бюджет в рублях (должен быть > 0)."
                },
                "exclude_allergens": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список исключаемых аллергенов: 'lactose', 'gluten', 'nuts', 'seafood'."
                }
            }
        }
    },
    {
        "name": "search_products",
        "description": "Поиск и фильтрация продуктов по названию, категории, диетическим тегам, калорийности и исключению аллергенов.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковая фраза (минимум 2 символа, например 'гречка', 'индейка')."
                },
                "category": {
                    "type": "string",
                    "description": "Категория: meat_poultry, dairy_eggs, grains_cereals, fish_seafood, vegetables_greens, nuts_snacks, bakery_bread, desserts_sugarfree."
                },
                "max_price": {
                    "type": "number",
                    "description": "Максимальная цена за единицу товара в рублях (> 0)."
                },
                "max_calories": {
                    "type": "integer",
                    "description": "Максимальная калорийность на 100г/порцию (> 0)."
                },
                "exclude_allergens": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список исключаемых аллергенов: 'lactose', 'gluten', 'nuts', 'seafood'."
                }
            }
        }
    },
    {
        "name": "calculate_cart_nutrition",
        "description": "Расчет суммарной стоимости корзины, динамических скидок, аллергенов и полного баланса КБЖУ (белки, жиры, углеводы, калории).",
        "inputSchema": {
            "type": "object",
            "required": ["items"],
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Список товаров в корзине с количествами.",
                    "items": {
                        "type": "object",
                        "required": ["product_id"],
                        "properties": {
                            "product_id": {"type": "string", "description": "ID товара, например 'prod-1'"},
                            "quantity": {"type": "integer", "default": 1, "description": "Количество единиц (> 0)"}
                        }
                    }
                }
            }
        }
    }
]

def handle_call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Диспетчеризация и выполнение вызова инструмента с обработкой ошибок.
    """
    try:
        if name == "get_theme_bundles":
            theme_id = arguments.get("theme_id")
            max_budget = arguments.get("max_budget")
            exclude_allergens = arguments.get("exclude_allergens")
            bundles = get_theme_bundles(theme_id=theme_id, max_budget=max_budget, exclude_allergens=exclude_allergens)
            return {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"bundles": bundles, "total_found": len(bundles)}, ensure_ascii=False, indent=2)
                    }
                ]
            }

        elif name == "search_products":
            query = arguments.get("query")
            category = arguments.get("category")
            max_price = arguments.get("max_price")
            max_calories = arguments.get("max_calories")
            exclude_allergens = arguments.get("exclude_allergens")
            tags = arguments.get("tags")

            products = search_products(
                query=query,
                category=category,
                max_price=max_price,
                max_calories=max_calories,
                exclude_allergens=exclude_allergens,
                tags=tags
            )
            return {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"products": products, "count": len(products)}, ensure_ascii=False, indent=2)
                    }
                ]
            }

        elif name == "calculate_cart_nutrition":
            items = arguments.get("items")
            if not isinstance(items, list):
                raise ServiceError("INVALID_ARGUMENT", "Параметр 'items' должен быть списком товаров.")
            cart = calculate_cart_nutrition(items=items)
            return {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"cart": cart}, ensure_ascii=False, indent=2)
                    }
                ]
            }

        else:
            return {
                "isError": True,
                "content": [
                    {"type": "text", "text": f"Error: Неизвестный инструмент '{name}'."}
                ]
            }

    except ServiceError as se:
        logger.warning(f"Validation error in tool '{name}': {se.code} - {se.message}")
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": True,
                        "code": se.code,
                        "message": se.message
                    }, ensure_ascii=False, indent=2)
                }
            ]
        }
    except Exception as e:
        logger.error(f"Unexpected error in tool '{name}': {e}", exc_info=True)
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "error": True,
                        "code": "INTERNAL_ERROR",
                        "message": f"Внутренняя ошибка сервера: {str(e)}"
                    }, ensure_ascii=False, indent=2)
                }
            ]
        }

def process_jsonrpc_request(line: str) -> Optional[str]:
    """Обработка одного JSON-RPC сообщения."""
    try:
        req = json.loads(line.strip())
    except Exception as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
        })

    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "vkusmart-smart-grocery-mcp",
                    "version": "1.0.0"
                }
            }
        })

    elif method == "notifications/initialized":
        # Уведомление, ответ не требуется
        return None

    elif method == "tools/list":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_METADATA
            }
        })

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        call_res = handle_call_tool(tool_name, arguments)
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": call_res
        }, ensure_ascii=False)

    elif method == "ping":
        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}})

    else:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"}
        })

def run_stdio_server():
    """Запуск сервера через стандартный ввод/вывод (stdio)."""
    logger.info("Starting VkusMart MCP Server via stdio...")
    for line in sys.stdin:
        if not line:
            break
        resp = process_jsonrpc_request(line)
        if resp:
            sys.stdout.write(resp + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-tool":
        # Удобный CLI режим для проверки инструментов
        tool_name = sys.argv[2]
        tool_args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        res = handle_call_tool(tool_name, tool_args)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        run_stdio_server()
