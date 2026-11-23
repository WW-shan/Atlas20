#!/bin/sh
# Atlas20 daily 09:05 production entry point.
#
# The daily production chain has exactly four business nodes:
#
#   1. data refresh        (prepared before the fill clock)
#   2. signal construction (prepared before the fill clock)
#   3. execution           (T+1 01:05 UTC / 09:05 Beijing)
#   4. read-only monitor   (19:00 Beijing)
#
# The 09:05 clock is the same clock used by the live-parity backtest.  It is
# not a data-rebuild clock and there is no automatic catch-up: a missed or
# failed execution is surfaced by the monitor and handled by an operator.
#
# Credentials are loaded here because launchd does not read shell rc files.

set -eu

# Defaults target this workstation; the deployments below override them.
PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$CONFIG_DIR}"

BITGET_ENV="$CONFIG_DIR/bitget.env"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"
TRACK_ENV="$PROJECT_ROOT/config/track.env"

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

# The non-secret profile pin lives in the repository so launchd, systemd and
# an interactive shell all read the same tracked value. Credentials remain in
# the external config directory. An explicit environment variable wins, which
# keeps emergency rollback to LS45 one command away.
if [ -z "${ATLAS20_TRACK_PROFILE+x}" ]; then
  if [ ! -r "$TRACK_ENV" ]; then
    echo "missing track profile file: $TRACK_ENV" >&2
    echo "missing ATLAS20_TRACK_PROFILE; refusing to trade" >&2
    exit 1
  fi
  set -a
  . "$TRACK_ENV"
  set +a
fi

cd "$PROJECT_ROOT"

# One wrapper serves both frozen tracks without rewriting either profile's
# target, state, journal, audit or kill-switch files.
TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-}"
if [ -z "$TRACK_PROFILE" ]; then
  echo "missing ATLAS20_TRACK_PROFILE; refusing to trade" >&2
  exit 1
fi
case "$TRACK_PROFILE" in
  ls45-g125)
    SPEC="PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
    TARGETS_FILE="reports/ls45_live_g125/oos_targets.csv"
    MANIFEST_FILE="reports/ls45_live_g125/manifest.json"
    STATE_FILE="data/ls45_g125_execution_state.json"
    JOURNAL_FILE="reports/ls45_live_g125_live/journal.csv"
    JSON_OUT="reports/ls45_live_g125_live/latest.json"
    KILL_FILE="data/ls45_g125_execution.KILL"
    LEVERAGE="2.0"
    MAX_GROSS="1.25"
    MARGIN_CAP="0.85"
    ;;
  ls104-g175-m090)
    SPEC="PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090"
    TARGETS_FILE="reports/ls45_live_g175/oos_targets.csv"
    MANIFEST_FILE="reports/ls45_live_g175/manifest.json"
    STATE_FILE="data/ls45_g175_execution_state.json"
    JOURNAL_FILE="reports/ls45_live_g175_live/journal.csv"
    JSON_OUT="reports/ls45_live_g175_live/latest.json"
    KILL_FILE="data/ls45_g175_execution.KILL"
    LEVERAGE="4.0"
    MAX_GROSS="1.75"
    MARGIN_CAP="0.90"
    ;;
  *)
    echo "unknown ATLAS20_TRACK_PROFILE: $TRACK_PROFILE" >&2
    exit 1
    ;;
esac
export ATLAS20_TRACK_PROFILE="$TRACK_PROFILE"
echo "Atlas20 track profile: $TRACK_PROFILE"

LOCK_FILE="data/derivatives_execution.lock"

# Data and signal are separate scheduled nodes.  This entry point only checks
# that their outputs exist and then performs the one live execution attempt.
# It deliberately does not acquire the data/signal lock, rebuild anything, or
# retry a failed order run.
.venv/bin/python scripts/execute_live_plan.py \
  --live --notify --require-isolated \
  --spec "$SPEC" \
  --targets-file "$TARGETS_FILE" \
  --manifest-file "$MANIFEST_FILE" \
  --state-file "$STATE_FILE" \
  --journal-file "$JOURNAL_FILE" \
  --json-out "$JSON_OUT" \
  --kill-switch "$KILL_FILE" \
  --lock-file "$LOCK_FILE" \
  --leverage "$LEVERAGE" \
  --max-gross-multiple "$MAX_GROSS" \
  --max-margin-utilization "$MARGIN_CAP"
