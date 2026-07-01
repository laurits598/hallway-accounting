from app.backend.google_sheets import SHEET_URL, get_client


RENAMES_2022 = {
    "Madklub - Februar 22": "Foodclub - Februar 2022",
    "Madklub - Marts 2022": "Foodclub - Marts 2022",
    "Madklub - April 22": "Foodclub - April 2022",
    "Madklub - Maj 2022": "Foodclub - Maj 2022",
    "Madklub - Juni 22": "Foodclub - Juni 2022",
    "Madklub - Juli 22": "Foodclub - Juli 2022",
    "Madklub - August 22": "Foodclub - August 2022",
    "Madklub - Oktober 22": "Foodclub - Oktober 2022",
    "Madklub - November 22": "Foodclub - November 2022",
    "Madklub- December 2022": "Foodclub - December 2022",

    "Januar22- Blue Book": "Januar 2022 - Blue Book",
    "Februar22- Blue Book": "Februar 2022 - Blue Book",
    "Marts22- Blue Book": "Marts 2022 - Blue Book",
    "April22- Blue Book": "April 2022 - Blue Book",
    "Maj22- Blue Book": "Maj 2022 - Blue Book",
    "Juni22- Blue Book": "Juni 2022 - Blue Book",
    "Juli22- Blue Book": "Juli 2022 - Blue Book",
    "August22- Blue Book": "August 2022 - Blue Book",
    "September22- Blue Book": "September 2022 - Blue Book",
    "October22- Blue Book": "October 2022 - Blue Book",
    "November22- Blue Book": "November 2022 - Blue Book",
    "December22 - Blue Book": "December 2022 - Blue Book",
}


RENAMES_2023 = {
    "Madklub- Januar 2023": "Foodclub - Januar 2023",
    "Madklub- Februar 2023": "Foodclub - Februar 2023",
    "Madklub- April 2023": "Foodclub - April 2023",
    "Madklub-Maj 2023 ": "Foodclub - Maj 2023",
    "Madklub- Juni 2023": "Foodclub - Juni 2023",
    "Madklub- September 2023": "Foodclub - September 2023",
    "Madklub- Oktober 2023": "Foodclub - Oktober 2023",
    "Madklub- November 2023": "Foodclub - November 2023",
    "Madklub- December 2023": "Foodclub - December 2023",
    "Januar 2023 - Blue Book": "Januar 2023 - Blue Book",
    "Februar 2023 - Blue Book": "Februar 2023 - Blue Book",
    "Marts 2023 - Blue Book": "Marts 2023 - Blue Book",
    "April 2023 - Blue Book": "April 2023 - Blue Book",
    "Maj 2023 - Blue Book": "Maj 2023 - Blue Book",
    "Juni 2023 - Blue Book": "Juni 2023 - Blue Book",
    "Juli 2023 - Blue Book": "Juli 2023 - Blue Book",
    "August 2023 - Blue Book": "August 2023 - Blue Book",
    "September 2023 - Blue Book": "September 2023 - Blue Book",
    "October 2023 - Blue Book": "October 2023 - Blue Book",
    "November 2023 - Blue Book": "November 2023 - Blue Book",
    "December 2023 - Blue Book": "December 2023 - Blue Book",
}

RENAMES_2024 = {
    "Madklub- Januar 2024": "Foodclub - Januar 2024",
    "Madklub- Maj 2024": "Foodclub - Maj 2024",
    "Madklub- Juni 2024": "Foodclub - Juni 2024",
    "Madklub- September 2024": "Foodclub - September 2024",
    "Madklub- Oktober 2024": "Foodclub - Oktober 2024",
    "Madklub- December 2024": "Foodclub - December 2024",
    "January 2024 - Blue Book": "January 2024 - Blue Book",
    "February 2024 - Blue Book": "February 2024 - Blue Book",
    "March 2024 - Blue Book": "March 2024 - Blue Book",
    "April 2024 - Blue Book": "April 2024 - Blue Book",
    "May 2024 - Blue Book": "May 2024 - Blue Book",
    "June 2024 - Blue Book": "June 2024 - Blue Book",
    "August 2024 - Blue Book": "August 2024 - Blue Book",
    "September 2024 - Blue Book": "September 2024 - Blue Book",
    "October 2024 - Blue Book": "October 2024 - Blue Book",
    "Novembere 2024 - Blue Book": "November 2024 - Blue Book",
    "Desember 2024 - Blue Book": "December 2024 - Blue Book",
}

