#!/bin/sh
# Inner body of the 08:30 data node.
#
# The launchd/systemd entry point wraps this file in scripts/run_node_deadline.py
# so the *entire* handoff (panel, Bitget tail, Top50 and receipt) has one hard
# 08:50 Beijing deadline.  Keeping the body separate also makes that boundary
# directly testable without starting a production download.
set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$CONFIG_DIR}"
TRACK_ENV="$PROJECT_ROOT/config/track.env"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [ -z "${ATLAS20_TRACK_PROFILE+x}" ]; then
  if [ ! -r "$TRACK_ENV" ]; then
    echo "missing track profile file: $TRACK_ENV" >&2
    exit 1
  fi
  set -a
  . "$TRACK_ENV"
  set +a
fi
cd "$PROJECT_ROOT"
TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-}"
case "$TRACK_PROFILE" in
  ls45-g125|ls104-g175-m090) ;;
  *) echo "unknown ATLAS20_TRACK_PROFILE: $TRACK_PROFILE" >&2; exit 1 ;;
esac
export ATLAS20_TRACK_PROFILE="$TRACK_PROFILE"
echo "Atlas20 data track profile: $TRACK_PROFILE"

LOCK_FILE="data/derivatives_execution.lock"
lock_status=0
.venv/bin/python scripts/refresh_derivatives_data.py --check-lock --lock-file "$LOCK_FILE" || lock_status=$?
if [ "$lock_status" -eq 3 ]; then
  echo "another Atlas20 execution holds $LOCK_FILE; signal already completed"
  exit 0
elif [ "$lock_status" -ne 0 ]; then
  exit "$lock_status"
fi

.venv/bin/python scripts/refresh_daily_data.py \
  --config config/base.yaml \
  --wait-seconds 300
/usr/bin/make derivatives-live-data
/usr/bin/make top50-readiness-unlocked
/usr/bin/make top50-readiness-check

# This receipt is the only completion boundary the signal node trusts.  It
# binds the finished panel/metadata/symbol map to the exact READY Top50 pointer
# consumed by the signal, so a slow download cannot be mistaken for completion
# merely because the 08:35 clock has arrived.
.venv/bin/python scripts/data_ready_receipt.py write
