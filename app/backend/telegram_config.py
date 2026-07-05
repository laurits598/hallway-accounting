import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOKEN_FILE = PROJECT_ROOT / "app" / "backend" / "telegram_bot_token.txt"


def normalize_room(room):
    room = str(room).strip()
    return f"5{room}" if len(room) == 2 and room.isdigit() else room


def _validate_configs(configs):
    if not configs:
        raise RuntimeError("No room-bound Telegram bot tokens were configured.")

    rooms = set()
    tokens = set()
    normalized = []
    for room, token in configs:
        room = normalize_room(room)
        token = str(token).strip()
        if not room or not token:
            raise RuntimeError("Every Telegram bot configuration needs a room and token.")
        if room in rooms:
            raise RuntimeError(f"Telegram room {room} is configured more than once.")
        if token in tokens:
            raise RuntimeError("The same Telegram bot token is configured more than once.")
        rooms.add(room)
        tokens.add(token)
        normalized.append({"room": room, "token": token})
    return normalized


def read_bot_configs():
    """Read room-bound bot tokens from the environment or credential file."""
    raw_json = os.environ.get("TELEGRAM_BOTS", "").strip()
    if raw_json:
        try:
            values = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("TELEGRAM_BOTS must be a JSON object of room-to-token values.") from exc
        if not isinstance(values, dict):
            raise RuntimeError("TELEGRAM_BOTS must be a JSON object of room-to-token values.")
        return _validate_configs(values.items())

    legacy_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if legacy_token:
        room = os.environ.get("TELEGRAM_BOT_ROOM", "").strip()
        if not room:
            raise RuntimeError("TELEGRAM_BOT_ROOM is required with TELEGRAM_BOT_TOKEN.")
        return _validate_configs([(room, legacy_token)])

    if not TOKEN_FILE.exists():
        raise RuntimeError(f"Telegram bot configuration not found at {TOKEN_FILE}")

    configs = []
    for line_number, raw_line in enumerate(TOKEN_FILE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError(
                f"Invalid Telegram bot configuration on line {line_number}; expected ROOM=TOKEN."
            )
        room, token = line.split("=", 1)
        configs.append((room, token))
    return _validate_configs(configs)
