"""Audit the CTREND champion's point-in-time Top20 universe and selections.

This is deliberately independent of the processed market-cap matrix for the
ranking audit: it reads the cached CoinMarketCap history payloads directly,
rebuilds the Top20 using the same eligibility gates, and compares that set and
order with the universe the strategy saw.  It also replays every scheduled
CTREND decision and checks that the executed coin was inside that date's Top20.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.config import load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from atlas20.universe.builder import build_rebalance_universe, prepare_market_data  # noqa: E402
from scripts.audit_finalist_selections import _eligible_mask, _raw_market_caps  # noqa: E402
from scripts.run_ctrend_champion import ChampionSpec, build_champion_targets  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/ctrend_champion_top20_2022"))
    args = parser.parse_args()

    config = load_config(args.config).model_copy(deep=True)
    config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    config.universe.universe_size = 20
    config.universe.min_history_days = 90
    config.universe.min_daily_dollar_volume = 25_000_000.0
    configure_logging("ERROR")

    panel, metadata = build_processed_datasets(
        config,
        load_sector_config(config.resolve_path("config/sectors.yaml")),
        persist=False,
    )
    market = prepare_market_data(panel, metadata, config)
    rebalance_dates = get_rebalance_dates(
        market.price.index,
        config.start_timestamp,
        "21D",
        "21D",
    )
    universe = build_rebalance_universe(market, rebalance_dates, config)
    symbols = {
        str(coin_id): str(symbol)
        for coin_id, symbol in metadata["symbol"].items()
        if coin_id in market.price.columns
    }
    raw_caps = _raw_market_caps(config, symbols)

    audit_rows: list[dict[str, object]] = []
    for date in rebalance_dates:
        date = pd.Timestamp(date)
        snapshot = universe[universe["rebalance_date"] == date].sort_values("universe_rank")
        if snapshot.empty:
            continue
        if date not in raw_caps.index:
            audit_rows.append({"rebalance_date": date, "status": "raw-cmc-missing-date"})
            continue
        columns = list(raw_caps.columns)
        eligible = _eligible_mask(market, config, date, columns, raw_caps.loc[date])
        independent = raw_caps.loc[date].where(eligible).dropna().sort_values(ascending=False).head(20)
        pipeline_ids = snapshot["coin_id"].tolist()
        independent_ids = independent.index.tolist()
        pipeline_caps = dict(zip(snapshot["coin_id"], snapshot["market_cap"]))
        mismatches = sum(
            1
            for coin in pipeline_ids
            if coin in raw_caps.columns
            and pd.notna(raw_caps.loc[date, coin])
            and abs(float(pipeline_caps[coin]) - float(raw_caps.loc[date, coin]))
            > max(1.0, 1e-6 * float(raw_caps.loc[date, coin]))
        )
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
                "cap_mismatch_n": mismatches,
                "pipeline_top1": pipeline_ids[0] if pipeline_ids else "",
                "independent_top1": independent_ids[0] if independent_ids else "",
            }
        )
    audit = pd.DataFrame(audit_rows)
    ok = audit[audit["status"] == "ok"] if not audit.empty else audit

    _, history, _ = build_champion_targets(
        market,
        universe,
        config,
        ChampionSpec(),
    )
    selection_rows: list[dict[str, object]] = []
    universe_by_date = {
        pd.Timestamp(date): frame.sort_values("universe_rank")
        for date, frame in universe.groupby("rebalance_date")
    }
    for _, row in history.iterrows():
        date = pd.Timestamp(row["rebalance_date"])
        snapshot = universe_by_date.get(date, pd.DataFrame())
        coin = str(row["executed_coin_id"])
        pipeline_rank = None
        independent_rank = None
        if coin:
            match = snapshot[snapshot["coin_id"] == coin]
            if not match.empty:
                pipeline_rank = int(match["universe_rank"].iloc[0])
            if date in raw_caps.index and coin in raw_caps.columns:
                eligible = _eligible_mask(
                    market,
                    config,
                    date,
                    list(raw_caps.columns),
                    raw_caps.loc[date],
                )
                caps = raw_caps.loc[date].where(eligible).dropna().sort_values(ascending=False)
                if coin in caps.index:
                    independent_rank = int(caps.index.get_loc(coin)) + 1
        selection_rows.append(
            {
                **row.to_dict(),
                "pipeline_rank": pipeline_rank,
                "independent_rank": independent_rank,
                "executed_in_top20": bool(
                    coin == "" or (pipeline_rank is not None and pipeline_rank <= 20)
                ),
                "top20_ids": " ".join(snapshot["coin_id"].tolist()),
            }
        )
    selections = pd.DataFrame(selection_rows)
    problems = (
        selections[~selections["executed_in_top20"]]
        if not selections.empty and "executed_in_top20" in selections.columns
        else pd.DataFrame()
    )
    output_dir = ensure_dir(args.output_dir)
    universe_out = output_dir / "universe_audit.csv"
    selections_out = output_dir / "selections.csv"
    audit.to_csv(universe_out, index=False)
    selections.to_csv(selections_out, index=False)

    summary = {
        "window": {
            "start": config.start_timestamp.date().isoformat(),
            "end": config.end_timestamp.date().isoformat(),
        },
        "rebalance_dates": len(rebalance_dates),
        "universe_dates_compared": int(len(ok)),
        "same_set": int(ok["same_set"].sum()) if not ok.empty else 0,
        "same_order": int(ok["same_order"].sum()) if not ok.empty else 0,
        "cap_mismatch_n": int(ok["cap_mismatch_n"].sum()) if not ok.empty else 0,
        "selection_rows": int(len(selections)),
        "picks_outside_top20": int(len(problems)),
        "executed_picks": int((selections["executed_coin_id"].astype(str) != "").sum())
        if not selections.empty
        else 0,
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# CTREND Top20 Universe and Selection Audit",
        "",
        "The ranking comparison below is rebuilt from raw cached CoinMarketCap "
        "payloads and does not use the processed market-cap matrix.",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
        "## Universe Check",
        "",
        dataframe_to_markdown(audit.head(20).reset_index(drop=True)),
        "",
        "## Recent Executed Selections",
        "",
        dataframe_to_markdown(
            selections.tail(20)[
                [
                    "rebalance_date",
                    "btc_gate_open",
                    "coin_id",
                    "executed_coin_id",
                    "pipeline_rank",
                    "independent_rank",
                    "executed_weight",
                ]
            ].reset_index(drop=True)
        )
        if not selections.empty
        else "No selections.",
        "",
        "Full per-date traces are in `selections.csv` and `universe_audit.csv`.",
        "",
    ]
    (output_dir / "selection_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote audit files to {output_dir}")


if __name__ == "__main__":
    main()
