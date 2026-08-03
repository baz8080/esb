#!/bin/sh
#
# Install the collector natively (no Docker) on a systemd host such as a
# Raspberry Pi. Run from a checkout of this repository:
#
#   sudo sh scripts/install-native.sh
#
# Idempotent: safe to re-run after a git pull to deploy an update.

set -eu

PREFIX="/opt/esb-outages"
DATA_DIR="/var/lib/esb-outages"
ENV_FILE="/etc/esb-outages.env"
SERVICE_USER="esb"

SRC=$(cd "$(dirname "$0")/.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "must run as root (use sudo)" >&2
    exit 1
fi

# The collector is standard library only, so this is the entire dependency list.
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "python3 3.9 or newer is required; found $(python3 -V 2>&1)" >&2
    exit 1
fi

# Timezone data must be present or every timestamp fails to parse. Standard on
# Raspberry Pi OS and Debian, but worth failing loudly rather than collecting
# months of outages with null times.
if ! python3 -c 'from zoneinfo import ZoneInfo; ZoneInfo("Europe/Dublin")' 2>/dev/null; then
    echo "Europe/Dublin timezone unavailable. Install tzdata:" >&2
    echo "  sudo apt-get install -y tzdata" >&2
    exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "creating service user $SERVICE_USER"
    useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

echo "installing code to $PREFIX"
mkdir -p "$PREFIX"
rm -rf "$PREFIX/esb_outages" "$PREFIX/scripts"
cp -r "$SRC/esb_outages" "$PREFIX/"
cp -r "$SRC/scripts" "$PREFIX/"
chmod +x "$PREFIX/scripts/"*.sh

mkdir -p "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"

if [ ! -f "$ENV_FILE" ]; then
    echo "creating $ENV_FILE"
    cat > "$ENV_FILE" <<'ENVEOF'
# Failure alerts. Without this, the collector can stop and nobody will know.
# An ntfy.sh topic needs no account - pick an unguessable name.
#ESB_ALERT_WEBHOOK=https://ntfy.sh/change-me-to-something-unguessable

# Only needed if ESB rotates the de-facto public key.
#ESB_API_KEY=
ENVEOF
    chmod 600 "$ENV_FILE"
fi

echo "installing systemd units"
cp "$SRC/scripts/systemd/native/"*.service "$SRC/scripts/systemd/native/"*.timer \
    /etc/systemd/system/
systemctl daemon-reload

echo
echo "Installed. Next:"
echo "  1. Set ESB_ALERT_WEBHOOK in $ENV_FILE"
echo "  2. Verify:  sudo -u $SERVICE_USER ESB_DATA_DIR=$DATA_DIR python3 -m esb_outages check"
echo "     (run it from $PREFIX)"
echo "  3. One run: sudo systemctl start esb-outages.service"
echo "  4. Enable:  sudo systemctl enable --now esb-outages.timer"
echo "  5. Watch:   journalctl -u esb-outages.service -n 20"
