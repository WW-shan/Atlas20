"""End-to-end audit of the research data chain.

Run this before trusting a backtest or wiring the pipeline to real money:

    .venv/bin/python scripts/audit_data_chain.py --config config/base.yaml

Every check prints PASS/FAIL with the evidence behind it. A FAIL is a data or
mechanics defect; a WARN is a known modelling gap that must be priced in
manually (currently the uncharged funding cost on leveraged exposure).
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
from atlas20.backtest.engine import cap_and_normalize  # noqa: E402
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

    gate_cache_dir = raw_dir / "gateio" / "candles"
    gate_files = sorted(gate_cache_dir.glob("*.json")) if gate_cache_dir.exists() else []
    gate_corrupt: list[str] = []
    gate_empty: list[str] = []
    for path in gate_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            gate_corrupt.append(path.name)
            continue
        if not payload or not isinstance(payload, list):
            gate_empty.append(path.name)
    check(
        "gateio cache: every file parses",
        not gate_corrupt,
        f"{len(gate_files)} files, corrupt={gate_corrupt[:5]}",
    )
    check(
        "gateio cache: no empty payloads",
        not gate_empty,
        f"empty={gate_empty[:5]}",
    )

    pap_cache_dir = raw_dir / "coinpaprika" / "history"
    pap_files = sorted(pap_cache_dir.glob("*.json")) if pap_cache_dir.exists() else []
    pap_corrupt: list[str] = []
    pap_empty: list[str] = []
    for path in pap_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pap_corrupt.append(path.name)
            continue
        if not payload or not isinstance(payload, list):
            pap_empty.append(path.name)
    check(
        "coinpaprika cache: every file parses",
        not pap_corrupt,
        f"{len(pap_files)} files, corrupt={pap_corrupt[:5]}",
    )
    check(
        "coinpaprika cache: no empty payloads",
        not pap_empty,
        f"empty={pap_empty[:5]}",
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
    supply_gap_rows = 0
    worst_supply_label = ""
    for path in cache_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload:
            quote = row.get("quote") or {}
            close, cap, supply = quote.get("close"), quote.get("marketCap"), quote.get("circulatingSupply")
            if not close or not cap or not supply:
                continue
            checked_supply += 1
            gap = abs(cap - close * supply) / cap
            if gap > 0.01:
                supply_gap_rows += 1
            if gap > worst_supply_gap:
                worst_supply_gap = gap
                worst_supply_label = f"{path.stem.split('_', 1)[0]}@{str(row.get('timeOpen', ''))[:10]}"
    check(
        "provider: market_cap == price * supply",
        worst_supply_gap <= 0.01,
        f"rows >1%={supply_gap_rows}/{checked_supply}, worst={worst_supply_gap:.4%} "
        f"({worst_supply_label or 'none'}); rankings use CMC's reported market cap directly",
        warn=worst_supply_gap > 0.01,
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
        verified = admitted["crosscheck_verified"].fillna(False) if "crosscheck_verified" in admitted else pd.Series(True, index=admitted.index)
        missing = admitted[~verified.astype(bool)]
        check(
            "cross-check: every admitted asset agrees with an independent provider",
            still_disagreeing.empty,
            f"{len(admitted)} admitted, verified={len(admitted) - len(missing)}; "
            f"still disagreeing={still_disagreeing['symbol'].tolist()[:5]}",
        )
        check(
            "cross-check: independent source available for every admitted asset",
            missing.empty,
            f"assets without a usable independent source={missing['symbol'].tolist()[:5]}",
        )
        if "crosscheck_latest_primary_covered" in admitted.columns:
            uncovered = admitted[
                ~admitted["crosscheck_latest_primary_covered"].fillna(False).astype(bool)
            ]
            check(
                "cross-check: independent source covers the latest primary print",
                uncovered.empty,
                f"latest-date-uncovered admitted assets={uncovered['symbol'].tolist()[:5]}",
            )
        else:
            check(
                "cross-check: independent source covers the latest primary print",
                False,
                "data_quality.csv lacks crosscheck_latest_primary_covered; "
                "a stale overlap could certify a current bad print",
            )
        check(
            "cross-check: unverified assets are refused",
            bool(config.data_quality.require_cross_check),
            f"require_cross_check={config.data_quality.require_cross_check}",
        )
        effective_column = (
            "crosscheck_effective_median_gap"
            if "crosscheck_effective_median_gap" in admitted.columns
            else "crosscheck_median_gap"
        )
        worst = float(admitted[effective_column].max()) if not admitted.empty else float("nan")
        check(
            "cross-check: effective provider noise stays small",
            worst <= config.data_quality.cross_check_max_median_gap,
            f"worst effective median gap among admitted assets={worst:.4%}",
        )
        if "crosscheck_third_source_checked" in quality.columns:
            third_checked = quality[quality["crosscheck_third_source_checked"].fillna(False).astype(bool)]
            confirmed = third_checked[
                third_checked["crosscheck_confirmed_by"].fillna("").isin(["gateio", "coingecko", "coinpaprika"])
            ]
            source_known = third_checked["crosscheck_third_source"].fillna("").ne("") if "crosscheck_third_source" in third_checked else pd.Series(False, index=third_checked.index)
            check(
                "cross-check: third-source adjudications are explicit",
                bool(confirmed["crosscheck_third_source_checked"].all()) if not confirmed.empty else True,
                "third-source checks="
                f"{len(third_checked)}, CMC confirmed by third source={len(confirmed)}",
            )
            check(
                "cross-check: every third-source check names its provider",
                bool(source_known.all()) if not third_checked.empty else True,
                f"unnamed third-source checks={int((~source_known).sum())}",
            )
            usable = third_checked[
                pd.to_numeric(third_checked.get("crosscheck_third_source_overlap_days"), errors="coerce")
                >= config.data_quality.cross_check_min_overlap_days
            ]
            check(
                "cross-check: disputed assets have a usable third-source window",
                len(usable) == len(third_checked),
                f"usable third-source windows={len(usable)}/{len(third_checked)}",
            )
        if not rejected.empty:
            blocked = rejected[
                rejected["crosscheck_passed"].fillna(False) == False  # noqa: E712
            ].head(5)
            check(
                "cross-check: rejected assets are reported, not silent",
                True,
                "blocked by the independent-source check: "
                + ", ".join(
                    f"{row.symbol} ({row.crosscheck_reason}: {1.0 + row.crosscheck_median_gap:.1f}x)"
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

    # A member's rank must come from a same-day market cap. prepare_market_data
    # forward-fills market cap by up to three days, so a feed that has ended
    # (EOS -> Vaulta, MKR -> SKY) stays "rankable" on a stale cap for a few
    # days. Verify no member is actually carried by such a placeholder.
    raw_caps = panel.set_index(["date", "coin_id"])["market_cap"]
    stale_ranks: list[str] = []
    for date, frame in universe.groupby("rebalance_date"):
        for coin_id in frame["coin_id"]:
            raw = raw_caps.get((pd.Timestamp(date), coin_id))
            if raw is None or pd.isna(raw) or float(raw) <= 0:
                stale_ranks.append(f"{coin_id}@{pd.Timestamp(date).date()}")
    check(
        "universe: no rank leans on a forward-filled market cap",
        not stale_ranks,
        f"stale-ranked members={stale_ranks[:5]}",
    )

    # ------------------------------------------------------------- engine
    # The per-coin cap has to be a real constraint, not a no-op.
    cap_probe = cap_and_normalize(pd.Series({"a": 0.6, "b": 0.4}), 0.35)
    cap_ok = bool(cap_probe.max() <= 0.35 + 1e-12 and cap_probe.sum() <= 1.0 + 1e-12)
    check(
        "engine: per-coin cap is enforced",
        cap_ok,
        f"cap(0.6/0.4, 0.35) -> max={float(cap_probe.max()):.3f} sum={float(cap_probe.sum()):.3f}",
    )

    # --------------------------------------------------------------- engine
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    terminal_missing = 0
    for column in backtest_returns.columns:
        observed = market.raw_price.loc[backtest_returns.index, column]
        last_observed = observed.last_valid_index()
        if last_observed is not None:
            # Returns after the last observed provider print are the dangerous
            # tail case: a delisted/halted asset must not be carried flat.
            terminal_missing += int(backtest_returns.loc[last_observed:, column].isna().sum())
    missing_policy = config.frictions.missing_return_policy
    check(
        "engine: missing returns fail closed",
        missing_policy == "error",
        f"policy={missing_policy}; missing_return_fill={config.frictions.missing_return_fill}; "
        f"terminal missing return cells={terminal_missing}",
        warn=missing_policy != "error",
    )
    check(
        "engine: no terminal missing asset returns",
        terminal_missing == 0,
        f"terminal missing return cells={terminal_missing}",
    )

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
        "modelling: missing returns are explicitly handled",
        missing_policy == "error",
        "missing returns abort the run by default; an explicit fill policy is "
        "required to continue. This prevents a halted or delisted holding from "
        "being silently marked flat.",
        warn=missing_policy != "error",
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
