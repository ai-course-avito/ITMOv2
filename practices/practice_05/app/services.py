"""
Сервисный слой приложения VkusMart (Feature B enhanced & Feature Favorites / Practice 5).
Реализует бизнес-логику поиска, фильтрации по диетическим требованиям,
формирования тематических подборок, расчета корзины со ступенчатыми скидками,
анализом баланса макронутриентов, механизмом Graceful Fallback и подсистемой Избранного (Favorites).
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import time

from app.catalog import (
    Product,
    ThemeBundle,
    PRODUCTS,
    THEMES,
    PRODUCTS_BY_ID,
    THEMES_BY_ID,
    CATEGORIES,
    ALLERGENS_LIST
)

@dataclass
class ServiceError(Exception):
    code: str
    message: str
    status_code: int = 400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.code.lower(),
            "code": self.code,
            "message": self.message
        }

def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    max_calories: Optional[int] = None,
    exclude_allergens: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    allow_fallback: bool = False
) -> List[Dict[str, Any]]:
    """
    Поиск товаров по каталогу с валидацией, фильтрацией и поддержкой Graceful Fallback (Фича B).
    """
    if query is not None:
        query_clean = query.strip()
        if len(query_clean) == 0:
            raise ServiceError("EMPTY_QUERY", "Поисковый запрос не может быть пустым.")
        if len(query_clean) < 2:
            raise ServiceError("QUERY_TOO_SHORT", "Поисковый запрос должен содержать минимум 2 символа.")
    else:
        query_clean = ""

    if category is not None and category != "":
        if category not in CATEGORIES:
            raise ServiceError(
                "UNKNOWN_CATEGORY",
                f"Неизвестная категория '{category}'. Допустимые: {', '.join(CATEGORIES)}"
            )

    if max_price is not None and max_price <= 0:
        raise ServiceError("INVALID_PRICE_LIMIT", "Лимит цены должен быть строго больше 0.")

    if max_calories is not None and max_calories <= 0:
        raise ServiceError("INVALID_CALORIE_LIMIT", "Лимит калорийности должен быть строго больше 0.")

    forbidden_allergens = set(exclude_allergens or [])
    required_tags = set(tags or [])

    results = []
    q_lower = query_clean.lower()

    for p in PRODUCTS:
        # Проверка запроса: точное вхождение либо по основе слов
        if q_lower:
            words = [w for w in q_lower.split() if len(w) >= 2]
            text = f"{p.name} {p.description}".lower()
            match_all = True
            for w in words:
                stem = w[:-1] if len(w) > 4 else w
                if w not in text and stem not in text:
                    match_all = False
                    break
            if not match_all:
                continue

        # Проверка категории
        if category and p.category != category:
            continue

        # Проверка цены
        if max_price is not None and p.price > max_price:
            continue

        # Проверка калорий
        if max_calories is not None and p.calories > max_calories:
            continue

        # Проверка аллергенов (Фича A)
        p_allergens = set(p.allergens)
        if forbidden_allergens and p_allergens.intersection(forbidden_allergens):
            continue

        # Проверка тегов
        if required_tags and not required_tags.issubset(set(p.tags)):
            continue

        results.append(p.to_dict())

    # Graceful Fallback (Фича B): если точных совпадений нет, но разрешен fallback
    if len(results) == 0 and allow_fallback:
        fallback_results = []
        relaxed_price = (max_price * 1.3) if max_price else None

        for p in PRODUCTS:
            if category and p.category != category:
                continue
            if relaxed_price is not None and p.price > relaxed_price:
                continue
            # Аллергены НЕ ослабляем из соображений безопасности здоровья
            if forbidden_allergens and set(p.allergens).intersection(forbidden_allergens):
                continue
            fallback_item = p.to_dict()
            fallback_item["_fallback_match"] = True
            fallback_results.append(fallback_item)

        return fallback_results

    return results

def search_live_vkusvill(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Поиск продуктов напрямую через официальный MCP-сервер ВкусВилл (https://mcp.vkusvill.ru/mcp).
    Нормализует формат товаров для отображения в каталоге и добавления в корзину.
    """
    if not query or len(query.strip()) == 0:
        raise ServiceError("EMPTY_QUERY", "Поисковый запрос не может быть пустым.")

    from mcp_server.vkusvill_client import search_vkusvill_products
    remote_res = search_vkusvill_products(q=query.strip(), limit=limit)
    if not remote_res.get("ok"):
        err = remote_res.get("error", {})
        msg = err.get("message", "Ошибка поиска во ВкусВилл") if isinstance(err, dict) else str(err)
        raise ServiceError("VKUSVILL_MCP_ERROR", msg)

    raw_items = remote_res.get("items", [])
    normalized = []
    for item in raw_items:
        price_obj = item.get("price", {})
        price_val = float(price_obj.get("current", 0)) if isinstance(price_obj, dict) else 0.0
        normalized.append({
            "id": f"vv-{item.get('id', item.get('xml_id'))}",
            "name": item.get("name", "").replace("&nbsp;", " "),
            "category": "vkusvill_live",
            "price": price_val,
            "calories": 150,
            "protein": 5.0,
            "fat": 5.0,
            "carbs": 15.0,
            "weight": item.get("weight", "1 шт"),
            "tags": ["vkusvill_official", "live_mcp"],
            "allergens": [],
            "description": f"Товар из официального каталога сети ВкусВилл (ID: {item.get('id')}). Источник: https://mcp.vkusvill.ru/mcp"
        })
    return normalized

