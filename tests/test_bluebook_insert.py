import unittest
from datetime import date
from unittest.mock import patch

from app.backend import google_sheets


class FakeWorksheet:
    def __init__(self, values, title="July 2026 - Blue Book"):
        self.values = values
        self.title = title
        self.updates = []
        self.cell_updates = []

    def get(self, cell_range):
        self.requested_range = cell_range
        return self.values

    def batch_update(self, updates):
        self.updates.extend(updates)

    def update(self, cell, values):
        self.cell_updates.append((cell, values))


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self.fake_worksheet = worksheet

    def worksheet(self, title):
        self.requested_title = title
        return self.fake_worksheet

    def worksheets(self):
        return [self.fake_worksheet]


class FakeClient:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    def open_by_url(self, url):
        return self.spreadsheet


class BluebookInsertTest(unittest.TestCase):
    def test_inserts_into_first_empty_slot_for_registered_room(self):
        worksheet = FakeWorksheet([
            ["Kata (25)", "1/7/26", "Existing", 10],
            ["Martin (26)"],
        ])
        spreadsheet = FakeSpreadsheet(worksheet)
        with patch.object(google_sheets, "get_client", return_value=FakeClient(spreadsheet)):
            result = google_sheets.insert_bluebook_expense(
                "526", "Flour and oil", 123.45, date(2026, 7, 2)
            )

        self.assertEqual(spreadsheet.requested_title, "July 2026 - Blue Book")
        self.assertEqual(result["slot"], 1)
        self.assertEqual(worksheet.updates, [{
            "range": "B6:D6",
            "values": [["2/7/26", "Flour and oil", 123.45]],
        }])

    def test_does_not_overwrite_partially_used_slot(self):
        worksheet = FakeWorksheet([
            ["Kata (25)", "", "Existing description", ""],
        ])
        spreadsheet = FakeSpreadsheet(worksheet)
        with patch.object(google_sheets, "get_client", return_value=FakeClient(spreadsheet)):
            result = google_sheets.insert_bluebook_expense(
                "525", "New expense", 50, date(2026, 7, 2)
            )
        self.assertEqual(result["slot"], 2)
        self.assertEqual(worksheet.updates[0]["range"], "E5:G5")


class FoodclubAttendanceTest(unittest.TestCase):
    def test_sets_registered_room_on_requested_day_and_counts_signups(self):
        values = [[""] for _ in range(6)]
        values[4] = [""] * 30
        values[4][10] = "Kata (25)"
        values[5] = [""] * 30
        values[5][2] = "2. July"
        values[5][11] = "1"
        worksheet = FakeWorksheet(values, "Foodclub - July 2026")
        spreadsheet = FakeSpreadsheet(worksheet)
        with patch.object(google_sheets, "get_client", return_value=FakeClient(spreadsheet)):
            result = google_sheets.set_foodclub_attendance(
                "525", "V", date(2026, 7, 2)
            )

        self.assertEqual(worksheet.cell_updates, [("K6", [["V"]])])
        self.assertEqual(result["signupCount"], 2)
        self.assertEqual(result["previous"], "")


if __name__ == "__main__":
    unittest.main()
