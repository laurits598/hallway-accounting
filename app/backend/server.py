#!/usr/bin/env python3
import argparse
import calendar as calendar_module
import csv
import http.server
import json
import os
import re
import sqlite3
import urllib.parse
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "app" / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
ASSETS_DIR = PROJECT_ROOT / "assets"
DB_PATH = PROJECT_ROOT / "kollegianeren.db"

print(f"[SERVER] Database path: {DB_PATH}")
print(f"[SERVER] Database exists: {DB_PATH.exists()}")


DANISH_MONTHS = {
    1: "Januar", 2: "Februar", 3: "Marts", 4: "April", 5: "Maj", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "December",
}

ENGLISH_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def _foodclub_sheet_names(month, year):
    """Accepted Foodclub titles, with the current English format first."""
    candidates = [
        f"Foodclub - {ENGLISH_MONTHS[month]} {year}",
        f"Foodclub - {DANISH_MONTHS[month]} {year}",
        f"Madklub - {ENGLISH_MONTHS[month]} {year}",
        f"Madklub - {DANISH_MONTHS[month]} {year}",
    ]
    # Some month names are identical in both languages. Preserve priority
    # while avoiding redundant Google worksheet lookups.
    return list(dict.fromkeys(candidates))


def _normalize_room(room):
    """Mirror of app.backend.accounting.normalize_room for the kiosk fallback."""
    room = str(room or "").strip()
    if len(room) == 2:
        return "5" + room
    return room


def _csv_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "ja", "checked", "done", "x"}


def _read_small_teddy_rows():
    rows = []
    if not SMALL_TEDDY_FILE.exists():
        return rows

    with open(SMALL_TEDDY_FILE, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            date_raw = (row[0] if len(row) > 0 else "").strip()
            room = (row[1] if len(row) > 1 else "").strip()
            checked_raw = (row[2] if len(row) > 2 else "").strip()
            if not date_raw:
                continue
            if date_raw.lower() == "date":
                continue
            rows.append({
                "date": date_raw,
                "room": room,
                "checked": _csv_bool(checked_raw),
            })
    return rows


def _write_small_teddy_rows(rows):
    with open(SMALL_TEDDY_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "room", "checked"])
        for row in rows:
            writer.writerow([
                row.get("date", ""),
                row.get("room", ""),
                "true" if row.get("checked") else "false",
            ])


def _small_teddy_rooms():
    rooms = []
    try:
        with open(SEED_DIR / "residents.json", encoding="utf-8") as fh:
            for entry in json.load(fh):
                if entry.get("active", True) is False:
                    continue
                room = _normalize_room(entry.get("room"))
                if room:
                    rooms.append(room)
    except Exception:
        pass
    return sorted(set(rooms), key=lambda value: int(value) if str(value).isdigit() else str(value))


def _latest_small_teddy_month(rows):
    months = []
    for row in rows:
        match = re.match(r"^(\d{4})-(\d{2})-\d{2}$", row.get("date", ""))
        if match:
            months.append((int(match.group(1)), int(match.group(2))))
    return max(months) if months else None


