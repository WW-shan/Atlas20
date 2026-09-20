"""Compare Sector-Lead V3 top1 against three research-backed overlays.

Published crypto evidence (see the module docstrings in atlas20.signals.risk)
suggests three improvements over a plain relative-strength rotation:

* A. absolute (time-series) trend filter  - buy only assets above their own MA
* B. volatility targeting                 - size the position by 1/realized vol
* C. volatility-scaled trailing stop      - Chandelier-style BTC exit band

This script isolates each one on the same point-in-time universe, then reports
return / CAGR / Sharpe / max-drawdown against a BTC buy-and-hold yardstick.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.analytics.metrics import compute_summary_metrics  # noqa: E402
from atlas20.backtest.calendar import get_rebalance_dates  # noqa: E402
from atlas20.backtest.engine import run_backtest  # noqa: E402
from atlas20.config import FrictionConfig, load_config, load_sector_config  # noqa: E402
from atlas20.data.processor import build_processed_datasets  # noqa: E402
from atlas20.logging_utils import configure_logging  # noqa: E402
from atlas20.signals.regime import build_regime_frame  # noqa: E402
from atlas20.signals.risk import (  # noqa: E402
    absolute_trend_mask,
    btc_above_volatility_scaled_trailing,
    volatility_target_leverage,
)
from atlas20.strategies.overlays import apply_daily_risk_overlay  # noqa: E402
from atlas20.strategies.sector_lead_v3 import build_sector_lead_v3_targets  # noqa: E402
from atlas20.universe.builder import (  # noqa: E402
    MarketDataBundle,
    build_rebalance_universe,
    prepare_market_data,
)


def _sector_by_coin(market: MarketDataBundle) -> pd.Series:
    return market.metadata["sector"]


def _apply_trend_filter(
    base_targets: dict[pd.Timestamp, pd.Series],
    trend_mask: pd.DataFrame,
) -> dict[pd.Timestamp, pd.Series]:
    """Drop any selected coin that is not above its own moving average."""
    out: dict[pd.Timestamp, pd.Series] = {}
    for date, target in base_targets.items():
        if target.empty:
            out[date] = target
            continue
        ts = pd.Timestamp(date)
        keep = []
        for coin, weight in target.items():
            above = False
            if coin in trend_mask.columns and ts in trend_mask.index:
                above = bool(trend_mask.loc[ts, coin])
            if above:
                keep.append((coin, weight))
        if not keep:
            out[date] = pd.Series(dtype=float)
            continue
        # Re-normalize so a surviving pick still sums to the same gross exposure.
        total = sum(w for _, w in keep)
        out[date] = pd.Series({c: w / total for c, w in keep})
    return out


def _leverage_for_targets(
    base_targets: dict[pd.Timestamp, pd.Series],
    leverage_grid: pd.DataFrame,
    target_volatility: float,
    max_leverage: float,
) -> dict[pd.Timestamp, float]:
    """Per-rebalance leverage = target vol / realized vol of the held basket."""
    out: dict[pd.Timestamp, float] = {}
    for date, target in base_targets.items():
        ts = pd.Timestamp(date)
        if target.empty or ts not in leverage_grid.index:
            out[ts] = 0.0
            continue
        weights = target[target > 0]
        if weights.empty:
            out[ts] = 0.0
            continue
        levs = []
        for coin in weights.index:
            if coin in leverage_grid.columns:
                value = leverage_grid.loc[ts, coin]
                if pd.notna(value):
                    levs.append(float(value))
        if not levs:
            out[ts] = 1.0
            continue
        basket = sum(levs) / len(levs)
        out[ts] = min(basket, max_leverage)
    return out


def _friction_for_lane(config, max_weight_per_coin: float) -> FrictionConfig:
    """Friction config for the concentrated lane.

    ``max_weight_per_coin`` is a diversification limit: when it binds, the
    engine trims the pick and parks the residual in cash. That is the right
    default for a 20-name book, but this lane is *deliberately* concentrated -
    the whole thesis is one high-beta leader - so it defaults to an uncapped
    1.0 and must ask for a cap explicitly if it ever wants one.
    """
    friction = config.frictions.model_copy(deep=True)
    friction.max_weight_per_coin = float(max_weight_per_coin)
    return friction


def _run(
    name: str,
    market: MarketDataBundle,
    targets: dict[pd.Timestamp, pd.Series],
    config,
    *,
    leverage_by_date: dict[pd.Timestamp, float] | None = None,
    max_weight_per_coin: float = 1.0,
):
    return run_backtest(
        name=name,
        asset_returns=market.returns.loc[config.start_timestamp : config.end_timestamp],
        rebalance_targets=targets,
        sector_by_coin=_sector_by_coin(market),
        friction=_friction_for_lane(config, max_weight_per_coin),
        initial_capital=config.initial_capital,
        gross_target_exposure=1.0,
        leverage_by_date=leverage_by_date,
    )


def _btc_buy_hold(market: MarketDataBundle, config) -> float:
    btc = market.price["bitcoin"].loc[config.start_timestamp : config.end_timestamp]
    return float(btc.iloc[-1] / btc.iloc[0] - 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sector-Lead V3 overlay comparison.")
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--frequency", default="14D")
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--liquidity", default="loose")
    parser.add_argument("--ma-window", type=int, default=100)
    parser.add_argument("--target-vol", type=float, default=0.60)
    parser.add_argument("--vol-window", type=int, default=30)
    parser.add_argument("--max-leverage", type=float, default=1.5)
    parser.add_argument("--regime", default="bull_only", choices=["bull_only", "always_on"])
    parser.add_argument("--risk-off", default="cash", choices=["cash", "btc"])
    parser.add_argument("--stop-lookback", type=int, default=30)
    parser.add_argument("--stop-vol-multiple", type=float, default=2.0)
    parser.add_argument(
        "--max-weight-per-coin",
        type=float,
        default=1.0,
        help="Per-coin cap for this concentrated lane; 1.0 means a single pick may be a full position.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    panel, metadata = build_processed_datasets(config, sector_config)
    market = prepare_market_data(panel, metadata, config)

    rebalance_dates = get_rebalance_dates(
        market.price.index, config.start_timestamp, args.frequency, args.frequency
    )
    universe = build_rebalance_universe(market, rebalance_dates, config)

    regime = build_regime_frame(market.price, market.market_cap, config)
    base = build_sector_lead_v3_targets(
        market,
        universe,
        regime,
        config,
        top_k=args.top_k,
        frequency=args.frequency,
        regime_mode=args.regime,
    ).targets
    parked = None if args.risk_off == "cash" else pd.Series({"bitcoin": 1.0})

    trend_mask = absolute_trend_mask(market.price, args.ma_window)
    trend_targets = _apply_trend_filter(base, trend_mask)

    leverage_grid = volatility_target_leverage(
        market.price, target_volatility=args.target_vol,
        window=args.vol_window, max_leverage=args.max_leverage,
    )
    lev_base = _leverage_for_targets(base, leverage_grid, args.target_vol, args.max_leverage)
    lev_trend = _leverage_for_targets(trend_targets, leverage_grid, args.target_vol, args.max_leverage)

    risk_on = btc_above_volatility_scaled_trailing(
        market.price,
        lookback=args.stop_lookback,
        vol_window=args.vol_window,
        vol_multiple=args.stop_vol_multiple,
        confirm_days=1,
    )
    stop_targets = apply_daily_risk_overlay(base, risk_on, risk_off_target=parked)
    stop_trend_targets = apply_daily_risk_overlay(trend_targets, risk_on, risk_off_target=parked)

    variants = {
        "S1_baseline_top1": (base, None),
        "S2_+trend_filter": (trend_targets, None),
        "S3_+vol_target": (base, lev_base),
        "S4_+vol_target+trend": (trend_targets, lev_trend),
        "S5_+vol_stop": (stop_targets, None),
        "S6_all_three": (stop_trend_targets, lev_trend),
    }

    rows = []
    for name, (targets, lev) in variants.items():
        result = _run(
            name,
            market,
            targets,
            config,
            leverage_by_date=lev,
            max_weight_per_coin=args.max_weight_per_coin,
        )
        metrics = compute_summary_metrics(result, config.annualization_days)
        rows.append(
            {
                "variant": name,
                "total_return": float(metrics["total_return"]),
                "cagr": float(metrics["cagr"]),
                "sharpe": float(metrics["sharpe"]),
                "max_drawdown": float(metrics["max_drawdown"]),
                "annualized_volatility": float(metrics["annualized_volatility"]),
            }
        )

    btc_return = _btc_buy_hold(market, config)
    table = pd.DataFrame(rows).sort_values("total_return", ascending=False)
    table["beats_btc"] = table["total_return"] > btc_return

    pd.set_option("display.width", 200)
    print(f"\nWindow: {config.start_timestamp.date()} -> {config.end_timestamp.date()}")
    print(f"BTC buy&hold total return: {btc_return:.4f} ({btc_return * 100:.1f}%)")
    print(f"Universe: sector_lead top{args.top_k} {args.frequency} liquidity={args.liquidity} "
          f"gate={config.universe.min_turnover_ratio} regime={args.regime} "
          f"risk_off={args.risk_off}")
    print(f"Bull days: {int(regime['bull'].sum())}/{len(regime)}")
    print()
    print(table.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))


if __name__ == "__main__":
    main()
