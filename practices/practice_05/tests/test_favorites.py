"""
Тесты подсистемы Избранного (Favorites & Wishlist) - Практика 5 (SDD / Spec-Kit).
Проверяют соответствие контракту specs/contract.md и спецификации specs/logic-spec.md:
- Идемпотентность добавления (200 OK вместо 400 при повторе)
- Валидация существования в каталоге (404)
- Обогащение данных полными объектами каталога (Enrichment)
- Атомарный перенос в корзину (move-to-cart)
- Корректная обработка граничных условий и лимитов
"""

import unittest
from app.services import FavoritesService, ServiceError
from app.catalog import PRODUCTS

class FavoritesSubsystemTestCase(unittest.TestCase):
    def setUp(self):
        # Изолированный экземпляр сервиса на каждый тест
        self.service = FavoritesService(max_limit=5)

    def test_add_favorite_success(self):
        """Контракт 2.2: Успешное добавление товара в избранное"""
        res = self.service.add_favorite("prod-1")
        self.assertEqual(res["status"], "added")
        self.assertFalse(res["already_exists"])
        self.assertEqual(res["product_id"], "prod-1")
        self.assertEqual(res["total_count"], 1)

    def test_add_favorite_idempotent(self):
        """Контракт 2.2 & Переговоры #4: Повторное добавление идемпотентно и не вызывает ошибку"""
        self.service.add_favorite("prod-1")
        # Повторный вызов
        res = self.service.add_favorite("prod-1")
        self.assertEqual(res["status"], "exists")
        self.assertTrue(res["already_exists"])
        self.assertEqual(res["total_count"], 1)

    def test_add_nonexistent_product_raises_404(self):
        """Контракт 2.2: Товар отсутствует в каталоге -> 404 PRODUCT_NOT_FOUND"""
        with self.assertRaises(ServiceError) as ctx:
            self.service.add_favorite("prod-nonexistent-999")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.code, "PRODUCT_NOT_FOUND")

    def test_add_missing_product_id_raises_400(self):
        """Контракт 2.2: Пустой ID товара -> 400 MISSING_PRODUCT_ID"""
        with self.assertRaises(ServiceError) as ctx:
            self.service.add_favorite("   ")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.code, "MISSING_PRODUCT_ID")

    def test_remove_favorite_success(self):
        """Контракт 2.3: Удаление товара из избранного"""
        self.service.add_favorite("prod-1")
        self.service.add_favorite("prod-2")
        self.assertEqual(len(self.service._items), 2)

        res = self.service.remove_favorite("prod-1")
        self.assertEqual(res["status"], "removed")
        self.assertEqual(res["product_id"], "prod-1")
        self.assertEqual(res["total_count"], 1)

    def test_remove_favorite_not_in_list_raises_404(self):
        """Контракт 2.3: Попытка удалить товар, которого нет в избранном -> 404 NOT_IN_FAVORITES"""
        with self.assertRaises(ServiceError) as ctx:
            self.service.remove_favorite("prod-3")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.code, "NOT_IN_FAVORITES")

    def test_get_favorites_enriched_dto(self):
        """Контракт 2.1 & Переговоры #3: Возвращается обогащенный список с ценами и КБЖУ"""
        self.service.add_favorite("prod-1") # 320 руб, 120 ккал
        self.service.add_favorite("prod-2") # 85 руб, 313 ккал

        fav_dto = self.service.get_favorites()
        self.assertEqual(fav_dto["total_count"], 2)
        self.assertEqual(fav_dto["total_price"], 405.0)
        self.assertEqual(fav_dto["total_calories"], 433)

        items = fav_dto["items"]
        self.assertEqual(len(items), 2)
        # Проверяем наличие всех доменных полей продукта
        first_item = items[0]
        self.assertEqual(first_item["id"], "prod-1")
        self.assertEqual(first_item["name"], "Филе грудки индейки су-вид")
        self.assertIn("added_at", first_item)
        self.assertIn("allergens", first_item)
        self.assertIn("tags", first_item)

    def test_clear_favorites(self):
        """Контракт 2.4: Полная очистка списка"""
        self.service.add_favorite("prod-1")
        self.service.add_favorite("prod-2")
        self.assertEqual(self.service.get_favorites()["total_count"], 2)

        res = self.service.clear()
        self.assertEqual(res["status"], "cleared")
        self.assertEqual(res["total_count"], 0)
        self.assertEqual(self.service.get_favorites()["total_count"], 0)

    def test_atomic_move_to_cart_success(self):
        """Контракт 2.5 & Переговоры #5: Атомарный перенос всех товаров в корзину с автоочисткой"""
        self.service.add_favorite("prod-1") # 320 руб
        self.service.add_favorite("prod-2") # 85 руб

        res = self.service.move_to_cart(clear_favorites=True)
        self.assertEqual(res["status"], "moved_to_cart")
        self.assertEqual(res["moved_items_count"], 2)
        self.assertEqual(res["favorites_count"], 0)
        self.assertIn("cart", res)
        self.assertEqual(res["cart"]["total_items"], 2)
        self.assertEqual(res["cart"]["subtotal"], 405.0)

        # Проверяем, что в сервисе избранного ничего не осталось
        self.assertEqual(self.service.get_favorites()["total_count"], 0)

    def test_move_empty_favorites_to_cart_raises_400(self):
        """Контракт 2.5: Ошибка при попытке перенести пустое избранное"""
        with self.assertRaises(ServiceError) as ctx:
            self.service.move_to_cart()
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.code, "EMPTY_FAVORITES")

    def test_favorites_limit_exceeded_raises_400(self):
        """Граничное условие: Превышение максимального лимита элементов"""
        # Лимит для теста установлен в 5
        products = PRODUCTS[:5]
        for p in products:
            self.service.add_favorite(p.id)

        # 6-й товар должен вызвать ошибку
        with self.assertRaises(ServiceError) as ctx:
            self.service.add_favorite(PRODUCTS[5].id)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.code, "LIMIT_EXCEEDED")

if __name__ == "__main__":
    unittest.main()
