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

if [ ! -r "$TELEGRAM_ENV" ]; then
  echo "missing Telegram environment: $TELEGRAM_ENV" >&2
  exit 1
fi

set -a
. "$TELEGRAM_ENV"
set +a

cd "$PROJECT_ROOT"
exec /usr/bin/make top50-readiness ARGS=--notify
