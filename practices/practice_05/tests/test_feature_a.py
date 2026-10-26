"""
Тесты Фичи A: Входная валидация, исключение аллергенов и бюджетные ограничения.
"""

import unittest
from app.services import search_products, get_theme_bundles, ServiceError

class FeatureATestCase(unittest.TestCase):
    def test_allergen_filtering_strict(self):
        """Фича A: При исключении lactose ни один продукт с лактозой не должен попасть в результат"""
        prods = search_products(exclude_allergens=["lactose"])
        self.assertGreater(len(prods), 0)
        for p in prods:
            self.assertNotIn("lactose", p["allergens"], f"Товар {p['name']} содержит лактозу")

    def test_multi_allergen_exclusion(self):
        """Фича A: Исключение нескольких аллергенов одновременно (nuts, seafood)"""
        prods = search_products(exclude_allergens=["nuts", "seafood"])
        for p in prods:
            self.assertNotIn("nuts", p["allergens"])
            self.assertNotIn("seafood", p["allergens"])

    def test_theme_budget_limit(self):
        """Фича A: Валидация бюджета в тематических подборках"""
        bundles = get_theme_bundles(max_budget=450.0)
        for b in bundles:
            if b["actual_price"] <= 450.0:
                self.assertTrue(b["is_within_budget"])
            else:
                self.assertFalse(b["is_within_budget"])

    def test_invalid_negative_budget_rejection(self):
        """Фича A: Отрицательный бюджет не допускается"""
        with self.assertRaises(ServiceError) as ctx:
            get_theme_bundles(max_budget=-50.0)
        self.assertEqual(ctx.exception.code, "INVALID_BUDGET")

    def test_empty_query_rejection(self):
        """Фича A: Пустой поисковый запрос отклоняется с понятным кодом"""
        with self.assertRaises(ServiceError) as ctx:
            search_products(query="   ")
        self.assertEqual(ctx.exception.code, "EMPTY_QUERY")

    def test_unknown_category_rejection(self):
        """Фича A: Неизвестная категория отклоняется"""
        with self.assertRaises(ServiceError) as ctx:
            search_products(category="electronics")
        self.assertEqual(ctx.exception.code, "UNKNOWN_CATEGORY")

if __name__ == "__main__":
    unittest.main()
