#!/bin/zsh
# Atlas20 live health monitor wrapper (macOS / launchd).
#
# Read-only: never places orders and never touches the executor's state.
# Runs the audit plus drift/gross/execution-freshness checks and pushes a
# Telegram alert ONLY when something needs attention (silence = healthy).
#
# launchd does not read shell rc files, so this wrapper loads the credentials
# itself, exactly like ops/run_derivatives_daily.sh.

set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

for env_file in "$CONFIG_DIR/bitget.env" "$CONFIG_DIR/telegram.env"; do
  if [ ! -r "$env_file" ]; then
    print -u2 "missing credentials file: $env_file"
    exit 1
  fi
done

set -a
. "$CONFIG_DIR/bitget.env"
. "$CONFIG_DIR/telegram.env"
set +a

cd "$PROJECT_ROOT"
exec .venv/bin/python scripts/monitor_live_track.py --notify
