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

notified=""
notify() {
    notified=1
    printf '%s\n' "$1" >&2
    if [ -n "${ESB_ALERT_WEBHOOK:-}" ]; then
        curl -fsS -m 10 -H "Title: ESB backup failure" \
            -d "$1" "$ESB_ALERT_WEBHOOK" >/dev/null 2>&1 || true
    fi
}

# set -e stops the script at any other failed step (a stale .git/index.lock
# after a power cut, a full disk), which would otherwise exit unannounced.
trap 'rc=$?; [ "$rc" -eq 0 ] || [ -n "$notified" ] || notify "ESB backup: failed (exit $rc), so what is new may not be offsite.
See: journalctl -u esb-backup.service -n 20"' EXIT

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

branch="$(git symbolic-ref --short HEAD)"

# Pull in anything pushed to origin from elsewhere, so a rejected
# non-fast-forward push doesn't strand local commits until someone notices.
# Fetched outside the lock: a poll waits only two minutes for it.
fetch_origin() {
    if ! err=$(git fetch -q origin 2>&1); then
        notify "ESB backup: git fetch failed, so it's unknown whether origin has
commits this checkout lacks. Nothing was pushed: the data is on this disk but
not offsite.

$err"
        exit 1
    fi
}

# The poll appends to raw/ while it holds this lock, so under it a commit never
# carries a half-written line and the merge never meets a file mid-write. A
# poll holds it for up to its unit's 26-minute backstop. Every git run under it
# closes the descriptor, or a detached auto-gc would keep the lock afterwards.
lock() {
    exec 9>>.poll.lock
    if ! flock -w 1800 9; then
        notify "ESB backup: the poll lock was held for 30 minutes, longer than
systemd lets a poll run, so a long esb rebuild or compact is the likelier
holder. Nothing was backed up this time."
        exit 1
    fi
}

# Committed again on a retry: a poll may have appended since the first time,
# and git refuses to merge over uncommitted changes to a file origin touched.
commit_and_merge() {
    git add -A .gitignore raw 9>&-
    if git diff --cached --quiet 9>&-; then
        echo "no new data to commit"
    else
        git -c user.name="esb-collector" -c user.email="esb-collector@localhost" \
            commit -q -m "Outage data through $(date -u '+%Y-%m-%dT%H:%M:%SZ')" 9>&-
    fi
    if git rev-parse --verify -q "origin/$branch" >/dev/null 9>&- &&
        ! err=$(git -c user.name="esb-collector" -c user.email="esb-collector@localhost" \
            merge -q --no-edit "origin/$branch" 2>&1 9>&-); then
        git merge --abort 2>/dev/null 9>&- || true
        notify "ESB backup: origin has commits that conflict with $DATA_DIR.
Resolve manually, then re-run this script.

$err"
        exit 1
    fi
}

fetch_origin
lock
commit_and_merge
exec 9>&-

# Push unconditionally, even when there was nothing new to commit. A previous
# push may have failed and left commits sitting only on this disk; treating
# "nothing to commit" as "nothing to do" would report success forever while the
# data was never actually offsite. Pushing an up-to-date branch is a cheap no-op.
# The fetch can be half an hour old after a wait for the lock, so a push another
# host made meanwhile gets one more fetch and merge before it counts as failed.
if ! git push -q origin HEAD 2>/dev/null; then
    fetch_origin
    lock
    commit_and_merge
    exec 9>&-
    if ! err=$(git push -q origin HEAD 2>&1); then
        notify "ESB backup: git push failed. The data is committed locally but is
NOT offsite, so an SD card failure would still lose everything since the last
successful push.

$err"
        exit 1
    fi
fi

echo "backed up through $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
