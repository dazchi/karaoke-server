#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PIP="$APP_DIR/.venv/bin/pip"
SERVICE_NAME="karaoke-server"

if [ ! -x "$VENV_PIP" ]; then
    echo "ERROR: pip not found at $VENV_PIP" >&2
    exit 1
fi

# Preserve venv ownership by running pip as the venv owner
OWNER="$(stat -c "%U" "$VENV_PIP")"

get_version() {
    runuser -u "$OWNER" -- "$VENV_PIP" show yt-dlp 2>/dev/null | awk "/^Version:/ {print \$2}"
}

OLD_VERSION="$(get_version)"
echo "current yt-dlp: ${OLD_VERSION:-none}"

runuser -u "$OWNER" -- "$VENV_PIP" install -U --disable-pip-version-check yt-dlp

NEW_VERSION="$(get_version)"
echo "new yt-dlp:     ${NEW_VERSION:-unknown}"

if [ "$OLD_VERSION" != "$NEW_VERSION" ]; then
    echo "version changed, restarting $SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
else
    echo "no version change, not restarting"
fi
