"""End-to-end audit of the research data chain.

Run this before trusting a backtest or wiring the pipeline to real money:

    .venv/bin/python scripts/audit_data_chain.py --config config/base.yaml

Every check prints PASS/FAIL with the evidence behind it. A FAIL is a data or
mechanics defect; a WARN is a gap that is understood and deliberate, so it must
be priced in by hand rather than fixed by the pipeline. There are three: the
uncharged funding cost on leveraged exposure, CMC rows whose market cap does
not equal price x supply, and the point-in-time Top-N members the panel cannot
carry (a coin delisted from CoinGecko, or one excluded as a stablecoin, still
displaces a real constituent on the days it qualified).
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
from atlas20.backtest.engine import cap_and_normalize, run_backtest  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, get_logger  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []
LOGGER = get_logger(__name__)


def check(name: str, ok: bool, detail: str, warn: bool = False) -> None:
    RESULTS.append((name, "WARN" if warn else ("PASS" if ok else "FAIL"), detail))


def _window_span_days(filename: str) -> int:
    """Days between the start and end recorded in a CMC cache filename."""
    parts = Path(filename).stem.split("_")
    if len(parts) != 3:
        return 0
    try:
        return int((int(parts[2]) - int(parts[1])) / 86_400)
    except ValueError:
        return 0


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
    # A short empty window is a tail refresh for a series that has ended (a
    # delisted or migrated coin has nothing to add), which is expected. An
    # empty *backfill* window means a full-history request came back with
    # nothing, and the filename alone would then convince ensure_history that
    # the coin is covered.
    empty_backfills = [name for name in empty if _window_span_days(name) >= 300]
    check(
        "cmc cache: no empty backfill windows",
        not empty_backfills,
        f"{len(empty)} empty window(s), backfill-sized={empty_backfills[:5]}",
    )
    check(
        "cmc cache: empty tail windows are only for ended series",
        all(_window_span_days(name) < 300 for name in empty),
        f"empty tail windows={len([name for name in empty if _window_span_days(name) < 300])}",
    )
    check(
        "cmc cache: one full window per coin",
        all(any(s <= 1577836800 for s, _ in w) for w in windows.values()),
        f"{len(windows)} coins with cached history",
    )

    for venue, label in (("gateio", "Gate.io"), ("binance", "Binance")):
        venue_dir = raw_dir / venue / "candles"
        venue_files = sorted(venue_dir.glob("*.json")) if venue_dir.exists() else []
        venue_corrupt: list[str] = []
        venue_empty: list[str] = []
        for path in venue_files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                venue_corrupt.append(path.name)
                continue
            if not payload or not isinstance(payload, list):
                venue_empty.append(path.name)
        check(
            f"{venue} cache: every file parses",
            not venue_corrupt,
            f"{len(venue_files)} files, corrupt={venue_corrupt[:5]}",
        )
        if venue == "gateio":
            check(
                f"{venue} cache: no empty payloads",
                not venue_empty,
                f"{len(venue_files)} files, empty={venue_empty[:5]}",
            )
        else:
            # Binance legitimately answers [] for a pair it does not carry
            # (BGB, HTX, KCS, OKB, CRO) or one it delisted before the cached
            # window opens (XMR, EOS). Caching that negative result on purpose
            # keeps the daily refresh from re-asking for a name that will never
            # appear. The failure mode worth catching is the opposite one: a
            # venue-wide block or outage would answer [] for *every* pair and
            # silently remove the venue's vote, so require most cached pairs to
            # carry data.
            carried = len(venue_files) - len(venue_empty)
            check(
                f"{venue} cache: venue-wide empty responses are ruled out",
                carried >= max(10, len(venue_files) // 2),
                f"{carried}/{len(venue_files)} cached pair(s) carry data; "
                f"unlisted/delisted={sorted(name.split('_', 1)[0] for name in venue_empty)}",
            )
        check(
            f"{venue} cache: populated for the venue vote",
            bool(venue_files),
            f"{len(venue_files)} cached pair window(s) from {label}",
        )

    # A venue vote is evidence only when the day behind it traded.  The
    # retired Binance.US feed proved the cost of counting a $2/day print: it
    # disagreed with CMC by double digits and blocked healthy assets.  The
    # floor is applied when the candles are read, so the invariant to audit is
    # that the newest *certifying* day of every pair clears it.
    binance_floor = float(config.providers.binance.min_daily_dollar_volume)
    binance_dir = raw_dir / "binance" / "candles"
    thin_rows: list[str] = []
    covered_pairs: set[str] = set()
    for path in sorted(binance_dir.glob("*.json")) if binance_dir.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, list) or not payload:
            continue
        latest_row: list | None = None
        liquid_days = 0
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 8:
                continue
            try:
                volume = float(row[7])
            except (TypeError, ValueError):
                continue
            if volume >= binance_floor:
                liquid_days += 1
                if latest_row is None or int(row[0]) > int(latest_row[0]):
                    latest_row = list(row)
        if liquid_days:
            covered_pairs.add(path.stem.split("_", 1)[0])
        else:
            thin_rows.append(path.name)
    check(
        "binance cache: every cached pair has a day above the volume floor",
        not thin_rows,
        f"pairs with no liquid day={thin_rows[:5]} (floor=${binance_floor:,.0f}/day)",
    )
    check(
        "binance cache: covers a meaningful share of the panel",
        len(covered_pairs) >= 50,
        f"{len(covered_pairs)} pair(s) with liquid history",
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
            # A live series must be corroborated at its newest print. An ended
            # series cannot be - no venue still quotes a delisted pair - so it
            # is verified on the overlap instead, and the days of its tail that
            # rest on CMC alone are reported rather than hidden.
            ended_flag = (
                admitted["crosscheck_primary_ended"].fillna(False).astype(bool)
                if "crosscheck_primary_ended" in admitted.columns
                else pd.Series(False, index=admitted.index)
            )
            live = admitted[~ended_flag]
            uncovered = live[~live["crosscheck_latest_primary_covered"].fillna(False).astype(bool)]
            check(
                "cross-check: independent source covers the latest primary print",
                uncovered.empty,
                f"{len(live)} live asset(s) checked; latest-date-uncovered={uncovered['symbol'].tolist()[:5]}",
            )
            ended = admitted[ended_flag]
            if not ended.empty:
                tails = pd.to_numeric(ended.get("crosscheck_unverified_tail_days"), errors="coerce").fillna(0)
                weak = ended[ended["crosscheck_overlap_days"].fillna(0) < config.data_quality.cross_check_min_overlap_days]
                check(
                    "cross-check: ended series verify on their overlap",
                    weak.empty,
                    "ended feed(s) verified over an overlap: "
                    + ", ".join(
                        f"{row.symbol} ({int(row.crosscheck_overlap_days)}d overlap vs "
                        f"{row.crosscheck_confirmed_by}, {int(tail)}d unverifiable tail)"
                        for row, tail in zip(ended.itertuples(), tails, strict=False)
                    ),
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
                third_checked["crosscheck_confirmed_by"]
                .fillna("")
                .isin(["gateio", "binance", "coingecko", "coinpaprika"])
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
    symbol_by_coin = (
        panel.drop_duplicates("coin_id").set_index("coin_id")["symbol"].to_dict() if "symbol" in panel else {}
    )
    last_date = panel["date"].max()
    early_end = panel.groupby("coin_id")["date"].max()
    early_end = early_end[early_end < last_date]
    ended_names = ", ".join(
        f"{symbol_by_coin.get(coin_id, coin_id)} (to {pd.Timestamp(ts).date()})"
        for coin_id, ts in early_end.items()
    )
    check(
        "feed: ended feeds are named, not silent",
        True,
        f"{len(early_end)} ended feed(s): {ended_names or 'none'}. These are delistings or "
        "token migrations; the engine liquidates the position at the last print "
        "instead of carrying it flat (verified below). Their unverifiable tails are "
        "reported by the cross-check section.",
        warn=bool(len(early_end)),
    )

    # Interior provider gaps: days CMC simply does not publish inside a live
    # series (2022-07-31 is missing for LINK, CRV and KCS alike - a provider
    # outage day, not a coin event). prepare_market_data carries those at the
    # last observed price and applies the cumulative move on the next print, so
    # they distort timing by a day rather than inventing a price. Anything much
    # longer stops being a provider hiccup and starts looking like a broken
    # feed, so it is called out.
    gap_report: list[str] = []
    long_gaps: list[str] = []
    for coin_id, group in panel.sort_values(["coin_id", "date"]).groupby("coin_id"):
        dates = pd.DatetimeIndex(pd.to_datetime(group["date"]))
        missing = pd.date_range(dates.min(), dates.max(), freq="D").difference(dates)
        missing = missing[missing >= pd.Timestamp(config.start_timestamp)]
        if len(missing) == 0:
            continue
        # Group consecutive missing days into runs.
        runs: list[int] = []
        current = 1
        for previous, following in zip(missing[:-1], missing[1:], strict=False):
            if (following - previous).days == 1:
                current += 1
            else:
                runs.append(current)
                current = 1
        runs.append(current)
        label = f"{symbol_by_coin.get(coin_id, coin_id)} ({len(missing)}d, longest run {max(runs)}d)"
        gap_report.append(label)
        if max(runs) > 10:
            long_gaps.append(label)
    check(
        "feed: interior provider gaps are short and named",
        not long_gaps,
        "assets with gaps in the traded window: " + (", ".join(gap_report) or "none"),
        warn=bool(gap_report),
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

    # Survivorship. The candidate pool is seeded from *today's* listings, so a
    # coin can only reach the panel if it was onboarded while it was still hot.
    # A name that has since slid down those listings is therefore the one most
    # likely to be absent - and for a momentum strategy those are exactly the
    # blow-ups that decide the drawdown. Recompute the real point-in-time Top-N
    # straight from the raw CMC cache (every coin ever fetched, ranked by CMC's
    # own market cap) and name anything the panel does not carry.
    id_map_path = raw_dir / "coinmarketcap" / "id_map.json"
    symbol_by_id: dict[int, str] = {}
    if id_map_path.exists():
        for symbol, coin_id in json.loads(id_map_path.read_text(encoding="utf-8")).items():
            symbol_by_id.setdefault(int(coin_id), str(symbol).upper())
    for symbol, coin_id in config.universe.cmc_symbol_aliases.items():
        symbol_by_id.setdefault(int(coin_id), str(symbol).upper())

    cap_frames: list[pd.DataFrame] = []
    for path in cache_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else (payload.get("quotes") or [])
        coin_id = int(path.stem.split("_", 1)[0])
        records = [
            {
                "date": str(row.get("timeOpen"))[:10],
                "cmc_id": coin_id,
                "symbol": symbol_by_id.get(coin_id, str(coin_id)),
                "market_cap": (row.get("quote") or {}).get("marketCap"),
            }
            for row in rows
            if isinstance(row, dict)
        ]
        if records:
            cap_frames.append(pd.DataFrame(records))

    missing_members: dict[str, int] = {}
    if cap_frames:
        caps = pd.concat(cap_frames, ignore_index=True)
        caps = caps[caps["market_cap"].notna() & (caps["market_cap"] > 0)]
        caps["date"] = pd.to_datetime(caps["date"])
        caps = caps.sort_values("market_cap", ascending=False).drop_duplicates(["date", "cmc_id"])
        caps["rank"] = caps.groupby("date").cumcount() + 1
        true_top = caps[caps["rank"] <= config.universe.universe_size]
        # Only rebalance dates matter: those are the days the strategy actually
        # picks a portfolio, so a name that was top-N mid-week but out of the
        # Top-N on every rebalance never displaced a constituent.
        # The strategy's real decision set, not the weekly probe above: a name
        # that is top-N on a Wednesday but out of the Top-N on every biweekly
        # rebalance never displaced a constituent the strategy could hold.
        portfolio_dates: set[pd.Timestamp] = set()
        for frequency_name in ("monthly", "biweekly"):
            value = config.rebalancing.frequencies.get(frequency_name)
            if value:
                portfolio_dates.update(
                    get_rebalance_dates(backtest_returns.index, config.start_timestamp, frequency_name, value)
                )
        rebalance_dates = set(pd.to_datetime(sorted(portfolio_dates)).unique())
        true_top = true_top[true_top["date"].isin(rebalance_dates)]
        # Compare against the *panel*, not the ranked universe. A coin that is
        # in the panel but fails the liquidity/turnover gate was filtered for
        # tradability on purpose and the next name was promoted deliberately.
        # Only a name the panel cannot carry at all is a survivorship hole.
        panel_symbols = {str(value).upper() for value in panel["symbol"].unique()}
        absent = true_top[~true_top["symbol"].str.upper().isin(panel_symbols)]
        missing_members = {str(k): int(v) for k, v in absent.groupby("symbol").size().sort_values(ascending=False).items()}

    check(
        "universe: no real Top-N member is missing (survivorship)",
        not missing_members,
        "absent=" + (", ".join(f"{symbol} ({days}d)" for symbol, days in list(missing_members.items())[:6]) or "none"),
        warn=bool(missing_members),
    )

    # The check above can only see coins that were fetched at least once, so a
    # name that never resolved a CoinMarketCap id is invisible to it. Every id
    # on the curated historical watchlist therefore has to reach the panel, or
    # be explicitly recorded as un-onboardable with a reason and a cost. This
    # is the guard that was missing when MATIC - Top-20 on 123 of the 215
    # rebalance dates - dropped out of the pool without a single warning.
    # "Onboarded" means the coin reached the screening stage with real history
    # - not that it survived it. A name the cross-check refuses (CEL, HT) is a
    # deliberate, recorded decision, while a name that never resolved an id or
    # never got fetched is the silent hole this check exists to catch.
    screened_coin_ids = {str(value).lower() for value in quality["coin_id"].unique()}
    excused = {str(key).lower(): str(value) for key, value in config.universe.legacy_unavailable.items()}
    unknown_excuses = sorted(set(excused) - {str(value).lower() for value in config.universe.legacy_candidate_ids})
    legacy_missing = sorted(
        coin_id
        for coin_id in config.universe.legacy_candidate_ids
        if coin_id.lower() not in screened_coin_ids and coin_id.lower() not in excused
    )
    refused = quality[
        quality["coin_id"].astype(str).str.lower().isin({value.lower() for value in config.universe.legacy_candidate_ids})
        & ~quality["included_in_panel"].fillna(False).astype(bool)
    ]
    check(
        "universe: every legacy watchlist coin is onboarded or excused",
        not legacy_missing,
        f"{len(config.universe.legacy_candidate_ids)} watchlist coin(s); never onboarded and "
        f"unexcused={legacy_missing[:6]}; onboarded but refused by the cross-check="
        f"{refused['symbol'].tolist()[:5]}",
    )
    check(
        "universe: excused watchlist coins are declared with a reason",
        not unknown_excuses and all(reason.strip() for reason in excused.values()),
        "excused="
        + (", ".join(f"{key}" for key in sorted(excused)) or "none")
        + (f"; excuses for non-watchlist ids={unknown_excuses}" if unknown_excuses else ""),
        warn=bool(excused),
    )

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
    # Terminal missing returns are only safe when the engine actually exits
    # them. Probe it: a synthetic holding whose feed ends must be liquidated at
    # its last print (no raise, weight to zero), while an interior provider gap
    # must still abort the run.
    probe_dates = pd.date_range("2024-01-01", periods=4, freq="D")
    probe_returns = pd.DataFrame({"a": [0.0, 0.10, float("nan"), float("nan")]}, index=probe_dates)
    probe_targets = {probe_dates[0]: pd.Series({"a": 1.0})}
    probe_friction = config.frictions.model_copy(update={"fee_bps": 0.0, "slippage_bps": 0.0, "max_weight_per_coin": 1.0})
    try:
        probe = run_backtest("probe", probe_returns, probe_targets, pd.Series({"a": "Other"}), probe_friction, 100.0)
        liquidated = float(probe.weights.loc[probe_dates[2], "a"]) == 0.0
    except Exception as exc:  # noqa: BLE001
        liquidated = False
        LOGGER.warning("Ended-feed probe failed: %s", exc)
    gap_returns = pd.DataFrame({"a": [0.0, float("nan"), 0.05, 0.05]}, index=probe_dates)
    try:
        run_backtest("gap", gap_returns, probe_targets, pd.Series({"a": "Other"}), probe_friction, 100.0)
        interior_gap_refused = False
    except ValueError:
        interior_gap_refused = True
    check(
        "engine: ended feeds are liquidated, interior gaps still refuse",
        bool(liquidated and interior_gap_refused),
        f"terminal missing return cells={terminal_missing}; ended feed liquidated={liquidated}, "
        f"interior provider gap refused={interior_gap_refused}",
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
