import os
import gspread
import re
from datetime import date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ASbwbixKncFgLsCCQtyPLrIVk_zHWUdreB1nLi9xrzs"

#SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_client():
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE,
                scopes=SCOPES,
            )
            creds = flow.run_local_server(port=0, open_browser=False)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return gspread.authorize(creds)


def get_worksheets():
    gc = get_client()
    spreadsheet = gc.open_by_url(SHEET_URL)
    return [ws.title for ws in spreadsheet.worksheets()]


def fetch_sheet_data(worksheet_name):
    gc = get_client()
    spreadsheet = gc.open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(worksheet_name)
    return worksheet.get_all_values()


def fetch_first_available_sheet_data(worksheet_names):
    """Fetch the first matching worksheet title, ignoring letter case."""
    gc = get_client()
    spreadsheet = gc.open_by_url(SHEET_URL)
    worksheets = {ws.title.casefold(): ws for ws in spreadsheet.worksheets()}

    for name in worksheet_names:
        worksheet = worksheets.get(name.casefold())
        if worksheet is not None:
            return worksheet.get_all_values()

    expected = ", ".join(worksheet_names)
    raise gspread.WorksheetNotFound(f"None of these worksheets exists: {expected}")


ENGLISH_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def insert_bluebook_expense(room, description, amount, expense_date=None):
    """Insert an expense into the first empty slot for a resident's room."""
    expense_date = expense_date or date.today()
    room = str(room).strip()
    short_room = room[1:] if len(room) == 3 and room.startswith("5") else room
    title = f"{ENGLISH_MONTHS[expense_date.month]} {expense_date.year} - Blue Book"

    spreadsheet = get_client().open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(title)
    values = worksheet.get("A5:J24")

    resident_row = None
    row_values = None
    for offset, row in enumerate(values):
        label = str(row[0] if row else "")
        match = re.search(r"\((\d+)\)", label)
        if match and match.group(1) == short_room:
            resident_row = offset + 5
            row_values = list(row) + [""] * (10 - len(row))
            break

    if resident_row is None:
        raise ValueError(f"Room {room} was not found in {title}")

    slots = ((1, "B", "D"), (4, "E", "G"), (7, "H", "J"))
    for start_index, start_column, end_column in slots:
        if not any(str(value).strip() for value in row_values[start_index:start_index + 3]):
            formatted_date = f"{expense_date.day}/{expense_date.month}/{str(expense_date.year)[2:]}"
            worksheet.batch_update([{
                "range": f"{start_column}{resident_row}:{end_column}{resident_row}",
                "values": [[formatted_date, description, float(amount)]],
            }])
            return {
                "sheet": title,
                "room": room,
                "slot": (start_index // 3) + 1,
                "date": formatted_date,
                "description": description,
                "amount": float(amount),
            }

    raise ValueError(f"Room {room} already uses all three expense slots in {title}")


#if __name__ == "__main__":
#    for sheet in get_worksheets():
#        print(sheet)
