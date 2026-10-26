# Logic & API Specification (Draft / Pre-Negotiation)
**Team:** Backend / Logic Engineering (Team 2)  
**Feature:** Favorites & Wishlist Management Subsystem  
**Status:** DRAFT (Awaiting frontend alignment)  
**Date:** 2026-10-23  

---

## 1. Архитектура и хранилище данных

### 1.1. Модель данных в памяти
В рамках сессионного хранилища VkusMart создается сервис `FavoritesManager` (синглтон/сессия):
* **Структура записи:**
  ```python
  @dataclass
  class FavoriteEntry:
      product_id: str
      added_at: float  # Unix timestamp
  ```
* Хранение в виде `Dict[str, FavoriteEntry]`, где ключ — `product_id`.

### 1.2. Бизнес-правила
1. **Валидация существования:** При попытке добавить `product_id`, которого нет в `PRODUCTS_BY_ID`, выбрасывать `ServiceError("Product not found", code=404)`.
2. **Уникальность:** Повторное добавление одного и того же товара не допускается. Возвращать ошибку `400 Bad Request` («Product already exists in favorites»).
3. **Лимит избранного:** Максимум 50 товаров на пользователя/сессию. При превышении возвращать `400 Bad Request` («Favorites limit exceeded»).

---

## 2. Эндпоинты API (первоначальное видение бэкенда)

> [!WARNING] Несогласованные предположения команды логики
> 1. Использовались RPC-стили эндпоинтов: `/api/favorites/add` и `/api/favorites/remove`.
> 2. Бэкенд возвращал только массив `product_id` и `added_at`, считая, что полные данные о товаре (цены, калории) фронтенд должен брать из своего кэша каталога.
> 3. Повторный клик по сердечку приводил бы к ошибке 400, ломая пользовательский опыт при быстрых кликах.
> 4. Пакетная операция переноса в корзину отсутствовала на бэкенде.

### 2.1. Добавление товара:
* **Метод:** `POST /api/favorites/add`
* **Request:**
  ```json
  {
    "product_id": "prod-1"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "product_id": "prod-1",
    "total_count": 1
  }
  ```
* **Ошибки:**
  * `404 Not Found`: если товар не существует.
  * `400 Bad Request`: если товар уже в избранном (`{"error": "already_added"}`).

### 2.2. Удаление товара:
* **Метод:** `POST /api/favorites/remove`
* **Request:**
  ```json
  {
    "product_id": "prod-1"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "product_id": "prod-1",
    "total_count": 0
  }
  ```

### 2.3. Получение списка:
* **Метод:** `GET /api/favorites/list`
* **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "product_id": "prod-1",
        "added_at": 1729641600.0
      }
    ],
    "count": 1
  }
  ```

### 2.4. Очистка:
* **Метод:** `POST /api/favorites/clear`
* **Response (200 OK):**
  ```json
  {
    "cleared": true
  }
  ```
