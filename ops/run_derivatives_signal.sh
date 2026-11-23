#!/bin/sh
# Atlas20 daily signal-construction node (no trading).
#
# 08:35 Beijing = 00:35 UTC.  It consumes the data node's outputs, builds the
# frozen target ledger and runs the immutable data/venue/signal audits.  The
# newest T+1 fill bar is intentionally deferred to the 09:05 executor; the
# daily signal itself only needs completed daily bars.
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
  ls45-g125)
    SIGNAL_TARGET="derivatives-ls45-signal"
    DATA_AUDIT_TARGET="audit-data"
    SIGNAL_AUDIT_TARGET="audit-signal"
    SYMBOL_AUDIT_JSON="reports/ls45_live_g125_live/venue_symbol_audit.json"
    LEVERAGE="2.0"
    ;;
  ls104-g175-m090)
    SIGNAL_TARGET="derivatives-ls104-signal"
    DATA_AUDIT_TARGET="audit-data-ls104"
    SIGNAL_AUDIT_TARGET="audit-signal-ls104"
    SYMBOL_AUDIT_JSON="reports/ls45_live_g175_live/venue_symbol_audit.json"
    LEVERAGE="4.0"
    ;;
  *) echo "unknown ATLAS20_TRACK_PROFILE: $TRACK_PROFILE" >&2; exit 1 ;;
esac
export ATLAS20_TRACK_PROFILE="$TRACK_PROFILE"
echo "Atlas20 signal track profile: $TRACK_PROFILE"

/usr/bin/make "$SIGNAL_TARGET"
/usr/bin/make audit-data-chain
/usr/bin/make "$DATA_AUDIT_TARGET"
.venv/bin/python scripts/audit_venue_symbols.py --required-leverage "$LEVERAGE" --out "$SYMBOL_AUDIT_JSON"
if [ "$TRACK_PROFILE" = "ls104-g175-m090" ]; then
  /usr/bin/make audit-contract-specs-ls104
fi
/usr/bin/make "$SIGNAL_AUDIT_TARGET"
