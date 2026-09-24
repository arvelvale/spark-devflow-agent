import unittest
from datetime import date

from tinyledger import store


class StoreTest(unittest.TestCase):
    def test_add_appends_entry(self):
        entries = []
        store.add(entries, "餐饮", "12.5", "午饭", day=date(2026, 9, 1))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["category"], "餐饮")
        self.assertEqual(entries[0]["date"], "2026-09-01")

    def test_total_of_whole_numbers(self):
        entries = []
        store.add(entries, "交通", "3")
        store.add(entries, "交通", "4")
        self.assertEqual(store.total(entries), 7)

    def test_in_month_filters(self):
        entries = []
        store.add(entries, "餐饮", "10", day=date(2026, 8, 31))
        store.add(entries, "餐饮", "20", day=date(2026, 9, 1))
        self.assertEqual(len(store.in_month(entries, "2026-09")), 1)


if __name__ == "__main__":
    unittest.main()
