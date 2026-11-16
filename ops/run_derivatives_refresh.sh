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
if [ "$(date -u +%H)" = "00" ]; then
  prepare_arg="--pre-execution"
  panel_wait=900
fi
exec .venv/bin/python scripts/refresh_derivatives_data.py \
  --skip-if-fresh-receipt --panel-wait-seconds "$panel_wait" $prepare_arg
