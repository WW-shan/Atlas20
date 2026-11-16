"""Independently replay a derivatives backtest artifact set and audit it.

The research engine already writes its event ledgers.  This script does not
trust the engine's summary: it rebuilds cash, isolated margin and open quantity
from ``oos_trades.csv`` / ``oos_funding.csv`` / ``oos_margin_events.csv`` at the
last daily close, marks the residual book from the raw Bitget mark tree, and
compares that independently reconstructed equity with the reported path.

It also checks the return/metric chain, target-gross cap, fee/notional
identities, funding identities and margin-neutrality of every normalization
event.  It is deterministic and performs no network access.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DEFAULT_COST_BPS = 20.0
DEFAULT_MAX_GROSS = 1.75


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    hard: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": bool(self.passed),
            "detail": self.detail,
            "hard": bool(self.hard),
        }


def _num(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return float("nan")


def _read_csv(path: Path, *, required: list[str], label: str) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    frame = pd.read_csv(path)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing columns {missing}")
    return frame



def _replay_position_states(
    trades: pd.DataFrame,
) -> dict[tuple[pd.Timestamp, str], tuple[float, float] | None]:
    """Replay quantity and weighted entry at each open/increase snapshot.

    This deliberately ignores cash, margin and funding: those are audited by
    the equity replay.  Here the question is whether the reported position
    ledger itself (quantity, weighted entry, notional) is a faithful
    projection of the trade ledger, including reduce/close/reopen cycles.
    """

    positions: dict[str, dict[str, float]] = {}
    states: dict[tuple[pd.Timestamp, str], tuple[float, float] | None] = {}
    frame = trades.sort_values("timestamp", kind="stable")
    for row in frame.itertuples(index=False):
        asset = str(row.asset)
        action = str(row.action)
        price = float(row.price)
        quantity = float(row.quantity)
        if action == "open":
            positions[asset] = {
                "side": 1.0 if str(row.side) == "long" else -1.0,
                "quantity": quantity,
                "entry_price": price,
            }
        elif action == "increase":
            position = positions[asset]
            old_quantity = position["quantity"]
            new_quantity = old_quantity + quantity
            position["entry_price"] = (
                old_quantity * position["entry_price"] + quantity * price
            ) / new_quantity
            position["quantity"] = new_quantity
        elif action in {"reduce", "close"}:
            position = positions[asset]
            position["quantity"] -= quantity
            if action == "close" or position["quantity"] <= 1e-12:
                del positions[asset]
        else:
            raise ValueError(f"unknown trade action {action!r}")
        current = positions.get(asset)
        states[(pd.Timestamp(row.timestamp), asset)] = (
            None if current is None else (current["quantity"], current["entry_price"])
        )
    return states


def _load_mark_series(raw_dir: Path, symbols: dict[str, str]) -> dict[str, pd.Series]:
    """Load every available mark-close series for the daily path replay."""

    series: dict[str, pd.Series] = {}
    for asset, symbol in symbols.items():
        path = raw_dir / "candles" / f"{symbol}_mark.csv"
        if not path.is_file():
            continue
        frame = pd.read_csv(path, usecols=["open_time", "close"])
        times = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
        values = pd.to_numeric(frame["close"], errors="coerce")
        valid = times.notna() & values.notna() & np.isfinite(values.to_numpy(dtype=float))
        candidate = pd.Series(
            values.loc[valid].to_numpy(dtype=float),
            index=pd.DatetimeIndex(times.loc[valid]),
        )
        candidate = candidate[~candidate.index.duplicated(keep="last")].sort_index()
        if not candidate.empty:
            series[asset] = candidate
    return series


def _replay_equity_path(
    *,
    trades: pd.DataFrame,
    funding: pd.DataFrame,
    margin_events: pd.DataFrame,
    initial_capital: float,
    cutoffs: list[pd.Timestamp],
    marks_by_symbol: dict[str, float] | None = None,
    mark_series: dict[str, pd.Series] | None = None,
) -> dict[pd.Timestamp, tuple[float, float, float]]:
    """Replay the event ledgers and value the book at each requested cutoff.

    Events are applied in engine order: funding settlement, then fills, then
    isolated-margin normalization.  A cutoff may fall between event rows; the
    state is value-only at that point.  This deliberately reconstructs every
    daily equity point from the raw ledgers instead of trusting ``oos_daily``.
    """

    cash = float(initial_capital)
    positions: dict[str, dict[str, float]] = {}

    funding = funding.copy()
    trades = trades.copy()
    margin_events = margin_events.copy()
    for frame in (funding, trades, margin_events):
        frame["__ts"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed", errors="coerce")
    funding = funding.loc[funding["__ts"].notna()]
    trades = trades.loc[trades["__ts"].notna()]
    margin_events = margin_events.loc[margin_events["__ts"].notna()]
    times = sorted(
        set(funding["__ts"])
        | set(trades["__ts"])
        | set(margin_events["__ts"])
    )

    def realised_pnl(position: dict[str, float], quantity: float, price: float) -> float:
        return position["side"] * quantity * (price - position["entry_price"])

    def mark_at(asset: str, timestamp: pd.Timestamp) -> float:
        if mark_series is not None:
            series = mark_series.get(asset)
            if series is None or timestamp not in series.index:
                raise ValueError(f"no mark for open position {asset} at {timestamp}")
            value = float(series.loc[timestamp])
        else:
            value = float((marks_by_symbol or {}).get(asset, float("nan")))
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError(f"no valid mark for open position {asset} at {timestamp}")
        return value

    results: dict[pd.Timestamp, tuple[float, float, float]] = {}
    event_index = 0
    for raw_cutoff in sorted(pd.Timestamp(item) for item in cutoffs):
        while event_index < len(times) and times[event_index] <= raw_cutoff:
            timestamp = times[event_index]
            for row in funding.loc[funding["__ts"] == timestamp].itertuples(index=False):
                position = positions.get(str(row.asset))
                if position is not None:
                    position["margin"] += float(row.amount)
            for row in trades.loc[trades["__ts"] == timestamp].itertuples(index=False):
                asset = str(row.asset)
                side = 1.0 if str(row.side) == "long" else -1.0
                quantity = float(row.quantity)
                price = float(row.price)
                fee = float(row.fee)
                action = str(row.action)
                if action == "open":
                    positions[asset] = {
                        "side": side,
                        "quantity": quantity,
                        "entry_price": price,
                        "margin": float(row.margin),
                    }
                    cash -= float(row.margin) + fee
                elif action == "increase":
                    position = positions[asset]
                    old_qty = position["quantity"]
                    new_qty = old_qty + quantity
                    position["entry_price"] = (
                        old_qty * position["entry_price"] + quantity * price
                    ) / new_qty
                    position["quantity"] = new_qty
                    position["margin"] += float(row.margin)
                    cash -= float(row.margin) + fee
                elif action == "reduce":
                    position = positions[asset]
                    cash += float(row.margin) + realised_pnl(position, quantity, price) - fee
                    position["quantity"] -= quantity
                    position["margin"] -= float(row.margin)
                elif action == "close":
                    position = positions[asset]
                    settlement = position["margin"] + realised_pnl(position, quantity, price) - fee
                    cash += max(0.0, settlement)
                    del positions[asset]
                else:
                    raise ValueError(f"unknown trade action {action!r}")
            for row in margin_events.loc[margin_events["__ts"] == timestamp].itertuples(index=False):
                position = positions.get(str(row.asset))
                if position is None:
                    continue
                amount = float(row.amount)
                if str(row.operation) == "add":
                    position["margin"] += amount
                    cash -= amount
                elif str(row.operation) == "remove":
                    position["margin"] -= amount
                    cash += amount
                else:
                    raise ValueError(f"unknown margin operation {row.operation!r}")
            event_index += 1

        equity = cash
        gross_notional = 0.0
        for asset, position in positions.items():
            mark = mark_at(asset, raw_cutoff)
            gross_notional += position["quantity"] * mark
            equity += position["margin"] + position["side"] * position["quantity"] * (
                mark - position["entry_price"]
            )
        gross_ratio = gross_notional / equity if equity > 0.0 else float("nan")
        results[raw_cutoff] = (
            float(equity),
            float(gross_notional),
            float(gross_ratio),
        )
    return results


def _replay_equity(
    *,
    trades: pd.DataFrame,
    funding: pd.DataFrame,
    margin_events: pd.DataFrame,
    initial_capital: float,
    cutoff: pd.Timestamp,
    marks_by_symbol: dict[str, float],
) -> float:
    cutoff = pd.Timestamp(cutoff)
    path = _replay_equity_path(
        trades=trades,
        funding=funding,
        margin_events=margin_events,
        initial_capital=initial_capital,
        cutoffs=[cutoff],
        marks_by_symbol=marks_by_symbol,
    )
    return path[cutoff][0]


def _metrics_from_daily(daily: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    equity = pd.to_numeric(daily["equity"], errors="coerce").to_numpy(dtype=float)
    returns = pd.to_numeric(daily["daily_return"], errors="coerce").to_numpy(dtype=float)
    multiple = float(equity[-1] / initial_capital)
    periods = max(len(returns), 1)
    cagr = (
        multiple ** (365.0 / periods) - 1.0
        if multiple > 0.0
        else -1.0
    )
    volatility = float(np.std(returns, ddof=0) * math.sqrt(365.0))
    sharpe = (
        float(np.mean(returns) * 365.0 / volatility)
        if volatility > 0.0
        else 0.0
    )
    wealth = np.concatenate(([1.0], (1.0 + returns).cumprod()))
    drawdown = wealth / np.maximum.accumulate(wealth) - 1.0
    return {
        "multiple": multiple,
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "max_drawdown": float(np.min(drawdown)),
    }


def audit_artifacts(
    *,
    output_dir: Path,
    raw_dir: Path,
    symbol_map: Path,
    initial_capital: float,
    cost_bps: float = DEFAULT_COST_BPS,
    max_gross: float = DEFAULT_MAX_GROSS,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    checks: list[Check] = []

    def check(name: str, passed: bool, detail: str, *, hard: bool = True) -> None:
        checks.append(Check(name, bool(passed), detail, hard))

    daily = _read_csv(
        output_dir / "oos_daily.csv",
        required=["date", "daily_return", "nav_multiple", "gross_exposure", "equity"],
        label="daily path",
    )
    targets = _read_csv(
        output_dir / "oos_targets.csv",
        required=[
            "signal_date",
            "execution_hint",
            "asset",
            "side",
            "target_weight",
            "change_weight",
            "action",
        ],
        label="target ledger",
    )
    trades = _read_csv(
        output_dir / "oos_trades.csv",
        required=["timestamp", "asset", "side", "action", "quantity", "price", "notional", "fee", "margin", "reason"],
        label="trade ledger",
    )
    funding = _read_csv(
        output_dir / "oos_funding.csv",
        required=["timestamp", "asset", "side", "rate", "notional", "amount", "carried"],
        label="funding ledger",
    )
    margin_events = _read_csv(
        output_dir / "oos_margin_events.csv",
        required=[
            "timestamp",
            "asset",
            "side",
            "operation",
            "amount",
            "margin_before",
            "margin_after",
            "target_margin",
            "cash_before",
            "cash_after",
            "equity_before",
            "equity_after",
            "reason",
        ],
        label="margin ledger",
    )
    positions = _read_csv(
        output_dir / "oos_positions.csv",
        required=[
            "timestamp",
            "asset",
            "side",
            "quantity",
            "entry_price",
            "notional",
            "margin",
            "margin_ratio",
            "liquidation_price",
        ],
        label="position ledger",
    )
    gross = _read_csv(
        output_dir / "oos_gross_exposure.csv",
        required=["gross_exposure"],
        label="gross path",
    )

    daily["date"] = pd.to_datetime(daily["date"], utc=True, format="mixed", errors="coerce")
    targets["signal_date"] = pd.to_datetime(
        targets["signal_date"], utc=True, format="mixed", errors="coerce"
    )
    targets["execution_hint"] = pd.to_datetime(
        targets["execution_hint"], utc=True, format="mixed", errors="coerce"
    )
    for frame, column in (
        (trades, "timestamp"),
        (funding, "timestamp"),
        (margin_events, "timestamp"),
        (positions, "timestamp"),
    ):
        frame[column] = pd.to_datetime(frame[column], utc=True, format="mixed", errors="coerce")

    check("daily path has rows", not daily.empty, f"{len(daily)} row(s)")
    check("target ledger has rows", not targets.empty, f"{len(targets)} row(s)")
    check(
        "daily dates are strictly increasing",
        daily["date"].is_monotonic_increasing and not daily["date"].duplicated().any(),
        f"{daily['date'].min()} .. {daily['date'].max()}",
    )
    check(
        "target execution hints are T+1 at 01:05 UTC",
        bool(
            targets["execution_hint"].notna().all()
            and (
                targets["execution_hint"]
                == targets["signal_date"].dt.normalize()
                + pd.Timedelta(days=1, hours=1, minutes=5)
            ).all()
        ),
        "all rows use the single frozen execution clock",
    )
    target_event = targets.groupby("signal_date", dropna=False)
    event_gross = target_event["target_weight"].apply(lambda values: float(values.abs().sum()))
    check(
        f"every target event gross <= {max_gross:.4f}x",
        bool((event_gross <= max_gross + 1e-12).all()),
        f"max event gross {float(event_gross.max()):.6f}x" if not event_gross.empty else "no events",
    )
    check(
        "target event weights are finite and unique per asset",
        bool(
            np.isfinite(pd.to_numeric(targets["target_weight"], errors="coerce")).all()
            and not targets.duplicated(["signal_date", "asset"]).any()
        ),
        f"{len(target_event)} event(s), {len(targets)} row(s)",
    )

    for frame, label in ((trades, "trade"), (funding, "funding"), (margin_events, "margin"), (positions, "position")):
        check(
            f"{label} timestamps are valid",
            bool(frame["timestamp"].notna().all()),
            f"{int(frame['timestamp'].isna().sum())} invalid",
        )

    normal_trades = trades.loc[~trades["reason"].isin(["stop_loss", "liquidation"])].copy()
    trade_notional = pd.to_numeric(normal_trades["quantity"], errors="coerce") * pd.to_numeric(normal_trades["price"], errors="coerce")
    normal_fee = pd.to_numeric(normal_trades["fee"], errors="coerce")
    check(
        "normal trade notional = quantity x price",
        bool(np.allclose(trade_notional, pd.to_numeric(normal_trades["notional"], errors="coerce"), rtol=1e-10, atol=1e-8)),
        "all normal trades",
    )
    check(
        f"normal trade fee = notional x {cost_bps:g}bps",
        bool(np.allclose(normal_fee, trade_notional * float(cost_bps) / 10_000.0, rtol=1e-10, atol=1e-8)),
        f"{len(normal_trades)} normal trade(s)",
    )
    forced_trades = trades.loc[trades["reason"].isin(["stop_loss", "liquidation"])].copy()
    if not forced_trades.empty:
        # Stop/liquidation execution prices already carry
        # ``liquidation_slippage_bps``.  Their fee must therefore be the taker
        # commission only; adding the slippage again would double-charge the
        # same adverse fill.
        forced_notional = pd.to_numeric(forced_trades["quantity"], errors="coerce") * pd.to_numeric(forced_trades["price"], errors="coerce")
        check(
            f"forced-exit fee = notional x {cost_bps:g}bps (slippage only in price)",
            bool(
                np.allclose(
                    pd.to_numeric(forced_trades["fee"], errors="coerce"),
                    forced_notional * float(cost_bps) / 10_000.0,
                    rtol=1e-10,
                    atol=1e-8,
                )
            ),
            f"{len(forced_trades)} forced exit(s)",
        )
    check(
        "all trade quantities/prices are positive",
        bool(
            (pd.to_numeric(trades["quantity"], errors="coerce") > 0.0).all()
            and (pd.to_numeric(trades["price"], errors="coerce") > 0.0).all()
        ),
        f"{len(trades)} trade(s)",
    )
    check(
        "trade timestamp order is non-decreasing",
        trades["timestamp"].is_monotonic_increasing,
        "event-ledger order",
    )

    funding_notional = pd.to_numeric(funding["notional"], errors="coerce")
    funding_rate = pd.to_numeric(funding["rate"], errors="coerce")
    funding_sign = funding["side"].map({"long": 1.0, "short": -1.0})
    expected_funding = -funding_sign * funding_rate * funding_notional
    check(
        "funding amount = -side x rate x notional",
        bool(np.allclose(pd.to_numeric(funding["amount"], errors="coerce"), expected_funding, rtol=1e-10, atol=1e-10)),
        f"{len(funding)} settlement(s)",
    )
    check(
        "funding rates are finite and not zero-filled",
        bool(np.isfinite(funding_rate).all() and funding_notional.gt(0.0).all()),
        f"max |rate| {float(funding_rate.abs().max()):.6g}" if not funding.empty else "no funding events",
    )

    if not margin_events.empty:
        before = pd.to_numeric(margin_events["margin_before"], errors="coerce")
        after = pd.to_numeric(margin_events["margin_after"], errors="coerce")
        amount = pd.to_numeric(margin_events["amount"], errors="coerce")
        equity_before = pd.to_numeric(margin_events["equity_before"], errors="coerce")
        equity_after = pd.to_numeric(margin_events["equity_after"], errors="coerce")
        cash_before = pd.to_numeric(margin_events["cash_before"], errors="coerce")
        cash_after = pd.to_numeric(margin_events["cash_after"], errors="coerce")
        add = margin_events["operation"].eq("add").to_numpy()
        expected_margin = np.where(add, before + amount, before - amount)
        expected_cash = np.where(add, cash_before - amount, cash_before + amount)
        check("margin event equity is unchanged", bool(np.allclose(equity_before, equity_after, rtol=1e-10, atol=1e-8)), f"{len(margin_events)} event(s)")
        check("margin event cash delta equals amount", bool(np.allclose(cash_after, expected_cash, rtol=1e-10, atol=1e-8)), "all normalizations")
        check("margin event margin delta equals amount", bool(np.allclose(after, expected_margin, rtol=1e-10, atol=1e-8)), "all normalizations")
        check("margin event direction is valid", bool(set(margin_events["operation"]) <= {"add", "remove"}), ", ".join(sorted(set(margin_events["operation"]))))

    if not positions.empty:
        orders = trades.loc[trades["action"].isin(["open", "increase"])].copy()
        order_by_key = {
            (pd.Timestamp(row.timestamp), str(row.asset)): row
            for row in orders.itertuples(index=False)
        }
        matched_actions: list[str] = []
        missing_position_orders: list[str] = []
        for row in positions.itertuples(index=False):
            key = (pd.Timestamp(row.timestamp), str(row.asset))
            order = order_by_key.get(key)
            if order is None:
                missing_position_orders.append(f"{row.timestamp}:{row.asset}")
            else:
                matched_actions.append(str(order.action))
        check(
            "every position snapshot maps to an open/increase fill",
            not missing_position_orders,
            ", ".join(missing_position_orders) or f"{len(positions)} snapshot(s)",
        )
        # ``oos_positions.csv`` records the post-fill position at an OPEN or
        # INCREASE: for an increase, ``notional`` is total remaining quantity x
        # the new fill price while ``entry_price`` is the weighted entry.
        # Replaying the whole trade ledger catches a stale quantity, a missing
        # reduce, or an entry price that was not carried through a close and
        # reopen cycle.
        replayed_states = _replay_position_states(trades)
        state_issues: list[str] = []
        for row in positions.itertuples(index=False):
            expected = replayed_states.get((pd.Timestamp(row.timestamp), str(row.asset)))
            if expected is None:
                state_issues.append(f"{row.timestamp}:{row.asset} no replayed position")
                continue
            expected_qty, expected_entry = expected
            if abs(float(row.quantity) - expected_qty) > max(1e-9, expected_qty * 1e-8):
                state_issues.append(
                    f"{row.timestamp}:{row.asset} qty {row.quantity} != {expected_qty}"
                )
            if abs(float(row.entry_price) - expected_entry) > max(1e-9, expected_entry * 1e-8):
                state_issues.append(
                    f"{row.timestamp}:{row.asset} entry {row.entry_price} != {expected_entry}"
                )
        check(
            "position snapshots match the replayed trade ledger",
            not state_issues,
            ", ".join(state_issues[:5]) or f"{len(positions)} snapshot(s)",
        )
        fill_prices = pd.Series(
            [float(order_by_key[(pd.Timestamp(row.timestamp), str(row.asset))].price) for row in positions.itertuples(index=False)],
            index=positions.index,
        )
        qty = pd.to_numeric(positions["quantity"], errors="coerce")
        notional = pd.to_numeric(positions["notional"], errors="coerce")
        check(
            "position notional = snapshot quantity x fill price",
            bool(np.allclose(notional, qty * fill_prices, rtol=1e-10, atol=1e-8)),
            f"{len(positions)} snapshot(s)",
        )
        open_positions = positions.loc[
            pd.Series(matched_actions, index=positions.index).eq("open")
        ].copy()
        if not open_positions.empty:
            margin = pd.to_numeric(open_positions["margin"], errors="coerce")
            open_notional = pd.to_numeric(open_positions["notional"], errors="coerce")
            ratio = pd.to_numeric(open_positions["margin_ratio"], errors="coerce")
            check(
                "OPEN position entry margin = notional x margin_ratio",
                bool(np.allclose(margin, open_notional * ratio, rtol=1e-10, atol=1e-8)),
                f"{len(open_positions)} OPEN snapshot(s)",
            )
        check(
            "position quantities and entry prices are positive",
            bool(
                (pd.to_numeric(positions["quantity"], errors="coerce") > 0.0).all()
                and (pd.to_numeric(positions["entry_price"], errors="coerce") > 0.0).all()
            ),
            "all entries",
        )

    # Every daily row is a 23:00 UTC mark.  Replaying the whole path (not
    # only the final point) proves that no intermediate equity point was
    # produced by an untracked cash or position change that later cancelled.
    cutoffs: list[pd.Timestamp] = []
    for value in daily["date"]:
        stamp = pd.Timestamp(value)
        if stamp.hour != 23 or stamp.minute != 0:
            stamp = stamp.normalize() + pd.Timedelta(hours=23)
        cutoffs.append(stamp)
    symbol_frame = pd.read_csv(symbol_map)
    symbols = {
        str(row.coin_id): str(row.bitget_symbol).upper()
        for row in symbol_frame.itertuples(index=False)
        if pd.notna(row.bitget_symbol) and str(row.bitget_symbol).strip()
    }
    mark_series = _load_mark_series(Path(raw_dir), symbols)
    gross_index = (
        pd.DatetimeIndex(
            pd.to_datetime(
                gross["Unnamed: 0"], utc=True, format="mixed", errors="coerce"
            )
        )
        if "Unnamed: 0" in gross.columns
        else pd.RangeIndex(len(gross))
    )
    hourly_cutoffs = (
        [pd.Timestamp(value) for value in gross_index]
        if isinstance(gross_index, pd.DatetimeIndex)
        else []
    )
    all_cutoffs = sorted(set(cutoffs) | set(hourly_cutoffs))
    try:
        replay_path = _replay_equity_path(
            trades=trades,
            funding=funding,
            margin_events=margin_events,
            initial_capital=float(initial_capital),
            cutoffs=all_cutoffs,
            mark_series=mark_series,
        )
        reconstructed = float(replay_path[cutoffs[-1]][0])
    except Exception as exc:  # noqa: BLE001 - report the exact accounting failure as a hard check
        check("independent event replay reconstructs final equity", False, f"{type(exc).__name__}: {exc}")
        check("independent daily replay reproduces every reported equity point", False, f"{type(exc).__name__}: {exc}")
        reconstructed = float("nan")
    else:
        reported = float(pd.to_numeric(daily["equity"], errors="coerce").iloc[-1])
        check(
            "independent event replay reconstructs final equity",
            abs(reconstructed - reported) <= max(1e-6, abs(reported) * 1e-12),
            f"replay={reconstructed:.8f}, reported={reported:.8f}",
        )
        reported_path = pd.to_numeric(daily["equity"], errors="coerce").to_numpy(dtype=float)
        replay_values = np.array([replay_path[stamp][0] for stamp in cutoffs], dtype=float)
        differences = np.abs(replay_values - reported_path)
        tolerances = np.maximum(1e-6, np.abs(reported_path) * 1e-12)
        worst = int(np.argmax(differences / tolerances))
        check(
            "independent daily replay reproduces every reported equity point",
            bool(np.all(differences <= tolerances)),
            (
                f"{len(cutoffs)} day(s); worst {cutoffs[worst]}: "
                f"replay={replay_values[worst]:.8f}, reported={reported_path[worst]:.8f}"
            ),
        )

    returns = pd.to_numeric(daily["daily_return"], errors="coerce").to_numpy(dtype=float)
    equity = pd.to_numeric(daily["equity"], errors="coerce").to_numpy(dtype=float)
    expected_returns = np.empty_like(equity)
    expected_returns[0] = equity[0] / float(initial_capital) - 1.0
    if len(equity) > 1:
        expected_returns[1:] = equity[1:] / equity[:-1] - 1.0
    check(
        "daily returns reproduce the reported equity path",
        bool(np.allclose(returns, expected_returns, rtol=1e-10, atol=1e-12)),
        f"{len(returns)} observations",
    )
    nav = np.cumprod(1.0 + returns)
    check(
        "reported nav_multiple is the compounded daily return",
        bool(np.allclose(pd.to_numeric(daily["nav_multiple"], errors="coerce").to_numpy(dtype=float), nav, rtol=1e-10, atol=1e-12)),
        f"final nav {float(nav[-1]):.10f}",
    )
    computed_metrics = _metrics_from_daily(daily, float(initial_capital))
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    for key in ("multiple", "cagr", "sharpe", "max_drawdown"):
        reported = _num(summary.get(key))
        actual = computed_metrics[key]
        check(
            f"summary {key} = independent daily-return calculation",
            bool(np.isfinite(reported) and abs(reported - actual) <= max(1e-10, abs(actual) * 1e-10)),
            f"summary={reported:.12g}, replay={actual:.12g}",
        )
    check(
        "summary fees_total = trade ledger fee sum",
        bool(np.isclose(_num(summary.get("fees_total")), float(pd.to_numeric(trades["fee"], errors="coerce").sum()), rtol=1e-10, atol=1e-8)),
        f"{float(pd.to_numeric(trades['fee'], errors='coerce').sum()):.10f}",
    )
    check(
        "summary funding_total = funding ledger amount sum",
        bool(np.isclose(_num(summary.get("funding_total")), float(pd.to_numeric(funding["amount"], errors="coerce").sum()), rtol=1e-10, atol=1e-8)),
        f"{float(pd.to_numeric(funding['amount'], errors='coerce').sum()):.10f}",
    )
    check(
        "summary max_observed_gross = gross path max",
        bool(np.isclose(_num(summary.get("max_observed_gross")), float(pd.to_numeric(gross["gross_exposure"], errors="coerce").max()), rtol=1e-10, atol=1e-12)),
        f"{float(pd.to_numeric(gross['gross_exposure'], errors='coerce').max()):.10f}",
    )
    check(
        "summary max_target_total_gross = max target-event gross",
        bool(
            np.isclose(
                _num(summary.get("max_target_total_gross")),
                float(event_gross.max()),
                rtol=1e-10,
                atol=1e-12,
            )
        ),
        f"summary={_num(summary.get('max_target_total_gross')):.10f}, ledger={float(event_gross.max()):.10f}",
    )
    short_event_gross = target_event["target_weight"].apply(
        lambda values: float(values.loc[values < 0.0].abs().sum())
    )
    check(
        "summary max_funded_short_gross = max short-event gross",
        bool(
            np.isclose(
                _num(summary.get("max_funded_short_gross")),
                float(short_event_gross.max()),
                rtol=1e-10,
                atol=1e-12,
            )
        ),
        f"summary={_num(summary.get('max_funded_short_gross')):.10f}, ledger={float(short_event_gross.max()):.10f}",
    )
    check(
        "summary days/metric_days match the daily path",
        bool(
            _num(summary.get("days")) == float(len(daily))
            and _num(summary.get("metric_days")) == float(len(returns))
        ),
        f"days={_num(summary.get('days')):g}, metric_days={_num(summary.get('metric_days')):g}, rows={len(daily)}",
    )
    check(
        "summary liquidation_count = liquidation trades",
        bool(
            _num(summary.get("liquidation_count"))
            == float((trades["reason"].astype(str) == "liquidation").sum())
        ),
        f"{int((trades['reason'].astype(str) == 'liquidation').sum())} trade(s)",
    )
    check(
        "summary stop_event_count = stop_loss trades",
        bool(
            _num(summary.get("stop_event_count"))
            == float((trades["reason"].astype(str) == "stop_loss").sum())
        ),
        f"{int((trades['reason'].astype(str) == 'stop_loss').sum())} trade(s)",
    )
    gross_series = pd.Series(
        pd.to_numeric(gross["gross_exposure"], errors="coerce").to_numpy(dtype=float),
        index=pd.to_datetime(gross["Unnamed: 0"], utc=True, format="mixed", errors="coerce")
        if "Unnamed: 0" in gross.columns
        else pd.RangeIndex(len(gross)),
    )
    # The engine writes the hourly gross series with its timestamp index.  The
    # daily frame stores the same last-of-day value; compare when both align.
    if isinstance(gross_series.index, pd.DatetimeIndex):
        daily_last = gross_series.resample("1D").last().reindex(daily["date"])
        check(
            "daily gross exposure is the last hourly gross of each day",
            bool(np.allclose(pd.to_numeric(daily["gross_exposure"], errors="coerce"), daily_last.to_numpy(dtype=float), rtol=1e-10, atol=1e-12)),
            f"{len(daily)} day(s)",
        )
        if hourly_cutoffs:
            try:
                hourly_ratios = np.array(
                    [replay_path[stamp][2] for stamp in hourly_cutoffs], dtype=float
                )
            except KeyError as exc:
                check(
                    "independent hourly gross replay covers every gross observation",
                    False,
                    f"missing replay cutoff {exc}",
                )
            else:
                reported_gross = pd.to_numeric(
                    gross["gross_exposure"], errors="coerce"
                ).to_numpy(dtype=float)
                gross_differences = np.abs(hourly_ratios - reported_gross)
                gross_tolerance = np.maximum(1e-10, np.abs(reported_gross) * 1e-10)
                worst_gross = int(np.argmax(gross_differences / gross_tolerance))
                check(
                    "independent hourly gross replay reproduces every gross observation",
                    bool(np.all(gross_differences <= gross_tolerance)),
                    (
                        f"{len(hourly_cutoffs)} hour(s); worst "
                        f"{hourly_cutoffs[worst_gross]}: replay="
                        f"{hourly_ratios[worst_gross]:.10f}, reported="
                        f"{reported_gross[worst_gross]:.10f}"
                    ),
                )
    check(
        f"all hourly gross observations <= {max_gross:.4f}x",
        bool((pd.to_numeric(gross["gross_exposure"], errors="coerce") <= max_gross + 1e-12).all()),
        f"{len(gross)} hour(s)",
    )

    hard_failures = [item for item in checks if not item.passed and item.hard]
    return {
        "output_dir": str(output_dir),
        "raw_dir": str(raw_dir),
        "reconstructed_equity": reconstructed,
        "checks": [item.as_dict() for item in checks],
        "hard_failures": [item.as_dict() for item in hard_failures],
        "passed": not hard_failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/ls45_live_g175"))
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/bitget_derivatives/merged_oos_20261112"),
    )
    parser.add_argument("--symbol-map", type=Path, default=None)
    parser.add_argument("--initial-capital", type=float, default=500.0)
    parser.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    parser.add_argument("--max-gross", type=float, default=DEFAULT_MAX_GROSS)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    symbol_map = args.symbol_map or (args.raw_dir / "symbol_map.csv")
    result = audit_artifacts(
        output_dir=args.output_dir,
        raw_dir=args.raw_dir,
        symbol_map=symbol_map,
        initial_capital=float(args.initial_capital),
        cost_bps=float(args.cost_bps),
        max_gross=float(args.max_gross),
    )
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in result["checks"]:
        print(("PASS" if item["passed"] else "FAIL" if item["hard"] else "WARN") + ": " + item["name"] + " — " + item["detail"])
    print(f"PASS={sum(item['passed'] for item in result['checks'])} FAIL={len(result['hard_failures'])}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
