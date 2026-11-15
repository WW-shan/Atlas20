#!/bin/zsh
# Atlas20 live health monitor wrapper (macOS / launchd).
#
# Read-only: never places orders and never touches the executor's state.
# Runs the audit plus drift/gross/execution-freshness checks and pushes a
# Telegram alert ONLY when something needs attention (silence = healthy).
#
# launchd does not read shell rc files, so this wrapper loads the credentials
# and the persisted track profile itself, exactly like the trading wrapper.

set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$CONFIG_DIR}"

BITGET_ENV="$CONFIG_DIR/bitget.env"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"
TRACK_ENV="$PROJECT_ROOT/config/track.env"

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

if [ -z "${ATLAS20_TRACK_PROFILE+x}" ]; then
  if [ ! -r "$TRACK_ENV" ]; then
    print -u2 "missing track profile file: $TRACK_ENV"
    print -u2 "missing ATLAS20_TRACK_PROFILE; refusing to monitor"
    exit 1
  fi
  set -a
  . "$TRACK_ENV"
  set +a
fi

cd "$PROJECT_ROOT"
TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-}"
if [ -z "$TRACK_PROFILE" ]; then
  print -u2 "missing ATLAS20_TRACK_PROFILE; refusing to monitor"
  exit 1
fi
case "$TRACK_PROFILE" in
  ls45-g125)
    SPEC="PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
    TARGETS_FILE="reports/ls45_live_g125/oos_targets.csv"
    MANIFEST_FILE="reports/ls45_live_g125/manifest.json"
    STATE_FILE="data/ls45_g125_execution_state.json"
    JOURNAL_FILE="reports/ls45_live_g125_live/journal.csv"
    HEALTH_JSON="reports/ls45_live_g125_live/health.json"
    AUDIT_JSON="reports/ls45_live_g125_live/audit.json"
    PRIOR_ORDER_REGISTRY=""
    ;;
  ls104-g175-m090)
    SPEC="PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090"
    TARGETS_FILE="reports/ls45_live_g175/oos_targets.csv"
    MANIFEST_FILE="reports/ls45_live_g175/manifest.json"
    STATE_FILE="data/ls45_g175_execution_state.json"
    JOURNAL_FILE="reports/ls45_live_g175_live/journal.csv"
    HEALTH_JSON="reports/ls45_live_g175_live/health.json"
    AUDIT_JSON="reports/ls45_live_g175_live/audit.json"
    PRIOR_ORDER_REGISTRY="reports/ls45_live_g175_live/prior_track_order_registry.json"
    ;;
  *)
    print -u2 "unknown ATLAS20_TRACK_PROFILE: $TRACK_PROFILE"
    exit 1
    ;;
esac
export ATLAS20_TRACK_PROFILE="$TRACK_PROFILE"
echo "Atlas20 monitor track profile: $TRACK_PROFILE"

PRIOR_ORDER_ARG=()
if [ -n "$PRIOR_ORDER_REGISTRY" ]; then
  PRIOR_ORDER_ARG=(--prior-track-registry "$PRIOR_ORDER_REGISTRY")
fi

exec .venv/bin/python scripts/monitor_live_track.py \
  --notify \
  --spec "$SPEC" \
  --state-file "$STATE_FILE" \
  --journal-file "$JOURNAL_FILE" \
  --targets-file "$TARGETS_FILE" \
  --manifest-file "$MANIFEST_FILE" \
  --out "$HEALTH_JSON" \
  --audit-out "$AUDIT_JSON" \
  "${PRIOR_ORDER_ARG[@]}"
