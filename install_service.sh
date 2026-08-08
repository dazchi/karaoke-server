#!/bin/bash
set -e

SERVICE_NAME="karaoke-server"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$APP_DIR/.venv/bin/python"
APP_SCRIPT="$APP_DIR/app.py"
UNIT_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# When invoked via sudo, prefer the invoking user, not root
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"

echo "==> Installing $SERVICE_NAME as a systemd service"
echo "    App dir:  $APP_DIR"
echo "    Python:   $VENV_PYTHON"
echo "    Run as:   $RUN_USER:$RUN_GROUP"
echo "    Unit:     $UNIT_FILE"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ERROR: venv python not found at $VENV_PYTHON" >&2
    exit 1
fi
if [ ! -f "$APP_SCRIPT" ]; then
    echo "ERROR: app.py not found at $APP_SCRIPT" >&2
    exit 1
fi

echo "==> Stopping any manually-running instance"
pkill -f "python app.py" 2>/dev/null || true
while pgrep -f "python app.py" >/dev/null; do sleep 0.2; done

echo "==> Writing unit file (needs sudo)"
sudo tee "$UNIT_FILE" >/dev/null <<UNIT
[Unit]
Description=Karaoke Server (Flask + audio-separator)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
Group=$RUN_GROUP
WorkingDirectory=$APP_DIR
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$VENV_PYTHON $APP_SCRIPT
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

echo "==> Reloading systemd, enabling and starting service"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"

echo "==> Status"
sudo systemctl status "$SERVICE_NAME" --no-pager
echo
echo "Done. Useful commands:"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl disable $SERVICE_NAME"
echo "  journalctl -u $SERVICE_NAME -f"
