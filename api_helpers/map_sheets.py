import re
from collections import defaultdict
from app.backend.google_sheets import fetch_sheet_data, get_worksheets


def choose_sheet():
    years, remaining = sort_sheets()

    print("Available years:")
    for year in sorted(years.keys()):
        print(f"  {year}")

    year = input("\nChoose year: ").strip()

    if year not in years:
        raise ValueError(f"No sheets found for {year}")

    print(f"\nAvailable months for {year}:")
    for i, (month, foodclub, bluebook) in enumerate(years[year], 1):
        print(f"{i:2}. {month:<10} | Foodclub: {foodclub} | Blue Book: {bluebook}")

    choice = int(input("\nChoose month: ")) - 1
    month, foodclub, bluebook = years[year][choice]

    if not foodclub:
        raise ValueError("No foodclub sheet exists for that month.")

    return fetch_sheet_data(foodclub)


def sort_sheets():
    sheets = get_worksheets()

    month_map = {
        "januar": "januar",
        "january": "januar",
        "februar": "februar",
        "february": "februar",
        "febrrrrrruary": "februar",
        "marts": "marts",
        "march": "marts",
        "april": "april",
        "maj": "maj",
        "may": "maj",
        "juni": "juni",
        "june": "juni",
        "juli": "juli",
        "july": "juli",
        "august": "august",
        "september": "september",
        "oktober": "oktober",
        "october": "oktober",
        "november": "november",
        "december": "december",
        "desember": "december",
    }

    month_order = [
        "januar",
        "februar",
        "marts",
        "april",
        "maj",
        "juni",
        "juli",
        "august",
        "september",
        "oktober",
        "november",
        "december",
    ]

    years = defaultdict(dict)
    parsed = set()

    for sheet in sheets:
        lower = sheet.lower()

        if "blue book" not in lower and "blå bog" not in lower and "madklub" not in lower:
            continue

        match = re.search(r"(20\d{2}|(?<!\d)\d{2}(?!\d))", sheet)
        if not match:
            continue

        year = match.group(1)
        if len(year) == 2:
            year = f"20{year}"

        month = None
        for key, value in month_map.items():
            if key in lower:
                month = value
                break

        if month is None:
            continue

        kind = "bluebook" if "blue book" in lower or "blå bog" in lower else "foodclub"

        years[year].setdefault(month, {"foodclub": None, "bluebook": None})
        years[year][month][kind] = sheet
        parsed.add(sheet)

    result = {}

    for year, data in years.items():
        result[year] = []

        for month in month_order:
            if month not in data:
                continue

            result[year].append(
                (
                    month,
                    data[month]["foodclub"],
                    data[month]["bluebook"],
                )
            )

    remaining = sorted(set(sheets) - parsed)

    return result, remaining


def print_remaining(remaining):
    print("\n===== Unclassified sheets =====")

    for sheet in remaining:
        print(sheet)

    print(f"\n{len(remaining)} sheet(s) were not classified.")


if __name__ == "__main__":
    years, remaining = sort_sheets()

    for year in sorted(years):
        print(f"\n===== {year} =====")
        for month, foodclub, bluebook in years[year]:
            print(f"{month:10} | {foodclub} | {bluebook}")

    print_remaining(remaining)