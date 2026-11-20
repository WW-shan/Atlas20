#!/bin/sh
# LS104 intraday data refresh only.  This wrapper never sources trading
# credentials and never calls the executor or Telegram sender.
set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$PROJECT_ROOT"

panel_wait=60
pre_execution=false
finalize_execution=false
latest_start=""
hour=$(date -u +%H)
minute=$(date -u +%M)
if [ "$hour" = "00" ] || { [ "$hour" = "01" ] && [ "$minute" -lt 5 ]; }; then
  pre_execution=true
  panel_wait=900
  # 00:55 is the bounded catch-up.  It must be allowed to start even though
  # the 00:50 cut-off has passed; otherwise a failed 00:35 prepare can never
  # be repaired before the 01:05 executor.  A fresh receipt still short-
  # circuits in the Python wrapper before this cut-off is evaluated.  Keep
  # the panel wait short so a stale panel fails over to the next retry rather
  # than holding the execution lock across 01:05.  The 01:00-01:04 branch
  # catches a launchd fire that was delayed past the top of the hour.
  if [ "$hour" = "01" ] || [ "$minute" -ge 55 ]; then
    latest_start="01:05"
    panel_wait=120
  fi
fi

# The 00:00 UTC bar is not published when the 00:35/00:55 prepare runs.  The
# 09:00 Beijing (01:00 UTC) fire is the bounded finalization window: fetch only
# the new mark tail and republish the receipt before the 09:05 executor.
if [ "$hour" = "01" ] && [ "$minute" -lt 5 ]; then
  finalize_execution=true
fi

# Build an argument vector instead of expanding a multi-word scalar.  macOS
# launchd invokes this file with zsh, which does not word-split an unquoted
# scalar; passing "--pre-execution --latest-start-utc 01:05" as one token makes
# argparse reject the entire refresh at the most important catch-up fire.
if [ "$finalize_execution" = true ]; then
  set -- --finalize-execution --mark-wait-seconds 120 --mark-poll-seconds 15
else
  set -- --skip-if-fresh-receipt --panel-wait-seconds "$panel_wait"
  if [ "$pre_execution" = true ]; then
    set -- "$@" --pre-execution
  fi
  if [ -n "$latest_start" ]; then
    set -- "$@" --latest-start-utc "$latest_start"
  fi
fi

exec .venv/bin/python scripts/refresh_derivatives_data.py "$@"
