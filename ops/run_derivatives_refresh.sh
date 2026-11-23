#!/bin/sh
# Deprecated compatibility entry point.
#
# The daily production chain no longer has an intraday derivatives refresh or
# a 01:00 finalize.  Data and signal are prepared by
# ops/run_derivatives_prepare.sh at 08:35 Beijing; execution happens once at
# 09:05.  Keep this wrapper as a fail-closed guard for stale timers.
set -eu
echo "run_derivatives_refresh.sh is retired; use run_derivatives_prepare.sh" >&2
exit 1
