#!/usr/bin/env python3
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.backend.server import build_accounting_summary, build_foodclub_widget_payload
from app.backend.google_sheets import insert_bluebook_expense, set_foodclub_attendance


PROJECT_ROOT = Path(__file__).resolve().parent
TOKEN_FILE = PROJECT_ROOT / "app" / "backend" / "telegram_bot_token.txt"
REGISTRATIONS_FILE = PROJECT_ROOT / "data" / "telegram_users.json"
RESIDENTS_FILE = PROJECT_ROOT / "data" / "seed" / "residents.json"


def normalize_room(room):
    room = str(room).strip()
    return f"5{room}" if len(room) == 2 and room.isdigit() else room


def active_rooms():
    with RESIDENTS_FILE.open(encoding="utf-8") as file:
        residents = json.load(file)
    return {
        normalize_room(resident["room"]): resident["name"]
        for resident in residents
        if resident.get("active", True) and resident.get("room") and resident.get("name")
    }


def load_registrations():
    if not REGISTRATIONS_FILE.exists():
        return {}
    with REGISTRATIONS_FILE.open(encoding="utf-8") as file:
        data = json.load(file)
    return {str(user_id): normalize_room(room) for user_id, room in data.items()}


def save_registration(user_id, room):
    registrations = load_registrations()
    registrations[str(user_id)] = room
    REGISTRATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRATIONS_FILE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(registrations, file, indent=2, sort_keys=True)
        file.write("\n")
    os.chmod(temporary, 0o600)
    temporary.replace(REGISTRATIONS_FILE)


def read_bot_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(
            f"Set TELEGRAM_BOT_TOKEN or place the token in {TOKEN_FILE}"
        )
    return token


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await help_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Available commands:\n\n"
        "/register 529 — link your Telegram account to a room\n"
        "/owe or /balance — current month's accounting balance\n"
        "/foodclub — today's dish and signup count\n"
        "/attend V or /foodclub attend V — sign up with V, G, or a number\n"
        "/bluebook — format for adding a Blue Book expense\n"
        "/bluebook Description | Amount — add an expense\n"
        "/help — show this command list"
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.effective_message.reply_text("Usage: /register 529")
        return

    room = normalize_room(context.args[0])
    rooms = active_rooms()
    if room not in rooms:
        await update.effective_message.reply_text("That room is not in the active resident list.")
        return

    save_registration(update.effective_user.id, room)
    await update.effective_message.reply_text(f"Registered {rooms[room]} in room {room}.")


def current_balance(room, now=None):
    now = now or datetime.now()
    summary = build_accounting_summary(now.month, now.year)
    row = next((item for item in summary["rows"] if str(item["room"]) == room), None)
    return summary, row


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room = load_registrations().get(str(update.effective_user.id))
    if not room:
        await update.effective_message.reply_text("Register your room first: /register 529")
        return

    try:
        summary, row = await asyncio.to_thread(current_balance, room)
    except Exception as exc:
        print(f"[TELEGRAM] Balance lookup failed: {exc}")
        await update.effective_message.reply_text("I could not load the accounting data right now.")
        return

    if row is None:
        await update.effective_message.reply_text(
            f"No accounting entry was found for room {room} in "
            f"{summary['monthName']} {summary['year']}."
        )
        return

    missing = [name for name, loaded in summary["sources"].items() if not loaded]
    warning = f"\nUnavailable sources: {', '.join(missing)}." if missing else ""
    await update.effective_message.reply_text(
        f"{row['name']} · room {room}\n"
        f"{summary['monthName']} {summary['year']}\n"
        f"Foodclub: {row['foodclub']:.2f} kr.\n"
        f"Blue Book: {row['bluebook']:.2f} kr.\n"
        f"Kiosk: {row['kiosk']:.2f} kr.\n"
        f"Total: {row['total']:.2f} kr.{warning}"
    )


def parse_bluebook_args(args):
    raw = " ".join(args).strip()
    if "|" not in raw:
        raise ValueError("Use: /bluebook Description | 123.45")
    description, amount_raw = (part.strip() for part in raw.rsplit("|", 1))
    if not description:
        raise ValueError("Description cannot be empty.")
    if len(description) > 200:
        raise ValueError("Description must be at most 200 characters.")
    try:
        amount = round(float(amount_raw.replace(",", ".")), 2)
    except ValueError as exc:
        raise ValueError("Amount must be a number, for example 123.45.") from exc
    if amount <= 0 or amount > 100000:
        raise ValueError("Amount must be greater than 0 and at most 100000.")
    return description, amount


