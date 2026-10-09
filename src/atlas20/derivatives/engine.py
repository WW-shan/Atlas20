"""Event-driven isolated-margin backtest for the Bitget derivatives track.

The engine is intentionally narrower than the spot engine: it consumes hourly
mark candles, signed target weights, and explicit funding settlements.  It
does not fill missing marks or funding with stale/zero values.  A held
position with no mark or funding print is a hard error, which is the research
track's fail-closed data policy.

The execution convention matches the project design: a signal dated ``D`` is
filled at ``D + execution_lag_days`` at ``execution_hour`` UTC.  Funding is
charged to the position's isolated margin before the hourly liquidation check,
and liquidation is checked against the hourly high/low mark path, never the
daily close.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from atlas20.derivatives.margin import initial_margin_ratio, liquidation_price


@dataclass(frozen=True)
class DerivativeBacktestConfig:
    """Costs and isolated-margin assumptions for one derivatives run."""

    initial_capital: float = 1.0
    taker_fee_bps: float = 6.0
    slippage_bps: float = 1.0
    liquidation_slippage_bps: float = 5.0
    maintenance_margin_rate: float = 0.01
    fee_buffer: float = 0.005
    long_buffer: float = 0.30
    short_buffer: float = 0.50
    max_gross_exposure: float = 1.25
    max_margin_utilization: float = 0.85
    execution_hour: int = 3
    execution_lag_days: int = 1
    funding_missing_policy: str = "error"
    funding_carry_max_hours: float = 24.0
    missing_mark_policy: str = "error"
    missing_mark_max_carry_hours: int = 1

    def __post_init__(self) -> None:
        if self.initial_capital <= 0.0:
            raise ValueError("initial_capital must be positive")
        if self.taker_fee_bps < 0.0:
            raise ValueError("taker_fee_bps must be non-negative")
        if self.slippage_bps < 0.0:
            raise ValueError("slippage_bps must be non-negative")
        if self.liquidation_slippage_bps < 0.0:
            raise ValueError("liquidation_slippage_bps must be non-negative")
        if not 0.0 <= self.maintenance_margin_rate < 1.0:
            raise ValueError("maintenance_margin_rate must be in [0, 1)")
        if self.fee_buffer < 0.0:
            raise ValueError("fee_buffer must be non-negative")
        if not 0.0 < self.long_buffer < 1.0:
            raise ValueError("long_buffer must be in (0, 1)")
        if not 0.0 < self.short_buffer < 1.0:
            raise ValueError("short_buffer must be in (0, 1)")
        if self.max_gross_exposure <= 0.0:
            raise ValueError("max_gross_exposure must be positive")
        if not 0.0 < self.max_margin_utilization <= 1.0:
            raise ValueError("max_margin_utilization must be in (0, 1]")
        if not 0 <= self.execution_hour <= 23:
            raise ValueError("execution_hour must be in [0, 23]")
        if self.execution_lag_days < 0:
            raise ValueError("execution_lag_days must be non-negative")
        if self.funding_missing_policy not in {"error", "skip", "carry_last", "stress_median"}:
            raise ValueError(
                "funding_missing_policy must be 'error', 'skip', 'carry_last', "
                "or 'stress_median'"
            )
        if self.funding_carry_max_hours < 0.0 or not np.isfinite(self.funding_carry_max_hours):
            raise ValueError("funding_carry_max_hours must be finite and non-negative")
        if self.missing_mark_policy not in {"error", "exit_last", "carry"}:
            raise ValueError("missing_mark_policy must be 'error', 'exit_last', or 'carry'")
        if self.missing_mark_max_carry_hours < 0:
            raise ValueError("missing_mark_max_carry_hours must be non-negative")


@dataclass
class _Position:
    asset: str
    side: int
    quantity: float
    entry_price: float
    entry_time: pd.Timestamp
    margin: float
    margin_ratio: float
    maintenance_margin_rate: float


@dataclass
class DerivativeBacktestResult:
    """Hourly and daily outputs plus auditable event ledgers."""

    equity_curve: pd.Series
    cash_curve: pd.Series
    gross_exposure: pd.Series
    daily_equity: pd.Series
    daily_returns: pd.Series
    drawdown: pd.Series
    trades: pd.DataFrame
    funding: pd.DataFrame
    liquidations: pd.DataFrame
    positions: pd.DataFrame
    mark_carries: pd.DataFrame


_TRADE_COLUMNS = [
    "timestamp",
    "asset",
    "side",
    "action",
    "quantity",
    "price",
    "notional",
    "fee",
    "margin",
    "reason",
]
_FUNDING_COLUMNS = ["timestamp", "asset", "side", "rate", "notional", "amount", "carried"]
_LIQUIDATION_COLUMNS = [
    "trigger_timestamp",
    "asset",
    "side",
    "entry_price",
    "liquidation_price",
    "execution_price",
    "quantity",
    "margin_before",
    "bad_debt",
]
_MARK_CARRY_COLUMNS = ["timestamp", "asset", "last_mark_time", "hours", "price"]
_POSITION_COLUMNS = [
    "timestamp",
    "asset",
    "side",
    "quantity",
    "entry_price",
    "notional",
    "margin",
    "margin_ratio",
    "liquidation_price",
]


def _as_utc(timestamp: object) -> pd.Timestamp:
    value = pd.Timestamp(timestamp)
    if value.tzinfo is None:
        return value.tz_localize("UTC")
    return value.tz_convert("UTC")


def _normalise_funding_index(values: Iterable[object]) -> pd.DatetimeIndex:
    """Map exchange timestamp jitter (milliseconds) to the settlement hour."""
    stamps: list[pd.Timestamp] = []
    for value in values:
        stamp = _as_utc(value)
        rounded = stamp.round("h")
        if abs(stamp - rounded) > pd.Timedelta(minutes=5):
            raise ValueError(f"funding timestamp is not close to an hourly settlement: {stamp}")
        stamps.append(pd.Timestamp(rounded))
    return pd.DatetimeIndex(stamps)


def _validate_candles(mark_candles: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if not mark_candles:
        raise ValueError("mark_candles must contain at least one asset")
    cleaned: dict[str, pd.DataFrame] = {}
    required = {"open", "high", "low", "close"}
    for asset, frame in mark_candles.items():
        if not isinstance(asset, str) or not asset:
            raise ValueError("mark_candles keys must be non-empty asset names")
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{asset}: mark candles are missing columns {sorted(missing)}")
        copy = frame.loc[:, ["open", "high", "low", "close"]].copy()
        copy.index = pd.DatetimeIndex([_as_utc(value) for value in copy.index])
        copy = copy[~copy.index.duplicated(keep="last")].sort_index()
        numeric = copy.apply(pd.to_numeric, errors="coerce")
        if numeric.isna().any().any():
            raise ValueError(f"{asset}: mark candles contain non-numeric or missing OHLC values")
        if (numeric <= 0.0).any().any():
            raise ValueError(f"{asset}: mark candles must be strictly positive")
        if (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).any():
            raise ValueError(f"{asset}: high is below another OHLC value")
        if (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError(f"{asset}: low is above another OHLC value")
        cleaned[asset] = numeric
    return cleaned


def _execution_time(signal_time: pd.Timestamp, config: DerivativeBacktestConfig) -> pd.Timestamp:
    signal_time = _as_utc(signal_time)
    day = signal_time.normalize()
    return day + pd.Timedelta(days=config.execution_lag_days, hours=config.execution_hour)


def _resolve_time(target: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp:
    target = _as_utc(target)
    if target in index:
        return target
    later = index[index >= target]
    if later.empty or later[0] - target > pd.Timedelta(hours=1):
        raise ValueError(f"no mark candle at or within one hour after execution time {target}")
    return pd.Timestamp(later[0])


def _normalise_targets(
    targets: Mapping[pd.Timestamp, pd.Series],
    config: DerivativeBacktestConfig,
) -> dict[pd.Timestamp, pd.Series]:
    normalised: dict[pd.Timestamp, pd.Series] = {}
    for signal_time, raw in targets.items():
        execution_time = _execution_time(_as_utc(signal_time), config)
        series = pd.Series(raw, dtype=float).copy()
        if series.index.has_duplicates:
            raise ValueError("target weights contain duplicate assets")
        series.index = series.index.astype(str)
        if series.isna().any() or not np.isfinite(series.to_numpy()).all():
            raise ValueError("target weights must be finite numbers")
        gross = float(series.abs().sum())
        if gross > config.max_gross_exposure + 1e-12:
            series = series * (config.max_gross_exposure / gross)
        if execution_time in normalised:
            raise ValueError(f"multiple signals map to execution time {execution_time}")
        normalised[execution_time] = series
    return dict(sorted(normalised.items()))


def _margin_ratio(config: DerivativeBacktestConfig, side: int) -> float:
    return initial_margin_ratio(
        "long" if side > 0 else "short",
        maintenance_margin_rate=config.maintenance_margin_rate,
        fee_buffer=config.fee_buffer,
        long_buffer=config.long_buffer,
        short_buffer=config.short_buffer,
    )


def _target_equal(left: pd.Series | None, right: pd.Series) -> bool:
    if left is None:
        return False
    index = left.index.union(right.index)
    return bool(
        np.allclose(
            left.reindex(index).fillna(0.0).to_numpy(dtype=float),
            right.reindex(index).fillna(0.0).to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-12,
        )
    )


def run_derivative_backtest(
    mark_candles: Mapping[str, pd.DataFrame],
    targets: Mapping[pd.Timestamp, pd.Series],
    *,
    funding_rates: pd.DataFrame | None = None,
    funding_intervals_hours: Mapping[str, float] | None = None,
    config: DerivativeBacktestConfig | None = None,
    start_time: object | None = None,
    end_time: object | None = None,
) -> DerivativeBacktestResult:
    """Run one isolated-margin derivatives path.

    ``mark_candles`` maps asset names to hourly OHLC frames.  ``targets`` maps
    signal timestamps to signed fractions of account equity.  Positive values
    are long, negative values are short, and gross exposure is capped by
    ``config.max_gross_exposure``.  ``funding_rates`` is a wide frame indexed by
    settlement timestamps; a NaN rate for a held asset is a hard error by
    default.  ``funding_intervals_hours`` optionally declares each asset's
    expected settlement interval; when supplied with fail-closed funding, a
    held position whose last known settlement is older than that interval
    raises instead of silently paying zero.  ``start_time`` and ``end_time``
    optionally bound the evaluation path; the interval is left-closed and
    right-open, and targets whose execution would fall outside it are ignored.
    """
    cfg = config or DerivativeBacktestConfig()
    candles = _validate_candles(mark_candles)
    target_schedule = _normalise_targets(targets, cfg)
    if funding_rates is None:
        funding = pd.DataFrame()
    else:
        funding = funding_rates.copy()
        funding.index = _normalise_funding_index(funding.index)
        funding = funding[~funding.index.duplicated(keep="last")].sort_index()
        funding.columns = funding.columns.astype(str)
        funding = funding.apply(pd.to_numeric, errors="coerce")
    funding_intervals: dict[str, float] = {}
    if funding_intervals_hours is not None:
        for asset, hours in funding_intervals_hours.items():
            interval = float(hours)
            if interval <= 0.0 or not np.isfinite(interval):
                raise ValueError("funding intervals must be positive finite hours")
            funding_intervals[str(asset)] = interval
    funding_times: dict[str, pd.DatetimeIndex] = {}
    if not funding.empty:
        for asset in funding.columns:
            values = funding[asset].dropna()
            if not values.empty:
                funding_times[str(asset)] = pd.DatetimeIndex(values.index)

    adverse_median: pd.Series | None = None
    if cfg.funding_missing_policy == "stress_median":
        if funding.empty:
            raise ValueError("stress_median funding policy requires funding rates")
        positive_only = funding.where(funding > 0.0)
        adverse_median = positive_only.median(axis=1, skipna=True).ffill()

    index = pd.DatetimeIndex(
        sorted(set().union(*(frame.index for frame in candles.values())) | set(funding.index))
    )
    if index.empty:
        raise ValueError("no hourly mark candles")
    window_start = _as_utc(start_time) if start_time is not None else None
    window_end = _as_utc(end_time) if end_time is not None else None
    if window_start is not None and window_end is not None and window_start >= window_end:
        raise ValueError("start_time must be earlier than end_time")
    if window_start is not None:
        index = index[index >= window_start]
        target_schedule = {
            time: target for time, target in target_schedule.items() if time >= window_start
        }
    if window_end is not None:
        index = index[index < window_end]
        target_schedule = {
            time: target for time, target in target_schedule.items() if time < window_end
        }
    if index.empty:
        raise ValueError("no hourly mark candles in the requested evaluation window")
    execution_times = {_resolve_time(time, index): target for time, target in target_schedule.items()}

    cash = float(cfg.initial_capital)
    positions: dict[str, _Position] = {}
    last_target: pd.Series | None = None
    trades: list[dict[str, object]] = []
    funding_events: list[dict[str, object]] = []
    liquidation_events: list[dict[str, object]] = []
    mark_carries: list[dict[str, object]] = []
    position_entries: list[dict[str, object]] = []
    equity_values: list[float] = []
    cash_values: list[float] = []
    gross_values: list[float] = []
    fee_rate = (cfg.taker_fee_bps + cfg.slippage_bps) / 10_000.0
    liquidation_fee_rate = (cfg.taker_fee_bps + cfg.liquidation_slippage_bps) / 10_000.0

    def _last_mark(asset: str, timestamp: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
        frame = candles.get(asset)
        if frame is None:
            return None
        prior = frame.index[frame.index <= timestamp]
        if prior.empty:
            return None
        last_time = pd.Timestamp(prior[-1])
        return last_time, float(frame.at[last_time, "close"])

    def bar(asset: str, timestamp: pd.Timestamp) -> pd.Series:
        frame = candles.get(asset)
        if frame is not None and timestamp in frame.index:
            return frame.loc[timestamp]
        if cfg.missing_mark_policy == "carry":
            carried = _last_mark(asset, timestamp)
            if carried is not None:
                last_time, price = carried
                hours = (timestamp - last_time).total_seconds() / 3600.0
                if hours <= cfg.missing_mark_max_carry_hours:
                    return pd.Series(
                        {"open": price, "high": price, "low": price, "close": price}
                    )
        raise ValueError(f"missing mark candle for held asset {asset} at {timestamp}")

    def mark(asset: str, timestamp: pd.Timestamp, column: str = "close") -> float:
        return float(bar(asset, timestamp)[column])

    def check_funding_coverage(asset: str, timestamp: pd.Timestamp) -> None:
        if cfg.funding_missing_policy != "error" or not funding_intervals:
            return
        interval = funding_intervals.get(asset)
        if interval is None:
            raise ValueError(f"missing funding interval for held asset {asset}")
        times = funding_times.get(asset)
        if times is None or times.empty:
            raise ValueError(f"funding gap for held asset {asset} at {timestamp}: no settlements")
        position = times.searchsorted(timestamp, side="right") - 1
        if position < 0:
            raise ValueError(f"funding gap for held asset {asset} at {timestamp}: no prior settlement")
        last_settlement = pd.Timestamp(times[position])
        if timestamp - last_settlement > pd.Timedelta(hours=interval + 0.25):
            raise ValueError(
                f"funding gap for held asset {asset} at {timestamp}: "
                f"last settlement {last_settlement}"
            )

    def carried_rate(asset: str, timestamp: pd.Timestamp) -> float:
        """Last observed settlement rate for an explicitly labelled carry stress."""

        times = funding_times.get(asset)
        if times is None or times.empty:
            raise ValueError(f"no prior funding for held asset {asset} at {timestamp}")
        position_index = times.searchsorted(timestamp, side="right") - 1
        if position_index < 0:
            raise ValueError(f"no prior funding for held asset {asset} at {timestamp}")
        last_settlement = pd.Timestamp(times[position_index])
        gap_hours = (timestamp - last_settlement).total_seconds() / 3600.0
        if gap_hours > cfg.funding_carry_max_hours:
            raise ValueError(
                f"funding carry limit exceeded for held asset {asset} at {timestamp}: "
                f"last settlement {last_settlement} is {gap_hours:.1f}h old"
            )
        return float(funding.at[last_settlement, asset])

    def settlement_due(asset: str, timestamp: pd.Timestamp) -> bool:
        """True when the asset's declared schedule says a settlement happened here."""

        interval = funding_intervals.get(asset)
        if interval is None:
            raise ValueError(f"missing funding interval for held asset {asset}")
        times = funding_times.get(asset)
        if times is None or times.empty:
            return True
        position_index = times.searchsorted(timestamp, side="left") - 1
        if position_index < 0:
            return True
        last_settlement = pd.Timestamp(times[position_index])
        gap_hours = (timestamp - last_settlement).total_seconds() / 3600.0
        return gap_hours >= interval - 0.25

    def adverse_median_rate(asset: str, timestamp: pd.Timestamp) -> float:
        """Cross-sectional long-adverse median, an explicit worst-case stress fill."""

        if adverse_median is None or adverse_median.empty:
            raise ValueError("stress_median funding policy requires funding rates")
        history = adverse_median.loc[:timestamp].dropna()
        if history.empty:
            raise ValueError(f"no adverse funding observation for held asset {asset} at {timestamp}")
        last_time = pd.Timestamp(history.index[-1])
        gap_hours = (timestamp - last_time).total_seconds() / 3600.0
        if gap_hours > cfg.funding_carry_max_hours:
            raise ValueError(
                f"funding carry limit exceeded for held asset {asset} at {timestamp}: "
                f"last adverse median {last_time} is {gap_hours:.1f}h old"
            )
        return float(history.iloc[-1])

    def account_equity(timestamp: pd.Timestamp, *, column: str = "close") -> float:
        value = cash
        for asset, position in positions.items():
            price = mark(asset, timestamp, column)
            value += position.margin + position.side * position.quantity * (price - position.entry_price)
        return value

    def close_position(
        asset: str,
        timestamp: pd.Timestamp,
        price: float,
        *,
        reason: str,
        fee_rate_override: float | None = None,
    ) -> float:
        nonlocal cash
        position = positions.pop(asset)
        pnl = position.side * position.quantity * (price - position.entry_price)
        notional = position.quantity * price
        rate = fee_rate if fee_rate_override is None else fee_rate_override
        fee = notional * rate
        settlement = position.margin + pnl - fee
        bad_debt = max(0.0, -settlement)
        cash += max(0.0, settlement)
        trades.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if position.side > 0 else "short",
                "action": "close",
                "quantity": position.quantity,
                "price": price,
                "notional": notional,
                "fee": fee,
                "margin": position.margin,
                "reason": reason,
            }
        )
        return bad_debt

    def liquidate_position(asset: str, timestamp: pd.Timestamp) -> None:
        position = positions[asset]
        candle = bar(asset, timestamp)
        open_price = float(candle["open"])
        effective_margin_ratio = position.margin / (position.quantity * position.entry_price)
        if effective_margin_ratio <= 0.0:
            theoretical = open_price
            trigger = open_price
        else:
            theoretical = liquidation_price(
                side="long" if position.side > 0 else "short",
                entry_price=position.entry_price,
                margin_ratio=min(effective_margin_ratio, 0.999999),
                maintenance_margin_rate=position.maintenance_margin_rate,
            )
            if position.side > 0:
                trigger = open_price if open_price <= theoretical else theoretical
                if open_price > theoretical and float(candle["low"]) > theoretical:
                    return
            else:
                trigger = open_price if open_price >= theoretical else theoretical
                if open_price < theoretical and float(candle["high"]) < theoretical:
                    return
        if position.side > 0:
            execution_price = trigger * (1.0 - cfg.liquidation_slippage_bps / 10_000.0)
        else:
            execution_price = trigger * (1.0 + cfg.liquidation_slippage_bps / 10_000.0)
        margin_before = position.margin
        bad_debt = close_position(
            asset,
            timestamp,
            execution_price,
            reason="liquidation",
            fee_rate_override=liquidation_fee_rate,
        )
        liquidation_events.append(
            {
                "trigger_timestamp": timestamp,
                "asset": asset,
                "side": "long" if position.side > 0 else "short",
                "entry_price": position.entry_price,
                "liquidation_price": theoretical,
                "execution_price": execution_price,
                "quantity": position.quantity,
                "margin_before": margin_before,
                "bad_debt": bad_debt,
            }
        )

    def open_position(
        asset: str,
        timestamp: pd.Timestamp,
        side: int,
        notional: float,
        price: float,
    ) -> None:
        nonlocal cash
        if notional <= 0.0:
            return
        ratio = _margin_ratio(cfg, side)
        margin = notional * ratio
        fee = notional * fee_rate
        if margin + fee > cash + 1e-12:
            scale = max(0.0, cash / (margin + fee))
            margin *= scale
            fee *= scale
            notional *= scale
        if notional <= 0.0:
            return
        quantity = notional / price
        cash -= margin + fee
        position = _Position(
            asset=asset,
            side=side,
            quantity=quantity,
            entry_price=price,
            entry_time=timestamp,
            margin=margin,
            margin_ratio=ratio,
            maintenance_margin_rate=cfg.maintenance_margin_rate,
        )
        positions[asset] = position
        trades.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if side > 0 else "short",
                "action": "open",
                "quantity": quantity,
                "price": price,
                "notional": notional,
                "fee": fee,
                "margin": margin,
                "reason": "rebalance",
            }
        )
        position_entries.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if side > 0 else "short",
                "quantity": quantity,
                "entry_price": price,
                "notional": notional,
                "margin": margin,
                "margin_ratio": ratio,
                "liquidation_price": liquidation_price(
                    side="long" if side > 0 else "short",
                    entry_price=price,
                    margin_ratio=ratio,
                    maintenance_margin_rate=cfg.maintenance_margin_rate,
                ),
            }
        )

    def reduce_position(
        asset: str,
        timestamp: pd.Timestamp,
        price: float,
        quantity: float,
    ) -> None:
        nonlocal cash
        position = positions[asset]
        quantity = min(float(quantity), position.quantity)
        if quantity <= 1e-15:
            return
        if quantity >= position.quantity - 1e-15:
            close_position(asset, timestamp, price, reason="rebalance")
            return
        fraction = quantity / position.quantity
        released_margin = position.margin * fraction
        pnl = position.side * quantity * (price - position.entry_price)
        notional = quantity * price
        fee = notional * fee_rate
        cash += released_margin + pnl - fee
        position.quantity -= quantity
        position.margin -= released_margin
        trades.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if position.side > 0 else "short",
                "action": "reduce",
                "quantity": quantity,
                "price": price,
                "notional": notional,
                "fee": fee,
                "margin": released_margin,
                "reason": "rebalance",
            }
        )

    def increase_position(
        asset: str,
        timestamp: pd.Timestamp,
        price: float,
        additional_notional: float,
    ) -> None:
        nonlocal cash
        position = positions[asset]
        if additional_notional <= 0.0:
            return
        ratio = position.margin_ratio
        margin = additional_notional * ratio
        fee = additional_notional * fee_rate
        if margin + fee > cash + 1e-12:
            scale = max(0.0, cash / (margin + fee))
            additional_notional *= scale
            margin *= scale
            fee *= scale
        if additional_notional <= 0.0:
            return
        quantity = additional_notional / price
        old_quantity = position.quantity
        new_quantity = old_quantity + quantity
        position.entry_price = (
            old_quantity * position.entry_price + quantity * price
        ) / new_quantity
        position.quantity = new_quantity
        position.margin += margin
        cash -= margin + fee
        trades.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if position.side > 0 else "short",
                "action": "increase",
                "quantity": quantity,
                "price": price,
                "notional": additional_notional,
                "fee": fee,
                "margin": margin,
                "reason": "rebalance",
            }
        )
        position_entries.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "side": "long" if position.side > 0 else "short",
                "quantity": new_quantity,
                "entry_price": position.entry_price,
                "notional": new_quantity * price,
                "margin": position.margin,
                "margin_ratio": position.margin_ratio,
                "liquidation_price": liquidation_price(
                    side="long" if position.side > 0 else "short",
                    entry_price=position.entry_price,
                    margin_ratio=position.margin_ratio,
                    maintenance_margin_rate=position.maintenance_margin_rate,
                ),
            }
        )

    def rebalance(timestamp: pd.Timestamp, target: pd.Series) -> None:
        equity = account_equity(timestamp, column="open")
        desired: dict[str, tuple[int, float]] = {}
        for asset, weight in target.items():
            weight = float(weight)
            if abs(weight) <= 1e-15:
                continue
            if asset not in candles:
                raise ValueError(f"target asset {asset} is absent from mark_candles")
            desired[asset] = (1 if weight > 0 else -1, abs(weight) * equity)
        required_margin = sum(
            notional * _margin_ratio(cfg, side) for side, notional in desired.values()
        )
        scale = 1.0
        if required_margin > cfg.max_margin_utilization * equity:
            scale = cfg.max_margin_utilization * equity / required_margin
        desired = {
            asset: (side, notional * scale)
            for asset, (side, notional) in desired.items()
        }

        # Reduce or close first so the released cash can fund increases.
        for asset in list(positions):
            price = mark(asset, timestamp, "open")
            current = positions[asset]
            target_entry = desired.get(asset)
            if target_entry is None or target_entry[0] != current.side:
                close_position(asset, timestamp, price, reason="rebalance")
                continue
            desired_quantity = target_entry[1] / price
            if desired_quantity < current.quantity - 1e-12:
                reduce_position(
                    asset,
                    timestamp,
                    price,
                    current.quantity - desired_quantity,
                )

        # Open or increase only after reductions have settled.
        for asset, (side, notional) in desired.items():
            price = mark(asset, timestamp, "open")
            current = positions.get(asset)
            if current is None:
                open_position(asset, timestamp, side, notional, price)
            else:
                current_notional = current.quantity * price
                if notional > current_notional + 1e-12:
                    increase_position(
                        asset,
                        timestamp,
                        price,
                        notional - current_notional,
                    )

    for timestamp in index:
        timestamp = pd.Timestamp(timestamp)

        # A provider gap after a delisting cannot be carried indefinitely.
        # ``exit_last`` closes on the first gap; ``carry`` is an explicit
        # diagnostic policy with a hard hour limit; ``error`` is production.
        if cfg.missing_mark_policy in {"exit_last", "carry"}:
            for asset in list(positions):
                frame = candles.get(asset)
                if frame is None:
                    raise ValueError(f"missing mark history for held asset {asset}")
                if timestamp not in frame.index:
                    prior = frame.index[frame.index < timestamp]
                    if prior.empty:
                        raise ValueError(f"no prior mark for held asset {asset} at {timestamp}")
                    last_time = pd.Timestamp(prior[-1])
                    hours = (timestamp - last_time).total_seconds() / 3600.0
                    if cfg.missing_mark_policy == "exit_last" or hours > cfg.missing_mark_max_carry_hours:
                        close_position(
                            asset,
                            timestamp,
                            float(frame.at[last_time, "close"]),
                            reason="missing_mark_exit",
                        )
                    else:
                        mark_carries.append(
                            {
                                "timestamp": timestamp,
                                "asset": asset,
                                "last_mark_time": last_time,
                                "hours": hours,
                                "price": float(frame.at[last_time, "close"]),
                            }
                        )

        # Funding is settled before the hourly liquidation check.
        for asset in positions:
            check_funding_coverage(asset, timestamp)
        if timestamp in funding.index:
            for asset, position in list(positions.items()):
                rate: float | None = None
                carried = False
                if asset in funding.columns:
                    raw_rate = funding.at[timestamp, asset]
                    if not pd.isna(raw_rate):
                        rate = float(raw_rate)
                if rate is None:
                    if cfg.funding_missing_policy == "error":
                        if asset not in funding.columns:
                            raise ValueError(
                                f"missing funding column for held asset {asset} at {timestamp}"
                            )
                        raise ValueError(f"missing funding for held asset {asset} at {timestamp}")
                    if cfg.funding_missing_policy == "skip":
                        continue
                    if not settlement_due(asset, timestamp):
                        continue
                    if cfg.funding_missing_policy == "carry_last":
                        rate = carried_rate(asset, timestamp)
                    else:
                        rate = adverse_median_rate(asset, timestamp)
                    carried = True
                price = mark(asset, timestamp, "open")
                notional = position.quantity * price
                amount = -position.side * rate * notional
                position.margin += amount
                funding_events.append(
                    {
                        "timestamp": timestamp,
                        "asset": asset,
                        "side": "long" if position.side > 0 else "short",
                        "rate": rate,
                        "notional": notional,
                        "amount": amount,
                        "carried": carried,
                    }
                )

        # A funding deficit or a mark-path breach liquidates the isolated leg.
        for asset in list(positions):
            liquidate_position(asset, timestamp)

        if timestamp in execution_times:
            target = execution_times[timestamp]
            if not _target_equal(last_target, target):
                rebalance(timestamp, target)
                last_target = target.copy()
                for asset in positions:
                    check_funding_coverage(asset, timestamp)

        equity = account_equity(timestamp)
        gross_notional = sum(position.quantity * mark(asset, timestamp) for asset, position in positions.items())
        equity_values.append(equity)
        cash_values.append(cash)
        gross_values.append(gross_notional / equity if equity > 0.0 else float("nan"))

    equity_curve = pd.Series(equity_values, index=index, name="equity")
    cash_curve = pd.Series(cash_values, index=index, name="cash")
    gross_exposure = pd.Series(gross_values, index=index, name="gross_exposure")
    daily_equity = equity_curve.resample("1D").last().dropna()
    daily_returns = daily_equity.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    return DerivativeBacktestResult(
        equity_curve=equity_curve,
        cash_curve=cash_curve,
        gross_exposure=gross_exposure,
        daily_equity=daily_equity,
        daily_returns=daily_returns,
        drawdown=drawdown,
        trades=pd.DataFrame(trades, columns=_TRADE_COLUMNS),
        funding=pd.DataFrame(funding_events, columns=_FUNDING_COLUMNS),
        liquidations=pd.DataFrame(liquidation_events, columns=_LIQUIDATION_COLUMNS),
        positions=pd.DataFrame(position_entries, columns=_POSITION_COLUMNS),
        mark_carries=pd.DataFrame(mark_carries, columns=_MARK_CARRY_COLUMNS),
    )


__all__ = ["DerivativeBacktestConfig", "DerivativeBacktestResult", "run_derivative_backtest"]
