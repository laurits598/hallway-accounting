import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.backend import telegram_notifications


class TelegramNotificationsTest(unittest.IsolatedAsyncioTestCase):
    async def test_no_registrations_does_not_calculate_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            registrations = Path(directory) / "missing.json"
            with (
                patch.object(telegram_notifications, "REGISTRATIONS_FILE", registrations),
                patch.object(telegram_notifications, "build_accounting_summary") as build,
            ):
                result = await telegram_notifications.broadcast_monthly_balances(6, 2026)
        self.assertEqual(result, {"sent": 0, "failed": 0, "errors": []})
        build.assert_not_called()

    def test_balance_message_contains_total_and_month(self):
        summary = {
            "monthName": "Juni",
            "year": 2026,
            "sources": {"foodclub": True, "bluebook": True, "kiosk": True},
        }
        row = {
            "name": "Wilma",
            "room": "529",
            "foodclub": 100.0,
            "bluebook": 20.0,
            "kiosk": 3.5,
            "total": 123.5,
        }
        message = telegram_notifications.format_balance(summary, row)
        self.assertIn("Gangregning", message)
        self.assertIn("Juni 2026", message)
        self.assertIn("Total: 123.50 kr.", message)


if __name__ == "__main__":
    unittest.main()
