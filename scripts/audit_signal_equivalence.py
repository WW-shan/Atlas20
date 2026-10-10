"""Prove the live target book is the backtested signal, not a look-alike.

The live book is rebuilt by the same functions the backtest uses
(``_load_market`` -> ``_resolve_build`` -> ``_long_targets_from_build``), but
with the calendar truncated at *today* instead of at the backtest's end date.
That makes this a genuine no-look-ahead test: if any part of the construction
peeked at future data, the two books would diverge on the period they share.

The script builds the book twice - once ending at the frozen backtest end
date, once ending at the newest completed UTC day - and compares every target
event on the overlapping dates, asset by asset.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.data import load_mark_candles  # noqa: E402
from atlas20.logging_utils import ensure_dir  # noqa: E402

from scripts.run_derivatives_backtest import _long_targets_from_build  # noqa: E402
from scripts.run_derivatives_oos import (  # noqa: E402
    TRACKED_SPEC,
    _load_market,
    _resolve_build,
    load_symbol_map,
    resolve_signal_window,
)

DEFAULT_CONFIG = "config/base.yaml"
DEFAULT_MARK_DIR = Path("data/raw/bitget_derivatives/merged_oos_20261009")
DEFAULT_JSON_OUT = Path("reports/derivatives_track_live/signal_equivalence.json")


def book_for(*, end_date: str, start_date: str) -> tuple[str, dict, pd.DatetimeIndex]:
    config, market, universe, index = _load_market(
        DEFAULT_CONFIG, start_date=start_date, end_date=end_date
    )
    _, _, built, trial_id = _resolve_build(market, universe, index, None)
    return trial_id, _long_targets_from_build(built, index), index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", default=TRACKED_SPEC)
    parser.add_argument("--start-date", default="2021-06-01")
    parser.add_argument(
        "--backtest-end",
        default="2026-09-21",
        help="the frozen in-sample end date of the reviewed backtest",
    )
    parser.add_argument("--live-end", default=None, help="default: newest completed UTC day in the marks")
    parser.add_argument("--mark-dir", type=Path, default=DEFAULT_MARK_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    if args.live_end is None:
        frames = load_mark_candles(args.mark_dir, load_symbol_map(args.mark_dir))
        if not frames:
            raise SystemExit(f"no mark candles under {args.mark_dir}")
        last_mark = max(frame.index.max() for frame in frames.values())
        resolved, _ = resolve_signal_window(last_mark, allow_stale=True)
        live_end = str(pd.Timestamp(resolved).date())
    else:
        live_end = args.live_end

    trial_backtest, backtest_book, _ = book_for(end_date=args.backtest_end, start_date=args.start_date)
    trial_live, live_book, _ = book_for(end_date=live_end, start_date=args.start_date)

    common = sorted(set(backtest_book) & set(live_book))
    differences: list[dict[str, object]] = []
    for date in common:
        left = backtest_book[date].sort_index()
        right = live_book[date].sort_index()
        joined = pd.concat([left, right], axis=1, keys=["backtest", "live"]).fillna(0.0)
        delta = (joined["backtest"] - joined["live"]).abs()
        worst = float(delta.max()) if len(delta) else 0.0
        if worst > 1e-12:
            differences.append({"date": str(date.date()), "max_weight_delta": worst})

    new_events = sorted(str(pd.Timestamp(date).date()) for date in set(live_book) - set(backtest_book))
    dropped = sorted(str(pd.Timestamp(date).date()) for date in set(backtest_book) - set(live_book))

    passed = trial_backtest == trial_live and not differences and not dropped
    payload = {
        "spec": args.spec,
        "trial_id_backtest": trial_backtest,
        "trial_id_live": trial_live,
        "backtest_end": args.backtest_end,
        "live_end": live_end,
        "overlapping_event_days": len(common),
        "differing_event_days": len(differences),
        "differences": differences[:20],
        "events_only_in_live": new_events,
        "events_only_in_backtest": dropped,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
    }
    output = ensure_dir(args.json_out.parent)
    (output / args.json_out.name).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(f"信号等价性核对 · {args.spec} · trial {trial_live}")
    print(f"  回测账本到 {args.backtest_end}: {len(backtest_book)} 个事件")
    print(f"  实盘账本 到 {live_end}: {len(live_book)} 个事件")
    print(f"  重叠事件日 {len(common)} 个 · 不一致 {len(differences)} 个 · 回测有而实盘没有 {len(dropped)} 个")
    if new_events:
        print(f"  只在实盘出现（OOS 新增）: {', '.join(new_events)}")
    print(f"  结论: {'一致（同一套计算，无前视）' if passed else '不一致，必须停下来排查'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
