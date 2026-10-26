"""
Базовые тесты целостности каталога товаров и тематических подборок.
"""

import unittest
from app.catalog import PRODUCTS, THEMES, PRODUCTS_BY_ID, THEMES_BY_ID, CATEGORIES

class CatalogTestCase(unittest.TestCase):
    def test_products_not_empty(self):
        self.assertGreaterEqual(len(PRODUCTS), 10, "Каталог должен содержать минимум 10 товаров")

    def test_all_products_valid_fields(self):
        for p in PRODUCTS:
            self.assertTrue(p.id.startswith("prod-"))
            self.assertGreater(p.price, 0, f"Товар {p.id} должен иметь положительную цену")
            self.assertGreaterEqual(p.calories, 0, f"Товар {p.id} калории >= 0")
            self.assertIn(p.category, CATEGORIES, f"Категория {p.category} не в списке допустимых")

    def test_themes_reference_valid_products(self):
        for theme in THEMES:
            self.assertGreater(len(theme.product_ids), 0, f"Тема {theme.id} не имеет товаров")
            for pid in theme.product_ids:
                self.assertIn(pid, PRODUCTS_BY_ID, f"Товар {pid} из темы {theme.id} отсутствует в каталоге")

if __name__ == "__main__":
    unittest.main()
