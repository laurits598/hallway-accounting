#!/usr/bin/env python3
"""Populate residents, foodclub_events and foodclub_attended from CSVs."""

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
FILENAME_PATTERN = re.compile(r"^(\d{4})_(\d{2})_foodclub\.csv$", re.IGNORECASE)
MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def normalize_name(value):
    value = re.sub(r"\(\s*\d+\s*\)", "", str(value).replace("\n", " "))
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in value if character.isalnum())


def clean_name(value):
    return re.sub(r"\s*\(\s*\d+\s*\)\s*", "", str(value).replace("\n", " ")).strip().rstrip(".")


def normalize_room(value):
    room = str(value).strip()
    return f"5{room}" if len(room) == 2 and room.isdigit() else room


def header_room(value):
    match = re.search(r"\(\s*(\d+)\s*\)", str(value))
    return normalize_room(match.group(1)) if match else ""


def parse_number(value):
    text = str(value).strip().replace(" ", "").replace("kr", "")
    if not text:
        return 0.0
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text:
        text = text.replace(",", "")
    return float(text)


def participant_quantity(value):
    text = str(value).strip()
    if not text or text in {"0", "0.0", "0.00"}:
        return 0.0
    try:
        return max(0.0, parse_number(text))
    except ValueError:
        return 1.0


def parse_event_date(value, sheet_year, sheet_month):
    match = re.match(r"^(\d{1,2})\.\s*([A-Za-z]+)?", str(value).strip())
    if not match:
        return None
    event_month = MONTH_NUMBERS.get((match.group(2) or "").casefold(), sheet_month)
    event_year = sheet_year
    if sheet_month == 1 and event_month == 12:
        event_year -= 1
    elif sheet_month == 12 and event_month == 1:
        event_year += 1
    return date(event_year, event_month, int(match.group(1))).isoformat()


def find_layout(rows):
    for row_index, row in enumerate(rows):
        headers = [value.strip().casefold() for value in row]
        if "date" not in headers or "total" not in headers or "dinner time" not in headers:
            continue
        price_pp = "price pp." if "price pp." in headers else "price pp"
        if price_pp not in headers:
            continue
        return {
            "header_row": row_index,
            "date": headers.index("date") + 1,
            "calendar": headers.index("calender") if "calender" in headers else None,
            "chef": headers.index("chef"),
            "menu": headers.index("menu"),
            "participant_start": headers.index("dinner time") + 1,
            "participant_end": headers.index("total"),
            "total_price": headers.index("price"),
            "price_per_person": headers.index(price_pp),
        }
    raise ValueError("Foodclub header row not found")


def cell(row, column):
    if column is None or column >= len(row):
        return ""
    return row[column].strip()


def read_file(path, year, month):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    layout = find_layout(rows)
    header = rows[layout["header_row"]]
    participant_headers = header[layout["participant_start"]:layout["participant_end"]]

    marker = next(
        (
            index for index, row in enumerate(rows[layout["header_row"] + 1:], layout["header_row"] + 1)
            if any(value.strip().casefold() == "ekstra madklubber:" for value in row)
        ),
        len(rows),
    )

    events = []
    for row in rows[layout["header_row"] + 1:marker]:
        event_date = parse_event_date(cell(row, layout["date"]), year, month)
        if not event_date:
            continue
        quantities = [
            participant_quantity(value)
            for value in row[layout["participant_start"]:layout["participant_end"]]
        ]
        attendance_values = [
            value.strip()
            for value in row[layout["participant_start"]:layout["participant_end"]]
        ]
        if not any(quantities):
            continue
        events.append({
            "event_date": event_date,
            "chef_room": normalize_room(cell(row, layout["chef"])),
            "dish": cell(row, layout["menu"]) or None,
            "price_per_person": parse_number(cell(row, layout["price_per_person"])),
            "total_price": parse_number(cell(row, layout["total_price"])),
            "notes": cell(row, layout["calendar"]) or None,
            "quantities": quantities,
            "attendance_values": attendance_values,
            "source": path.name,
        })
    return participant_headers, events


