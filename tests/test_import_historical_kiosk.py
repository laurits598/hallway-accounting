import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from scripts.import_historical_kiosk import HISTORICAL_PRODUCT, import_directory


class HistoricalKioskImportTest(unittest.TestCase):
    def test_imports_totals_once_and_skips_existing_month(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "test.db"
            input_dir = root / "historical_kiosk"
            input_dir.mkdir()

            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY, name TEXT UNIQUE, retail_price REAL,
                    price REAL, image TEXT, active BOOLEAN
                );
                CREATE TABLE residents (
                    rid INTEGER PRIMARY KEY, name TEXT, room TEXT, active BOOLEAN
                );
                CREATE TABLE purchases (
                    id INTEGER PRIMARY KEY, product_id INTEGER, resident_id INTEGER,
                    quantity INTEGER, price REAL, timestamp TEXT
                );
                INSERT INTO residents (rid, name, room, active) VALUES
                    (1, 'One', '525', 1), (2, 'Two', '526', 1);
                """
            )
            connection.commit()
            connection.close()

            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["name", "room", "total", "Product"])
            sheet.append(["One", "525", "12.50", 2])
            sheet.append(["Two", "526", "20.25", 3])
            workbook.save(input_dir / "2_1_2026_2_28_2026.xlsx")

            first = import_directory(db_path, input_dir)
            second = import_directory(db_path, input_dir)
            self.assertEqual(first[0]["status"], "imported")
            self.assertEqual(second[0]["status"], "skipped")

            connection = sqlite3.connect(db_path)
            count, total = connection.execute(
                "SELECT COUNT(*), SUM(quantity * price) FROM purchases"
            ).fetchone()
            product = connection.execute("SELECT name, active FROM products").fetchone()
            connection.close()
            self.assertEqual(count, 2)
            self.assertAlmostEqual(total, 32.75)
            self.assertEqual(product, (HISTORICAL_PRODUCT, 0))


if __name__ == "__main__":
    unittest.main()
