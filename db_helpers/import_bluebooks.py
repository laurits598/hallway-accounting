#!/usr/bin/env python3
"""Populate Blue Book months and expenses from downloaded CSV files."""

import argparse
import csv
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "kollegianeren.db"
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "downloaded_sheets"
FILENAME_PATTERN = re.compile(r"^(\d{4})_(\d{2})_bluebook\.csv$", re.IGNORECASE)
EXPENSE_SLOTS = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
MONTH_NAMES = {
    "january": 1, "januar": 1, "february": 2, "februar": 2,
    "march": 3, "marts": 3, "april": 4, "may": 5, "maj": 5,
    "june": 6, "juni": 6, "july": 7, "juli": 7, "august": 8,
    "september": 9, "october": 10, "oktober": 10,
    "november": 11, "december": 12,
}


def normalize_name(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def normalize_room(value):
    room = value.strip()
    return f"5{room}" if len(room) == 2 and room.isdigit() else room


def parse_resident_label(value):
    text = str(value).replace("\n", " ").strip()
    leading_room = re.match(r"^(\d{2,3})\s+(.+)$", text)
    if leading_room:
        return leading_room.group(2).strip(), normalize_room(leading_room.group(1))
    trailing_room = re.search(r"\(\s*(\d{2,3})\s*\)", text)
    if trailing_room:
        name = re.sub(r"\s*\(\s*\d{2,3}\s*\)\s*", "", text).strip().rstrip(".")
        return name, normalize_room(trailing_room.group(1))
    return "", ""


def parse_amount(value):
    text = str(value).strip().replace("$", "").replace("kr", "").replace(" ", "")
    if "," in text and "." not in text:
        # Blue Book uses commas as thousands separators in the downloaded files.
        text = text.replace(",", "")
    else:
        text = text.replace(",", "")
    return float(text)


def parse_expense_date(value, sheet_year, sheet_month):
    text = str(value).strip().casefold()
    if not text:
        return None
    numbers = [int(number) for number in re.findall(r"\d+", text)]
    if not numbers:
        return None
    day = numbers[0]
    named_month = next((number for name, number in MONTH_NAMES.items() if name in text), None)
    month = named_month or (numbers[1] if len(numbers) >= 2 else sheet_month)
    year = numbers[2] if len(numbers) >= 3 else sheet_year
    if year < 100:
        year += 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


class Residents:
    def __init__(self, connection):
        self.connection = connection
        self.by_name = defaultdict(list)
        self.created = 0
        for rid, name, room in connection.execute("SELECT rid, name, room FROM residents"):
            self.by_name[normalize_name(name)].append((rid, normalize_room(room)))

    def resolve(self, name, room):
        candidates = self.by_name.get(normalize_name(name), [])
        exact_room = [rid for rid, candidate_room in candidates if candidate_room == room]
        if len(exact_room) == 1:
            return exact_room[0]
        if len(candidates) == 1:
            return candidates[0][0]
        if not name or not room:
            return None
        cursor = self.connection.execute(
            "INSERT INTO residents (name, room, active) VALUES (?, ?, 0)",
            (name, room),
        )
        rid = cursor.lastrowid
        self.by_name[normalize_name(name)].append((rid, room))
        self.created += 1
        return rid


def ensure_schema(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS bluebook_months (
            id INTEGER PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            sheet_name TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (year, month)
        )
    """)

    foreign_keys = list(connection.execute("PRAGMA foreign_key_list(bluebook_expenses)"))
    bmid_target = next((row[4] for row in foreign_keys if row[3] == "bmid"), None)
    if bmid_target not in {None, "id"}:
        connection.execute("DROP TABLE bluebook_expenses")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS bluebook_expenses (
            xid INTEGER PRIMARY KEY,
            bmid INTEGER NOT NULL,
            rid INTEGER,
            expense_date DATE,
            description TEXT,
            amount REAL NOT NULL,
            source_row INTEGER,
            source_slot INTEGER,
            FOREIGN KEY (bmid) REFERENCES bluebook_months(id) ON DELETE CASCADE,
            FOREIGN KEY (rid) REFERENCES residents(rid),
            UNIQUE (bmid, source_row, source_slot)
        )
    """)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    paths = sorted(args.source.glob("*_bluebook.csv"))
    if not paths:
        raise SystemExit(f"No Blue Book CSV files found in {args.source}")

    connection = sqlite3.connect(args.db)
    connection.execute("PRAGMA foreign_keys = ON")
    skipped = []
    null_dates = 0
    expense_count = 0

    try:
        ensure_schema(connection)
        residents = Residents(connection)
        with connection:
            connection.execute("DELETE FROM bluebook_expenses")
            connection.execute("DELETE FROM bluebook_months")

            for path in paths:
                match = FILENAME_PATTERN.match(path.name)
                if not match:
                    skipped.append((path.name, None, None, "invalid filename"))
                    continue
                year, month = map(int, match.groups())
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.reader(handle))
                cursor = connection.execute(
                    "INSERT INTO bluebook_months (year, month, sheet_name) VALUES (?, ?, ?)",
                    (year, month, path.name),
                )
                bmid = cursor.lastrowid

                for row_index, row in enumerate(rows[4:], start=5):
                    label = row[0].strip() if row else ""
                    name, room = parse_resident_label(label)
                    if not name:
                        continue
                    rid = residents.resolve(name, room)
                    for slot, (date_column, description_column, amount_column) in enumerate(EXPENSE_SLOTS, start=1):
                        values = [row[column].strip() if column < len(row) else "" for column in (date_column, description_column, amount_column)]
                        if not any(values):
                            continue
                        if not values[2]:
                            skipped.append((path.name, row_index, slot, "missing amount"))
                            continue
                        try:
                            amount = parse_amount(values[2])
                        except ValueError:
                            skipped.append((path.name, row_index, slot, f"invalid amount {values[2]!r}"))
                            continue
                        expense_date = parse_expense_date(values[0], year, month)
                        if values[0] and expense_date is None:
                            null_dates += 1
                        connection.execute(
                            """INSERT INTO bluebook_expenses
                               (bmid, rid, expense_date, description, amount, source_row, source_slot)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (bmid, rid, expense_date, values[1] or None, amount, row_index, slot),
                        )
                        expense_count += 1

        print("Blue Book import complete")
        print(f"  CSV files read:       {len(paths)}")
        print(f"  Residents created:    {residents.created}")
        print(f"  Expenses inserted:    {expense_count}")
        print(f"  Invalid dates kept as NULL: {null_dates}")
        print(f"  Skipped slots:        {len(skipped)}")
        for filename, row, slot, reason in skipped:
            location = f" row {row}, slot {slot}" if row else ""
            print(f"    - {filename}{location}: {reason}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