class Residents:
    def __init__(self, connection):
        self.connection = connection
        self.by_name = defaultdict(list)
        self.created = 0
        for rid, name, room in connection.execute("SELECT rid, name, room FROM residents"):
            self.by_name[normalize_name(name)].append((rid, normalize_room(room)))

    def resolve(self, header):
        name = clean_name(header)
        key = normalize_name(name)
        room = header_room(header)
        candidates = self.by_name.get(key, [])
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
        self.by_name[key].append((rid, room))
        self.created += 1
        return rid


def verify_schema(connection):
    required = {
        "residents": {"rid", "name", "room", "active"},
        "foodclub_events": {
            "fid", "event_date", "chef_rid", "dish",
            "price_per_person", "total_price", "notes",
        },
        "foodclub_attended": {"fid", "rid", "attendance_value"},
    }
    for table, expected in required.items():
        actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        missing = expected - actual
        if missing:
            raise RuntimeError(f"{table} is missing columns: {', '.join(sorted(missing))}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    paths = sorted(args.source.glob("*_foodclub.csv"))
    if not paths:
        raise SystemExit(f"No Foodclub CSV files found in {args.source}")

    connection = sqlite3.connect(args.db)
    connection.execute("PRAGMA foreign_keys = ON")
    verify_schema(connection)
    residents = Residents(connection)
    candidates = defaultdict(list)
    skipped = []

    try:
        for path in paths:
            match = FILENAME_PATTERN.match(path.name)
            if not match:
                skipped.append((path.name, "invalid filename"))
                continue
            year, month = map(int, match.groups())
            try:
                headers, events = read_file(path, year, month)
                resident_ids = [residents.resolve(header) for header in headers]
                residents_by_room = {
                    header_room(header): rid
                    for header, rid in zip(headers, resident_ids)
                    if rid is not None and header_room(header)
                }
                for event in events:
                    event["resident_ids"] = resident_ids
                    event["chef_rid"] = residents_by_room.get(event["chef_room"])
                    candidates[event["event_date"]].append(event)
            except Exception as error:
                skipped.append((path.name, str(error)))

        selected = []
        duplicate_dates = 0
        for event_date, options in candidates.items():
            if len(options) > 1:
                duplicate_dates += 1
            selected.append(max(options, key=lambda event: (sum(event["quantities"]), event["total_price"])))

        with connection:
            # Remove tables from the superseded month/event schema. Their foreign
            # keys target the old foodclub_events.id column and otherwise prevent
            # the replacement event table from being cleared.
            connection.execute("DROP TABLE IF EXISTS foodclub_participants")
            connection.execute("DROP TABLE IF EXISTS foodclub_months")
            connection.execute("DELETE FROM foodclub_attended")
            connection.execute("DELETE FROM foodclub_events")
            attendance_count = 0
            unresolved_chefs = 0
            for event in sorted(selected, key=lambda item: item["event_date"]):
                if event["chef_room"] and event["chef_rid"] is None:
                    unresolved_chefs += 1
                cursor = connection.execute(
                    """INSERT INTO foodclub_events
                       (event_date, chef_rid, dish, price_per_person, total_price, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        event["event_date"], event["chef_rid"], event["dish"],
                        event["price_per_person"], event["total_price"], event["notes"],
                    ),
                )
                fid = cursor.lastrowid
                for rid, quantity, attendance_value in zip(
                    event["resident_ids"],
                    event["quantities"],
                    event["attendance_values"],
                ):
                    if rid is None or quantity <= 0:
                        continue
                    attendance_cursor = connection.execute(
                        """INSERT OR IGNORE INTO foodclub_attended
                           (fid, rid, attendance_value) VALUES (?, ?, ?)""",
                        (fid, rid, attendance_value),
                    )
                    attendance_count += attendance_cursor.rowcount

        print("Foodclub import complete")
        print(f"  CSV files read:       {len(paths) - len(skipped)}")
        print(f"  Residents created:    {residents.created}")
        print(f"  Events inserted:      {len(selected)}")
        print(f"  Attendance rows:      {attendance_count}")
        print(f"  Duplicate dates resolved: {duplicate_dates}")
        print(f"  Unresolved chefs:     {unresolved_chefs}")
        print(f"  Skipped files:        {len(skipped)}")
        for filename, reason in skipped:
            print(f"    - {filename}: {reason}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
