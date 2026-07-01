from app.backend.accounting import get_resident_costs
from app.backend.google_sheets import fetch_sheet_data
from scripts import monthly_summary 
import sqlite3
import subprocess
import textwrap
import re
import tempfile
import os


def main():
    print("Running monthly summary for June 2026...")
    monthly_summary.main()
    

    tables = ["bluebook_months", "foodclub_attended", "products", "residents", "bluebook_expenses", "foodclub_events", "purchases"]
    tables = ["bluebook_months", "bluebook_expenses"]



    def list():
        for table in tables:
            cmd = f"sqlite3 kollegianeren.db '.mode box' 'PRAGMA table_info({table});' .quit"
            print("")
            print(f"\n========================= {table} ==============================\n")
            subprocess.run(cmd, shell=True)

    list()


    sql = """
    .headers on
    .mode box

    SELECT *
    FROM foodclub_sheet
    WHERE date >= '2025-04-01'
    AND date <  '2025-05-01';
    """
    '''
    subprocess.run(
        ["sqlite3", "kollegianeren.db"],
        input=sql,
        text=True,
    )
    '''    





if __name__ == "__main__":
    main()
