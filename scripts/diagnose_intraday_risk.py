"""Diagnose intraday risk overlays on the frozen H5 book.

This is a diagnostic, not a pre-registered strategy trial.  It asks whether an
hourly exit can improve the frozen specification without changing selection,
ranking, or the long-only spot constraints.  The two families are:

* a portfolio price stop, fixed from the day's prior close or trailing from
  the intraday high;
* the already-used BTC 100-day moving-average gate, moved from two daily
  closes to two hourly closes.

The simulator keeps cash as a residual, executes a target one hour after the
hourly close that emitted a signal, and charges the same per-unit one-way cost
as the production engine.  Missing hourly asset-days are filled geometrically
from the daily close return and counted separately; that is a diagnostic
assumption, not a production data policy.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Literal

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.backtest.intraday import load_hourly_bars, pre_fill_returns  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.reporting.report import dataframe_to_markdown  # noqa: E402

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402
from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id  # noqa: E402
from scripts.run_strategy_evidence_audit import _metrics_from_returns  # noqa: E402

OverlayKind = Literal[
    "baseline",
    "fast_gate_roundtrip",
    "fast_gate_slow_reentry",
    "fixed_stop",
    "trailing_stop",
]


@dataclass(frozen=True)
class HourlyRiskOverlay:
    kind: OverlayKind
    threshold: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {
            "baseline",
            "fast_gate_roundtrip",
            "fast_gate_slow_reentry",
            "fixed_stop",
            "trailing_stop",
        }:
            raise ValueError(f"unknown hourly risk overlay {self.kind!r}")
        if self.kind in {"fixed_stop", "trailing_stop"}:
            if self.threshold is None or not 0.0 < self.threshold < 1.0:
                raise ValueError("stop overlays require a threshold in (0, 1)")
        elif self.threshold is not None:
            raise ValueError("threshold is only valid for stop overlays")


@dataclass
class HourlyRiskResult:
    daily_returns: pd.Series
    events: pd.DataFrame
    observed: pd.DataFrame


def _as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _day_key(value: object) -> pd.Timestamp:
    return _as_utc(value).normalize()


def _naive_day_index(values: object) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(values)
    return index.tz_localize(None) if index.tz is not None else index


def build_hourly_return_panel(
    daily_returns: pd.DataFrame,
    hourly_returns: pd.DataFrame,
    days: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the hourly panel plus a daily coverage mask.

    An asset-day whose 24 hourly returns are not all present uses the observed
    daily close-to-close return, spread geometrically over the 24 hours.  The
    total daily return therefore remains exact while the intraday path is
    explicitly an interpolation.
    """
    if hourly_returns.empty:
        raise ValueError("hourly_returns must not be empty")
    panel = hourly_returns.copy()
    panel.index = pd.DatetimeIndex([_as_utc(value) for value in panel.index])
    panel = panel.sort_index()
    daily = daily_returns.copy()
    daily.index = pd.DatetimeIndex([_day_key(value) for value in daily.index])
    observed = pd.DataFrame(
        False,
        index=pd.DatetimeIndex([_day_key(value) for value in days]),
        columns=daily.columns,
    )
    result = panel.copy()
    for raw_day in days:
        day = _day_key(raw_day)
        day_hours = pd.date_range(day, periods=24, freq="h", tz="UTC")
        for asset in daily.columns:
            if asset not in panel.columns:
                result[asset] = np.nan
                panel[asset] = np.nan
            values = pd.to_numeric(panel[asset].reindex(day_hours), errors="coerce")
            if values.notna().all():
                observed.at[day, asset] = True
                continue
            daily_value = pd.to_numeric(pd.Series([daily.at[day, asset]]), errors="coerce").iloc[0]
            if pd.isna(daily_value):
                daily_value = 0.0
            daily_value = max(float(daily_value), -0.999999)
            step = (1.0 + daily_value) ** (1.0 / 24.0) - 1.0
            result.loc[day_hours, asset] = step
    return result, observed


def _apply_target(
    weights: np.ndarray,
    target: np.ndarray,
    *,
    fee_rate: float,
    day_return: float,
) -> tuple[np.ndarray, float, float]:
    target = np.clip(np.nan_to_num(target.astype(float)), 0.0, None)
    gross = float(target.sum())
    if gross > 1.0:
        target = target / gross
    turnover = float(np.abs(target - weights).sum())
    cost = turnover * fee_rate
    return target, day_return * (1.0 - cost), turnover


