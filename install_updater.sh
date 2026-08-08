#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_SCRIPT="$APP_DIR/update_ytdlp.sh"
SERVICE_FILE="/etc/systemd/system/karaoke-server-update.service"
TIMER_FILE="/etc/systemd/system/karaoke-server-update.timer"

echo "==> App dir:        $APP_DIR"
echo "==> Update script:  $UPDATE_SCRIPT"
echo "==> Service file:   $SERVICE_FILE"
echo "==> Timer file:     $TIMER_FILE"

# --- 1. Write the updater script ---
echo "==> Writing $UPDATE_SCRIPT"
cat > "$UPDATE_SCRIPT" << "INNER_EOF"
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
INNER_EOF
chmod +x "$UPDATE_SCRIPT"

# --- 2. Write the systemd service unit ---
echo "==> Writing $SERVICE_FILE (needs sudo)"
sudo tee "$SERVICE_FILE" > /dev/null << UNIT_EOF
[Unit]
Description=Update yt-dlp for karaoke-server
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$UPDATE_SCRIPT
UNIT_EOF

# --- 3. Write the systemd timer unit ---
echo "==> Writing $TIMER_FILE (needs sudo)"
sudo tee "$TIMER_FILE" > /dev/null << "UNIT_EOF"
[Unit]
Description=Daily yt-dlp update check for karaoke-server

[Timer]
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true
Unit=karaoke-server-update.service

[Install]
WantedBy=timers.target
UNIT_EOF

# --- 4. Reload and enable the timer ---
echo "==> Reloading systemd and enabling timer"
sudo systemctl daemon-reload
sudo systemctl enable --now karaoke-server-update.timer

echo
echo "==> Timer status"
sudo systemctl list-timers karaoke-server-update.timer --no-pager
echo
echo "Done. Useful commands:"
echo "  sudo systemctl start karaoke-server-update.service   # run update now"
echo "  sudo systemctl list-timers karaoke-server-update"
echo "  journalctl -u karaoke-server-update -n 100"
echo "  sudo systemctl disable --now karaoke-server-update.timer  # turn it off"
