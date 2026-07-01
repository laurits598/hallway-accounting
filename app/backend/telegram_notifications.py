import asyncio
import json
import os
from pathlib import Path

from telegram import Bot

from .server import build_accounting_summary


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = PROJECT_ROOT / "app" / "backend" / "telegram_bot_token.txt"
REGISTRATIONS_FILE = PROJECT_ROOT / "data" / "telegram_users.json"


def read_bot_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"Telegram bot token not found at {TOKEN_FILE}")
    return token


def load_registrations():
    if not REGISTRATIONS_FILE.exists():
        return {}
    with REGISTRATIONS_FILE.open(encoding="utf-8") as file:
        registrations = json.load(file)
    return {str(chat_id): str(room) for chat_id, room in registrations.items()}


def format_balance(summary, row):
    missing = [name for name, loaded in summary["sources"].items() if not loaded]
    warning = f"\nUnavailable sources: {', '.join(missing)}." if missing else ""
    return (
        f"{row['name']} · room {row['room']}\n"
        f"{summary['monthName']} {summary['year']}\n"
        f"Foodclub: {row['foodclub']:.2f} kr.\n"
        f"Blue Book: {row['bluebook']:.2f} kr.\n"
        f"Kiosk: {row['kiosk']:.2f} kr.\n"
        f"Total: {row['total']:.2f} kr.{warning}"
    )


async def broadcast_monthly_balances(month, year):
    """Send one balance message to every registered Telegram user."""
    registrations = load_registrations()
    if not registrations:
        return {"sent": 0, "failed": 0, "errors": []}

    summary = await asyncio.to_thread(build_accounting_summary, month, year)
    rows = {str(row["room"]): row for row in summary["rows"]}
    bot = Bot(read_bot_token())
    sent = 0
    errors = []

    async with bot:
        for chat_id, room in registrations.items():
            row = rows.get(room)
            if row is None:
                text = (
                    f"No accounting entry was found for room {room} in "
                    f"{summary['monthName']} {summary['year']}."
                )
            else:
                text = format_balance(summary, row)
            try:
                await bot.send_message(chat_id=chat_id, text=text)
                sent += 1
            except Exception as exc:
                errors.append(f"{chat_id}: {exc}")

    return {"sent": sent, "failed": len(errors), "errors": errors}


def send_monthly_balances(month, year):
    return asyncio.run(broadcast_monthly_balances(month, year))
