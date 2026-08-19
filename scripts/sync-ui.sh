#!/bin/sh
# Refresh the vendored shared UI from ../statusui (see esb_site/ui/UPSTREAM).
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
exec "$here/../statusui/sync.sh" "$here/esb_site/ui"
