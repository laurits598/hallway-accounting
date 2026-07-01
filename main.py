import argparse

from app.backend.server import clear_small_teddy_month, generate_next_small_teddy_month
from app.backend.telegram_notifications import send_monthly_balances
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
    monthly_summary.main(monthly_summary.MONTH, monthly_summary.YEAR)

    # Generate the next small teddy month schedule
    generate_next_small_teddy_month()

    send_balance_notifications(monthly_summary.MONTH, monthly_summary.YEAR)


def run_monthly_accounting(month, year):
    monthly_summary.main(month, year)
    send_balance_notifications(month, year)


def send_balance_notifications(month, year):
    delivery = send_monthly_balances(month, year)
    print(
        f"Telegram balances: {delivery['sent']} sent, "
        f"{delivery['failed']} failed."
    )
    for error in delivery["errors"]:
        print(f"Telegram delivery failed: {error}")


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
    parser = argparse.ArgumentParser(description="Run monthly accounting or the July 2026 test workflow.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--test", action="store_true", help="generate sheets, summary, and Small Teddy schedule")
    mode.add_argument("--reset", action="store_true", help="delete generated July 2026 sheets and Small Teddy rows")
    mode.add_argument("--month", type=int, metavar="1-12", help="summarize and notify for this month")
    parser.add_argument("--year", type=int, help="year used with --month")
    args = parser.parse_args(argv)
    if args.month is not None:
        if not 1 <= args.month <= 12:
            parser.error("--month must be between 1 and 12")
        if args.year is None:
            parser.error("--year is required with --month")
    elif args.year is not None:
        parser.error("--year can only be used with --month")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.test:
        run_test()
    elif args.reset:
        reset_test()
    else:
        run_monthly_accounting(args.month, args.year)

if __name__ == "__main__":
    main()
