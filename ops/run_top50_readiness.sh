#!/bin/sh
# Top50 readiness fallback and notification delivery.
#
# This wrapper loads only Telegram credentials.  It never loads Bitget keys,
# never places orders and never invokes the executor.
set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
CONFIG_DIR="${ATLAS20_CONFIG_DIR:-$HOME/.config/atlas20}"
TELEGRAM_ENV="$CONFIG_DIR/telegram.env"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

telegram_ready=1
if [ ! -r "$TELEGRAM_ENV" ]; then
  echo "missing Telegram environment: $TELEGRAM_ENV" >&2
  telegram_ready=0
else
  set -a
  set +eu
  . "$TELEGRAM_ENV"
  telegram_source_rc=$?
  set -eu
  set +a
  if [ "$telegram_source_rc" -ne 0 ]; then
    echo "could not load Telegram environment: $TELEGRAM_ENV" >&2
    telegram_ready=0
  fi
fi

cd "$PROJECT_ROOT"
PYTHON_BIN="${ATLAS20_PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
MAKE_BIN="${ATLAS20_MAKE_BIN:-/usr/bin/make}"

# Deliver any events queued by the 08:35/08:55 primary run first.  When that
# run already produced today's 50/50 READY pointer, the 09:45 job is a
# notification fallback only and must not rebuild the same Top50 again.
notify_rc=0
if [ "$telegram_ready" -eq 1 ]; then
  "$PYTHON_BIN" scripts/run_top50_readiness.py --notify-only || notify_rc=$?
else
  notify_rc=1
fi
if [ "$notify_rc" -ne 0 ]; then
  echo "top50 notify-only failed ($notify_rc); continuing data fallback" >&2
fi

check_rc=0
"$PYTHON_BIN" scripts/run_top50_readiness.py --check-current || check_rc=$?
if [ "$check_rc" -eq 0 ]
then
  echo "today's Top50 readiness is already READY; data rebuild not needed"
  # A Telegram failure must remain visible even when the data pointer is good.
  if [ "$notify_rc" -ne 0 ]; then
    exit 1
  fi
  exit 0
fi

make_rc=0
if [ "$telegram_ready" -eq 1 ]; then
  "$MAKE_BIN" top50-readiness ARGS=--notify || make_rc=$?
else
  "$MAKE_BIN" top50-readiness || make_rc=$?
fi
if [ "$telegram_ready" -ne 1 ] || [ "$notify_rc" -ne 0 ]; then
  exit 1
fi
exit "$make_rc"