def get_theme_bundles(
    theme_id: Optional[str] = None,
    max_budget: Optional[float] = None,
    exclude_allergens: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Получение тематических подборок с фильтрацией по бюджету и аллергенам.
    """
    if max_budget is not None and max_budget <= 0:
        raise ServiceError("INVALID_BUDGET", f"Бюджет должен быть строго положительным числом, получено: {max_budget}")

    forbidden_allergens = set(exclude_allergens or [])
    selected_themes = [THEMES_BY_ID[theme_id]] if theme_id and theme_id in THEMES_BY_ID else THEMES

    bundles = []
    for t in selected_themes:
        matched_products = []
        for pid in t.product_ids:
            p = PRODUCTS_BY_ID.get(pid)
            if not p:
                continue
            if forbidden_allergens and set(p.allergens).intersection(forbidden_allergens):
                continue
            matched_products.append(p.to_dict())

        total_price = sum(item["price"] for item in matched_products)
        total_calories = sum(item["calories"] for item in matched_products)
        total_protein = round(sum(item["protein"] for item in matched_products), 1)
        total_fat = round(sum(item["fat"] for item in matched_products), 1)
        total_carbs = round(sum(item["carbs"] for item in matched_products), 1)

        is_within_budget = True
        if max_budget is not None and total_price > max_budget:
            is_within_budget = False

        bundles.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "icon": t.icon,
            "target_budget": t.target_budget,
            "actual_price": round(total_price, 2),
            "total_calories": total_calories,
            "macros": {
                "protein": total_protein,
                "fat": total_fat,
                "carbs": total_carbs
            },
            "is_within_budget": is_within_budget,
            "products_count": len(matched_products),
            "products": matched_products
        })

    return bundles

def calculate_cart_nutrition(
    items: List[Dict[str, Any]],
    apply_discount_feature_b: bool = True
) -> Dict[str, Any]:
    """
    Расчет корзины: итоговая цена, динамическая ступенчатая скидка,
    расчет баланса макронутриентов и предупреждения (Фича B).
    """
    if not items:
        return {
            "total_items": 0,
            "subtotal": 0.0,
            "discount_percent": 0.0,
            "discount_rub": 0.0,
            "final_price": 0.0,
            "total_calories": 0,
            "protein": 0.0,
            "fat": 0.0,
            "carbs": 0.0,
            "macro_percentages": {"protein": 0.0, "fat": 0.0, "carbs": 0.0},
            "nutrition_alerts": [],
            "allergens": [],
            "items_detail": []
        }

    subtotal = 0.0
    total_cals = 0
    protein = 0.0
    fat = 0.0
    carbs = 0.0
    all_allergens = set()
    items_detail = []

    for item in items:
        pid = item.get("product_id")
        qty = int(item.get("quantity", 1))
        if qty <= 0:
            continue
        p = PRODUCTS_BY_ID.get(pid)
        if not p:
            if pid and pid.startswith("vv-"):
                name = item.get("name", "Товар ВкусВилл")
                price = float(item.get("price", 150.0))
                cals = int(item.get("calories", 120))
                p = Product(
                    id=pid,
                    name=name,
                    category="vkusvill_live",
                    price=price,
                    calories=cals,
                    protein=4.0,
                    fat=4.0,
                    carbs=15.0,
                    weight="1 шт",
                    tags=["vkusvill_official"]
                )
            else:
                raise ServiceError("PRODUCT_NOT_FOUND", f"Товар с id '{pid}' не найден в каталоге.", status_code=404)

        line_price = p.price * qty
        subtotal += line_price
        total_cals += p.calories * qty
        protein += p.protein * qty
        fat += p.fat * qty
        carbs += p.carbs * qty
        all_allergens.update(p.allergens)

        items_detail.append({
            "product_id": p.id,
            "name": p.name,
            "price": p.price,
            "quantity": qty,
            "line_price": round(line_price, 2),
            "calories": p.calories * qty,
            "allergens": list(p.allergens)
        })

    discount_pct = 0.0
    if apply_discount_feature_b:
        if subtotal >= 2500.0:
            discount_pct = 12.0
        elif subtotal >= 1500.0:
            discount_pct = 7.0

    discount_rub = round(subtotal * (discount_pct / 100.0), 2)
    final_price = round(subtotal - discount_rub, 2)

    macro_cals = (protein * 4) + (fat * 9) + (carbs * 4)
    if macro_cals > 0:
        protein_pct = round((protein * 4 / macro_cals) * 100, 1)
        fat_pct = round((fat * 9 / macro_cals) * 100, 1)
        carbs_pct = round((carbs * 4 / macro_cals) * 100, 1)
    else:
        protein_pct = fat_pct = carbs_pct = 0.0

    nutrition_alerts = []
    if carbs_pct > 65.0:
        nutrition_alerts.append("Высокая доля углеводов (> 65%). Рекомендуется добавить источник белка.")
    if fat_pct > 70.0 and protein_pct < 15.0:
        nutrition_alerts.append("Высокая доля жиров при низком белке. Проверьте баланс рациона.")

    return {
        "total_items": sum(i["quantity"] for i in items_detail),
        "subtotal": round(subtotal, 2),
        "discount_percent": discount_pct,
        "discount_rub": discount_rub,
        "final_price": final_price,
        "total_calories": total_cals,
        "protein": round(protein, 1),
        "fat": round(fat, 1),
        "carbs": round(carbs, 1),
        "macro_percentages": {
            "protein": protein_pct,
            "fat": fat_pct,
            "carbs": carbs_pct
        },
        "nutrition_alerts": nutrition_alerts,
        "allergens": sorted(list(all_allergens)),
        "items_detail": items_detail
    }


# =========================================================================
# FEATURE: Favorites & Wishlist Subsystem (Practice 5 SDD Implementation)
# =========================================================================

@dataclass
class FavoriteItem:
    product_id: str
    added_at: float = field(default_factory=time.time)

class FavoritesService:
    def __init__(self, max_limit: int = 50):
        self._items: Dict[str, FavoriteItem] = {}
        self.max_limit = max_limit

    def add_favorite(self, product_id: str) -> Dict[str, Any]:
        """
        Идемпотентное добавление товара в избранное согласно контракту specs/contract.md.
        """
        if not product_id or not isinstance(product_id, str) or not product_id.strip():
            raise ServiceError("MISSING_PRODUCT_ID", "Field 'product_id' is required.", status_code=400)

        pid = product_id.strip()
        if pid not in PRODUCTS_BY_ID and not pid.startswith("vv-"):
            raise ServiceError("PRODUCT_NOT_FOUND", f"Product with id '{pid}' not found in catalog.", status_code=404)

        if pid in self._items:
            return {
                "status": "exists",
                "already_exists": True,
                "product_id": pid,
                "total_count": len(self._items)
            }

        if len(self._items) >= self.max_limit:
            raise ServiceError("LIMIT_EXCEEDED", f"Favorites limit of {self.max_limit} items reached.", status_code=400)

        self._items[pid] = FavoriteItem(product_id=pid)
        return {
            "status": "added",
            "already_exists": False,
            "product_id": pid,
            "total_count": len(self._items)
        }

    def remove_favorite(self, product_id: str) -> Dict[str, Any]:
        """
        Удаление товара из избранного.
        """
        if not product_id or not isinstance(product_id, str) or not product_id.strip():
            raise ServiceError("MISSING_PRODUCT_ID", "Field 'product_id' is required.", status_code=400)

        pid = product_id.strip()
        if pid not in self._items:
            raise ServiceError("NOT_IN_FAVORITES", f"Product '{pid}' is not in favorites.", status_code=404)

        del self._items[pid]
        return {
            "status": "removed",
            "product_id": pid,
            "total_count": len(self._items)
        }

    def clear(self) -> Dict[str, Any]:
        """
        Очистка всех товаров из избранного.
        """
        self._items.clear()
        return {
            "status": "cleared",
            "total_count": 0
        }

    def get_favorites(self) -> Dict[str, Any]:
        """
        Получение обогащенного списка товаров в избранном с агрегатами сумм и калорий.
        """
        items_detail = []
        total_price = 0.0
        total_calories = 0

        for pid, fav in self._items.items():
            product = PRODUCTS_BY_ID.get(pid)
            if product:
                p_dict = product.to_dict()
                p_dict["added_at"] = fav.added_at
                items_detail.append(p_dict)
                total_price += product.price
                total_calories += product.calories
            elif pid.startswith("vv-"):
                items_detail.append({
                    "id": pid,
                    "name": "Товар ВкусВилл (Live)",
                    "category": "vkusvill_live",
                    "price": 150.0,
                    "calories": 120,
                    "protein": 4.0,
                    "fat": 4.0,
                    "carbs": 15.0,
                    "weight": "1 шт",
                    "tags": ["vkusvill_official"],
                    "allergens": [],
                    "description": "Товар из живого каталога ВкусВилл",
                    "added_at": fav.added_at
                })
                total_price += 150.0
                total_calories += 120

        return {
            "items": items_detail,
            "total_count": len(items_detail),
            "total_price": round(total_price, 2),
            "total_calories": total_calories
        }

    def move_to_cart(self, clear_favorites: bool = True) -> Dict[str, Any]:
        """
        Атомарный перенос всех товаров из избранного в корзину с пересчетом питательности.
        """
        if not self._items:
            raise ServiceError("EMPTY_FAVORITES", "Cannot move empty favorites list to cart.", status_code=400)

        cart_items = [{"product_id": pid, "quantity": 1} for pid in self._items.keys()]
        cart_result = calculate_cart_nutrition(cart_items)

        moved_count = len(self._items)
        if clear_favorites:
            self._items.clear()

        return {
            "status": "moved_to_cart",
            "moved_items_count": moved_count,
            "cart": cart_result,
            "favorites_count": len(self._items)
        }

# Глобальный экземпляр сервиса избранного
favorites_service = FavoritesService()
