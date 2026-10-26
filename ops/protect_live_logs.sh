#!/bin/sh
# Keep the append-only launchd logs alive through desktop cleanup tools.
#
# Tencent Lemon has no documented, stable per-path cleanup exclusion that can
# be safely written from this repository. macOS append-only user flags protect
# the files at the filesystem layer instead: launchd can append new output, but
# cleanup tools cannot truncate or unlink an existing log. The launchd job
# com.atlas20.protect-live-logs reruns this script at login and every five
# minutes so a missing file is recreated and its protection is restored.
#
# This is intentionally macOS-specific. ATLAS20_LOG_DIR exists only to let the
# real filesystem behavior run in tests against a temporary directory.

set -eu

LOG_DIR="${ATLAS20_LOG_DIR:-$HOME/Library/Logs}"
LOG_NAMES="
atlas20-cmc-probe.log
atlas20-daily-refresh.log
atlas20-derivatives-execute.log
atlas20-live-monitor.log
atlas20-log-protect.log
"

if ! command -v chflags >/dev/null 2>&1; then
  echo "chflags is required to protect Atlas20 launchd logs" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"
umask 077

for name in $LOG_NAMES; do
  log_path="$LOG_DIR/$name"

  if [ -L "$log_path" ]; then
    echo "refusing to protect symlink: $log_path" >&2
    exit 1
  fi
  if [ ! -e "$log_path" ]; then
    : >"$log_path"
  elif [ ! -f "$log_path" ]; then
    echo "refusing to protect non-regular file: $log_path" >&2
    exit 1
  fi

  flags=$(stat -f '%Sf' "$log_path")
  case ",$flags," in
    *,uappnd,*) ;;
    *) chflags uappnd "$log_path" ;;
  esac

  flags=$(stat -f '%Sf' "$log_path")
  case ",$flags," in
    *,uappnd,*) ;;
    *)
      echo "failed to set append-only flag: $log_path" >&2
      exit 1
      ;;
  esac
done
