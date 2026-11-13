"""LS100: Bitget same-venue spot-perp basis research study.

This is a research-only daily long-spot / short-perp proxy.  Prices are from
Bitget spot and Bitget perp mark; the full-history funding series is still a
Binance proxy.  Exact recent Bitget funding is used only for a reconciliation
window.  No orders are sent.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402
from scripts.fetch_bitget_spot_daily import audit_daily_coverage  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

TRIAL_ID = "PR2026-11-LS100-SAME-VENUE-BASIS"
START = pd.Timestamp("2022-01-02", tz="UTC")
END = pd.Timestamp("2026-09-20", tz="UTC")
VALIDATION_START = pd.Timestamp("2024-01-01", tz="UTC")
ASSETS = ("bitcoin", "ethereum")
SYMBOLS = {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT"}
NOTIONAL_PER_LEG = 0.25
LEGS_PER_ASSET = 2
COSTS_BPS = (10.0, 20.0)
PRIMARY_COST_BPS = 10.0
MAX_MARK_STALENESS_HOURS = 2.0
EXACT_FUNDING_START = pd.Timestamp("2026-07-11", tz="UTC")
DEFAULT_SPOT_DIR = PROJECT_ROOT / "data/raw/bitget_spot/20261113"
DEFAULT_PERP_DIR = PROJECT_ROOT / "data/raw/bitget_derivatives/merged_20261009/candles"
DEFAULT_BINANCE_FUNDING_DIR = PROJECT_ROOT / "data/raw/binance_funding"
DEFAULT_BITGET_FUNDING_DIR = PROJECT_ROOT / "data/raw/bitget_derivatives/funding"


def _as_utc_index(values: Sequence[object]) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(list(values), utc=True))
    return index


def align_perp_mark(
    marks: pd.DataFrame,
    target_index: pd.DatetimeIndex,
    *,
    max_staleness_hours: float,
) -> pd.DataFrame:
    """Use the latest completed 1h mark bar at or before each daily close.

    A bar opened at 23:00 UTC closes at the next 00:00 boundary.  Missing bars
    are allowed only within ``max_staleness_hours``; otherwise the row is
    marked unavailable and the caller must account for the reduced coverage.
    """
    if max_staleness_hours < 0.0:
        raise ValueError("max_staleness_hours must be non-negative")
    required = {"open_time", "close"}
    missing = sorted(required.difference(marks.columns))
    if missing:
        raise ValueError(f"mark frame missing columns: {missing}")
    if target_index.empty:
        return pd.DataFrame(index=target_index, columns=["mark_close", "staleness_hours", "available"])
    source = marks.loc[:, ["open_time", "close"]].copy()
    source["bar_close"] = _as_utc_index(source["open_time"]) + pd.Timedelta(hours=1)
    source["close"] = pd.to_numeric(source["close"], errors="coerce")
    source = source.dropna(subset=["bar_close", "close"]).sort_values("bar_close")
    source = source.drop_duplicates("bar_close", keep="last")
    if source.empty or not np.isfinite(source["close"].to_numpy(dtype=float)).all():
        raise ValueError("mark frame has no finite completed bars")
    target = pd.DatetimeIndex(pd.to_datetime(target_index, utc=True)).sort_values()
    positions = source["bar_close"].searchsorted(target, side="right") - 1
    rows: list[dict[str, Any]] = []
    for position, target_time in zip(positions, target, strict=True):
        if position < 0:
            rows.append({"mark_close": np.nan, "staleness_hours": np.inf, "available": False})
            continue
        bar_time = source["bar_close"].iloc[int(position)]
        staleness = float((target_time - bar_time).total_seconds() / 3600.0)
        available = staleness <= float(max_staleness_hours) + 1e-12
        rows.append(
            {
                "mark_close": float(source["close"].iloc[int(position)]) if available else np.nan,
                "staleness_hours": staleness,
                "available": bool(available),
            }
        )
    return pd.DataFrame(rows, index=target, columns=["mark_close", "staleness_hours", "available"])


def basis_daily_return(
    *,
    spot_close: pd.DataFrame,
    perp_close: pd.DataFrame,
    funding: pd.DataFrame,
    positions: pd.DataFrame,
) -> pd.DataFrame:
    """Return two-leg basis and funding PnL for each supplied position."""
    common_index = spot_close.index.intersection(perp_close.index).intersection(funding.index).intersection(positions.index)
    common_assets = spot_close.columns.intersection(perp_close.columns).intersection(funding.columns).intersection(positions.columns)
    if len(common_index) == 0 or len(common_assets) == 0:
        raise ValueError("basis inputs have no common sample")
    spot = spot_close.loc[common_index, common_assets]
    perp = perp_close.loc[common_index, common_assets]
    carry = funding.loc[common_index, common_assets]
    weights = positions.loc[common_index, common_assets]
    if any(frame.isna().to_numpy().any() for frame in (spot, perp, carry, weights)):
        raise ValueError("basis inputs contain missing values")
    spot_returns = spot.pct_change(fill_method=None).fillna(0.0)
    perp_returns = perp.pct_change(fill_method=None).fillna(0.0)
    basis = (weights * (spot_returns - perp_returns)).sum(axis=1)
    carry_pnl = (weights * carry).sum(axis=1)
    return pd.DataFrame(
        {
            "basis_pnl": basis,
            "funding_pnl": carry_pnl,
            "daily_return": basis + carry_pnl,
        },
        index=common_index,
    )


def turnover_from_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """One-way turnover by asset, including initial entry and final exit."""
    turnover = positions.diff().abs()
    if not turnover.empty:
        turnover.iloc[0] = positions.iloc[0].abs()
        turnover.iloc[-1] += positions.iloc[-1].abs()
    return turnover.fillna(0.0)


def turnover_cost(positions: pd.DataFrame, *, cost_bps: float) -> pd.Series:
    """Cost for both spot and perp legs, including entry and final exit."""
    if not np.isfinite(cost_bps) or cost_bps < 0.0:
        raise ValueError("cost_bps must be finite and non-negative")
    return (
        turnover_from_positions(positions).sum(axis=1)
        * float(LEGS_PER_ASSET)
        * float(cost_bps)
        / 10_000.0
    ).rename("cost")


def funding_proxy_match(*, proxy: float, exact: float) -> bool:
    """Require the exact funding subset to have the same sign and be within 50%."""
    if not np.isfinite(proxy) or not np.isfinite(exact):
        return False
    if proxy == 0.0:
        return exact == 0.0
    if np.sign(proxy) != np.sign(exact):
        return False
    return abs(exact - proxy) / abs(proxy) <= 0.50 + 1e-12


def classify_same_venue_basis(
    *,
    metrics: Mapping[str, float],
    yearly_returns: pd.Series,
    asset_net_pnl: pd.Series,
    funding_pnl: float,
    basis_pnl: float,
    coverage_ok: bool,
    proxy_match: bool,
) -> str:
    """Apply the frozen LS100 gates and return the research classification."""
    required = (
        "full_multiple_10bps",
        "full_sharpe_10bps",
        "full_mdd_10bps",
        "full_multiple_20bps",
        "validation_multiple_10bps",
        "validation_sharpe_10bps",
    )
    if not coverage_ok:
        return "partial"
    if not proxy_match:
        return "funding-proxy-mismatch"
    values = [float(metrics.get(key, np.nan)) for key in required]
    if not all(np.isfinite(value) for value in values):
        return "fail"
    full_multiple_10, full_sharpe_10, full_mdd_10, full_multiple_20, validation_multiple_10, validation_sharpe_10 = values
    if (
        full_multiple_10 <= 0.0
        or full_multiple_20 <= 0.0
        or validation_multiple_10 <= 0.0
        or full_sharpe_10 <= 1.0
        or validation_sharpe_10 <= 0.0
        or full_mdd_10 < -0.05
    ):
        return "fail"
    if len(yearly_returns) < 4 or int((yearly_returns > 0.0).sum()) < 4:
        return "fail"
    total_assets = float(asset_net_pnl.sum())
    if total_assets <= 0.0 or float(asset_net_pnl.max()) / total_assets > 0.70:
        return "asset-concentrated"
    total_years = float(yearly_returns.sum())
    if total_years <= 0.0 or float(yearly_returns.max()) / total_years > 0.70:
        return "year-concentrated"
    if funding_pnl <= 0.0 or basis_pnl > funding_pnl:
        return "basis-dominated"
    return "pass"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError(f"{path}: empty CSV")
    return frame


def load_spot_close(path: Path) -> pd.Series:
    frame = _read_csv(path)
    if not {"open_time", "close"}.issubset(frame.columns):
        raise ValueError(f"{path}: expected open_time and close")
    open_time = pd.to_datetime(frame["open_time"], utc=True)
    close = pd.to_numeric(frame["close"], errors="coerce")
    values = pd.Series(close.to_numpy(dtype=float), index=pd.DatetimeIndex(open_time) + pd.Timedelta(days=1))
    values = values.sort_index()
    if values.index.duplicated().any() or values.isna().any() or not np.isfinite(values.to_numpy()).all():
        raise ValueError(f"{path}: invalid spot close series")
    return values.astype(float)


def load_mark_frame(path: Path) -> pd.DataFrame:
    frame = _read_csv(path)
    if not {"open_time", "close"}.issubset(frame.columns):
        raise ValueError(f"{path}: expected open_time and close")
    return frame.loc[:, ["open_time", "close"]].copy()


def load_funding_daily(
    path: Path,
    *,
    target_index: pd.DatetimeIndex,
    source: str,
) -> pd.Series:
    frame = _read_csv(path)
    if source == "binance":
        time_column, rate_column = "calc_time", "last_funding_rate"
    elif source == "bitget":
        time_column, rate_column = "funding_time", "funding_rate"
    else:
        raise ValueError(f"unknown funding source: {source}")
    if not {time_column, rate_column}.issubset(frame.columns):
        raise ValueError(f"{path}: missing funding columns")
    if source == "binance":
        dates = pd.to_datetime(pd.to_numeric(frame[time_column], errors="coerce"), unit="ms", utc=True)
    else:
        dates = pd.to_datetime(frame[time_column], utc=True, errors="coerce")
    values = pd.to_numeric(frame[rate_column], errors="coerce")
    if dates.isna().any() or values.isna().any():
        raise ValueError(f"{path}: invalid funding rows")
    settlements = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates).normalize())
    required_dates = pd.DatetimeIndex(pd.to_datetime(target_index, utc=True)).normalize() - pd.Timedelta(days=1)
    settlements = settlements.loc[settlements.index.isin(required_dates)]
    counts = settlements.groupby(level=0).size()
    bad = counts[~counts.eq(3)]
    if not bad.empty:
        raise ValueError(f"{path}: funding days without exactly 3 settlements: {bad.index[:5].tolist()}")
    daily = settlements.groupby(level=0).sum().sort_index()
    # A daily close at 00:00 uses the funding settlements from the prior day.
    daily.index = daily.index + pd.Timedelta(days=1)
    result = daily.reindex(target_index)
    if result.isna().any():
        missing = result.index[result.isna()][:5].tolist()
        raise ValueError(f"{path}: missing funding on target dates: {missing}")
    return result.astype(float)


def _sample_metrics(series: pd.Series, *, validation: bool = False) -> dict[str, float]:
    segment = series.loc[
        (series.index >= (VALIDATION_START if validation else START))
        & (series.index <= END)
    ]
    if segment.empty:
        raise ValueError("requested sample is empty")
    return {key: float(value) for key, value in _metrics_from_returns(segment).items()}


def _asset_summary(
    *,
    spot_close: pd.DataFrame,
    perp_close: pd.DataFrame,
    funding: pd.DataFrame,
    positions: pd.DataFrame,
    cost_bps: float,
) -> pd.DataFrame:
    spot_returns = spot_close.pct_change(fill_method=None).fillna(0.0)
    perp_returns = perp_close.pct_change(fill_method=None).fillna(0.0)
    basis = positions * (spot_returns - perp_returns)
    carry = positions * funding
    costs = (
        turnover_from_positions(positions)
        * float(LEGS_PER_ASSET)
        * float(cost_bps)
        / 10_000.0
    )
    result = pd.DataFrame(
        {
            "asset": list(positions.columns),
            "basis_pnl": basis.sum().to_numpy(),
            "funding_pnl": carry.sum().to_numpy(),
            "costs": costs.sum().to_numpy(),
        }
    )
    result["net_pnl"] = result["basis_pnl"] + result["funding_pnl"] - result["costs"]
    return result.sort_values("net_pnl", ascending=False).reset_index(drop=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(
    *,
    summary: pd.DataFrame,
    yearly: pd.DataFrame,
    assets: pd.DataFrame,
    funding_reconciliation: pd.DataFrame,
    coverage: Mapping[str, Any],
    classification: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    exact_funding_window: str,
) -> str:
    decision = {
        "pass": "PASS (research proxy only; not live approval)",
        "partial": "PARTIAL (coverage gate not met; not live approval)",
        "funding-proxy-mismatch": "FAIL (funding proxy mismatch)",
        "asset-concentrated": "FAIL (asset concentration)",
        "year-concentrated": "FAIL (year concentration)",
        "basis-dominated": "FAIL (not funding-dominated)",
        "fail": "FAIL",
    }[classification]
    lines = [
        f"# {TRIAL_ID}",
        "",
        "LS100 is a Bitget same-venue price proxy for a long-spot / short-perp BTC/ETH basis",
        "sleeve. Full-history funding is still a Binance proxy; exact Bitget funding is only",
        "reconciled on the recent overlap. It is not a live signal and sends no orders.",
        "",
        f"- Sample: {start} → {end} ({coverage['rows']} usable daily observations)",
        "- Structure: per asset spot 0.25x NAV + perp short 0.25x NAV; portfolio gross 1.00x",
        "- Cost: 10bps per leg per side primary; 20bps stress",
        f"- Mark coverage: {coverage['mark_coverage']:.2%}; max staleness {coverage['max_staleness_hours']:.2f}h",
        f"- Spot coverage continuous: {coverage['spot_continuous']}",
        f"- Exact Bitget funding reconciliation: {exact_funding_window}",
        "",
        "## Variant summary",
        "",
        dataframe_to_markdown(summary),
        "",
        "## Yearly returns (always-on, 10bps)",
        "",
        dataframe_to_markdown(yearly),
        "",
        "## Asset attribution (always-on, 10bps)",
        "",
        dataframe_to_markdown(assets),
        "",
        "## Funding reconciliation",
        "",
        dataframe_to_markdown(funding_reconciliation),
        "",
        "## Decision",
        "",
        f"**{decision}**",
        "",
        "The exact-Bitget funding window is too short to backfill full history. A pass only",
        "earns a same-venue execution, funding, margin and small-order study; it does not",
        "change `PR2026-10-D-L125-V2`.",
        "",
        "Research output only; no orders sent.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--spot-dir", type=Path, default=DEFAULT_SPOT_DIR)
    parser.add_argument("--perp-dir", type=Path, default=DEFAULT_PERP_DIR)
    parser.add_argument("--binance-funding-dir", type=Path, default=DEFAULT_BINANCE_FUNDING_DIR)
    parser.add_argument("--bitget-funding-dir", type=Path, default=DEFAULT_BITGET_FUNDING_DIR)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    target_index = pd.date_range(START, END, freq="D", tz="UTC")
    spot_close = {}
    spot_coverage: dict[str, Any] = {}
    mark_frames = {}
    for asset in ASSETS:
        symbol = SYMBOLS[asset]
        spot = load_spot_close(args.spot_dir / f"{symbol}_1Dutc.csv")
        spot = spot.loc[(spot.index >= START) & (spot.index <= END)]
        if not spot.index.equals(target_index):
            raise ValueError(f"{asset}: spot dates do not match the frozen sample")
        spot_close[asset] = spot
        spot_coverage[asset] = audit_daily_coverage(pd.DatetimeIndex(spot.index))
        mark_frames[asset] = load_mark_frame(args.perp_dir / f"{symbol}_mark.csv")
    spot_frame = pd.DataFrame(spot_close).sort_index()

    mark_alignments = {
        asset: align_perp_mark(
            mark_frames[asset],
            target_index,
            max_staleness_hours=MAX_MARK_STALENESS_HOURS,
        )
        for asset in ASSETS
    }
    mark_available = pd.concat(
        [mark_alignments[asset]["available"].rename(asset) for asset in ASSETS],
        axis=1,
    ).all(axis=1)
    usable_index = target_index[mark_available]
    if len(usable_index) / len(target_index) < 0.95:
        raise ValueError("mark coverage below the frozen 95% floor")
    all_staleness = pd.concat(
        [mark_alignments[asset]["staleness_hours"].rename(asset) for asset in ASSETS],
        axis=1,
    ).loc[usable_index]
    mark_coverage = float(mark_available.mean())
    max_staleness = float(all_staleness.max().max())
    spot_frame = spot_frame.reindex(usable_index)
    perp_close = pd.DataFrame(
        {
            asset: mark_alignments[asset]["mark_close"].loc[usable_index]
            for asset in ASSETS
        }
    )

    funding = pd.DataFrame(
        {
            asset: load_funding_daily(
                args.binance_funding_dir / f"{asset}.csv",
                target_index=usable_index,
                source="binance",
            )
            for asset in ASSETS
        }
    )
    positions = pd.DataFrame(NOTIONAL_PER_LEG, index=usable_index, columns=ASSETS)
    pnl = basis_daily_return(
        spot_close=spot_frame,
        perp_close=perp_close,
        funding=funding,
        positions=positions,
    )

    summary_rows: list[dict[str, Any]] = []
    variants: dict[str, pd.DataFrame] = {
        "always-on": positions,
        "btc-only": pd.DataFrame({"bitcoin": NOTIONAL_PER_LEG}, index=usable_index),
        "eth-only": pd.DataFrame({"ethereum": NOTIONAL_PER_LEG}, index=usable_index),
    }
    for name, variant_positions in variants.items():
        assets = list(variant_positions.columns)
        variant_pnl = basis_daily_return(
            spot_close=spot_frame[assets],
            perp_close=perp_close[assets],
            funding=funding[assets],
            positions=variant_positions[assets],
        )
        for cost in COSTS_BPS:
            net = variant_pnl["daily_return"] - turnover_cost(
                variant_positions[assets], cost_bps=cost
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
                    "mean_gross": float(LEGS_PER_ASSET * variant_positions[assets].abs().sum(axis=1).mean()),
                    "turnover": float(turnover_from_positions(variant_positions[assets]).sum().sum()),
                }
            )
    summary = pd.DataFrame(summary_rows)
    primary = summary.loc[
        (summary["variant"] == "always-on")
        & np.isclose(summary["cost_bps"], PRIMARY_COST_BPS)
    ].iloc[0]
    stress = summary.loc[
        (summary["variant"] == "always-on")
        & np.isclose(summary["cost_bps"], 20.0)
    ].iloc[0]
    validation = _sample_metrics(
        pnl["daily_return"] - turnover_cost(positions, cost_bps=PRIMARY_COST_BPS),
        validation=True,
    )
    metrics = {
        "full_multiple_10bps": float(primary["full_multiple"]),
        "full_sharpe_10bps": float(primary["full_sharpe"]),
        "full_mdd_10bps": float(primary["full_max_drawdown"]),
        "full_multiple_20bps": float(stress["full_multiple"]),
        "validation_multiple_10bps": float(validation["multiple"]),
        "validation_sharpe_10bps": float(validation["sharpe"]),
    }
    net_primary = pnl["daily_return"] - turnover_cost(positions, cost_bps=PRIMARY_COST_BPS)
    yearly_returns = (
        net_primary.groupby(net_primary.index.year)
        .apply(lambda values: float((1.0 + values).prod() - 1.0))
    )
    yearly = pd.DataFrame(
        {
            "year": yearly_returns.index.astype(int),
            "return": yearly_returns.to_numpy(dtype=float),
            "net_pnl": net_primary.groupby(net_primary.index.year).sum().to_numpy(dtype=float),
        }
    )
    assets = _asset_summary(
        spot_close=spot_frame,
        perp_close=perp_close,
        funding=funding,
        positions=positions,
        cost_bps=PRIMARY_COST_BPS,
    )

    # The first two exact Bitget dates are partial (the feed starts at 08:00),
    # so use the first full-settlement close for the reconciliation window.
    exact_start = max(usable_index.min(), EXACT_FUNDING_START + pd.Timedelta(days=2))
    exact_index = usable_index[usable_index >= exact_start]
    exact_funding = pd.DataFrame(
        {
            asset: load_funding_daily(
                args.bitget_funding_dir / f"{asset}.csv",
                target_index=exact_index,
                source="bitget",
            )
            for asset in ASSETS
        }
    )
    reconciliation_rows: list[dict[str, Any]] = []
    for asset in ASSETS:
        proxy_value = float(funding.loc[exact_index, asset].sum())
        exact_value = float(exact_funding[asset].sum())
        match = funding_proxy_match(proxy=proxy_value, exact=exact_value)
        reconciliation_rows.append(
            {
                "asset": asset,
                "proxy_funding_pnl": proxy_value,
                "exact_funding_pnl": exact_value,
                "relative_difference": abs(exact_value - proxy_value) / abs(proxy_value) if proxy_value else np.inf,
                "match": match,
            }
        )
    funding_reconciliation = pd.DataFrame(reconciliation_rows)
    proxy_match = bool(funding_reconciliation["match"].all())

    coverage_ok = (
        all(bool(audit["is_continuous"]) for audit in spot_coverage.values())
        and mark_coverage >= 0.95
        and max_staleness <= MAX_MARK_STALENESS_HOURS
    )
    classification = classify_same_venue_basis(
        metrics=metrics,
        yearly_returns=yearly_returns,
        asset_net_pnl=assets.set_index("asset")["net_pnl"],
        funding_pnl=float(assets["funding_pnl"].sum()),
        basis_pnl=float(assets["basis_pnl"].sum()),
        coverage_ok=coverage_ok,
        proxy_match=proxy_match,
    )
    coverage = {
        "rows": int(len(usable_index)),
        "spot_continuous": all(bool(audit["is_continuous"]) for audit in spot_coverage.values()),
        "mark_coverage": mark_coverage,
        "max_staleness_hours": max_staleness,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "summary": output_dir / "variant_summary.csv",
        "yearly": output_dir / "yearly.csv",
        "assets": output_dir / "asset_summary.csv",
        "reconciliation": output_dir / "funding_reconciliation.csv",
        "daily": output_dir / "daily_returns.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")
    summary.to_csv(files["summary"], index=False)
    yearly.to_csv(files["yearly"], index=False)
    assets.to_csv(files["assets"], index=False)
    funding_reconciliation.to_csv(files["reconciliation"], index=False)
    daily = pnl.copy()
    daily["turnover_cost_10bps"] = turnover_cost(positions, cost_bps=PRIMARY_COST_BPS)
    daily["net_return_10bps"] = net_primary
    daily["gross_exposure"] = LEGS_PER_ASSET * positions.abs().sum(axis=1)
    daily.to_csv(files["daily"], index_label="date")
    files["report"].write_text(
        _report(
            summary=summary,
            yearly=yearly,
            assets=assets,
            funding_reconciliation=funding_reconciliation,
            coverage=coverage,
            classification=classification,
            start=usable_index.min(),
            end=usable_index.max(),
            exact_funding_window=f"{exact_index.min()} → {exact_index.max()}",
        ),
        encoding="utf-8",
    )
    manifest = {
        "trial_id": TRIAL_ID,
        "classification": classification,
        "start": str(usable_index.min()),
        "end": str(usable_index.max()),
        "rows": int(len(usable_index)),
        "notional_per_leg": NOTIONAL_PER_LEG,
        "legs_per_asset": LEGS_PER_ASSET,
        "total_gross": float(LEGS_PER_ASSET * len(ASSETS) * NOTIONAL_PER_LEG),
        "costs_bps": list(COSTS_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "mark_staleness_hours_max": MAX_MARK_STALENESS_HOURS,
        "coverage": coverage,
        "metrics": metrics,
        "proxy_match": proxy_match,
        "exact_funding_window": {
            "start": str(exact_index.min()),
            "end": str(exact_index.max()),
        },
        "funding_sources": {"full": "Binance proxy", "reconciliation": "Bitget exact"},
        "spot_dir": str(args.spot_dir),
        "perp_dir": str(args.perp_dir),
        "binance_funding_dir": str(args.binance_funding_dir),
        "bitget_funding_dir": str(args.bitget_funding_dir),
        "spot_files": {
            asset: _sha256(args.spot_dir / f"{SYMBOLS[asset]}_1Dutc.csv") for asset in ASSETS
        },
        "perp_files": {
            asset: _sha256(args.perp_dir / f"{SYMBOLS[asset]}_mark.csv") for asset in ASSETS
        },
        "orders_sent": False,
    }
    files["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"classification: {classification}")
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()
