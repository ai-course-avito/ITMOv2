# Logic & API Specification (Approved / Post-Negotiation)
**Team:** Backend / Logic Engineering (Team 2)  
**Feature:** Favorites & Wishlist Management Subsystem  
**Status:** APPROVED (Aligned with `specs/contract.md`)  
**Date:** 2026-10-23  

---

## 1. Архитектура и хранение данных

### 1.1. Доменная модель
В модуле [`app/services.py`](file:///D:/3sem/vibecoding/ITMOv2/practices/practice_05/app/services.py) объявляются структуры:

```python
from dataclasses import dataclass
import time

@dataclass
class FavoriteItem:
    product_id: str
    added_at: float = field(default_factory=time.time)

class FavoritesService:
    def __init__(self, max_limit: int = 50):
        self._items: Dict[str, FavoriteItem] = {}
        self.max_limit = max_limit
```

### 1.2. Бизнес-правила и инварианты
1. **Проверка существования товара:**
   - Перед добавлением проверяется `product_id in PRODUCTS_BY_ID`.
   - Если нет: возбуждать исключение `ServiceError("Product with id '{product_id}' not found in catalog", code=404, error="product_not_found")`.
2. **Идемпотентность добавления:**
   - Если товар уже присутствует в `self._items`: операция добавления возвращает результат с флагом `already_exists=True`, не выбрасывая ошибку.
3. **Лимит емкости:**
   - Если размер коллекции достиг `max_limit` и добавляется новый товар: возбуждать `ServiceError("Favorites limit of 50 items reached", code=400, error="limit_exceeded")`.
4. **Обогащение данных (Enrichment):**
   - При запросе списка возвращается не просто массив ключей, а список словарей с полными полями `Product` + поле `added_at`.
   - Вычисляются агрегаты: `total_count`, `total_price` (округлённо до 2 знаков), `total_calories`.
5. **Атомарный перенос в корзину:**
   - Избранные товары конвертируются в список элементов корзины (`[{"product_id": pid, "quantity": 1}]`).
   - Если список пуст: возбуждать `ServiceError("Cannot move empty favorites list to cart", code=400, error="empty_favorites")`.
   - При успешном переносе: вызывается сервис корзины, очищается `self._items` (если `clear_favorites=True`), и возвращаются результаты операции.

---

## 2. Спецификация серверных обработчиков (HTTP Handler)

В [`app/server.py`](file:///D:/3sem/vibecoding/ITMOv2/practices/practice_05/app/server.py):

* **`GET /api/favorites`:**
  - Извлекает текущее состояние из `favorites_service.get_favorites()`.
  - Возвращает статус 200 с DTO:
    ```json
    {
      "items": [...],
      "total_count": int,
      "total_price": float,
      "total_calories": int
    }
    ```

* **`POST /api/favorites`:**
  - Парсит JSON payload: `{"product_id": str}`.
  - При отсутствии `product_id`: статус 400 `{"error": "missing_product_id", "message": "Field 'product_id' is required"}`.
  - Возвращает статус 200:
    ```json
    {
      "status": "added" | "exists",
      "already_exists": bool,
      "product_id": str,
      "total_count": int
    }
    ```

* **`DELETE /api/favorites`** и **`POST /api/favorites/remove`:**
  - Парсит JSON payload: `{"product_id": str}`.
  - Если товар не найден в избранном: статус 404 `{"error": "not_in_favorites", "message": "Product is not in favorites"}`.
  - Возвращает статус 200:
    ```json
    {
      "status": "removed",
      "product_id": str,
      "total_count": int
    }
    ```

* **`POST /api/favorites/clear`:**
  - Очищает хранилище.
  - Возвращает статус 200: `{"status": "cleared", "total_count": 0}`.

* **`POST /api/favorites/move-to-cart`:**
  - Переносит все товары из избранного в текущую корзину.
  - Очищает избранное.
  - Возвращает статус 200 с новой корзиной и `favorites_count: 0`.

---

## 3. Требования к тестированию
* Тестирование изоляции и граничных случаев в [`tests/test_favorites.py`](file:///D:/3sem/vibecoding/ITMOv2/practices/practice_05/tests/test_favorites.py):
  1. Добавление существующего товара (успех, счетчик увеличивается).
  2. Идемпотентность: повторное добавление того же товара (200 OK, `already_exists=True`, счетчик не растет).
  3. Добавление несуществующего товара (404 `product_not_found`).
  4. Удаление товара из избранного (успех, счетчик уменьшается).
  5. Попытка удаления товара, которого нет в избранном (404 `not_in_favorites`).
  6. Очистка списка (все элементы удалены).
  7. Обогащение данных: расчет суммы цен и калорий корректен.
  8. Атомарный перенос в корзину: расчет корзины обновлен, избранное очищено.
  9. Ошибка переноса пустой корзины (400 `empty_favorites`).
  10. Проверка лимита (50 товаров).
