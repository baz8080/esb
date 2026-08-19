#!/bin/sh
#
# Commit and push the raw logs to a git remote, as an offsite backup.
#
# One-time setup (see README for the full walkthrough):
#   cd /var/lib/esb-outages
#   git init -b main
#   git remote add origin git@github.com:<you>/esb-data.git
#
# Only raw/ is committed. esb.db is deliberately excluded: it is a binary that
# rewrites wholesale every run, so git cannot delta it, and it is rebuildable
# from raw/ anyway. The raw logs alone are a complete backup.

set -eu

DATA_DIR="${ESB_DATA_DIR:-/var/lib/esb-outages}"

notify() {
    printf '%s\n' "$1" >&2
    if [ -n "${ESB_ALERT_WEBHOOK:-}" ]; then
        curl -fsS -m 10 -H "Title: ESB backup failure" \
            -d "$1" "$ESB_ALERT_WEBHOOK" >/dev/null 2>&1 || true
    fi
}

cd "$DATA_DIR" || {
    notify "ESB backup: $DATA_DIR does not exist. Nothing is being backed up."
    exit 1
}

if [ ! -d .git ]; then
    notify "ESB backup: $DATA_DIR is not a git repository. Run the one-time
setup in scripts/backup-to-git.sh. Nothing is being backed up."
    exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
    notify "ESB backup: no 'origin' remote configured in $DATA_DIR.
Nothing is being backed up."
    exit 1
fi

# Belt and braces: the poller never writes anything but raw/ and esb.db, but an
# accidentally committed database would bloat the repo permanently.
if [ ! -f .gitignore ]; then
    printf 'esb.db\nesb.db-wal\nesb.db-shm\n.poll.lock\n.write-test\n' > .gitignore
fi

git add -A .gitignore raw

if git diff --cached --quiet; then
    echo "no new data to commit"
else
    git -c user.name="esb-collector" -c user.email="esb-collector@localhost" \
        commit -q -m "Outage data through $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
fi

# Pull in anything pushed to origin from elsewhere first, so a rejected
# non-fast-forward push doesn't strand local commits until someone notices.
branch="$(git rev-parse --abbrev-ref HEAD)"
if ! git fetch -q origin 2>/tmp/esb-backup-fetch.err; then
    notify "ESB backup: git fetch failed, so it's unknown whether origin has
commits this checkout lacks. Data is committed locally but not pushed.

$(cat /tmp/esb-backup-fetch.err)"
    exit 1
fi

if git rev-parse --verify -q "origin/$branch" >/dev/null &&
    ! git merge -q --no-edit "origin/$branch" 2>/tmp/esb-backup-merge.err; then
    git merge --abort 2>/dev/null || true
    notify "ESB backup: origin has commits that conflict with $DATA_DIR.
Resolve manually, then re-run this script.

$(cat /tmp/esb-backup-merge.err)"
    exit 1
fi

# Push unconditionally, even when there was nothing new to commit. A previous
# push may have failed and left commits sitting only on this disk; treating
# "nothing to commit" as "nothing to do" would report success forever while the
# data was never actually offsite. Pushing an up-to-date branch is a cheap no-op.
if ! git push -q origin HEAD 2>/tmp/esb-backup-push.err; then
    notify "ESB backup: git push failed. The data is committed locally but is
NOT offsite, so an SD card failure would still lose everything since the last
successful push.

$(cat /tmp/esb-backup-push.err)"
    exit 1
fi

echo "backed up through $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
