import sys
import csv
from pathlib import Path
from app.backend.google_sheets import get_worksheets, fetch_sheet_data
from app.backend.google_sheets import fetch_sheet_data
from temp import build_sheet_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def choose_sheet():
    print(get_worksheets())
    data = fetch_sheet_data("Madklub - Juni 2026")
    #sheets = get_worksheets()
    '''
    for i, sheet in enumerate(sheets):
        print(f"{i}: {sheet}")

    choice = int(input("Choose sheet: "))
    data = fetch_sheet_data(sheets[choice])
    '''
    return data

def get_current():
    import re

    pattern = re.compile(
        r"^(Madklub - .+ \d{4}|.+ \d{4} - Blue Book)$"
    )

    foodclubs = []
    bluebooks = []

    for sheet in get_worksheets():
        if pattern.match(sheet):
            if "2026" in sheet:
                if sheet.startswith("Madklub - "):
                    foodclubs.append(sheet)
                elif sheet.endswith(" - Blue Book"):
                    bluebooks.append(sheet)

    print(foodclubs)
    print(bluebooks)



def download_sheets(output_dir="downloaded_sheets"):
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    manifest, unclassified = build_sheet_manifest(start_year=2022)

    for year, months in manifest.items():
        for month, kinds in months.items():
            for kind, info in kinds.items():
                original_name = info["original_name"]
                clean_name = info["clean_name"]

                rows = fetch_sheet_data(original_name)

                file_path = output_path / f"{clean_name}.csv"

                with file_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)

                print(f"Saved {original_name} -> {file_path}")

    return manifest, unclassified


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

if __name__ == "__main__":
    download_sheets()