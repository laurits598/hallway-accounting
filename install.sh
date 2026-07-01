#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="kollegianeren"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
VENV_DIR="${PROJECT_DIR}/.venv"
DB_PATH="${PROJECT_DIR}/kollegianeren.db"
CLIENT_SECRET="${PROJECT_DIR}/app/backend/client_secret.json"
TOKEN_FILE="${PROJECT_DIR}/app/backend/token.json"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${KOLLEGIANEREN_PORT:-8080}"

if [[ ${EUID} -eq 0 ]]; then
    SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-root}}"
else
    SERVICE_USER="${SERVICE_USER:-$(id -un)}"
fi

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
    echo "Unknown service user: ${SERVICE_USER}" >&2
    exit 1
fi

SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

for command in "${PYTHON_BIN}" systemctl sudo; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "Required command not found: ${command}" >&2
        exit 1
    fi
done

if [[ ! -f "${CLIENT_SECRET}" || ! -f "${TOKEN_FILE}" ]]; then
    echo "Google credentials are required before installing the background service." >&2
    echo "Expected files:" >&2
    echo "  ${CLIENT_SECRET}" >&2
    echo "  ${TOKEN_FILE}" >&2
    exit 1
fi

run_as_service_user() {
    if [[ ${EUID} -eq 0 && ${SERVICE_USER} != root ]]; then
        sudo -u "${SERVICE_USER}" -- "$@"
    else
        "$@"
    fi
}

if [[ ${EUID} -ne 0 ]]; then
    sudo -v
fi

echo "Creating/updating Python environment in ${VENV_DIR}"
run_as_service_user "${PYTHON_BIN}" -m venv "${VENV_DIR}"
run_as_service_user "${VENV_DIR}/bin/python" -m pip install --upgrade pip
run_as_service_user "${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"

if [[ -f "${DB_PATH}" ]]; then
    echo "Existing database found; it will not be recreated."
    run_as_service_user "${VENV_DIR}/bin/python" - "${DB_PATH}" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
result = connection.execute("PRAGMA quick_check").fetchone()[0]
connection.close()
if result != "ok":
    raise SystemExit(f"SQLite integrity check failed: {result}")
print("SQLite integrity check: ok")
PY
else
    echo "No database found; initializing it from the seed data."
    run_as_service_user "${VENV_DIR}/bin/python" "${PROJECT_DIR}/scripts/setup_db.py"
fi

UNIT_FILE="$(mktemp)"
trap 'rm -f "${UNIT_FILE}"' EXIT

cat >"${UNIT_FILE}" <<EOF
[Unit]
Description=Kollegianeren local web application
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/python -m app.backend.server --host 0.0.0.0 --port ${PORT}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Restart=always
RestartSec=5
TimeoutStopSec=30
KillSignal=SIGTERM
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "Installing systemd service ${SERVICE_NAME}.service"
sudo install -o root -g root -m 0644 "${UNIT_FILE}" "${SERVICE_FILE}"
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}.service"

echo
echo "Kollegianeren is installed and running on port ${PORT}."
echo "Status: sudo systemctl status ${SERVICE_NAME}"
echo "Logs:   journalctl -u ${SERVICE_NAME} -f"
echo "Site:   http://localhost:${PORT}/system"
