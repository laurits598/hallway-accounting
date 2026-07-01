import unittest
from datetime import date
from unittest.mock import patch

from app.backend import google_sheets


class FakeWorksheet:
    def __init__(self, values):
        self.values = values
        self.updates = []

    def get(self, cell_range):
        self.requested_range = cell_range
        return self.values

    def batch_update(self, updates):
        self.updates.extend(updates)


class FakeSpreadsheet:
    def __init__(self, worksheet):
        self.fake_worksheet = worksheet

    def worksheet(self, title):
        self.requested_title = title
        return self.fake_worksheet


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


if __name__ == "__main__":
    unittest.main()
