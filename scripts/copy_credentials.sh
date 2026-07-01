#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
SOURCE_DIR="${PROJECT_DIR}/app/backend"

usage() {
    echo "Usage: $0 <user@host> [remote-project-directory]" >&2
    echo "Example: $0 lau@legion-server hallway-accounting" >&2
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage
    exit 2
fi

REMOTE_HOST="$1"
REMOTE_PROJECT_DIR="${2:-hallway-accounting}"
REMOTE_CREDENTIAL_DIR="${REMOTE_PROJECT_DIR%/}/app/backend"

# These values become part of SSH/SCP arguments. Restrict them to ordinary
# host and Unix path characters instead of accepting shell syntax.
if [[ ! ${REMOTE_HOST} =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "Invalid SSH destination: ${REMOTE_HOST}" >&2
    exit 2
fi
if [[ ! ${REMOTE_PROJECT_DIR} =~ ^[A-Za-z0-9_./~-]+$ ]]; then
    echo "Invalid remote project directory: ${REMOTE_PROJECT_DIR}" >&2
    exit 2
fi

for command in ssh scp; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "Required command not found: ${command}" >&2
        exit 1
    fi
done

CREDENTIAL_FILES=(client_secret.json token.json)
for file in "${CREDENTIAL_FILES[@]}"; do
    if [[ ! -r "${SOURCE_DIR}/${file}" ]]; then
        echo "Missing credential file: ${SOURCE_DIR}/${file}" >&2
        exit 1
    fi
done

echo "Creating ${REMOTE_CREDENTIAL_DIR} on ${REMOTE_HOST}"
ssh "${REMOTE_HOST}" mkdir -p -- "${REMOTE_CREDENTIAL_DIR}"

echo "Copying Google credentials"
scp \
    "${SOURCE_DIR}/client_secret.json" \
    "${SOURCE_DIR}/token.json" \
    "${REMOTE_HOST}:${REMOTE_CREDENTIAL_DIR}/"

ssh "${REMOTE_HOST}" chmod 600 \
    "${REMOTE_CREDENTIAL_DIR}/client_secret.json" \
    "${REMOTE_CREDENTIAL_DIR}/token.json"

echo "Credentials copied to ${REMOTE_HOST}:${REMOTE_CREDENTIAL_DIR}/"
