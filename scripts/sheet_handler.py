from app.backend.google_sheets import SHEET_URL, get_client
import datetime
import calendar
import random

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ASbwbixKncFgLsCCQtyPLrIVk_zHWUdreB1nLi9xrzs"

MONTHS = {
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

ROOT_TEMPLATE_FOODCLUB = "FC_Template_26"


def basic_template(month, year):
    SHEET_TEMPLATE_FOODCLUB = f"Foodclub - {month} {year}"
    SHEET_TEMPLATE_BLUEBOOK = f"{month} {year} - Blue Book"

    foodclub_sheet = from_template(SHEET_TEMPLATE_FOODCLUB)
    bluebook_sheet = from_template(SHEET_TEMPLATE_BLUEBOOK)


def set_cell(cell, value, sheet_name=ROOT_TEMPLATE_FOODCLUB):
    spreadsheet = get_client().open_by_url(SHEET_URL)

    template_sheet = spreadsheet.worksheet(sheet_name)
    template_sheet.update(cell, [[value]])


def from_template(title, template_name=ROOT_TEMPLATE_FOODCLUB):
    spreadsheet = get_client().open_by_url(SHEET_URL)
    template_sheet = spreadsheet.worksheet(template_name)
    existing_titles = [sheet.title for sheet in spreadsheet.worksheets()]

    if title not in existing_titles:
        spreadsheet.duplicate_sheet(
            source_sheet_id=template_sheet.id,
            new_sheet_name=title,
        )

    #print([sheet.title for sheet in spreadsheet.worksheets()])
    return template_sheet


def delete_month_sheets(month, year):
    """Delete the Foodclub and Blue Book sheets generated for a month.

    Missing sheets are ignored so reset can safely be run more than once.
    Returns the titles that were actually deleted.
    """
    month_name = MONTHS[month]
    target_titles = {
        f"Foodclub - {month_name} {year}",
        f"{month_name} {year} - Blue Book",
    }
    spreadsheet = get_client().open_by_url(SHEET_URL)
    worksheets = {worksheet.title: worksheet for worksheet in spreadsheet.worksheets()}
    deleted = []
    for title in sorted(target_titles):
        worksheet = worksheets.get(title)
        if worksheet is not None:
            spreadsheet.del_worksheet(worksheet)
            deleted.append(title)
    return deleted


def short_room(room):
    return str(room)[1:]


def pick_room(rooms, counts, last_room):
    candidates = [r for r in rooms if r != last_room]
    min_count = min(counts[r] for r in candidates)
    best = [r for r in candidates if counts[r] == min_count]
    return random.choice(best)


def populate_foodclub(worksheet, year, month, rooms, wishes):
    worksheet.batch_clear(["F6:F36"])

    rooms_short = [short_room(r) for r in rooms]
    wishes = {int(day): short_room(room) for room, day in wishes}

    _, last_day = calendar.monthrange(year, month)

    updates = []
    counts = {room: 0 for room in rooms_short}
    last_room = None

    for day in range(1, last_day + 1):
        weekday = calendar.weekday(year, month, day)

        if weekday in (4, 5):  # Friday, Saturday
            continue

        row = day + 5
        wanted = wishes.get(day)

        if wanted and wanted != last_room:
            chef = wanted
        else:
            chef = pick_room(rooms_short, counts, last_room)

        counts[chef] += 1
        last_room = chef

        updates.append({
            "range": f"F{row}",
            "values": [[chef]],
        })

    worksheet.batch_update(updates)


'''
Day: U1, Month: W1, Year: Y1
Menu start: G6

'''

def init(year=None, month=None):
    today = datetime.date.today()
    year_int = year or today.year
    month_int = month or today.month
    sheet_title_bb = f"{MONTHS[month_int]} {year_int} - Blue Book"
    from_template(sheet_title_bb, template_name="BB_Template_26")
    print(MONTHS[month_int] + " " + str(year_int))
    sheet_title_fc = f"Foodclub - {MONTHS[month_int]} {year_int}"
    print(sheet_title_fc)
   
    worksheet = from_template(sheet_title_fc)
    set_cell("U1", 1, sheet_title_fc)
    set_cell("W1", month_int, sheet_title_fc)
    set_cell("Y1", year_int, sheet_title_fc)
    #worksheet = spreadsheet.worksheet(sheet_title_fc)

    spreadsheet = get_client().open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(sheet_title_fc)
    
    populate_foodclub(
        worksheet=worksheet,
        year=year_int,
        month=month_int,
        rooms=[str(room) for room in range(525, 548)],
        wishes=[("532", 5), ("533", 6)],
    )


def main(year=None, month=None):
    init(year, month)


if __name__ == "__main__":
    main()

