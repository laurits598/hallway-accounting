import re
import sqlite3
from pathlib import Path

from .google_sheets import fetch_sheet_data


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "kollegianeren.db"
KAFFEKLUB_PRICE_PER_PERSON = 30.0


def to_float(value):
    try:
        return float(str(value).replace(",", ".").replace("$", "").strip())
    except ValueError:
        return 0.0


def extract_room(name):
    match = re.search(r"\((\d+)\)", name)
    return match.group(1) if match else None

def normalize_room(room):
    room = str(room).strip()
    if len(room) == 2:
        return "5" + room
    return room

def clean_name(name):
    return re.sub(r"\s*\(\d+\)", "", name.replace("\n", " ")).strip()


def find_extra_club_row(data, club_name):
    """Find a named club below the 'Ekstra madklubber:' section."""
    in_extra_clubs = False
    target = club_name.strip().casefold()

    for row in data:
        values = [str(value).strip().casefold() for value in row]
        if "ekstra madklubber:" in values:
            in_extra_clubs = True
            continue
        if in_extra_clubs and target in values:
            return row
    return None


def get_resident_costs(data, include_kaffeklub=True):
    resident_names = [name.replace("\n", " ") for name in data[4][10:30]]

    accounting = {}

    for resident in resident_names:
        room = normalize_room(extract_room(resident))
        if room:
            accounting[room] = {
                "name": clean_name(resident),
                "amount": 0.0,
            }

    def add_row_costs(row, require_meal_count=True, price_override=None):
        if len(row) <= 33:
            return
        if require_meal_count and row[5] == "":
            return

        price_pp = price_override if price_override is not None else to_float(row[33])

        for resident, status in zip(resident_names, row[10:30]):
            if str(status).strip() != "":
                room = normalize_room(extract_room(resident))
                if room:
                    accounting[room]["amount"] += price_pp

    for row in data[5:36]:
        add_row_costs(row)

    kaffeklub_row = find_extra_club_row(data, "Kaffeklub")
    if include_kaffeklub and kaffeklub_row is not None:
        # Extra clubs do not necessarily populate the normal meal-count column.
        add_row_costs(
            kaffeklub_row,
            require_meal_count=False,
            price_override=KAFFEKLUB_PRICE_PER_PERSON,
        )

    return accounting


def get_kaffeklub_costs(data):
    """Return the fixed Kaffeklub charge separately from normal Foodclub."""
    resident_names = [name.replace("\n", " ") for name in data[4][10:30]]
    accounting = {}
    for resident in resident_names:
        room = normalize_room(extract_room(resident))
        if room:
            accounting[room] = {"name": clean_name(resident), "amount": 0.0}

    kaffeklub_row = find_extra_club_row(data, "Kaffeklub")
    if kaffeklub_row is None:
        return accounting

    for resident, status in zip(resident_names, kaffeklub_row[10:30]):
        if str(status).strip() not in {"", "0", "0.0", "0.00"}:
            room = normalize_room(extract_room(resident))
            if room:
                accounting[room]["amount"] += KAFFEKLUB_PRICE_PER_PERSON

    return accounting


def get_bluebook_summary(data):
    residents = [name.replace("\n", " ") for name in data[35][2:22]]
    balances = data[38][2:22]

    accounting = {}

    for resident, balance in zip(residents, balances):
        room = normalize_room(extract_room(resident))
        if room:
            accounting[room] = {
                "name": clean_name(resident),
                "amount": to_float(balance),
            }

    return accounting


def get_purchases_for_month(month, year, db_path=DEFAULT_DB_PATH):
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            r.name,
            r.room,
            p.quantity,
            p.price
        FROM purchases p
        JOIN residents r ON p.resident_id = r.rid
        WHERE p.timestamp >= ?
          AND p.timestamp < ?
    """, (start, end))

    accounting = {}

    for name, room, quantity, price in cursor.fetchall():
        room = normalize_room(room)
        accounting.setdefault(room, {"name": name, "amount": 0.0})
        accounting[room]["amount"] += quantity * price

    conn.close()
    return accounting


def print_monthly_summary(foodclub, bluebook, kiosk, kaffeklub=None, detailed=False):
    kaffeklub = kaffeklub or {}
    rooms = set(foodclub) | set(kaffeklub) | set(bluebook) | set(kiosk)

    print("\n" + "=" * 90)
    print("MONTHLY ACCOUNTING SUMMARY")
    print("=" * 90)
    if detailed:
        print(f"{'Room':<6} {'Name':<18} {'Foodclub':>12} {'Kaffeklub':>12} {'BlueBook':>12} {'Kiosk':>12} {'Total':>12}")
    else:
        print(f"{'Room':<6} {'Name':<18} {'Foodclub':>12} {'BlueBook':>12} {'Kiosk':>12} {'Total':>12}")
    print("-" * 90)

    for room in sorted(rooms, key=lambda x: int(x) if x.isdigit() else 9999):
        name = (
            foodclub.get(room, {}).get("name")
            or kaffeklub.get(room, {}).get("name")
            or bluebook.get(room, {}).get("name")
            or kiosk.get(room, {}).get("name")
            or "Unknown"
        )

        food = foodclub.get(room, {}).get("amount", 0.0)
        coffee = kaffeklub.get(room, {}).get("amount", 0.0)
        blue = bluebook.get(room, {}).get("amount", 0.0)
        kios = kiosk.get(room, {}).get("amount", 0.0)
        total = food + coffee + blue + kios

        if detailed:
            print(f"{room:<6} {name:<18} {food:>12.2f} {coffee:>12.2f} {blue:>12.2f} {kios:>12.2f} {total:>12.2f}")
        else:
            print(f"{room:<6} {name:<18} {food:>12.2f} {blue:>12.2f} {kios:>12.2f} {total:>12.2f}")

def main():
    foodclub_data = fetch_sheet_data("Madklub - Maj 2026")
    bluebook_data = fetch_sheet_data("May 2026 - Blue Book")
    accounting_foodclub = get_resident_costs(foodclub_data)
    accounting_bluebook = get_bluebook_summary(bluebook_data)
    accounting_kiosk = get_purchases_for_month(5, 2026)
    print_monthly_summary(accounting_foodclub, accounting_bluebook, accounting_kiosk)


if __name__ == "__main__":
    main()
