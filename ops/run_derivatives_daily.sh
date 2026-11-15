#!/bin/sh
# Atlas20 derivatives daily automation wrapper.
#
# Runs the full live chain in one job, in order, with the credentials that the
# trade step needs:
#
#   1. decide whether this load may trade at all              (preflight window)
#   2. repair the point-in-time Top20 panel if it lags        (self-heal)
#   3. refresh Bitget mark candles and rebuild the selected track book
#   4. audit CMC/mark/funding/contract reliability                  (audit-data)
#   5. size the book from the real account equity, place the orders, write the
#      journal, and push the Telegram report                  (derivatives-live)
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
# The primary schedule fires at 09:05 Beijing = 01:05 UTC, the owner-approved
# live fast path after the 08:30/08:50 Beijing panel refresh and catch-up. The
# 01:35/03:05/03:35/04:35/06:35 UTC fires remain fallbacks; a successful same-day
# alpha execution makes those retries non-alpha no-ops, but they still run the
# risk-reducing protect-only path and the read-only monitor.
# macOS loads the job at boot (RunAtLoad) and
# systemd replays a missed timer fire (Persistent=true);
# scripts/live_chain_preflight.py keeps those from turning into a second trade
# or an out-of-hours one.
#
# Do not run two copies at once: launchd carries a start-interval throttle, the
# refresh step takes its own lock, and the executor is idempotent per run day
# plus exact target-book identity; protect-only never opens or increases risk.

set -eu

# Defaults target this workstation; the deployments below override them.
PROJECT_ROOT="/Users/ww/Project/Atlas20"
CONFIG_DIR="$HOME/.config/atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$CONFIG_DIR}"

BITGET_ENV="$CONFIG_DIR/bitget.env"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"
TRACK_ENV="$CONFIG_DIR/track.env"

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

# Persistent track selection lives outside the repository so launchd and
# systemd see the same choice as an interactive shell.  An explicit environment
# variable wins, which keeps emergency rollback to LS45 one command away.
if [ -r "$TRACK_ENV" ] && [ -z "${ATLAS20_TRACK_PROFILE+x}" ]; then
  set -a
  . "$TRACK_ENV"
  set +a
fi

cd "$PROJECT_ROOT"

# One wrapper serves both frozen tracks without rewriting either profile's
# target, state, journal, audit or kill-switch files.
TRACK_PROFILE="${ATLAS20_TRACK_PROFILE:-ls45-g125}"
case "$TRACK_PROFILE" in
  ls45-g125)
    SPEC="PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
    TARGETS_FILE="reports/ls45_live_g125/oos_targets.csv"
    MANIFEST_FILE="reports/ls45_live_g125/manifest.json"
    STATE_FILE="data/ls45_g125_execution_state.json"
    JOURNAL_FILE="reports/ls45_live_g125_live/journal.csv"
    JSON_OUT="reports/ls45_live_g125_live/latest.json"
    AUDIT_JSON="reports/ls45_live_g125_live/audit.json"
    HEALTH_JSON="reports/ls45_live_g125_live/health.json"
    KILL_FILE="data/ls45_g125_execution.KILL"
    PRIOR_ORDER_REGISTRY=""
    SYMBOL_AUDIT_JSON="reports/ls45_live_g125_live/venue_symbol_audit.json"
    SIGNAL_TARGET="derivatives-ls45-signal"
    DATA_AUDIT_TARGET="audit-data"
    SIGNAL_AUDIT_TARGET="audit-signal"
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
    AUDIT_JSON="reports/ls45_live_g175_live/audit.json"
    HEALTH_JSON="reports/ls45_live_g175_live/health.json"
    KILL_FILE="data/ls45_g175_execution.KILL"
    PRIOR_ORDER_REGISTRY="reports/ls45_live_g175_live/prior_track_order_registry.json"
    SYMBOL_AUDIT_JSON="reports/ls45_live_g175_live/venue_symbol_audit.json"
    SIGNAL_TARGET="derivatives-ls104-signal"
    DATA_AUDIT_TARGET="audit-data-ls104"
    SIGNAL_AUDIT_TARGET="audit-signal-ls104"
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

# A new track starts from an empty state/journal.  The first application of
# its frozen book is an explicit one-time bootstrap, not a late replay of an
# old signal.  Once any state file exists, retries use the normal active-event
# completion path and this flag is never added again.
BOOTSTRAP_ARG=""
if [ "$TRACK_PROFILE" = "ls104-g175-m090" ] && [ ! -e "$STATE_FILE" ]; then
  BOOTSTRAP_ARG="--bootstrap-track"
fi
PRIOR_ORDER_ARG=""
if [ -n "$PRIOR_ORDER_REGISTRY" ]; then
  PRIOR_ORDER_ARG="--prior-track-registry $PRIOR_ORDER_REGISTRY"
fi

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
late_arg=""
window_status=0
if [ "${1:-}" = "--force" ]; then
  .venv/bin/python scripts/live_chain_preflight.py \
    --check window --force \
    --manifest-file "$MANIFEST_FILE" \
    --state-file "$STATE_FILE" || window_status=$?
  late_arg="--allow-late-execution"