async def bluebook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room = load_registrations().get(str(update.effective_user.id))
    if not room:
        await update.effective_message.reply_text("Register your room first: /register 529")
        return
    if not context.args:
        await update.effective_message.reply_text(
            "Send the expense like this:\n"
            "/bluebook Description | Amount\n\n"
            "Example:\n/bluebook Flour and oil | 123.45"
        )
        return

    try:
        description, amount = parse_bluebook_args(context.args)
        today = datetime.now(ZoneInfo("Europe/Copenhagen")).date()
        result = await asyncio.to_thread(
            insert_bluebook_expense, room, description, amount, today
        )
    except Exception as exc:
        print(f"[TELEGRAM] Blue Book insert failed: {exc}")
        await update.effective_message.reply_text(f"Could not add the expense: {exc}")
        return

    receipt = "\nRemember to put the receipt in the folder." if amount > 200 else ""
    await update.effective_message.reply_text(
        f"Added to {result['sheet']}:\n"
        f"{description}: {amount:.2f} kr. (slot {result['slot']}){receipt}"
    )


async def foodclub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0].casefold() == "attend":
        await attend(update, context, context.args[1:])
        return
    today = datetime.now(ZoneInfo("Europe/Copenhagen"))
    try:
        payload = await asyncio.to_thread(build_foodclub_widget_payload, today)
    except Exception as exc:
        print(f"[TELEGRAM] Foodclub lookup failed: {exc}")
        await update.effective_message.reply_text("I could not load today's Foodclub data.")
        return

    if not payload.get("hasFoodclub"):
        await update.effective_message.reply_text(
            f"No Foodclub is listed for {payload['displayDate']}."
        )
        return

    dish = payload.get("menu") or "No dish has been entered yet."
    chef = payload.get("foodclubName") or (
        f"Room {payload['foodclubRoom']}" if payload.get("foodclubRoom") else "Not assigned"
    )
    await update.effective_message.reply_text(
        f"Foodclub · {payload['displayDate']}\n"
        f"Dish: {dish}\n"
        f"Chef: {chef}\n"
        f"Signed up: {payload.get('signupCount', 0)}"
    )


def parse_attendance(args):
    if len(args) != 1:
        raise ValueError("Use /attend V, /attend G, or /attend 1")
    value = args[0].strip().upper()
    if value in {"V", "G"}:
        return value
    if value.isdigit() and 1 <= int(value) <= 20:
        return str(int(value))
    raise ValueError("Attendance must be V, G, or a number from 1 to 20.")


async def attend(update: Update, context: ContextTypes.DEFAULT_TYPE, args=None):
    room = load_registrations().get(str(update.effective_user.id))
    if not room:
        await update.effective_message.reply_text("Register your room first: /register 529")
        return
    try:
        attendance = parse_attendance(context.args if args is None else args)
        today = datetime.now(ZoneInfo("Europe/Copenhagen")).date()
        result = await asyncio.to_thread(
            set_foodclub_attendance, room, attendance, today
        )
    except Exception as exc:
        print(f"[TELEGRAM] Foodclub attendance failed: {exc}")
        await update.effective_message.reply_text(f"Could not update attendance: {exc}")
        return

    changed = f" (replaced {result['previous']})" if result["previous"] else ""
    await update.effective_message.reply_text(
        f"Added room {room} to Foodclub with {attendance}{changed}.\n"
        f"Signed up now: {result['signupCount']}"
    )


async def text_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.effective_message.text or "").casefold()
    if any(word in text for word in ("owe", "balance", "skylder", "saldo")):
        await balance(update, context)
    else:
        await update.effective_message.reply_text("Use /owe to see your current balance.")


def main():
    application = ApplicationBuilder().token(read_bot_token()).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler(["owe", "balance"], balance))
    application.add_handler(CommandHandler("bluebook", bluebook))
    application.add_handler(CommandHandler("foodclub", foodclub))
    application.add_handler(CommandHandler("attend", attend))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_question))
    application.run_polling()


if __name__ == "__main__":
    main()
