#!/bin/sh
# Atlas20 daily data acquisition node (no trading, no signal build).
#
# 08:30 Beijing = 00:30 UTC.  The strategy is daily-bar based, so the previous
# completed daily close is available here.  The 01:05 execution clock does not
# require a 00:00 hourly mark bar.  This node only acquires inputs and publishes
# the executable Top50 readiness evidence.
#
# The inner body is wrapped by one process-group deadline.  A slow CMC, venue
# or Top50 subprocess therefore stops at 08:50 Beijing instead of continuing
# past the execution clock and only being noticed later.
set -eu

PROJECT_ROOT="/Users/ww/Project/Atlas20"
PROJECT_ROOT="${ATLAS20_PROJECT_ROOT:-$PROJECT_ROOT}"
DEADLINE_UTC="${ATLAS20_DATA_DEADLINE_UTC:-$(date -u +%Y-%m-%d)T00:50:00+00:00}"

exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/scripts/run_node_deadline.py" \
  --deadline-utc "$DEADLINE_UTC" \
  -- /bin/sh "$PROJECT_ROOT/ops/run_derivatives_data_inner.sh"
