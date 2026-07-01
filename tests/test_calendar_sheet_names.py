import unittest

from app.backend.server import _foodclub_sheet_names


class FoodclubSheetNamesTest(unittest.TestCase):
    def test_current_english_title_is_preferred(self):
        self.assertEqual(
            _foodclub_sheet_names(7, 2026),
            [
                "Foodclub - July 2026",
                "Foodclub - Juli 2026",
                "Madklub - July 2026",
                "Madklub - Juli 2026",
            ],
        )

    def test_identical_translations_are_not_duplicated(self):
        self.assertEqual(
            _foodclub_sheet_names(8, 2026),
            ["Foodclub - August 2026", "Madklub - August 2026"],
        )


if __name__ == "__main__":
    unittest.main()