else
  .venv/bin/python scripts/live_chain_preflight.py \
    --check window \
    --manifest-file "$MANIFEST_FILE" \
    --state-file "$STATE_FILE" || window_status=$?
fi
if [ "$window_status" -eq 4 ]; then
  # Today's trade is already complete.  Run risk-reducing protection only:
  # reconcile venue-triggered stops, normalize/restore every short stop, and
  # enforce the gross cap.  OPEN/INCREASE are structurally disabled, so this
  # cannot add risk on a fallback fire.
  protect_status=0
  .venv/bin/python scripts/execute_live_plan.py \
    --live --notify --require-isolated --protect-only \
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
    --max-margin-utilization "$MARGIN_CAP" || protect_status=$?

  monitor_status=0
  .venv/bin/python scripts/monitor_live_track.py \
    --notify --spec "$SPEC" \
    --state-file "$STATE_FILE" \
    --journal-file "$JOURNAL_FILE" \
    --targets-file "$TARGETS_FILE" \
    --manifest-file "$MANIFEST_FILE" \
    --out "$HEALTH_JSON" \
    --audit-out "$AUDIT_JSON" $PRIOR_ORDER_ARG || monitor_status=$?

  if [ "$protect_status" -ne 0 ]; then
    exit "$protect_status"
  fi
  exit "$monitor_status"
elif [ "$window_status" -eq 3 ]; then
  exit 0
elif [ "$window_status" -ne 0 ]; then
  echo "live chain window preflight failed with status $window_status" >&2
  exit "$window_status"
fi

# --- 2. Self-heal and re-check the panel -------------------------------------
# A shutdown in the middle of the daily refresh leaves the panel a day behind
# while the Bitget marks keep moving; the executor would then fail closed and
# silently skip the day. Repair it once here, waiting for a scheduled refresh
# that is already in flight instead of racing it. The panel can also carry the
# right date while the newest provider day is still partial; --force rebuilds
# that case instead of letting refresh_daily_data.py skip it as date-current.
# Re-check after the refresh: a lock timeout or an unfinished provider day must
# stop the chain before any order is planned.
panel_status=0
.venv/bin/python scripts/live_chain_preflight.py --check panel || panel_status=$?
if [ "$panel_status" -eq 3 ]; then
  echo "panel is stale or partial; forcing a rebuild before the chain" >&2
  .venv/bin/python scripts/refresh_daily_data.py \
    --config config/base.yaml \
    --force \
    --wait-seconds 900
elif [ "$panel_status" -ne 0 ]; then
  echo "live chain panel preflight failed with status $panel_status" >&2
  exit "$panel_status"
fi

panel_status=0
.venv/bin/python scripts/live_chain_preflight.py --check panel || panel_status=$?
if [ "$panel_status" -eq 3 ]; then
  echo "panel is still stale or partial after self-heal; refusing to trade" >&2
  exit 1
elif [ "$panel_status" -ne 0 ]; then
  echo "live chain panel recheck failed with status $panel_status" >&2
  exit "$panel_status"
fi

# --- 3/4. The chain itself ---------------------------------------------------
# Refresh the Bitget mark tree, rebuild the selected frozen ledger, then execute.
# The executor refuses to trade on stale data, so this order is mandatory.
# A human `--force` catch-up also passes the executor's explicit late-window
# acknowledgement; scheduled fires never receive that argument.
/usr/bin/make derivatives-live-data "$SIGNAL_TARGET"
/usr/bin/make audit-data-chain
.venv/bin/python scripts/audit_venue_symbols.py \
  --required-leverage "$LEVERAGE" \
  --out "$SYMBOL_AUDIT_JSON"
/usr/bin/make "$DATA_AUDIT_TARGET"
/usr/bin/make "$SIGNAL_AUDIT_TARGET"

# Independent post-trade verification.  The executor already validates its own
# fills and stops, but a read-only full-account audit here catches any mismatch
# between the venue's final book, the frozen target and the journal while the
# operator is still close to the execution window.  Run it even after a partial
# execution so its Telegram alert describes the actual venue state; then
# preserve the execution failure as the wrapper's exit status.
execution_status=0
.venv/bin/python scripts/execute_live_plan.py \
  --live --notify --require-isolated $late_arg \
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
  --max-margin-utilization "$MARGIN_CAP" $BOOTSTRAP_ARG || execution_status=$?

monitor_status=0
.venv/bin/python scripts/monitor_live_track.py \
  --notify --spec "$SPEC" \
  --state-file "$STATE_FILE" \
  --journal-file "$JOURNAL_FILE" \
  --targets-file "$TARGETS_FILE" \
  --manifest-file "$MANIFEST_FILE" \
  --out "$HEALTH_JSON" \
  --audit-out "$AUDIT_JSON" $PRIOR_ORDER_ARG || monitor_status=$?

if [ "$execution_status" -ne 0 ]; then
  exit "$execution_status"
fi
exit "$monitor_status"
