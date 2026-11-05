import unittest

from practices.practice_04.src.calc import add, avg, median


class TestCalc(unittest.TestCase):
    def test_add_numbers(self):
        self.assertEqual(add(2, 3), 5.0)

    def test_add_numeric_strings(self):
        self.assertEqual(add("2", "3.5"), 5.5)

    def test_add_invalid(self):
        with self.assertRaises(ValueError):
            add("a", 1)

    def test_avg_simple(self):
        self.assertAlmostEqual(avg([1, 2, 3]), 2.0)

    def test_avg_numeric_strings(self):
        self.assertAlmostEqual(avg(["1", "2.5"]), 1.75)

    def test_avg_empty(self):
        with self.assertRaises(ValueError):
            avg([])

    def test_avg_rounding(self):
        self.assertEqual(avg([1, 2], ndigits=1), 1.5)
        self.assertEqual(avg([1, 2], ndigits=0), 2.0)
        with self.assertRaises(ValueError):
            avg([1, 2], ndigits="x")

    def test_median_basic(self):
        self.assertEqual(median([1, 3, 2]), 2.0)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)
        with self.assertRaises(ValueError):
            median([])


if __name__ == "__main__":
    unittest.main()
