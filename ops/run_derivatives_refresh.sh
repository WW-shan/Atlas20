#!/bin/sh
# LS104 intraday data refresh only.  This wrapper never sources trading
# credentials and never calls the executor or Telegram sender.
set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$PROJECT_ROOT"
prepare_arg=""
panel_wait=60
hour=$(date -u +%H)
minute=$(date -u +%M)
if [ "$hour" = "00" ] || { [ "$hour" = "01" ] && [ "$minute" -lt 5 ]; }; then
  prepare_arg="--pre-execution"
  panel_wait=900
  # 00:55 is the bounded catch-up.  It must be allowed to start even though
  # the 00:50 cut-off has passed; otherwise a failed 00:35 prepare can never
  # be repaired before the 01:05 executor.  A fresh receipt still short-
  # circuits in the Python wrapper before this cut-off is evaluated.  Keep
  # the panel wait short so a stale panel fails over to the next retry rather
  # than holding the execution lock across 01:05.  The 01:00-01:04 branch
  # catches a launchd fire that was delayed past the top of the hour.
  if [ "$hour" = "01" ] || [ "$minute" -ge 55 ]; then
    prepare_arg="--pre-execution --latest-start-utc 01:05"
    panel_wait=120
  fi
fi
exec .venv/bin/python scripts/refresh_derivatives_data.py \
  --skip-if-fresh-receipt --panel-wait-seconds "$panel_wait" $prepare_arg
