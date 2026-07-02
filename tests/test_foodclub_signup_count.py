import unittest

from app.backend.server import _foodclub_schedule_from_sheet


class FoodclubSignupCountTest(unittest.TestCase):
    def test_counts_nonempty_resident_signup_cells(self):
        row = [""] * 30
        row[2] = "2. July"
        row[5] = "29"
        row[6] = "Tacos"
        row[10] = "1"
        row[11] = "v"
        row[12] = "2"
        row[13] = "   "

        schedule = _foodclub_schedule_from_sheet([row], 7)

        self.assertEqual(schedule[2]["menu"], "Tacos")
        self.assertEqual(schedule[2]["signupCount"], 3)

    def test_ignores_rows_for_another_month(self):
        row = [""] * 30
        row[2] = "2. June"
        row[10] = "1"
        self.assertEqual(_foodclub_schedule_from_sheet([row], 7), {})


if __name__ == "__main__":
    unittest.main()
