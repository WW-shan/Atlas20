"""Refresh the raw cache and rebuild the processed panel, safely and once.

``ops/com.atlas20.daily-refresh.plist`` fires this several times a day: a
primary run after the UTC close and one or more catch-up runs, the earliest of
which lands before the 11:05 Beijing trade job.  Two properties matter more
than speed here:

* **No overlap.**  A slow primary run must never race the catch-up fire, or
  two processes would interleave writes into the raw cache.  The whole
  download-and-build pair runs under a ``filelock`` that is released by the OS
  if the process is killed, so a shutdown cannot leave a stale lock behind.
* **No wasted work.**  A catch-up that finds the panel already carrying the
  last completed UTC day does nothing.  Re-downloading cannot add a day that
  is already on disk, and the strategy only ever reads completed days.

The freshness question is asked again after the lock is taken, so a run that
waited on a sibling exits without a second download.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from filelock import FileLock, Timeout
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import load_config  # noqa: E402
from atlas20.derivatives.live_chain import (  # noqa: E402
    PANEL_FILENAME,
    as_utc,
    last_completed_utc_day,
    panel_end_date,
    panel_lags_last_completed_day,
)

from scripts import build_datasets, download_data  # noqa: E402

DEFAULT_CONFIG = "config/base.yaml"
DEFAULT_LOCK = PROJECT_ROOT / "data" / ".daily-refresh.lock"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument(
        "--panel",
        type=Path,
        default=None,
        help="processed panel to check (default: the path the strategy resolves)",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=0.0,
        help="how long to wait for a sibling refresh before skipping (default: do not wait)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="refresh even when the panel already carries the last completed day",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="ISO-8601 UTC timestamp to evaluate against (default: the real clock)",
    )
    return parser.parse_args(argv)


def panel_path_for(config_path: str) -> Path:
    """The processed panel the strategy reads, resolved the same way it does."""

    config = load_config(config_path)
    return config.resolve_path(config.paths.processed_dir) / PANEL_FILENAME


def run_refresh(config_path: str) -> None:
    """The two steps the plist used to chain with ``&&``."""

    download_data.main(["--config", config_path])
    build_datasets.main(["--config", config_path])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = (
        as_utc(datetime.fromisoformat(args.now))
        if args.now
        else datetime.now(timezone.utc)
    )
    panel = Path(args.panel) if args.panel is not None else panel_path_for(args.config)

    if not args.force and not panel_lags_last_completed_day(panel, now):
        print(f"panel already carries {last_completed_utc_day(now).isoformat()}; skipping refresh")
        return 0

    lock = FileLock(str(args.lock))
    try:
        lock.acquire(timeout=float(args.wait_seconds))
    except Timeout:
        print(f"another refresh holds {args.lock}; skipping")
        return 0
    try:
        # A sibling may have finished while we waited for the lock.
        if not args.force and not panel_lags_last_completed_day(panel, now):
            print("panel became current while waiting for the lock; skipping refresh")
            return 0
        print(
            f"refreshing: panel ends {panel_end_date(panel) or 'missing'}, "
            f"{last_completed_utc_day(now).isoformat()} is the last completed UTC day"
        )
        run_refresh(args.config)
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
