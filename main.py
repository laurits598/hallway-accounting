from app.backend.accounting import get_resident_costs
from app.backend.google_sheets import fetch_sheet_data
from app.backend.server import generate_next_small_teddy_month
from scripts import monthly_summary 
import sqlite3
import subprocess
import textwrap
import re
import tempfile
import os

import sheet_handler


'''
Need an "end of the month" trigger to run a function/script automatically?
Script should do the following:
=> Create new worksheets for the next month (Foodclub and Blue Book)
=> Create new "lillebamse" schedule for the next month
=> Do hallway accounting for the current month (Foodclub, Blue Book, Kaffeklub, Kiosk)
'''


def main():
    
    # Create new worksheets for the next month (Foodclub and Blue Book)
    sheet_handler.main()

    # Do accounting summary for the current month
    monthly_summary.main()

    # Generate the next small teddy month schedule
    generate_next_small_teddy_month()

if __name__ == "__main__":
    main()
