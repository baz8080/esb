#!/bin/sh
#
# Paste this into Synology DSM:
#   Control Panel -> Task Scheduler -> Create -> Scheduled Task -> User-defined script
#     Run command : bash /volume1/docker/esb/scripts/synology-task.sh
#     User        : root         (required for docker access)
#     Schedule    : daily, repeat every hour
#
# ALERTING: set ESB_ALERT_WEBHOOK below.
#
# DSM's own "Send run details by email" is a documented dead end - the Control
# Panel test email arrives, but per-task notifications silently never send. Leave
# those checkboxes ticked if you like (they cost nothing and may work on some DSM
# versions), but do not depend on them. The webhook is the channel that works,
# and `test-alert` proves it.

set -eu

IMAGE="esb-outages:latest"
DATA_DIR="/volume1/docker/esb/data"

# Where failures are sent. An ntfy.sh topic needs no account: pick an
# unguessable name, install the ntfy app, and subscribe to the same topic.
# Discord and Slack incoming webhook URLs work here too.
# ESB_ALERT_WEBHOOK="https://ntfy.sh/some-unguessable-topic-name"

# If ESB rotates the public API key, the poller exits 2 and alerts. Put the
# replacement here and the alert stops.
# ESB_API_KEY="..."

# After a reboot, Task Scheduler can fire before the Container Manager package
# has finished starting. Wait rather than reporting a spurious failure.
attempts=0
while [ ! -x /usr/local/bin/docker ] && [ "$attempts" -lt 60 ]; do
    attempts=$((attempts + 1))
    sleep 5
done

# Failures before the container starts have to be reported from here: the
# poller cannot alert about its own failure to run.
alert_locally() {
    printf '%s\n' "$1" >&2
    if [ -n "${ESB_ALERT_WEBHOOK:-}" ]; then
        curl -fsS -m 10 -H "Title: ESB poller failure" \
            -d "$1" "$ESB_ALERT_WEBHOOK" >/dev/null 2>&1 || true
    fi
}

if [ ! -x /usr/local/bin/docker ]; then
    alert_locally "ESB poller: docker never appeared at /usr/local/bin/docker.
The Container Manager package may be stopped or uninstalled. No outage data is
being collected."
    exit 1
fi

# The container runs as uid 1000, not root. A bind mount takes the host
# directory's ownership, so a directory created by root (or by `docker run -v`
# on first use) would be unwritable inside the container. Cheap and idempotent.
mkdir -p "$DATA_DIR"
chown 1000:1000 "$DATA_DIR"

status=0
/usr/local/bin/docker run --rm \
    --name esb-outages-poll \
    -v "$DATA_DIR":/data \
    -e TZ=Europe/Dublin \
    ${ESB_ALERT_WEBHOOK:+-e ESB_ALERT_WEBHOOK="$ESB_ALERT_WEBHOOK"} \
    ${ESB_API_KEY:+-e ESB_API_KEY="$ESB_API_KEY"} \
    "$IMAGE" poll || status=$?

# 2-6 mean the poller ran and has already alerted for itself, with far better
# detail than anything available out here. Anything else means it never got that
# far - a missing image, a dead daemon, an OOM kill - and would otherwise fail
# completely silently.
case "$status" in
    0 | 2 | 3 | 4 | 5 | 6) ;;
    *)
        alert_locally "ESB poller: container failed to run (exit $status).
The image '$IMAGE' may be missing, or the Docker daemon may be unhealthy.
No outage data is being collected."
        ;;
esac

exit "$status"