def run_hourly_simulation(
    targets: pd.DataFrame,
    hourly_returns: pd.DataFrame,
    above_sma: pd.Series,
    days: pd.DatetimeIndex,
    *,
    cost_bps: float = 20.0,
    overlay: HourlyRiskOverlay | None = None,
) -> HourlyRiskResult:
    """Run one hourly diagnostic path for a daily target schedule.

    ``targets`` is indexed by signal day and is executed at 01:00 UTC on the
    following day.  ``above_sma`` is the hourly BTC state known at each hourly
    close.  Gate/stop decisions made at an hourly close execute one hour later.
    """
    overlay = overlay or HourlyRiskOverlay("baseline")
    if cost_bps < 0.0:
        raise ValueError("cost_bps must be non-negative")
    if not 0.0 <= cost_bps:
        raise ValueError("cost_bps must be non-negative")
    if hourly_returns.empty:
        raise ValueError("hourly_returns must not be empty")
    if above_sma.empty:
        raise ValueError("above_sma must not be empty")
    panel = hourly_returns.copy()
    panel.index = pd.DatetimeIndex([_as_utc(value) for value in panel.index])
    panel = panel.sort_index()
    state = above_sma.copy()
    state.index = pd.DatetimeIndex([_as_utc(value) for value in state.index])
    state = state.sort_index()
    target_frame = targets.copy()
    target_frame.index = pd.DatetimeIndex([_day_key(value) for value in target_frame.index])
    target_rows = {pd.Timestamp(index): row.astype(float) for index, row in target_frame.iterrows()}
    assets = list(panel.columns)
    weights = np.zeros(len(assets))
    latest_target = np.zeros(len(assets))
    fee_rate = float(cost_bps) / 10_000.0
    risk_on = True
    pending: bool | None = None
    pending_reason: str | None = None
    below_count = 0
    above_count = 0
    daily_returns: list[float] = []
    events: list[dict[str, object]] = []

    for raw_day in days:
        day = _day_key(raw_day)
        day_hours = pd.date_range(day, periods=24, freq="h", tz="UTC")
        day_equity = 1.0
        day_high = 1.0
        signal_day = day - pd.Timedelta(days=1)
        target_event_row = target_rows.get(signal_day)
        for hour in day_hours:
            if hour not in panel.index:
                raise ValueError(f"missing hourly row at {hour}")
            hourly_return = pd.to_numeric(panel.loc[hour], errors="coerce").fillna(0.0).to_numpy(float)
            gross_return = float(weights @ hourly_return)
            gross_return = max(gross_return, -1.0)
            weights = np.nan_to_num(weights * (1.0 + hourly_return) / (1.0 + gross_return))
            day_equity *= 1.0 + gross_return
            day_high = max(day_high, day_equity)

            target_event = hour.hour == 1 and target_event_row is not None
            if target_event:
                latest_target = target_event_row.reindex(assets).fillna(0.0).to_numpy(float)
            desired: np.ndarray | None = None
            reason: str | None = None
            if pending is not None:
                risk_on = bool(pending)
                reason = pending_reason
                pending = None
                pending_reason = None
                desired = latest_target if risk_on else np.zeros(len(assets))
                if reason is None:
                    reason = "gate_on" if risk_on else "gate_off"
            if target_event:
                if risk_on:
                    if desired is None or reason is None:
                        reason = "rebalance"
                    desired = latest_target
                elif (
                    overlay.kind
                    in {"fast_gate_slow_reentry", "fixed_stop", "trailing_stop"}
                    and desired is None
                ):
                    risk_on = True
                    desired = latest_target
                    reason = "target_reentry"
            if desired is not None:
                weights, day_equity, turnover = _apply_target(
                    weights,
                    desired,
                    fee_rate=fee_rate,
                    day_return=day_equity,
                )
                events.append(
                    {
                        "timestamp": hour,
                        "reason": reason or "rebalance",
                        "turnover": turnover,
                        "cost": turnover * fee_rate,
                        "risk_on": risk_on,
                    }
                )

            above_now = bool(state.get(hour, False))
            if overlay.kind == "fast_gate_roundtrip":
                if above_now:
                    above_count += 1
                    below_count = 0
                else:
                    below_count += 1
                    above_count = 0
                if risk_on and below_count >= 2:
                    pending = False
                    pending_reason = "gate_off"
                    below_count = 0
                elif not risk_on and above_count >= 2:
                    pending = True
                    pending_reason = "gate_on"
                    above_count = 0
            elif overlay.kind == "fast_gate_slow_reentry":
                if risk_on:
                    if above_now:
                        below_count = 0
                    else:
                        below_count += 1
                    if below_count >= 2:
                        pending = False
                        pending_reason = "gate_off"
                        below_count = 0
            elif overlay.kind in {"fixed_stop", "trailing_stop"}:
                if risk_on:
                    assert overlay.threshold is not None
                    if overlay.kind == "fixed_stop":
                        drawdown = day_equity - 1.0
                    else:
                        drawdown = day_equity / day_high - 1.0
                    if drawdown <= -float(overlay.threshold):
                        pending = False
                        pending_reason = (
                            "fixed_stop_off"
                            if overlay.kind == "fixed_stop"
                            else "trailing_stop_off"
                        )
                # Once stopped, only a subsequent target event can re-enter;
                # the event path above deliberately does not reset risk_on.

        daily_returns.append(day_equity - 1.0)

    event_frame = pd.DataFrame(events, columns=["timestamp", "reason", "turnover", "cost", "risk_on"])
    observed = pd.DataFrame(True, index=pd.DatetimeIndex(days), columns=assets)
    return HourlyRiskResult(
        daily_returns=pd.Series(daily_returns, index=pd.DatetimeIndex(days), name=overlay.kind),
        events=event_frame,
        observed=observed,
    )


