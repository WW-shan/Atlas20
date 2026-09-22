"""Independently audit the point-in-time Top-N universe and the picked coin.

The point-in-time universe is the one thing that can silently destroy this
strategy: if "was this coin Top-20 on that date?" is answered with today's
membership, or with a forward-filled market cap, the backtest buys tomorrow's
winners. This script re-derives the ranking from the raw CoinMarketCap payload
that the pipeline cached, without going through the pipeline's own market-cap
matrix, and compares it date by date with what the strategy actually saw.

It then replays the champion's weekly selection and writes, for every rebalance
date, the whole Top-N, the picked coin, its rank, the BTC gate state and the
executed gross exposure, so the selection can be eyeballed rather than trusted.

Outputs (next to the finalist report):
  selections.csv       one row per rebalance date: gate, pick, rank, exposure
  universe_audit.csv   one row per rebalance date: pipeline vs raw-CMC Top-N
  selection_audit.md   human-readable summary
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.config import ResearchConfig, load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.signals.risk import absolute_trend_mask, realized_volatility  # noqa: E402
from atlas20.strategies.bull_offense import build_bull_offense_targets  # noqa: E402
from atlas20.strategies.overlays import apply_daily_asset_stop_overlay  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402


def _cmc_id_map(config: ResearchConfig) -> dict[str, int]:
    """Symbol -> CMC id, exactly as the data processor resolves it."""
    path = config.resolve_path(config.paths.raw_dir) / "coinmarketcap" / "id_map.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = {str(symbol).upper(): int(cmc_id) for symbol, cmc_id in raw.items()}
    mapping.update(
        {symbol.upper(): int(cmc_id) for symbol, cmc_id in config.universe.cmc_symbol_aliases.items()}
    )
    return mapping


def _raw_market_caps(config: ResearchConfig, symbols: dict[str, str]) -> pd.DataFrame:
    """Market cap per (date, coin) straight from the cached CMC payloads.

    Deliberately does not touch ``data/processed``: the whole point is to check
    the processed panel against the provider data it claims to represent.
    """
    history_dir = config.resolve_path(config.paths.raw_dir) / "coinmarketcap" / "history"
    id_map = _cmc_id_map(config)
    series: dict[str, pd.Series] = {}
    unresolved: list[str] = []

    for coin_id, symbol in symbols.items():
        cmc_id = id_map.get(str(symbol).upper())
        if cmc_id is None:
            unresolved.append(coin_id)
            continue
        per_date: dict[pd.Timestamp, float] = {}
        for path in sorted(history_dir.glob(f"{cmc_id}_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, list):
                continue
            for entry in payload:
                try:
                    close = pd.Timestamp(entry["timeClose"])
                    # CMC stamps the close in UTC ("...T23:59:59.999Z"); the
                    # panel is tz-naive calendar dates, so normalise to a naive
                    # date or every lookup silently misses.
                    close = close.tz_localize(None) if close.tzinfo else close
                    close = close.normalize()
                    cap = entry["quote"]["marketCap"]
                except (KeyError, TypeError, ValueError):
                    continue
                if cap is None:
                    continue
                # Later files win: the incremental refresh carries the newest
                # revision of a date the full-history file also contains.
                per_date[close] = float(cap)
        if per_date:
            series[coin_id] = pd.Series(per_date).sort_index()

    if unresolved:
        print(f"  note: {len(unresolved)} coin(s) have no CMC id: {', '.join(sorted(unresolved))}")
    if not series:
        raise RuntimeError("no raw CoinMarketCap history could be parsed")
    frame = pd.DataFrame(series)
    frame.index.name = "date"
    return frame


def _eligible_mask(
    market,
    config: ResearchConfig,
    date: pd.Timestamp,
    columns,
    raw_caps: pd.Series,
) -> pd.Series:
    """Every eligibility gate the universe builder applies, applied to the panel.

    The market-cap *values* deliberately come from the raw provider payload;
    everything else (price, dollar volume, history, and the turnover/liquidity
    gate that keeps high-cap / low-float names such as CRO out) has to match the
    builder exactly, or the comparison flags differences that are the auditor's
    fault rather than the pipeline's.
    """
    price = market.price.loc[date].reindex(columns)
    volume = market.volume.loc[date].reindex(columns)
    history = market.history_count.loc[date].reindex(columns)
    caps = raw_caps.reindex(columns)
    eligible = (
        price.notna()
        & (price > 0)
        & (price >= config.universe.min_price)
        & caps.notna()
        & (caps > 0)
        & volume.notna()
        & (volume >= config.universe.min_daily_dollar_volume)
        & history.notna()
        & (history >= config.universe.min_history_days)
    )
    if config.universe.min_turnover_ratio > 0:
        turnover = volume / caps
        eligible &= (turnover >= config.universe.min_turnover_ratio) | (
            volume >= config.universe.min_turnover_volume_usd
        )
    return eligible


def _default_output_dir(
    config: ResearchConfig, start_date: str | None, end_date: str | None
) -> Path:
    """Return an isolated report directory for a custom audit window.

    A custom start/end date must never overwrite the canonical 2021 report.
    For the common January-1 case use the year suffix (for example,
    ``bull_offense_finalist_2022``), matching the runner's report naming.
    """
    reports_parent = config.resolve_path(config.paths.reports_dir).parent
    if not start_date and not end_date:
        return reports_parent / "bull_offense_finalist"

    if start_date:
        start = pd.Timestamp(start_date)
        if start == pd.Timestamp(year=start.year, month=1, day=1):
            suffix = str(start.year)
        else:
            suffix = start.date().isoformat()
    else:
        suffix = "default-start"
    if end_date:
        suffix = f"{suffix}_to_{pd.Timestamp(end_date).date().isoformat()}"
    return reports_parent / f"bull_offense_finalist_{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--hold-count", type=int, default=1)
    parser.add_argument("--lookback", type=int, default=30)
    parser.add_argument("--btc-ma", type=int, default=50)
    parser.add_argument("--asset-ma", type=int, default=50)
    parser.add_argument("--target-vol", type=float, default=0.8)
    parser.add_argument("--tail", type=int, default=12, help="How many recent dates to print.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.start_date or args.end_date:
        config = config.model_copy(deep=True)
        if args.start_date:
            config.start_date = args.start_date
        if args.end_date:
            config.end_date = args.end_date
    configure_logging("ERROR")

    panel, metadata = build_processed_datasets(
        config,
        load_sector_config(config.resolve_path("config/sectors.yaml")),
        persist=False,
    )
    market = prepare_market_data(panel, metadata, config)
    backtest_returns = market.returns.loc[config.start_timestamp : config.end_timestamp]
    weekly_dates = get_rebalance_dates(
        backtest_returns.index, config.start_timestamp, "7D", "7D"
    )
    universe = build_rebalance_universe(market, weekly_dates, config)
    print(
        f"window {backtest_returns.index.min().date()} .. {backtest_returns.index.max().date()} "
        f"({len(weekly_dates)} weekly rebalances, {universe['coin_id'].nunique()} coins ever in the Top-N)"
    )

    # ---------------------------------------------------------- raw CMC audit
    symbols = {
        str(coin_id): str(symbol)
        for coin_id, symbol in metadata["symbol"].items()
        if coin_id in market.price.columns
    }
    raw_caps = _raw_market_caps(config, symbols)
    print(
        f"raw CoinMarketCap matrix: {raw_caps.shape[1]} coins x {raw_caps.shape[0]} dates "
        f"({raw_caps.index.min().date()} .. {raw_caps.index.max().date()})"
    )

    audit_rows: list[dict[str, object]] = []
    for date in weekly_dates:
        pipeline = universe[universe["rebalance_date"] == date].sort_values("universe_rank")
        if pipeline.empty:
            continue
        columns = [c for c in raw_caps.columns]
        if date not in raw_caps.index:
            audit_rows.append(
                {"rebalance_date": date, "status": "raw-cmc-missing-date", "pipeline_n": len(pipeline)}
            )
            continue

        eligible = _eligible_mask(market, config, date, columns, raw_caps.loc[date])
        caps = raw_caps.loc[date].where(eligible).dropna()
        independent = caps.sort_values(ascending=False).head(config.universe.universe_size)

        pipeline_ids = list(pipeline["coin_id"])
        independent_ids = list(independent.index)
        pipeline_caps = dict(zip(pipeline["coin_id"], pipeline["market_cap"]))
        cap_mismatch = {
            coin: (pipeline_caps[coin], float(raw_caps.loc[date, coin]))
            for coin in pipeline_ids
            if coin in raw_caps.columns
            and pd.notna(raw_caps.loc[date, coin])
            and abs(float(pipeline_caps[coin]) - float(raw_caps.loc[date, coin]))
            > max(1.0, 1e-6 * float(raw_caps.loc[date, coin]))
        }
        missing_in_raw = [c for c in pipeline_ids if c not in raw_caps.columns or pd.isna(raw_caps.loc[date, c])]
        audit_rows.append(
            {
                "rebalance_date": date,
                "status": "ok",
                "pipeline_n": len(pipeline_ids),
                "independent_n": len(independent_ids),
                "same_set": set(pipeline_ids) == set(independent_ids),
                "same_order": pipeline_ids == independent_ids,
                "overlap": len(set(pipeline_ids) & set(independent_ids)),
                "only_pipeline": ",".join(sorted(set(pipeline_ids) - set(independent_ids))),
                "only_independent": ",".join(sorted(set(independent_ids) - set(pipeline_ids))),
                "cap_mismatch_n": len(cap_mismatch),
                "missing_in_raw_n": len(missing_in_raw),
                "top1": pipeline_ids[0] if pipeline_ids else "",
            }
        )

    audit = pd.DataFrame(audit_rows)
    ok = audit[audit["status"] == "ok"]
    print(
        f"\nuniverse audit: {len(ok)} dates compared, "
        f"{int(ok['same_set'].sum())} identical sets, {int(ok['same_order'].sum())} identical order, "
        f"cap mismatches={int(ok['cap_mismatch_n'].sum())}, "
        f"members missing from raw cache={int(ok['missing_in_raw_n'].sum())}"
    )
    if not ok.empty and not ok["same_set"].all():
        bad = ok[~ok["same_set"]]
        print(f"  {len(bad)} date(s) disagree; first few:")
        print(bad.head(5).to_string(index=False))

    # ------------------------------------------------------- selection replay
    built = build_bull_offense_targets(
        market,
        universe,
        hold_count=args.hold_count,
        frequency="weekly",
        frequency_value="7D",
        lookback=args.lookback,
        exit_ma_window=args.btc_ma,
        max_leverage=1.0,
        leverage_when_strong=1.0,
        rebalance_dates=weekly_dates,
    )
    targets = built.targets
    if args.asset_ma > 0:
        targets = apply_daily_asset_stop_overlay(
            targets, absolute_trend_mask(market.price, ma_window=args.asset_ma)
        )
    vol_frame = realized_volatility(market.price, window=30)

    history = built.signal_history.set_index("date")
    rows: list[dict[str, object]] = []
    for date in weekly_dates:
        date = pd.Timestamp(date)
        if date not in history.index:
            continue
        record = history.loc[date]
        pipeline = universe[universe["rebalance_date"] == date].sort_values("universe_rank")
        picks = targets.get(date)
        # The stop overlay returns a dense Series reindexed over every asset
        # that ever appeared, with the un-held names at exactly 0.0. Taking
        # ``index[0]`` there reads the first *label* (alphabetically "aptos"),
        # not the position, so the held name must be selected by weight.
        held = picks[picks > 0] if picks is not None and not picks.empty else None
        pick = str(held.sort_values(ascending=False).index[0]) if held is not None and not held.empty else ""
        rank = (
            int(pipeline.loc[pipeline["coin_id"] == pick, "universe_rank"].iloc[0])
            if pick and (pipeline["coin_id"] == pick).any()
            else None
        )
        exposure = 0.0
        if pick and date in vol_frame.index and pick in vol_frame.columns:
            realised = float(vol_frame.loc[date, pick])
            if pd.notna(realised) and realised > 0:
                exposure = min(1.0, float(args.target_vol) / realised)
        independent_rank = None
        if date in raw_caps.index and pick:
            eligible = _eligible_mask(
                market, config, date, list(raw_caps.columns), raw_caps.loc[date]
            )
            caps = raw_caps.loc[date].where(eligible).dropna().sort_values(ascending=False)
            if pick in caps.index:
                independent_rank = int(caps.index.get_loc(pick)) + 1
        rows.append(
            {
                "rebalance_date": date.date().isoformat(),
                "btc_gate_open": bool(record["trend_ok"]),
                "top20": " ".join(pipeline["coin_id"].tolist()),
                "picked": pick,
                "picked_symbol": (
                    str(metadata.loc[pick, "symbol"]) if pick and pick in metadata.index else ""
                ),
                "pipeline_rank": rank,
                "independent_rank": independent_rank,
                "in_top20": bool(rank is not None),
                "target_vol_exposure": round(exposure, 4),
                "top_score": float(record["top_score"]) if "top_score" in record and pd.notna(record.get("top_score")) else None,
            }
        )

    selections = pd.DataFrame(rows)
    selections["picked"] = selections["picked"].fillna("").astype(str)
    # An empty pick means the BTC gate was shut (deliberately in cash); it is
    # not a selection that failed the universe test.
    problems = selections[~selections["in_top20"] & (selections["picked"] != "")]
    print(
        f"selection replay: {len(selections)} rebalances, "
        f"{int(selections['btc_gate_open'].sum())} with the BTC gate open, "
        f"{len(problems)} pick(s) outside that date's Top-N"
    )

    report_dir = ensure_dir(
        args.output_dir
        if args.output_dir is not None
        else _default_output_dir(config, args.start_date, args.end_date)
    )
    selections.to_csv(report_dir / "selections.csv", index=False)
    audit.to_csv(report_dir / "universe_audit.csv", index=False)

    recent = selections.tail(args.tail)
    gate_open = selections[selections["btc_gate_open"]]
    lines = [
        "# Finalist selection and universe audit",
        "",
        f"- Window: {selections['rebalance_date'].min()} .. {selections['rebalance_date'].max()}",
        f"- Weekly rebalances replayed: {len(selections)}",
        f"- BTC gate open on {int(selections['btc_gate_open'].sum())} of them "
        f"({selections['btc_gate_open'].mean():.1%}); flat otherwise",
        f"- Picks outside that date's Top-N: {len(problems)}",
        "",
        "## Independent point-in-time ranking check",
        "",
        "The ranking was rebuilt straight from the cached CoinMarketCap payload "
        "(`data/raw/coinmarketcap/history`) and compared with the universe the "
        "strategy used. Same eligibility gates (price, dollar volume, history) "
        "are applied to both sides so the comparison isolates the market-cap "
        "ranking itself.",
        "",
        f"- Dates compared: {len(ok)}",
        f"- Identical membership: {int(ok['same_set'].sum())} / {len(ok)}",
        f"- Identical order: {int(ok['same_order'].sum())} / {len(ok)}",
        f"- Market-cap value mismatches beyond 1e-6 relative: {int(ok['cap_mismatch_n'].sum())}",
        f"- Members absent from the raw cache: {int(ok['missing_in_raw_n'].sum())}",
        "",
        "## Recent rebalances",
        "",
        dataframe_to_markdown(recent.set_index("rebalance_date")[
            ["btc_gate_open", "picked_symbol", "pipeline_rank", "independent_rank", "target_vol_exposure"]
        ]),
        "",
        "## How often each coin was picked",
        "",
        dataframe_to_markdown(
            gate_open["picked_symbol"]
            .value_counts()
            .rename_axis("symbol")
            .to_frame("picks")
        ),
        "",
        "Full per-date trace (including the entire Top-N on every date) is in "
        "`selections.csv`; the per-date universe comparison is in "
        "`universe_audit.csv`.",
        "",
    ]
    (report_dir / "selection_audit.md").write_text("\n".join(lines), encoding="utf-8")

    print("\nMost recent rebalances (gate / pick / rank / exposure):")
    print(
        recent[["rebalance_date", "btc_gate_open", "picked_symbol", "pipeline_rank", "independent_rank", "target_vol_exposure"]]
        .to_string(index=False)
    )
    print(f"\nWrote {report_dir / 'selections.csv'}, universe_audit.csv, selection_audit.md")


if __name__ == "__main__":
    main()
