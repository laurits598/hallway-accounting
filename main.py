import argparse

from app.backend.server import clear_small_teddy_month, generate_next_small_teddy_month
from scripts import monthly_summary, sheet_handler

'''
Need an "end of the month" trigger to run a function/script automatically?
Script should do the following:
=> Create new worksheets for the next month (Foodclub and Blue Book)
=> Create new "lillebamse" schedule for the next month
=> Do hallway accounting for the current month (Foodclub, Blue Book, Kaffeklub, Kiosk)
'''


RESET_MONTH = 7
RESET_YEAR = 2026


def run_test():
    # Create new worksheets for the next month (Foodclub and Blue Book)
    sheet_handler.main()

    # Do accounting summary for the current month
    monthly_summary.main()

    # Generate the next small teddy month schedule
    generate_next_small_teddy_month()


def reset_test():
    deleted = sheet_handler.delete_month_sheets(RESET_MONTH, RESET_YEAR)
    removed_teddy_rows = clear_small_teddy_month(RESET_MONTH, RESET_YEAR)

    if deleted:
        for title in deleted:
            print(f"Deleted sheet: {title}")
    else:
        print("No July 2026 test sheets existed.")
    print(f"Removed {removed_teddy_rows} Small Teddy rows for July 2026.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run or reset the July 2026 monthly test workflow.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--test", action="store_true", help="generate sheets, summary, and Small Teddy schedule")
    mode.add_argument("--reset", action="store_true", help="delete generated July 2026 sheets and Small Teddy rows")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.test:
        run_test()
    else:
        reset_test()

if __name__ == "__main__":
    main()
