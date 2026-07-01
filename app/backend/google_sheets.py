import os
import gspread
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


#if __name__ == "__main__":
#    for sheet in get_worksheets():
#        print(sheet)
