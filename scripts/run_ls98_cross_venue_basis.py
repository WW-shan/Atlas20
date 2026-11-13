"""LS98: research proxy for a BTC/ETH cross-venue spot-perp basis sleeve.

The sleeve is long spot and short perpetual for each asset, with no portfolio
leverage.  It is research-only: the spot tape is a CMC/Binance daily proxy and
the funding is a Binance proxy, not a same-venue Bitget execution proof.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS98-CROSS-VENUE-BASIS"
START = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-09-20", tz="UTC")
ASSETS = ("bitcoin", "ethereum")
PERP_SYMBOLS = {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT"}
NOTIONAL_PER_LEG = 0.25
LEGS_PER_ASSET = 2
COSTS_BPS = (5.0, 10.0, 20.0)
PRIMARY_COST_BPS = 10.0
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")


def basis_daily_return(
    *,
    spot_returns: pd.DataFrame,
    perp_returns: pd.DataFrame,
    funding: pd.DataFrame,
    positions: pd.DataFrame,
) -> pd.DataFrame:
    """Return hedged basis and funding PnL for the supplied NAV positions."""
    common_index = spot_returns.index.intersection(perp_returns.index).intersection(funding.index).intersection(positions.index)
    common_assets = spot_returns.columns.intersection(perp_returns.columns).intersection(funding.columns).intersection(positions.columns)
    if len(common_index) == 0 or len(common_assets) == 0:
        raise ValueError("basis inputs have no common sample")
    spot = spot_returns.loc[common_index, common_assets]
    perp = perp_returns.loc[common_index, common_assets]
    carry = funding.loc[common_index, common_assets]
    weights = positions.loc[common_index, common_assets]
    if any(frame.isna().to_numpy().any() for frame in (spot, perp, carry, weights)):
        raise ValueError("basis inputs contain missing values")
    basis_pnl = (weights * (spot - perp)).sum(axis=1)
    funding_pnl = (weights * carry).sum(axis=1)
    return pd.DataFrame(
        {
            "basis_pnl": basis_pnl,
            "funding_pnl": funding_pnl,
            "daily_return": basis_pnl + funding_pnl,
        },
        index=common_index,
    )


def positive_funding_positions(
    funding: pd.DataFrame,
    *,
    index: pd.DatetimeIndex,
    assets: Sequence[str],
    lookback_days: int,
    rebalance_days: int,
    notional: float,
) -> pd.DataFrame:
    """Hold an asset only when its trailing funding sum is positive at rebalance."""
    if lookback_days < 1 or rebalance_days < 1:
        raise ValueError("lookback_days and rebalance_days must be positive")
    if notional < 0.0 or notional > 1.0:
        raise ValueError("notional must be in [0, 1]")
    missing = set(assets).difference(funding.columns)
    if missing:
        raise ValueError(f"funding is missing assets: {sorted(missing)}")
    frame = funding.reindex(index=index, columns=list(assets))
    if frame.isna().any().any():
        raise ValueError("funding has missing days on the requested index")
    trailing = frame.rolling(lookback_days, min_periods=lookback_days).sum().shift(1)
    positions = pd.DataFrame(0.0, index=index, columns=list(assets))
    rebalance_dates = index[::rebalance_days]
    for position, date in enumerate(rebalance_dates):
        signal = trailing.loc[date] > 0.0
        end = rebalance_dates[position + 1] if position + 1 < len(rebalance_dates) else index[-1] + pd.Timedelta(days=1)
        positions.loc[(index >= date) & (index < end), :] = np.where(signal.to_numpy(), float(notional), 0.0)
    return positions


def basis_gross_exposure(positions: pd.DataFrame) -> pd.Series:
    """Actual gross including both the spot long and perp short legs."""
    if (positions < 0.0).to_numpy().any():
        raise ValueError("basis positions must be non-negative")
    return (positions.abs().sum(axis=1) * LEGS_PER_ASSET).rename("gross_exposure")


def turnover_from_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """One-way turnover by asset, including initial entry and final exit."""
    turnover = positions.diff().abs()
    if not turnover.empty:
        turnover.iloc[0] = positions.iloc[0].abs()
        turnover.iloc[-1] += positions.iloc[-1].abs()
    return turnover.fillna(0.0)


def basis_turnover_cost(positions: pd.DataFrame, *, cost_bps: float) -> pd.Series:
    """Per-day cost for both spot and perp legs, including initial/final exit."""
    if not np.isfinite(cost_bps) or cost_bps < 0.0:
        raise ValueError("cost_bps must be finite and non-negative")
    turnover = turnover_from_positions(positions).sum(axis=1)
    return (turnover * float(LEGS_PER_ASSET) * float(cost_bps) / 10_000.0).rename("cost")


def classify_basis_evidence(
    *,
    asset_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    funding_pnl: float,
    basis_pnl: float,
) -> str:
    """Classify whether the basis sleeve is diversified or a one-asset artifact."""
    total = float(asset_summary["net_pnl"].sum())
    if total <= 0.0:
        return "inconclusive"
    if float(asset_summary["net_pnl"].max()) / total > 0.70:
        return "asset-concentrated"
    if float(year_summary["net_pnl"].max()) / total > 0.70:
        return "year-concentrated"
    if funding_pnl > 0.0 and funding_pnl >= basis_pnl:
        return "funding-dominated"
    if basis_pnl > 0.0:
        return "basis-dominated"
    return "inconclusive"


def _load_inputs(
    *,
    panel_path: Path,
    perp_dir: Path,
    funding_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = pd.read_csv(panel_path, usecols=["date", "coin_id", "price"], parse_dates=["date"])
    panel = panel.loc[panel["coin_id"].isin(ASSETS)]
    spot = panel.pivot(index="date", columns="coin_id", values="price").sort_index()
    spot.index = pd.DatetimeIndex(pd.to_datetime(spot.index, utc=True))
    if spot.isna().any().any():
        raise ValueError("spot panel has missing BTC/ETH prices")
    perp_frames: dict[str, pd.Series] = {}
    for asset in ASSETS:
        path = perp_dir / f"{PERP_SYMBOLS[asset]}_mark.csv"
        frame = pd.read_csv(path, parse_dates=["open_time"])
        frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
        perp_frames[asset] = frame.set_index("open_time")["close"].resample("1D").last()
    perp = pd.DataFrame(perp_frames).sort_index()
    funding_frames: dict[str, pd.Series] = {}
    for asset in ASSETS:
        frame = pd.read_csv(funding_dir / f"{asset}.csv")
        frame["date"] = pd.to_datetime(frame["calc_time"], unit="ms", utc=True).dt.normalize()
        counts = frame.groupby("date").size()
        if not counts.eq(3).all():
            bad = counts[~counts.eq(3)].index[:5].tolist()
            raise ValueError(f"{asset} funding has non-3-settlement days: {bad}")
        funding_frames[asset] = frame.groupby("date")["last_funding_rate"].sum()
    funding = pd.DataFrame(funding_frames).sort_index()
    common = spot.index.intersection(perp.index).intersection(funding.index)
    common = common[(common >= START) & (common <= END)]
    if len(common) < 100:
        raise ValueError("insufficient common basis observations")
    spot = spot.reindex(common)
    perp = perp.reindex(common)
    funding = funding.reindex(common)
    if spot.isna().any().any() or perp.isna().any().any() or funding.isna().any().any():
        raise ValueError("basis inputs have missing values after alignment")
    return spot, perp, funding, perp / spot - 1.0


def _sample_metrics(series: pd.Series, *, validation: bool = False) -> dict[str, float]:
    segment = series
    if validation:
        segment = series.loc[(series.index >= VALIDATION_START) & (series.index <= END)]
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _asset_summary(
    *,
    spot_returns: pd.DataFrame,
    perp_returns: pd.DataFrame,
    funding: pd.DataFrame,
    positions: pd.DataFrame,
    cost_bps: float,
) -> pd.DataFrame:
    basis = positions * (spot_returns - perp_returns)
    carry = positions * funding
    costs = (
        turnover_from_positions(positions)
        * float(LEGS_PER_ASSET)
        * float(cost_bps)
        / 10_000.0
    )
    frame = pd.DataFrame(
        {
            "asset": list(positions.columns),
            "basis_pnl": basis.sum().to_numpy(),
            "funding_pnl": carry.sum().to_numpy(),
            "costs": costs.sum().to_numpy(),
        }
    )
    frame["net_pnl"] = frame["basis_pnl"] + frame["funding_pnl"] - frame["costs"]
    return frame.sort_values("net_pnl", ascending=False).reset_index(drop=True)


def _report(
    *,
    variant_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    asset_summary: pd.DataFrame,
    classification: str,
    rows: int,
    start: str,
    end: str,
) -> str:
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS98 is a research proxy for a long-spot / short-perp BTC/ETH basis sleeve. It is not a",
        "live signal and does not prove same-venue Bitget execution.",
        "",
        f"- Common sample: {start} → {end} ({rows} daily observations)",
        "- Per asset: spot long 0.25x NAV + perp short 0.25x NAV; portfolio gross 1.00x",
        "- Primary cost: 10bps per leg per side; 5/20bps shown as a band",
        "- Funding is a Binance proxy; perp mark is Bitget; spot is a CMC/Binance daily proxy",
        "- Gross counts both legs; costs are charged on each leg per side",
        "",
        "## Variant summary",
        "",
        dataframe_to_markdown(variant_summary),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Asset attribution (always-on, 10bps)",
        "",
        dataframe_to_markdown(asset_summary),
        "",
        "## Evidence classification",
        "",
        f"**{classification}**",
        "",
        "The label is a research diagnostic. It does not promote the sleeve or change the live track.",
        "A positive result only earns a same-venue spot/perp data and execution study.",
        "",
        "Research output only; no orders sent.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--panel", type=Path, default=Path("data/processed/panel_daily.csv"))
    parser.add_argument(
        "--perp-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_20261009/candles"),
    )
    parser.add_argument("--funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    args = parser.parse_args(argv)

    spot, perp, funding, basis = _load_inputs(
        panel_path=args.panel,
        perp_dir=args.perp_dir,
        funding_dir=args.funding_dir,
    )
    spot_returns = spot.pct_change().fillna(0.0)
    perp_returns = perp.pct_change().fillna(0.0)
    always = pd.DataFrame(NOTIONAL_PER_LEG, index=spot.index, columns=ASSETS)
    filtered = positive_funding_positions(
        funding,
        index=spot.index,
        assets=ASSETS,
        lookback_days=7,
        rebalance_days=7,
        notional=NOTIONAL_PER_LEG,
    )
    variants: dict[str, pd.DataFrame] = {
        "always-on": always,
        "positive-funding": filtered,
        "btc-only": pd.DataFrame({"bitcoin": NOTIONAL_PER_LEG}, index=spot.index),
        "eth-only": pd.DataFrame({"ethereum": NOTIONAL_PER_LEG}, index=spot.index),
    }
    summary_rows: list[dict[str, Any]] = []
    yearly_rows: list[pd.DataFrame] = []
    primary_daily: pd.DataFrame | None = None
    for name, positions in variants.items():
        assets = list(positions.columns)
        pnl = basis_daily_return(
            spot_returns=spot_returns[assets],
            perp_returns=perp_returns[assets],
            funding=funding[assets],
            positions=positions[assets],
        )
        turnover = turnover_from_positions(positions[assets]).sum(axis=1)
        for cost in COSTS_BPS:
            net = pnl["daily_return"] - basis_turnover_cost(
                positions[assets], cost_bps=float(cost)
            )
            full = _sample_metrics(net)
            validation = _sample_metrics(net, validation=True)
            summary_rows.append(
                {
                    "variant": name,
                    "cost_bps": float(cost),
                    "full_multiple": full["multiple"],
                    "full_sharpe": full["sharpe"],
                    "full_max_drawdown": full["max_drawdown"],
                    "validation_multiple": validation["multiple"],
                    "validation_sharpe": validation["sharpe"],
                    "mean_gross": float(basis_gross_exposure(positions[assets]).mean()),
                    "turnover": float(turnover.sum()),
                }
            )
            if name == "always-on" and cost == PRIMARY_COST_BPS:
                primary_daily = pnl.copy()
                primary_daily["turnover"] = turnover
                primary_daily["net_return"] = net
                yearly = primary_daily["net_return"].groupby(primary_daily.index.year).apply(
                    lambda values: float((1.0 + values).prod() - 1.0)
                )
                yearly_pnl = primary_daily["net_return"].groupby(primary_daily.index.year).sum()
                yearly_rows.append(
                    pd.DataFrame(
                        {
                            "year": yearly.index.astype(int),
                            "return": yearly.to_numpy(dtype=float),
                            "net_pnl": yearly_pnl.reindex(yearly.index).to_numpy(dtype=float),
                        }
                    )
                )
    if primary_daily is None:
        raise RuntimeError("primary always-on 10bps variant did not run")
    asset_summary = _asset_summary(
        spot_returns=spot_returns[list(ASSETS)],
        perp_returns=perp_returns[list(ASSETS)],
        funding=funding[list(ASSETS)],
        positions=always,
        cost_bps=PRIMARY_COST_BPS,
    )
    classification = classify_basis_evidence(
        asset_summary=asset_summary,
        year_summary=pd.concat(yearly_rows, ignore_index=True),
        funding_pnl=float(asset_summary["funding_pnl"].sum()),
        basis_pnl=float(asset_summary["basis_pnl"].sum()),
    )
    variant_summary = pd.DataFrame(summary_rows)
    yearly_table = pd.concat(yearly_rows, ignore_index=True)
    output_dir = ensure_dir(args.output_dir)
    variant_summary.to_csv(output_dir / "variant_summary.csv", index=False)
    yearly_table.to_csv(output_dir / "yearly.csv", index=False)
    asset_summary.to_csv(output_dir / "asset_summary.csv", index=False)
    primary_daily.to_csv(output_dir / "daily_returns.csv", index_label="date")
    basis.to_csv(output_dir / "basis.csv", index_label="date")
    manifest = {
        "trial_id": TRIAL_ID,
        "assets": list(ASSETS),
        "notional_per_leg": NOTIONAL_PER_LEG,
        "legs_per_asset": LEGS_PER_ASSET,
        "total_gross": float(LEGS_PER_ASSET * len(ASSETS) * NOTIONAL_PER_LEG),
        "costs_bps": list(COSTS_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "start": str(spot.index.min()),
        "end": str(spot.index.max()),
        "rows": int(len(spot)),
        "panel": str(args.panel),
        "perp_dir": str(args.perp_dir),
        "funding_dir": str(args.funding_dir),
        "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "classification": classification,
        "orders_sent": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        _report(
            variant_summary=variant_summary,
            yearly=yearly_table,
            asset_summary=asset_summary,
            classification=classification,
            rows=len(spot),
            start=str(spot.index.min()),
            end=str(spot.index.max()),
        ),
        encoding="utf-8",
    )
    print(variant_summary.to_string(index=False))
    print(asset_summary.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
