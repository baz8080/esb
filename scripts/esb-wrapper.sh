#!/bin/sh
#
# Installed as /usr/local/bin/esb by install-native.sh.
#
# Runs the collector as its service user with the right data directory and
# environment, so day-to-day commands are just:
#
#   sudo esb stats
#   sudo esb check
#   sudo esb test-alert
#   sudo esb rebuild

set -eu

PREFIX="/opt/esb-outages"
DATA_DIR="/var/lib/esb-outages"
ENV_FILE="/etc/esb-outages.env"
SERVICE_USER="esb"

# Readable only by root, which is why these commands need sudo.
if [ -r "$ENV_FILE" ]; then
    . "$ENV_FILE"
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "esb: run with sudo (needs to read $ENV_FILE and write as $SERVICE_USER)" >&2
    exit 1
fi

exec sudo -u "$SERVICE_USER" env \
    ESB_DATA_DIR="$DATA_DIR" \
    ${ESB_ALERT_WEBHOOK:+ESB_ALERT_WEBHOOK="$ESB_ALERT_WEBHOOK"} \
    ${ESB_API_KEY:+ESB_API_KEY="$ESB_API_KEY"} \
    sh -c 'cd "$1" && shift && exec python3 -m esb_outages "$@"' _ "$PREFIX" "$@"
