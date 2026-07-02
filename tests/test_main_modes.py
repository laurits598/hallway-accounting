import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from app.backend import server


class MainModesTest(unittest.TestCase):
    def test_modes_are_mutually_exclusive_and_required(self):
        self.assertTrue(main.parse_args(["--test"]).test)
        self.assertTrue(main.parse_args(["--reset"]).reset)
        self.assertTrue(main.parse_args(["--kalender-refresh"]).kalender_refresh)
        selected = main.parse_args(["--month", "2", "--year", "2026"])
        self.assertEqual((selected.month, selected.year), (2, 2026))
        with self.assertRaises(SystemExit):
            main.parse_args([])
        with self.assertRaises(SystemExit):
            main.parse_args(["--test", "--reset"])
        with self.assertRaises(SystemExit):
            main.parse_args(["--month", "13", "--year", "2026"])
        with self.assertRaises(SystemExit):
            main.parse_args(["--month", "2"])

    @patch.object(main, "clear_small_teddy_month", return_value=31)
    @patch.object(main.sheet_handler, "delete_month_sheets", return_value=["Foodclub - July 2026"])
    def test_reset_targets_july_2026(self, delete_sheets, clear_teddy):
        main.main(["--reset"])
        delete_sheets.assert_called_once_with(7, 2026)
        clear_teddy.assert_called_once_with(7, 2026)

    @patch.object(main, "send_monthly_balances", return_value={"sent": 2, "failed": 0, "errors": []})
    @patch.object(main, "generate_next_small_teddy_month")
    @patch.object(main.monthly_summary, "main")
    @patch.object(main.sheet_handler, "main")
    def test_test_mode_broadcasts_the_accounting_month(
        self, generate_sheets, accounting, generate_teddy, send_balances
    ):
        main.main(["--test"])
        generate_sheets.assert_called_once_with()
        accounting.assert_called_once_with(main.monthly_summary.MONTH, main.monthly_summary.YEAR)
        generate_teddy.assert_called_once_with()
        send_balances.assert_called_once_with(main.monthly_summary.MONTH, main.monthly_summary.YEAR)

    @patch.object(main, "send_monthly_balances", return_value={"sent": 1, "failed": 0, "errors": []})
    @patch.object(main.monthly_summary, "main")
    def test_month_mode_summarizes_and_broadcasts_selected_month(self, accounting, send_balances):
        main.main(["--month", "2", "--year", "2026"])
        accounting.assert_called_once_with(2, 2026)
        send_balances.assert_called_once_with(2, 2026)

    @patch.object(main.sheet_handler, "main")
    def test_calendar_refresh_only_populates_foodclub_sheet(self, generate_sheet):
        main.main(["--kalender-refresh"])
        generate_sheet.assert_called_once_with()


class ClearSmallTeddyMonthTest(unittest.TestCase):
    def test_only_target_month_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "small_teddy.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["date", "room", "checked"])
                writer.writerow(["2026-06-30", "525", "true"])
                writer.writerow(["2026-07-01", "526", "false"])
                writer.writerow(["2026-07-31", "527", "false"])
                writer.writerow(["2026-08-01", "528", "false"])

            with patch.object(server, "SMALL_TEDDY_FILE", path):
                self.assertEqual(server.clear_small_teddy_month(7, 2026), 2)
                self.assertEqual(server.clear_small_teddy_month(7, 2026), 0)

            with path.open(newline="", encoding="utf-8") as file:
                dates = [row[0] for row in list(csv.reader(file))[1:]]
            self.assertEqual(dates, ["2026-06-30", "2026-08-01"])


if __name__ == "__main__":
    unittest.main()
