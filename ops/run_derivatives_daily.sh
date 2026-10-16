#!/bin/sh
# Atlas20 derivatives daily automation wrapper.
#
# Runs the full live chain in one job, in order, with the credentials that the
# trade step needs:
#
#   1. decide whether this load may trade at all              (preflight window)
#   2. repair the point-in-time Top20 panel if it lags        (self-heal)
#   3. refresh Bitget mark candles and rebuild the book       (derivatives-oos)
#   4. size the book from the real account equity, place the orders, write the
#      journal, and push the Telegram report                  (execute-plan-live)
#
# Why a wrapper instead of a ProgramArguments one-liner: launchd does not read
# ~/.zshrc or any shell rc file, so export statements living in a shell profile
# are invisible to the job. The Bitget and Telegram credentials live outside
# the repo on purpose; this script is the single place that loads them, and it
# fails closed if they are missing.
#
# Written for POSIX sh because the same file is the entry point for both
# deployments: macOS launchd (ops/com.atlas20.derivatives-execute.plist, which
# calls /bin/zsh explicitly) and Ubuntu systemd
# (ops/systemd/atlas20-derivatives-execute.service). The Ubuntu host keeps the
# checkout and the credentials somewhere else, so both paths are overridable.
#
# The schedule fires at 11:05 Beijing = 03:05 UTC, five minutes after the
# model's T+1 03:00 UTC fill point. macOS also loads the job at boot
# (RunAtLoad) and systemd replays a missed timer fire (Persistent=true);
# scripts/live_chain_preflight.py is what keeps those from turning into a
# second trade or an out-of-hours one.
#
# Do not run two copies at once: launchd carries a start-interval throttle, the
# refresh step takes its own lock, and the executor is idempotent per run day.

set -eu

# Defaults target this workstation; the deployments below override them.
PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$CONFIG_DIR}"

BITGET_ENV="$CONFIG_DIR/bitget.env"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"

# launchd starts jobs with a minimal PATH; systemd units start with almost
# none. make, git and the venv python all need to be reachable.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

for env_file in "$BITGET_ENV" "$TELEGRAM_ENV"; do
  if [ ! -r "$env_file" ]; then
    echo "missing credentials file: $env_file" >&2
    exit 1
  fi
done

set -a
. "$BITGET_ENV"
. "$TELEGRAM_ENV"
set +a

cd "$PROJECT_ROOT"

# --- 1. May this load trade? -------------------------------------------------
# The preflight exits 3 when a documented reason says no (before the fill
# point, today's run day already succeeded, or past the catch-up budget) and
# anything else on a real error, which must still abort the job loudly.
#
# A manual `ops/run_derivatives_daily.sh --force` is the operator's deliberate
# late catch-up and drops *only* the window gate.  The panel self-heal below
# and every executor guard still apply, and the executor's per-run-day
# idempotency still refuses a second trade.  Neither launchd nor systemd ever
# passes an argument, so the scheduled and boot-replay fires always obey the
# window.
window_status=0
if [ "${1:-}" = "--force" ]; then
  .venv/bin/python scripts/live_chain_preflight.py --check window --force || window_status=$?
else
  .venv/bin/python scripts/live_chain_preflight.py --check window || window_status=$?
fi
if [ "$window_status" -eq 3 ]; then
  exit 0
elif [ "$window_status" -ne 0 ]; then
  echo "live chain window preflight failed with status $window_status" >&2
  exit "$window_status"
fi

# --- 2. Self-heal the panel --------------------------------------------------
# A shutdown in the middle of the daily refresh leaves the panel a day behind
# while the Bitget marks keep moving; the executor would then fail closed and
# silently skip the day. Repair it once here, waiting for a scheduled refresh
# that is already in flight instead of racing it. If the panel is still stale
# afterwards the executor's own guard remains the backstop and refuses to
# trade.
panel_status=0
.venv/bin/python scripts/live_chain_preflight.py --check panel || panel_status=$?
if [ "$panel_status" -eq 3 ]; then
  echo "panel lags the last completed UTC day; refreshing before the chain" >&2
  .venv/bin/python scripts/refresh_daily_data.py \
    --config config/base.yaml \
    --wait-seconds 900
elif [ "$panel_status" -ne 0 ]; then
  echo "live chain panel preflight failed with status $panel_status" >&2
  exit "$panel_status"
fi

# --- 3/4. The chain itself ---------------------------------------------------
# Refresh the Bitget mark tree before the book is rebuilt; the executor refuses
# to trade on a stale mark tree, so this order is mandatory.
/usr/bin/make derivatives-oos-data derivatives-oos execute-plan-live
