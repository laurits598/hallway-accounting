#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="kollegianeren"
BOT_SERVICE_NAME="kollegianeren-telegram"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
BOT_SERVICE_FILE="/etc/systemd/system/${BOT_SERVICE_NAME}.service"

if ! command -v systemctl >/dev/null 2>&1; then
    echo "Required command not found: systemctl" >&2
    exit 1
fi

if [[ ${EUID} -eq 0 ]]; then
    SUDO=()
else
    if ! command -v sudo >/dev/null 2>&1; then
        echo "Required command not found: sudo" >&2
        exit 1
    fi
    SUDO=(sudo)
    sudo -v
fi

echo "Stopping and disabling ${SERVICE_NAME}.service"
"${SUDO[@]}" systemctl disable --now "${SERVICE_NAME}.service" 2>/dev/null || true
echo "Stopping and disabling ${BOT_SERVICE_NAME}.service"
"${SUDO[@]}" systemctl disable --now "${BOT_SERVICE_NAME}.service" 2>/dev/null || true

if [[ -f ${SERVICE_FILE} ]]; then
    echo "Removing ${SERVICE_FILE}"
    "${SUDO[@]}" rm -f -- "${SERVICE_FILE}"
else
    echo "Service file is already absent."
fi

if [[ -f ${BOT_SERVICE_FILE} ]]; then
    echo "Removing ${BOT_SERVICE_FILE}"
    "${SUDO[@]}" rm -f -- "${BOT_SERVICE_FILE}"
fi

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl reset-failed "${SERVICE_NAME}.service" 2>/dev/null || true
"${SUDO[@]}" systemctl reset-failed "${BOT_SERVICE_NAME}.service" 2>/dev/null || true

echo "${SERVICE_NAME}.service has been removed."
echo "Project files, virtual environment, credentials, and database were preserved."
