"""
Тесты Фичи B: Расчет динамических скидок корзины, аналитика БЖУ
и механизм Graceful Fallback при отсутствии прямых совпадений.
"""

import unittest
from app.services import calculate_cart_nutrition, search_products, get_theme_bundles

class FeatureBTestCase(unittest.TestCase):
    def test_discount_zero_under_1500(self):
        """Фича B: Корзина дешевле 1500 ₽ не получает скидку (0%)"""
        # prod-2 (85 ₽) * 10 = 850 ₽
        cart = calculate_cart_nutrition([{"product_id": "prod-2", "quantity": 10}])
        self.assertEqual(cart["subtotal"], 850.0)
        self.assertEqual(cart["discount_percent"], 0.0)
        self.assertEqual(cart["discount_rub"], 0.0)
        self.assertEqual(cart["final_price"], 850.0)

    def test_discount_7_percent_boundary(self):
        """Фича B: Корзина от 1500 ₽ до 2499 ₽ получает скидку 7%"""
        # prod-1 (320 ₽) * 5 = 1600 ₽ (> 1500 ₽)
        cart = calculate_cart_nutrition([{"product_id": "prod-1", "quantity": 5}])
        self.assertEqual(cart["subtotal"], 1600.0)
        self.assertEqual(cart["discount_percent"], 7.0)
        # 1600 * 0.07 = 112.0 ₽
        self.assertEqual(cart["discount_rub"], 112.0)
        self.assertEqual(cart["final_price"], 1488.0)

    def test_discount_12_percent_boundary(self):
        """Фича B: Корзина от 2500 ₽ получает максимальную скидку 12%"""
        # prod-5 (390 ₽) * 7 = 2730 ₽ (> 2500 ₽)
        cart = calculate_cart_nutrition([{"product_id": "prod-5", "quantity": 7}])
        self.assertEqual(cart["subtotal"], 2730.0)
        self.assertEqual(cart["discount_percent"], 12.0)
        # 2730 * 0.12 = 327.6 ₽
        self.assertEqual(cart["discount_rub"], 327.6)
        self.assertEqual(cart["final_price"], 2402.4)

    def test_macro_percentages_and_alerts(self):
        """Фича B: Расчет процентного баланса макронутриентов и выдача предупреждений"""
        # Гречка (много углеводов): 62.1 г углев vs 12.6 г белка vs 3.3 г жира
        cart = calculate_cart_nutrition([{"product_id": "prod-2", "quantity": 3}])
        macros = cart["macro_percentages"]
        self.assertGreater(macros["carbs"], 60.0)
        self.assertIn("protein", macros)
        self.assertIn("fat", macros)
        self.assertGreater(len(cart["nutrition_alerts"]), 0)

    def test_graceful_fallback_when_strict_price_zero_matches(self):
        """Фича B: Graceful Fallback возвращает альтернативы при слишком жесткой цене"""
        # В категории meat_poultry минимальная цена индейки 320 ₽.
        # Если искать мясо дешевле 260 ₽ без fallback -> 0 результатов.
        strict = search_products(category="meat_poultry", max_price=260.0, allow_fallback=False)
        self.assertEqual(len(strict), 0)

        # С allow_fallback=True сервис расширяет лимит и предлагает индейку (320 ₽ <= 260 * 1.3 = 338 ₽)
        fallback = search_products(category="meat_poultry", max_price=260.0, allow_fallback=True)
        self.assertGreater(len(fallback), 0)
        self.assertTrue(fallback[0].get("_fallback_match"))

    def test_regression_feature_a_preserved(self):
        """Регрессионная проверка: все контракты Фичи A продолжают работать в Фиче B"""
        prods = search_products(exclude_allergens=["lactose", "nuts"])
        for p in prods:
            self.assertNotIn("lactose", p["allergens"])
            self.assertNotIn("nuts", p["allergens"])

if __name__ == "__main__":
    unittest.main()
