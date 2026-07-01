import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backend.accounting import (
    fetch_sheet_data,
    get_bluebook_summary,
    get_kaffeklub_costs,
    get_purchases_for_month,
    get_resident_costs,
    print_monthly_summary,
)


MONTH = 6
YEAR = 2026

DANISH_MONTHS = {
    1: "Januar",
    2: "Februar",
    3: "Marts",
    4: "April",
    5: "Maj",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "December",
}

ENGLISH_MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def accounting_summary():
    month = MONTH
    year = YEAR

    foodclub_sheet = f"Foodclub - {DANISH_MONTHS[month]} {year}"
    bluebook_sheet = f"{ENGLISH_MONTHS[month]} {year} - Blue Book"

    foodclub_data = fetch_sheet_data(foodclub_sheet)
    bluebook_data = fetch_sheet_data(bluebook_sheet)

    accounting_foodclub = get_resident_costs(foodclub_data, include_kaffeklub=False)
    accounting_kaffeklub = get_kaffeklub_costs(foodclub_data)
    accounting_bluebook = get_bluebook_summary(bluebook_data)
    accounting_kiosk = get_purchases_for_month(month, year)

    print_monthly_summary(
        accounting_foodclub,
        accounting_bluebook,
        accounting_kiosk,
        kaffeklub=accounting_kaffeklub,
        detailed=True,
    )


def main():
    accounting_summary()


if __name__ == "__main__":
    accounting_summary()