RENAMES_2025 = {
    "Madklub- Januar 2025": "Foodclub - Januar 2025",
    "Madklub - Februar 2025": "Foodclub - Februar 2025",
    "Madklub - Marts 2025": "Foodclub - Marts 2025",
    "Madklub - April 2025": "Foodclub - April 2025",
    "Madklub - Maj 2025": "Foodclub - Maj 2025",
    "Madklub - Juni 2025": "Foodclub - Juni 2025",
    "Madklub - August 2025": "Foodclub - August 2025",
    "Madklub - September 25": "Foodclub - September 2025",
    "Madklub - oktober 25": "Foodclub - Oktober 2025",
    "Madklub - november 25": "Foodclub - November 2025",
    "Madklub - december 25": "Foodclub - December 2025",
    "Januar 2025 - Blue Book": "Januar 2025 - Blue Book",
    "February 2025 - Blue Book": "February 2025 - Blue Book",
    "March 2025 - Blue Book": "March 2025 - Blue Book",
    "April 2025 - Blue Book": "April 2025 - Blue Book",
    "May 2025 - Blue Book": "May 2025 - Blue Book",
    "Juni 2025 - Blue Book": "Juni 2025 - Blue Book",
    "Juli 2025 - Blue Book": "Juli 2025 - Blue Book",
    "August 2025 - Blue Book": "August 2025 - Blue Book",
    "September 2025 - Blue Book": "September 2025 - Blue Book",
    "October 2025 - Blue Book": "October 2025 - Blue Book",
    "November 2025 - Blue Book": "November 2025 - Blue Book",
    "December 2025 - Blue Book": "December 2025 - Blue Book",
}

RENAMES_2026 = {
    "Madklub - januar 26": "Foodclub - Januar 2026",
    "Madklub - februar 26": "Foodclub - Februar 2026",
    "Madklub - marts 26": "Foodclub - Marts 2026",
    "Madklub - April 26": "Foodclub - April 2026",
    "Madklub - Maj 2026": "Foodclub - Maj 2026",
    "Madklub - Juni 2026": "Foodclub - Juni 2026",
    "Marts 2026 - Blue Book": "Marts 2026 - Blue Book",
    "April 2026 - Blue Book": "April 2026 - Blue Book",
    "May 2026 - Blue Book": "May 2026 - Blue Book",
    "June 2026 - Blue Book": "June 2026 - Blue Book",
}


import os

def clear():
    os.system("cls" if os.name == "nt" else "clear")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ASbwbixKncFgLsCCQtyPLrIVk_zHWUdreB1nLi9xrzs"

spreadsheet = get_client().open_by_url(SHEET_URL)
def print_sheet_titles(year):
    year = str(year)
    two = year[-2:]

    titles = [
        sheet.title
        for sheet in spreadsheet.worksheets()
        if two in sheet.title or year in sheet.title
    ]

    for title in titles:
        print(title)

check = [(RENAMES_2023, 2023), (RENAMES_2024, 2024), (RENAMES_2025, 2025), (RENAMES_2026, 2026)]


for renames, year in check:
    for old_name, new_name in renames.items():
        clear()
        print_sheet_titles(year)

        try:
            sheet = spreadsheet.worksheet(old_name)
            sheet.update_title(new_name)
        except Exception as e:
            print(f"Skipped {old_name}: {e}")
    
clear()
print_sheet_titles()