def generate_next_small_teddy_month():
    rows = _read_small_teddy_rows()
    latest = _latest_small_teddy_month(rows)
    if not latest:
        raise ValueError("small_teddy.csv does not contain any monthly source data")

    current_year, current_month = latest
    next_year = current_year + 1 if current_month == 12 else current_year
    next_month = 1 if current_month == 12 else current_month + 1

    if any(row.get("date", "").startswith(f"{next_year:04d}-{next_month:02d}-") for row in rows):
        raise ValueError(f"small_teddy.csv already contains {next_year:04d}-{next_month:02d}")

    resident_rooms = _small_teddy_rooms()
    if not resident_rooms:
        raise ValueError("No resident rooms found in data/seed/residents.json")

    current_rows = [row for row in rows if row.get("date", "").startswith(f"{current_year:04d}-{current_month:02d}-")]
    unchecked_rooms = {
        _normalize_room(row.get("room"))
        for row in current_rows
        if row.get("room") and not row.get("checked")
    }

    days_in_month = calendar_module.monthrange(next_year, next_month)[1]
    counts = {room: 1 for room in resident_rooms}
    for room in unchecked_rooms:
        if room in counts:
            counts[room] += 2

    assigned = sum(counts.values())
    if assigned > days_in_month:
        raise ValueError(
            f"Cannot generate {next_year:04d}-{next_month:02d}: {assigned} assignments exceed {days_in_month} days"
        )

    room_order = resident_rooms[:]
    room_index = {room: index for index, room in enumerate(room_order)}
    remaining = days_in_month - assigned
    while remaining > 0:
        candidate = min(room_order, key=lambda room: (counts[room], room_index[room]))
        counts[candidate] += 1
        remaining -= 1

    last_room = _normalize_room(current_rows[-1]["room"]) if current_rows and current_rows[-1].get("room") else room_order[-1]
    start_index = (room_index[last_room] + 1) % len(room_order) if last_room in room_index else 0
    cycle = room_order[start_index:] + room_order[:start_index]
    remaining_counts = counts.copy()

    schedule_rooms = []
    while len(schedule_rooms) < days_in_month:
        progressed = False
        for room in cycle:
            if remaining_counts[room] <= 0:
                continue
            schedule_rooms.append(room)
            remaining_counts[room] -= 1
            progressed = True
            if len(schedule_rooms) >= days_in_month:
                break
        if not progressed:
            break

    if len(schedule_rooms) != days_in_month:
        raise ValueError("Failed to build a full next-month schedule")

    new_rows = [
        {"date": f"{next_year:04d}-{next_month:02d}-{day:02d}", "room": room, "checked": False}
        for day, room in enumerate(schedule_rooms, start=1)
    ]
    _write_small_teddy_rows(rows + new_rows)

    return {
        "generatedMonth": f"{next_year:04d}-{next_month:02d}",
        "days": days_in_month,
        "uncheckedFromPreviousMonth": sorted(unchecked_rooms, key=lambda value: int(value) if str(value).isdigit() else str(value)),
        "counts": counts,
    }


def update_small_teddy_check(date_str, checked):
    rows = _read_small_teddy_rows()
    updated = False
    for row in rows:
        if row["date"] == date_str:
            row["checked"] = bool(checked)
            updated = True
            break
    if not updated:
        raise KeyError(f"No small teddy row found for {date_str}")
    _write_small_teddy_rows(rows)


def clear_small_teddy_month(month, year):
    """Remove all Small Teddy entries for one month and return their count."""
    prefix = f"{year:04d}-{month:02d}-"
    rows = _read_small_teddy_rows()
    remaining = [row for row in rows if not row.get("date", "").startswith(prefix)]
    removed = len(rows) - len(remaining)
    if removed:
        _write_small_teddy_rows(remaining)
    return removed


