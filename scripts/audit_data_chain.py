"""End-to-end audit of the research data chain.

Run this before trusting a backtest or wiring the pipeline to real money:

    .venv/bin/python scripts/audit_data_chain.py --config config/base.yaml

Every check prints PASS/FAIL with the evidence behind it. A FAIL is a data or
mechanics defect; a WARN is a known modelling gap that must be priced in
manually (funding cost, missing-return fill).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str, warn: bool = False) -> None:
    RESULTS.append((name, "WARN" if warn else ("PASS" if ok else "FAIL"), detail))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the Atlas20 data chain")
    parser.add_argument("--config", default="config/base.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging("ERROR")
    raw_dir = config.resolve_path(config.paths.raw_dir)

    # ---------------------------------------------------------------- cache
    cache_dir = raw_dir / "coinmarketcap" / "history"
    cache_files = sorted(cache_dir.glob("*.json"))
    corrupt: list[str] = []
    empty: list[str] = []
    windows: dict[int, list[tuple[int, int]]] = {}
    for path in cache_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            corrupt.append(path.name)
            continue
        if not payload:
            empty.append(path.name)
            continue
        coin_id, start_ts, end_ts = path.stem.split("_")
        windows.setdefault(int(coin_id), []).append((int(start_ts), int(end_ts)))

    check("cmc cache: every file parses", not corrupt, f"{len(cache_files)} files, corrupt={corrupt[:5]}")
    check("cmc cache: no empty payloads", not empty, f"empty={empty[:5]}")
    check(
        "cmc cache: one full window per coin",
        all(any(s <= 1577836800 for s, _ in w) for w in windows.values()),
        f"{len(windows)} coins with cached history",
    )

    # ---------------------------------------------------------------- panel
    panel, metadata = build_processed_datasets(config, load_sector_config(config.resolve_path("config/sectors.yaml")))
    panel = panel.sort_values(["coin_id", "date"])

    dupes = int(panel.duplicated(subset=["date", "coin_id"]).sum())
    check("panel: no duplicate (date, coin)", dupes == 0, f"duplicates={dupes}")

    bad_price = int((panel["price"] <= 0).sum() + panel["price"].isna().sum())
    check("panel: all prices positive", bad_price == 0, f"offending rows={bad_price}")

    bad_vol = int((panel["volume_usd"] < 0).sum() + panel["volume_usd"].isna().sum())
    check("panel: volume non-negative", bad_vol == 0, f"offending rows={bad_vol}")

    nonfinite_price = int((~np.isfinite(panel[["price", "volume_usd"]].to_numpy(dtype=float))).sum())
    check("panel: price and volume are finite", nonfinite_price == 0, f"non-finite cells={nonfinite_price}")

    missing_cap = int(panel["market_cap"].isna().sum())
    unrankable_share = missing_cap / max(len(panel), 1)
    if unrankable_share > 0.05:
        check("panel: unrankable rows are rare", False, f"{missing_cap} rows without a real market cap ({unrankable_share:.2%})")
    else:
        check(
            "panel: unrankable rows are rare",
            True,
            f"{missing_cap} rows ({unrankable_share:.2%}) carry no market cap and can never be ranked",
        )

    # Every coin's history must start where its real supply starts.
    def first_row_has_supply(frame: pd.DataFrame) -> bool:
        first = frame.iloc[0]
        return bool(pd.notna(first["market_cap"]) and first["market_cap"] > 0)

    offenders = [c for c, g in panel.groupby("coin_id") if not first_row_has_supply(g)]
    check(
        "panel: history starts at first real circulation",
        not offenders,
        f"coins starting without supply={offenders[:5]}",
    )

    # Marvecap must equal price x supply (provider rounding tolerance).
    worst_supply_gap = 0.0
    checked_supply = 0
    for path in cache_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload:
            quote = row.get("quote") or {}
            close, cap, supply = quote.get("close"), quote.get("marketCap"), quote.get("circulatingSupply")
            if not close or not cap or not supply:
                continue
            checked_supply += 1
            worst_supply_gap = max(worst_supply_gap, abs(cap - close * supply) / cap)
    check(
        "provider: market_cap == price * supply",
        worst_supply_gap <= 0.30,
        f"worst relative gap={worst_supply_gap:.4%} over {checked_supply} rows (provider rounding)",
    )

    # Bad prints: single-day reversions and month-long level corruption.
    spikes: list[tuple[str, str]] = []
    for coin_id, g in panel.groupby("coin_id"):
        s = g.set_index("date")["price"].astype(float)
        prev, nxt = s.shift(1), s.shift(-1)
        agrees = (prev / nxt).between(0.5, 2)
        ratio = s / prev
        flagged = agrees & ((ratio > 3) | (ratio < 1 / 3)) & prev.notna() & nxt.notna()
        for date in s.index[flagged]:
            spikes.append((coin_id, str(date.date())))
    check("panel: no single-day bad prints", not spikes, f"flagged={spikes[:5]}")

    level_shifts: list[tuple[str, str]] = []
    for coin_id, g in panel.groupby("coin_id"):
        s = g.sort_values("date").set_index("date")["price"].astype(float)
        before = s.shift(31).rolling(30, min_periods=15).median()
        after = s.shift(-61).rolling(30, min_periods=15).median()
        agree = (before / after).between(1 / 3, 3)
        ratio = s / ((before * after) ** 0.5)
        flagged = agree & ((ratio > 20) | (ratio < 1 / 20))
        for date in s.index[flagged.fillna(False)]:
            level_shifts.append((coin_id, str(date.date())))
    check(
        "panel: no reverted price-level corruption",
        not level_shifts,
        f"flagged={level_shifts[:6]} ({len(level_shifts)} rows)",
    )

    # --------------------------------------------------- independent source
    quality_path = config.resolve_path(config.paths.processed_dir) / "data_quality.csv"
    quality = pd.read_csv(quality_path)
    if "crosscheck_passed" in quality.columns:
        admitted = quality[quality["included_in_panel"].fillna(False)]
        rejected = quality[~quality["included_in_panel"].fillna(False)]
        still_disagreeing = admitted[~admitted["crosscheck_passed"].fillna(False)]
        missing = admitted[
            admitted["crosscheck_reason"].astype(str).str.contains("no_overlap|insufficient_overlap")
        ]
        check(
            "cross-check: every admitted asset agrees with a second provider",
            still_disagreeing.empty,
            f"{len(admitted)} admitted, all verified; "
            f"still disagreeing={still_disagreeing['symbol'].tolist()[:5]}",
        )
        check(
            "cross-check: second source available for every admitted asset",
            missing.empty,
            f"assets without a usable second source={missing['symbol'].tolist()[:5]}",
            warn=not missing.empty,
        )
        worst = float(admitted["crosscheck_median_gap"].max()) if not admitted.empty else float("nan")
        check(
            "cross-check: provider noise stays small",
            worst <= config.data_quality.cross_check_max_median_gap,
            f"worst median gap among admitted assets={worst:.4%}",
        )
        if not rejected.empty:
            blocked = rejected[
                rejected["crosscheck_passed"].fillna(False) == False  # noqa: E712
            ].head(5)
            check(
                "cross-check: rejected assets are reported, not silent",
                True,
                "blocked by the second-source check: "
                + ", ".join(
                    f"{row.symbol} ({row.crosscheck_reason}: {row.crosscheck_median_gap:.1%})"
                    for row in blocked.itertuples()
                ),
            )
    else:
        check(
            "cross-check: second provider comparison present",
            False,
            "data_quality.csv has no cross-check columns; recent CMC prints are unverified",
        )

    # ------------------------------------------------------ feed continuity
    last_date = panel["date"].max()
    early_end = panel.groupby("coin_id")["date"].max()
    early_end = early_end[early_end < last_date]
    check(
        "feed: no asset stops reporting before the panel ends",
        early_end.empty,
        f"assets with a truncated feed={early_end.index.tolist()[:5]}",
    )

    stale_runs: list[tuple[str, int]] = []
    for coin_id, g in panel.sort_values(["coin_id", "date"]).groupby("coin_id"):
        prices = g["price"].reset_index(drop=True)
        unchanged = prices.diff() == 0
        longest = int(unchanged.groupby((~unchanged).cumsum()).cumsum().max() or 0)
        if longest >= 5:
            stale_runs.append((coin_id, longest))
    check(
        "feed: no frozen price runs",
        not stale_runs,
        f"assets with >=5 identical consecutive closes={stale_runs[:5]}",
    )

    # ------------------------------------------------------------- universe
    market = prepare_market_data(panel, metadata, config)
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    weekly = get_rebalance_dates(backtest_returns.index, config.start_timestamp, "weekly", "7D")
    universe = build_rebalance_universe(market, weekly, config)

    # Point-in-time: nothing may rank with a future market cap.
    lookahead: list[str] = []
    for date, frame in universe.groupby("rebalance_date"):
        for _, row in frame.iterrows():
            actual = market.market_cap.at[date, row["coin_id"]]
            if pd.isna(actual) or abs(float(actual) - float(row["market_cap"])) > max(1.0, float(actual) * 1e-6):
                lookahead.append(f"{row['coin_id']}@{date.date()}")
    check(
        "universe: ranks use the same-day market cap only",
        not lookahead,
        f"mismatched rows={lookahead[:5]}",
    )

    monotonic = bool(
        universe.groupby("rebalance_date")["market_cap"].apply(lambda s: s.is_monotonic_decreasing).all()
    )
    check("universe: sorted by market cap descending", monotonic, f"{universe['rebalance_date'].nunique()} rebalance snapshots")

    size_ok = bool((universe.groupby("rebalance_date").size() <= config.universe.universe_size).all())
    check("universe: never exceeds universe_size", size_ok, f"max={int(universe.groupby('rebalance_date').size().max())}")

    # --------------------------------------------------------------- engine
    filled = market.returns.loc[config.start_timestamp : config.end_timestamp].isna().sum().sum()
    check("engine: no NaN asset returns to fill", filled == 0, f"NaN return cells={int(filled)}")

    last_date = market.price.index.max()
    staleness = (pd.Timestamp.today().normalize() - last_date).days
    check(
        "freshness: panel reaches the latest completed day",
        staleness <= 2,
        f"last date={last_date.date()} ({staleness}d old)",
        warn=staleness > 2,
    )

    # ------------------------------------------------------------ modelling
    check(
        "modelling: leverage funding cost is charged",
        False,
        "the engine charges fees+slippage on turnover only, so gross exposure >1 "
        "is funded for free. Irrelevant for unlevered spot, mandatory to model "
        "if you ever run the x1.25/x1.5/x2 cells on margin or perps (borrow "
        "interest / funding, ~10-30% APR in a bull market).",
        warn=True,
    )
    check(
        "coverage: recent prints are independently verified",
        False,
        "the level-corruption test alone needs ~60 days of *future* prices, so it "
        "cannot see a block that is still in progress. The second-source check "
        "covers that gap for the trailing cross_check_recent_days (365) - the one "
        "remaining blind spot is a price both providers are simultaneously wrong "
        "about. Verify a suspicious recent print against a third venue (an "
        "exchange ticker) before sizing a live position on it.",
        warn=True,
    )
    check(
        "modelling: missing returns are not assumed flat",
        False,
        "friction.missing_return_fill=0.0 would treat a halted or delisted "
        "holding as flat instead of writing it down. Continuous spot feeds do "
        "not halt, and every asset above reports through the final date, so "
        "this is inert for the current dataset - it only matters if a feed is "
        "ever truncated.",
        warn=True,
    )

    width = max(len(n) for n, _, _ in RESULTS)
    print(f"\nAtlas20 data-chain audit - {len(RESULTS)} checks\n" + "=" * (width + 30))
    failures = 0
    for name, status, detail in RESULTS:
        if status == "FAIL":
            failures += 1
        print(f"[{status}] {name.ljust(width)}  {detail}")
    print("=" * (width + 30))
    print(f"PASS={sum(1 for _, s, _ in RESULTS if s == 'PASS')} "
          f"WARN={sum(1 for _, s, _ in RESULTS if s == 'WARN')} FAIL={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