def _metrics_row(name: str, returns: pd.Series) -> dict[str, object]:
    return {"overlay": name, **_metrics_from_returns(returns)}


def _yearly_returns(returns: pd.Series) -> pd.Series:
    return (1.0 + returns).resample("YE").prod() - 1.0


def _hourly_btc_state(
    market,
    index: pd.DatetimeIndex,
    hourly: dict[str, pd.DataFrame],
    days: pd.DatetimeIndex,
) -> pd.Series:
    btc = hourly["bitcoin"].set_index("open_time")
    closes = pd.Series(
        pd.to_numeric(btc["close"], errors="coerce").to_numpy(),
        index=pd.DatetimeIndex(pd.to_datetime(btc.index, utc=True)),
    ).sort_index()
    daily_close = market.raw_price["bitcoin"].reindex(index).astype(float)
    sma = daily_close.rolling(100, min_periods=100).mean().shift(1)
    hours = pd.date_range(days[0], periods=len(days) * 24, freq="h", tz="UTC")
    state = pd.Series(False, index=hours)
    for day in days:
        if not np.isfinite(sma.get(day, np.nan)):
            continue
        day_hours = pd.date_range(day, periods=24, freq="h", tz="UTC")
        state.loc[day_hours] = (closes.reindex(day_hours) >= float(sma.loc[day])).to_numpy()
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--hourly-dir", type=Path, default=Path("data/raw/binance_1h"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase_momentum_intraday_risk_diagnostic"))
    args = parser.parse_args()

    configure_logging("ERROR")
    if args.cost_bps < 0.0:
        raise SystemExit("--cost-bps must be non-negative")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    # The hourly feed ends before the exclusive end date; use complete UTC days.
    last_hour = max(
        pd.to_datetime(frame["open_time"], utc=True).max()
        for frame in load_hourly_bars(args.hourly_dir).values()
    )
    last_complete_day = last_hour.tz_convert("UTC").normalize().tz_localize(None)
    days = pd.DatetimeIndex(index[_naive_day_index(index) <= last_complete_day])
    if days.empty:
        raise SystemExit("no complete UTC days overlap the hourly feed")
    built = build_trial(trial_by_id("PR2026-10-H5"), market, universe, index)
    hourly = load_hourly_bars(args.hourly_dir)
    target_assets = sorted(
        {
            str(asset)
            for target in built.targets.values()
            for asset, weight in target.items()
            if abs(float(weight)) > 1e-12
        }
    )
    daily = market.returns.reindex(index=days).reindex(columns=target_assets)
    closes = market.raw_price.reindex(index=index, columns=market.returns.columns)
    prefill = pre_fill_returns(
        market.returns.loc[index],
        hourly,
        fill_hours=1,
        missing_fill="day_close",
        reference_close=closes,
    )
    production = _production_result(
        config,
        market,
        built,
        index,
        cost_bps=args.cost_bps,
        pre_fill=prefill,
    ).daily_returns.reindex(days)
    zero = _production_result(
        config,
        market,
        built,
        index,
        cost_bps=0.0,
        pre_fill=prefill,
    )
    targets = zero.rebalance_targets
    hourly_returns = pd.DataFrame(index=pd.date_range(days[0], days[-1] + pd.Timedelta(hours=23), freq="h", tz="UTC"))
    for asset in target_assets:
        bars = hourly.get(asset)
        if bars is None:
            hourly_returns[asset] = np.nan
            continue
        close = pd.Series(
            pd.to_numeric(bars["close"], errors="coerce").to_numpy(),
            index=pd.DatetimeIndex(pd.to_datetime(bars["open_time"], utc=True)),
        ).sort_index()
        hourly_returns[asset] = close.pct_change().reindex(hourly_returns.index)
    hourly_panel, observed = build_hourly_return_panel(daily, hourly_returns, days)
    state = _hourly_btc_state(market, index, hourly, days)
    target_frame = targets.reindex(columns=target_assets).fillna(0.0)
    overlays = [
        HourlyRiskOverlay("baseline"),
        HourlyRiskOverlay("fast_gate_roundtrip"),
        HourlyRiskOverlay("fast_gate_slow_reentry"),
        *(
            HourlyRiskOverlay("fixed_stop", threshold=threshold)
            for threshold in (0.05, 0.08, 0.10)
        ),
        *(
            HourlyRiskOverlay("trailing_stop", threshold=threshold)
            for threshold in (0.05, 0.08, 0.10)
        ),
    ]
    rows: list[dict[str, object]] = []
    results: dict[str, HourlyRiskResult] = {}
    for overlay in overlays:
        result = run_hourly_simulation(
            target_frame,
            hourly_panel,
            state,
            days,
            cost_bps=args.cost_bps,
            overlay=overlay,
        )
        results[overlay.kind if overlay.threshold is None else f"{overlay.kind}_{int(round(overlay.threshold * 100))}"] = result
        label = overlay.kind if overlay.threshold is None else f"{overlay.kind}_{int(round(overlay.threshold * 100))}"
        rows.append({**_metrics_row(label, result.daily_returns), "events": len(result.events), "turnover": float(result.events["turnover"].sum()) if not result.events.empty else 0.0})
    metrics = pd.DataFrame(rows)
    yearly = pd.DataFrame(
        {label: _yearly_returns(result.daily_returns) for label, result in results.items()}
    )
    output = ensure_dir(args.output_dir)
    metrics.to_csv(output / "summary.csv", index=False)
    yearly.to_csv(output / "yearly_returns.csv", index_label="year")
    observed.to_csv(output / "hourly_coverage.csv")
    for label, result in results.items():
        result.daily_returns.rename(label).to_frame().to_csv(output / f"returns_{label}.csv", index_label="date")
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "trial_id": "PR2026-10-H5",
                "diagnostic_only": True,
                "pre_registered": False,
                "start": str(days[0].date()),
                "end": str(days[-1].date()),
                "cost_bps": float(args.cost_bps),
                "hourly_feed": str(args.hourly_dir),
                "target_assets": target_assets,
                "missing_hourly_policy": "geometric interpolation of the observed daily return",
                "production_anchor": _metrics_from_returns(production),
                "simulated_baseline": _metrics_from_returns(results["baseline"].daily_returns),
                "simulated_baseline_correlation": float(
                    results["baseline"].daily_returns.corr(production)
                ),
                "hourly_observed_share": float(observed.to_numpy().mean()),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Intraday Risk Overlay Diagnostic",
        "",
        "**Diagnostic only.** No rule is promoted, no trial is registered, and the live H5 book is unchanged.",
        "",
        "This screen uses the frozen H5 target schedule and Binance hourly closes. A target from signal day D executes at 01:00 UTC on D+1; any hourly risk signal executes on the next hourly close. Missing hourly asset-days are geometrically interpolated from the daily return and explicitly counted.",
        "",
        f"Coverage: {float(observed.to_numpy().mean()):.2%} of target-asset-days have all 24 hourly returns. The production +1h H5 anchor is shown separately because the hourly simulator is an approximation.",
        "",
        "## Production anchor versus simulated baseline",
        "",
        dataframe_to_markdown(
            pd.DataFrame(
                [
                    {"book": "production +1h", **_metrics_from_returns(production)},
                    {
                        "book": "hourly simulator baseline",
                        **_metrics_from_returns(results["baseline"].daily_returns),
                    },
                ]
            )
        ),
        "",
        "## Summary",
        "",
        dataframe_to_markdown(metrics),
        "",
        "## Yearly returns",
        "",
        dataframe_to_markdown(yearly.rename_axis("year").reset_index()),
        "",
        "## Decision",
        "",
        "None of the intraday overlays is promoted. The diagnostic must be treated as a rejected hypothesis generator, not as evidence for live intraday trading.",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(output), "metric_rows": metrics.to_dict("records")}, indent=2))


if __name__ == "__main__":
    main()