def _kiosk_fallback(month, year):
    """Fallback kiosk summary straight from SQLite.

    Used only when the Google integration cannot be imported, so the
    accounting page still works. Mirrors overview.get_purchases_for_month.
    """
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year + 1:04d}-01-01" if month == 12 else f"{year:04d}-{month + 1:02d}-01"

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.name, r.room, p.quantity, p.price
        FROM purchases p
        JOIN residents r ON p.resident_id = r.rid
        WHERE p.timestamp >= ? AND p.timestamp < ?
        """,
        (start, end),
    )
    accounting = {}
    for name, room, quantity, price in cursor.fetchall():
        room = _normalize_room(room)
        accounting.setdefault(room, {"name": name, "amount": 0.0})
        accounting[room]["amount"] += (quantity or 0) * (price or 0)
    conn.close()
    return accounting


def build_accounting_summary(month, year):
    """Combine Foodclub + Blue Book + Kiosk into one monthly summary.

    Reuses the existing functions in app.backend.accounting without
    changing them. Each source degrades independently: if Google Sheets is not
    reachable the page still renders with whatever loaded (typically Kiosk).
    """
    sources = {"foodclub": False, "bluebook": False, "kiosk": False}
    errors = {}
    foodclub, bluebook, kiosk = {}, {}, {}

    try:
        from app.backend.accounting import (
            get_resident_costs,
            get_bluebook_summary,
            get_purchases_for_month,
        )
        from app.backend.google_sheets import (
            fetch_first_available_sheet_data,
            fetch_sheet_data,
        )
        have_overview = True
    except Exception as exc:  # google libs missing, etc.
        have_overview = False
        errors["overview_import"] = str(exc)

    # Kiosk (local DB) -- always attempt, even without google libraries.
    try:
        if have_overview:
            kiosk = get_purchases_for_month(month, year, db_path=str(DB_PATH))
        else:
            kiosk = _kiosk_fallback(month, year)
        sources["kiosk"] = True
    except Exception as exc:
        errors["kiosk"] = str(exc)

    # Foodclub + Blue Book (Google Sheets) -- best effort.
    if have_overview:
        bluebook_sheet = f"{ENGLISH_MONTHS[month]} {year} - Blue Book"
        try:
            foodclub = get_resident_costs(
                fetch_first_available_sheet_data(_foodclub_sheet_names(month, year))
            )
            sources["foodclub"] = True
        except Exception as exc:
            errors["foodclub"] = str(exc)
        try:
            bluebook = get_bluebook_summary(fetch_sheet_data(bluebook_sheet))
            sources["bluebook"] = True
        except Exception as exc:
            errors["bluebook"] = str(exc)

    rooms = set(foodclub) | set(bluebook) | set(kiosk)
    rows = []
    for room in sorted(rooms, key=lambda x: int(x) if str(x).isdigit() else 9999):
        name = (
            foodclub.get(room, {}).get("name")
            or bluebook.get(room, {}).get("name")
            or kiosk.get(room, {}).get("name")
            or "Ukendt"
        )
        food = round(float(foodclub.get(room, {}).get("amount", 0.0)), 2)
        blue = round(float(bluebook.get(room, {}).get("amount", 0.0)), 2)
        kios = round(float(kiosk.get(room, {}).get("amount", 0.0)), 2)
        rows.append({
            "room": room,
            "name": name,
            "foodclub": food,
            "bluebook": blue,
            "kiosk": kios,
            "total": round(food + blue + kios, 2),
        })

    totals = {
        "foodclub": round(sum(r["foodclub"] for r in rows), 2),
        "bluebook": round(sum(r["bluebook"] for r in rows), 2),
        "kiosk": round(sum(r["kiosk"] for r in rows), 2),
        "total": round(sum(r["total"] for r in rows), 2),
    }

    return {
        "month": month,
        "year": year,
        "monthName": DANISH_MONTHS.get(month, str(month)),
        "rows": rows,
        "totals": totals,
        "sources": sources,
        "errors": errors,
        "generatedAt": datetime.now().isoformat(),
    }


SMALL_TEDDY_FILE = DATA_DIR / "small_teddy.csv"
FOODCLUB_MONTH_TO_NUM = {
    **{name.lower(): num for num, name in ENGLISH_MONTHS.items()},
    **{name.lower(): num for num, name in DANISH_MONTHS.items()},
}
WEEKDAYS_DA = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]


def _residents_by_room():
    """Map normalized room -> current resident name.

    The SQLite residents table also contains historical residents imported for
    accounting.  The current roster used by the frontend lives in the seed
    file, so it must take precedence when calendar assignments are labelled.
    Rooms missing from that roster are intentionally left unnamed rather than
    being labelled with an arbitrary historical occupant from SQLite.
    """
    out = {}
    try:
        with open(SEED_DIR / "residents.json", encoding="utf-8") as fh:
            for entry in json.load(fh):
                if entry.get("active", True) is False:
                    continue
                room = _normalize_room(entry.get("room"))
                if room and entry.get("name"):
                    out[room] = entry["name"]
    except Exception:
        pass

    return out


def _small_teddy_for_month(month, year):
    """Read the simple sample sheet (columns: date, room, checked).

    Accepts an ISO date (YYYY-MM-DD) or a bare day-of-month in the first column.
    Returns ({day:int -> {room:str, checked:bool}}, loaded:bool).
    """
    schedule = {}
    if not SMALL_TEDDY_FILE.exists():
        return schedule, False
    try:
        for row in _read_small_teddy_rows():
            date_raw = row["date"]
            room = row["room"]
            if not room:
                continue
            iso = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", date_raw)
            if iso:
                y, mo, day = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
                if y == year and mo == month:
                    schedule[day] = {"room": room, "checked": row["checked"]}
            elif date_raw.isdigit():
                schedule[int(date_raw)] = {"room": room, "checked": row["checked"]}
        return schedule, True
    except Exception:
        return schedule, False


def _foodclub_schedule_from_sheet(data, month):
    """Parse the Madklub sheet (get_all_values) into {day:int -> {room, menu}}.

    Day rows hold the date in column 2 (e.g. "1. June"), the responsible cook's
    room in column 5 (the "Chef" column) and the menu in column 6.
    """
    schedule = {}
    date_re = re.compile(r"(\d{1,2})\s*\.\s*([A-Za-z]+)")
    for row in data:
        if len(row) <= 6:
            continue
        match = date_re.search(str(row[2]))
        if not match:
            continue
        if FOODCLUB_MONTH_TO_NUM.get(match.group(2).lower()) != month:
            continue
        day = int(match.group(1))
        chef = str(row[5]).strip()
        menu = str(row[6]).strip()
        if chef or menu:
            schedule[day] = {"room": chef, "menu": menu}
    return schedule


def build_calendar(month, year):
    """Per-day calendar: foodclub responsible (from Madklub) + small teddy (sample sheet)."""
    sources = {"foodclub": False, "smallTeddy": False}
    errors = {}
    names = _residents_by_room()

    teddy_schedule, teddy_ok = _small_teddy_for_month(month, year)
    sources["smallTeddy"] = teddy_ok

    foodclub_schedule = {}
    try:
        from app.backend.google_sheets import fetch_first_available_sheet_data
        sheet = fetch_first_available_sheet_data(_foodclub_sheet_names(month, year))
        foodclub_schedule = _foodclub_schedule_from_sheet(sheet, month)
        sources["foodclub"] = True
    except Exception as exc:
        errors["foodclub"] = str(exc)

    days_in_month = calendar_module.monthrange(year, month)[1]
    days = []
    for day in range(1, days_in_month + 1):
        foodclub = None
        entry = foodclub_schedule.get(day)
        if entry:
            room = _normalize_room(entry.get("room"))
            foodclub = {"room": room, "name": names.get(room), "menu": entry.get("menu") or ""}

        small_teddy = None
        teddy_entry = teddy_schedule.get(day)
        if teddy_entry:
            room = _normalize_room(teddy_entry.get("room"))
            small_teddy = {"room": room, "name": names.get(room)}

        days.append({
            "day": day,
            "date": f"{year:04d}-{month:02d}-{day:02d}",
            "weekday": calendar_module.weekday(year, month, day),  # Mon=0 .. Sun=6
            "foodclub": foodclub,
            "smallTeddy": small_teddy,
            "smallTeddyDone": bool(teddy_entry and teddy_entry.get("checked")),
        })

    return {
        "month": month,
        "year": year,
        "monthName": DANISH_MONTHS.get(month, str(month)),
        "days": days,
        "sources": sources,
        "errors": errors,
        "generatedAt": datetime.now().isoformat(),
    }


def build_foodclub_widget_payload(target_date):
    cal = build_calendar(target_date.month, target_date.year)
    day_data = next((day for day in cal["days"] if day["date"] == target_date.strftime("%Y-%m-%d")), None)
    foodclub = day_data.get("foodclub") if day_data else None
    weekday_index = calendar_module.weekday(target_date.year, target_date.month, target_date.day)
    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "weekday": WEEKDAYS_DA[weekday_index],
        "displayDate": f"{WEEKDAYS_DA[weekday_index]} {target_date.day}. {DANISH_MONTHS[target_date.month].lower()} {target_date.year}",
        "hasFoodclub": bool(foodclub),
        "foodclubName": foodclub.get("name") if foodclub else "",
        "foodclubRoom": foodclub.get("room") if foodclub else "",
        "menu": foodclub.get("menu") if foodclub else "",
        "sources": cal.get("sources", {}),
        "errors": cal.get("errors", {}),
        "generatedAt": datetime.now().isoformat(),
    }


class SpaRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def translate_path(self, path):
        """Serve only the frontend plus explicitly public assets and seed data."""
        request_path = urllib.parse.unquote(urllib.parse.urlparse(path).path)
        public_roots = {
            "/assets/": ASSETS_DIR,
            "/data/seed/": SEED_DIR,
        }
        for prefix, public_root in public_roots.items():
            if request_path.startswith(prefix):
                candidate = (public_root / request_path[len(prefix):]).resolve()
                if candidate == public_root or public_root in candidate.parents:
                    return str(candidate)
                return str(FRONTEND_DIR / "__not_found__")
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/purchases":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                conn = sqlite3.connect(str(DB_PATH))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        p.id,
                        p.product_id,
                        pr.name as productName,
                        p.resident_id,
                        r.name as residentName,
                        r.room,
                        p.quantity,
                        p.price as unitPrice,
                        p.timestamp
                    FROM purchases p
                    JOIN products pr ON p.product_id = pr.id
                    JOIN residents r ON p.resident_id = r.rid
                    ORDER BY p.timestamp DESC
                """)
                rows = cursor.fetchall()
                purchases = []
                for row in rows:
                    purchases.append({
                        "id": f"purchase-{row['id']}",
                        "productId": f"product-{row['product_id']}",
                        "productName": row["productName"],
                        "residentId": f"resident-{row['resident_id']}",
                        "residentName": row["residentName"],
                        "room": row["room"],
                        "quantity": row["quantity"],
                        "unitPrice": row["unitPrice"],
                        "timestamp": row["timestamp"]
                    })
                conn.close()
                print(f"[GET] Returning {len(purchases)} purchases")
                self.wfile.write(json.dumps(purchases).encode())
            except Exception as e:
                print(f"[ERROR] GET /api/purchases failed: {e}")
                self.wfile.write(json.dumps([]).encode())
            return

        if self.path.split("?", 1)[0] == "/api/accounting":
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            now = datetime.now()

            def _int_param(key, default):
                try:
                    return int(params.get(key, [default])[0])
                except (TypeError, ValueError):
                    return default

            month = _int_param("month", now.month)
            year = _int_param("year", now.year)
            month = min(12, max(1, month))

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                summary = build_accounting_summary(month, year)
                src = summary["sources"]
                print(
                    f"[GET] /api/accounting {month}/{year} -> "
                    f"foodclub={src['foodclub']} bluebook={src['bluebook']} kiosk={src['kiosk']} "
                    f"({len(summary['rows'])} rows)"
                )
                self.wfile.write(json.dumps(summary).encode())
            except Exception as e:
                print(f"[ERROR] GET /api/accounting failed: {e}")
                self.wfile.write(json.dumps({
                    "month": month, "year": year, "rows": [],
                    "totals": {"foodclub": 0, "bluebook": 0, "kiosk": 0, "total": 0},
                    "sources": {"foodclub": False, "bluebook": False, "kiosk": False},
                    "errors": {"server": str(e)},
                }).encode())
            return

        if self.path.split("?", 1)[0] == "/api/calendar":
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            now = datetime.now()

            def _int_param(key, default):
                try:
                    return int(params.get(key, [default])[0])
                except (TypeError, ValueError):
                    return default

            month = min(12, max(1, _int_param("month", now.month)))
            year = _int_param("year", now.year)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                cal = build_calendar(month, year)
                src = cal["sources"]
                print(
                    f"[GET] /api/calendar {month}/{year} -> "
                    f"foodclub={src['foodclub']} smallTeddy={src['smallTeddy']} ({len(cal['days'])} days)"
                )
                self.wfile.write(json.dumps(cal).encode())
            except Exception as e:
                print(f"[ERROR] GET /api/calendar failed: {e}")
                self.wfile.write(json.dumps({
                    "month": month, "year": year, "days": [],
                    "sources": {"foodclub": False, "smallTeddy": False},
                    "errors": {"server": str(e)},
                }).encode())
            return

        if self.path.split("?", 1)[0] == "/api/widgy/foodclub":
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            date_raw = params.get("date", [""])[0]
            try:
                target_date = datetime.strptime(date_raw, "%Y-%m-%d") if date_raw else datetime.now()
            except ValueError:
                target_date = datetime.now()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            try:
                payload = build_foodclub_widget_payload(target_date)
                print(
                    f"[GET] /api/widgy/foodclub {payload['date']} -> "
                    f"hasFoodclub={payload['hasFoodclub']}"
                )
                self.wfile.write(json.dumps(payload).encode())
            except Exception as e:
                print(f"[ERROR] GET /api/widgy/foodclub failed: {e}")
                self.wfile.write(json.dumps({
                    "date": target_date.strftime("%Y-%m-%d"),
                    "weekday": "",
                    "displayDate": target_date.strftime("%Y-%m-%d"),
                    "hasFoodclub": False,
                    "foodclubName": "",
                    "foodclubRoom": "",
                    "menu": "",
                    "sources": {"foodclub": False, "smallTeddy": False},
                    "errors": {"server": str(e)},
                    "generatedAt": datetime.now().isoformat(),
                }).encode())
            return

        target = self.translate_path(self.path)
        if self.path == "/" or os.path.exists(target):
            return super().do_GET()

        self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/admin/generate-small-teddy-next-month":
            try:
                payload = generate_next_small_teddy_month()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", **payload}).encode())
            except Exception as exc:
                print(f"[ERROR] /api/admin/generate-small-teddy-next-month failed: {exc}")
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode())
            return

        if self.path == "/api/small-teddy-check":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode())
                date_str = str(payload.get("date", "")).strip()
                checked = bool(payload.get("checked"))
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    raise ValueError("Invalid date format; expected YYYY-MM-DD")

                update_small_teddy_check(date_str, checked)
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "date": date_str, "checked": checked}).encode())
            except KeyError as exc:
                self.send_response(404)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode())
            except Exception as exc:
                print(f"[ERROR] /api/small-teddy-check failed: {exc}")
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(exc)}).encode())
            return

        if self.path == "/api/purchases":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode())
                print(f"[POST] Received: {len(data)} purchases" if isinstance(data, list) else f"[POST] Received: {data}")

                # If data is a list (bulk upload from frontend)
                if isinstance(data, list):
                    print(f"[DB] Syncing {len(data)} purchases from frontend")
                    conn = sqlite3.connect(str(DB_PATH))
                    cursor = conn.cursor()
                    synced = 0

                    for purchase in data:
                        try:
                            # Look up product by name
                            product_name = purchase.get("productName")
                            cursor.execute("SELECT id FROM products WHERE name = ?", (product_name,))
                            product = cursor.fetchone()
                            product_id = product[0] if product else None

                            # Look up resident by name
                            resident_name = purchase.get("residentName")
                            cursor.execute("SELECT rid FROM residents WHERE name = ?", (resident_name,))
                            resident = cursor.fetchone()
                            resident_id = resident[0] if resident else None

                            if not product_id or not resident_id:
                                print(f"  ✗ Skipped: {resident_name} / {product_name} - not found in DB")
                                continue

                            # Check if already exists (same product, resident, timestamp)
                            cursor.execute("""
                                SELECT id FROM purchases
                                WHERE product_id = ? AND resident_id = ? AND timestamp = ?
                                LIMIT 1
                            """, (product_id, resident_id, purchase.get("timestamp")))

                            if cursor.fetchone():
                                print(f"  ⊘ Skipped: Already synced - {resident_name} / {product_name}")
                                continue

                            cursor.execute("""
                                INSERT INTO purchases (product_id, resident_id, quantity, price, timestamp)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                product_id,
                                resident_id,
                                purchase.get("quantity", 1),
                                purchase.get("unitPrice", 0),
                                purchase.get("timestamp")
                            ))
                            synced += 1
                            print(f"  ✓ {resident_name} bought {product_name}")
                        except Exception as e:
                            print(f"  ✗ Error: {e}")

                    conn.commit()
                    conn.close()

                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "synced": synced}).encode())
                    return

                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid data"}).encode())
            except Exception as e:
                print(f"[ERROR] {e}")
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        self.send_response(404)
        self.end_headers()


def parse_args():
    parser = argparse.ArgumentParser(description="Serve the EHP local mirror with SPA fallback.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main():
    args = parse_args()
    server = http.server.ThreadingHTTPServer((args.host, args.port), SpaRequestHandler)
    bind_label = "all interfaces" if args.host == "0.0.0.0" else args.host
    print(f"Serving local mirror on {bind_label}:{args.port}")
    print(f"Open http://localhost:{args.port}/system")
    server.serve_forever()


if __name__ == "__main__":
    main()
