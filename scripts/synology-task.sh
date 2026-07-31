#!/bin/sh
#
# Paste this into Synology DSM:
#   Control Panel -> Task Scheduler -> Create -> Scheduled Task -> User-defined script
#
# Settings that matter:
#   User      : root         (required for docker access)
#   Schedule  : daily, repeat every hour
#   Notification tab:
#     [x] Send run details by email
#     [x] Send run details only when the script terminates abnormally
#
# The second checkbox is the whole alerting design: DSM emails this script's
# output only when it exits non-zero, and the collector exits non-zero only when
# something needs a human. Requires Control Panel -> Notification -> Email to be
# configured first.

set -eu

IMAGE="esb-outages:latest"
DATA_DIR="/volume1/docker/esb/data"

# If ESB ever rotates the public API key, the poller will exit 2 and email you.
# Put the replacement here and the alert stops.
# ESB_API_KEY="..."

# After a reboot, Task Scheduler can fire before the Container Manager package
# has finished starting. Wait rather than reporting a spurious failure.
attempts=0
while [ ! -x /usr/local/bin/docker ] && [ "$attempts" -lt 60 ]; do
    attempts=$((attempts + 1))
    sleep 5
done

if [ ! -x /usr/local/bin/docker ]; then
    echo "docker binary never appeared at /usr/local/bin/docker" >&2
    exit 1
fi

# The container runs as uid 1000, not root. A bind mount takes the host
# directory's ownership, so a directory created by root (or by `docker run -v`
# on first use) would be unwritable inside the container. Cheap and idempotent.
mkdir -p "$DATA_DIR"
chown 1000:1000 "$DATA_DIR"

exec /usr/local/bin/docker run --rm \
    --name esb-outages-poll \
    -v "$DATA_DIR":/data \
    -e TZ=Europe/Dublin \
    ${ESB_API_KEY:+-e ESB_API_KEY="$ESB_API_KEY"} \
    "$IMAGE" poll
