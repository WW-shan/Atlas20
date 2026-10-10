#!/bin/zsh
# Atlas20 derivatives daily automation wrapper (macOS / launchd).
#
# Runs the full live chain in one job, in order, with the credentials that the
# trade step needs:
#
#   1. refresh the point-in-time Top20 panel from CMC          (daily refresh data)
#   2. refresh Bitget mark candles and rebuild the target book (derivatives-oos-data / -oos)
#   3. size the book from the real account equity, place the orders, write the
#      journal, and push the Telegram report                    (execute-plan-live)
#
# Why a wrapper instead of a ProgramArguments one-liner: launchd does not read
# ~/.zshrc or any shell rc file, so export statements living in a shell profile
# are invisible to the job. The Bitget and Telegram credentials live outside
# the repo on purpose; this script is the single place that loads them, and it
# fails closed if they are missing.
#
# The schedule (ops/com.atlas20.derivatives-execute.plist) fires at 11:05
# Beijing = 03:05 UTC, five minutes after the model's T+1 03:00 UTC fill point
# and after the 02:30 UTC panel refresh. Do not run two copies at once: the
# plist also carries a start-interval throttle, and the executor itself is
# idempotent per run day.

set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
BITGET_ENV="$CONFIG_DIR/bitget.env"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"

# launchd starts jobs with a minimal PATH; make, git and the venv python all
# need to be reachable.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

for env_file in "$BITGET_ENV" "$TELEGRAM_ENV"; do
  if [ ! -r "$env_file" ]; then
    print -u2 "missing credentials file: $env_file"
    exit 1
  fi
done

set -a
. "$BITGET_ENV"
. "$TELEGRAM_ENV"
set +a

cd "$PROJECT_ROOT"

# Refresh the panel and the Bitget mark tree before the book is rebuilt; the
# executor refuses to trade on a stale mark tree, so this order is mandatory.
/usr/bin/make derivatives-oos-data derivatives-oos execute-plan-live
