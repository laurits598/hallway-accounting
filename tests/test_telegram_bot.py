import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("telegram_bot", Path(__file__).parents[1] / "telegram-bot.py")
telegram_bot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_bot)


class TelegramBotTest(unittest.TestCase):
    def test_normalizes_two_digit_room(self):
        self.assertEqual(telegram_bot.normalize_room("29"), "529")
        self.assertEqual(telegram_bot.normalize_room("529"), "529")

    def test_parses_bluebook_description_and_comma_amount(self):
        self.assertEqual(
            telegram_bot.parse_bluebook_args(["Flour", "and", "oil", "|", "123,45"]),
            ("Flour and oil", 123.45),
        )

    def test_parses_foodclub_attendance(self):
        self.assertEqual(telegram_bot.parse_attendance(["v"]), "V")
        self.assertEqual(telegram_bot.parse_attendance(["G"]), "G")
        self.assertEqual(telegram_bot.parse_attendance(["02"]), "2")
        with self.assertRaises(ValueError):
            telegram_bot.parse_attendance(["no"])

    def test_registration_is_persisted_by_telegram_user(self):
        with tempfile.TemporaryDirectory() as directory:
            registrations = Path(directory) / "telegram_users.json"
            with patch.object(telegram_bot, "REGISTRATIONS_FILE", registrations):
                telegram_bot.save_registration(1234, "529")
                self.assertEqual(telegram_bot.load_registrations(), {"1234": "529"})
                self.assertEqual(json.loads(registrations.read_text()), {"1234": "529"})

    def test_current_balance_uses_current_month_and_room(self):
        summary = {
            "rows": [{"room": "529", "total": 123.0}],
            "monthName": "Juli",
            "year": 2026,
        }
        with patch.object(telegram_bot, "build_accounting_summary", return_value=summary) as build:
            result, row = telegram_bot.current_balance("529", datetime(2026, 7, 2))
        build.assert_called_once_with(7, 2026)
        self.assertIs(result, summary)
        self.assertEqual(row["total"], 123.0)


if __name__ == "__main__":
    unittest.main()
