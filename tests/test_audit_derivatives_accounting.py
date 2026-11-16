from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_derivatives_accounting import _replay_equity, audit_artifacts

INITIAL_CAPITAL = 500.0
FINAL_EQUITY = 464.22


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    output = tmp_path / "report"
    raw = tmp_path / "raw"
    (raw / "candles").mkdir(parents=True)
    output.mkdir()

    pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "daily_return": [504.67 / INITIAL_CAPITAL - 1.0, FINAL_EQUITY / 504.67 - 1.0],
            "nav_multiple": [504.67 / INITIAL_CAPITAL, FINAL_EQUITY / INITIAL_CAPITAL],
            "gross_exposure": [0.3269463213585115, 0.21541510490715607],
            "equity": [504.67, FINAL_EQUITY],
        }
    ).to_csv(output / "oos_daily.csv", index=False)

    pd.DataFrame(
        {
            "signal_date": ["2025-12-31", "2026-01-01"],
            "execution_hint": ["2026-01-01 01:05:00+00:00", "2026-01-02 01:05:00+00:00"],
            "asset": ["aaa", "aaa"],
            "side": ["long", "short"],
            "target_weight": [0.2, -0.1],
            "change_weight": [0.2, -0.1],
            "action": ["OPEN", "OPEN"],
        }
    ).to_csv(output / "oos_targets.csv", index=False)

    trades = pd.DataFrame(
        {
            "timestamp": [
                "2026-01-01 01:00:00+00:00",
                "2026-01-01 09:00:00+00:00",
                "2026-01-02 01:00:00+00:00",
                "2026-01-02 02:00:00+00:00",
                "2026-01-02 03:00:00+00:00",
            ],
            "asset": ["aaa"] * 5,
            "side": ["long", "long", "long", "long", "short"],
            "action": ["open", "increase", "reduce", "close", "open"],
            "quantity": [10.0, 5.0, 5.0, 10.0, 4.0],
            "price": [10.0, 12.0, 11.0, 9.0, 20.0],
            "notional": [100.0, 60.0, 55.0, 90.0, 80.0],
            "fee": [0.2, 0.12, 0.11, 0.18, 0.16],
            "margin": [20.0, 12.0, 10.0, 22.99, 16.0],
            "reason": ["rebalance"] * 5,
        }
    )
    trades.to_csv(output / "oos_trades.csv", index=False)

    pd.DataFrame(
        {
            "timestamp": ["2026-01-01 08:00:00+00:00", "2026-01-01 20:00:00+00:00"],
            "asset": ["aaa", "aaa"],
            "side": ["long", "long"],
            "rate": [0.001, -0.0005],
            "notional": [100.0, 180.0],
            "amount": [-0.1, 0.09],
            "carried": [False, False],
        }
    ).to_csv(output / "oos_funding.csv", index=False)

    pd.DataFrame(
        {
            "timestamp": ["2026-01-01 21:00:00+00:00", "2026-01-02 01:30:00+00:00"],
            "asset": ["aaa", "aaa"],
            "side": ["long", "long"],
            "operation": ["add", "remove"],
            "amount": [5.0, 4.0],
            "margin_before": [31.99, 26.99],
            "margin_after": [36.99, 22.99],
            "target_margin": [36.99, 22.99],
            "cash_before": [467.68, 474.2366666666667],
            "cash_after": [462.68, 478.2366666666667],
            "equity_before": [504.67, 504.67],
            "equity_after": [504.67, 504.67],
            "reason": ["daily_isolated_margin_normalization"] * 2,
        }
    ).to_csv(output / "oos_margin_events.csv", index=False)

    # The increase snapshot intentionally has notional = total_qty * new_fill
    # (15 * 12 = 180) while entry_price is the weighted entry (10.666...).
    # Only OPEN snapshots are subject to notional == quantity * entry_price.
    pd.DataFrame(
        {
            "timestamp": [
                "2026-01-01 01:00:00+00:00",
                "2026-01-01 09:00:00+00:00",
                "2026-01-02 03:00:00+00:00",
            ],
            "asset": ["aaa"] * 3,
            "side": ["long", "long", "short"],
            "quantity": [10.0, 15.0, 4.0],
            "entry_price": [10.0, 160.0 / 15.0, 20.0],
            "notional": [100.0, 180.0, 80.0],
            "margin": [20.0, 31.9, 16.0],
            "margin_ratio": [0.2, 31.9 / 180.0, 0.2],
            "liquidation_price": [2.0, 2.0, 36.0],
        }
    ).to_csv(output / "oos_positions.csv", index=False)

    gross = pd.DataFrame(
        {"gross_exposure": [0.0, 0.3269463213585115, 0.21541510490715607]},
        index=pd.to_datetime(
            [
                "2026-01-01 00:00:00+00:00",
                "2026-01-01 23:00:00+00:00",
                "2026-01-02 23:00:00+00:00",
            ]
        ),
    )
    gross.to_csv(output / "oos_gross_exposure.csv")

    returns = [504.67 / INITIAL_CAPITAL - 1.0, FINAL_EQUITY / 504.67 - 1.0]
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    sharpe = mean * 365.0 / (math.sqrt(variance) * math.sqrt(365.0))
    multiple = FINAL_EQUITY / INITIAL_CAPITAL
    cagr = multiple ** (365.0 / len(returns)) - 1.0
    wealth = [1.0]
    for value in returns:
        wealth.append(wealth[-1] * (1.0 + value))
    drawdown = min(
        wealth[index] / max(wealth[: index + 1]) - 1.0 for index in range(len(wealth))
    )
    (output / "summary.json").write_text(
        json.dumps(
            {
                "multiple": multiple,
                "cagr": cagr,
                "sharpe": sharpe,
                "max_drawdown": drawdown,
                "fees_total": 0.77,
                "funding_total": -0.01,
                "max_observed_gross": 0.3269463213585115,
                "max_target_total_gross": 0.2,
                "max_funded_short_gross": 0.1,
                "days": 2,
                "metric_days": 2,
                "liquidation_count": 0,
                "stop_event_count": 0,
            }
        ),
        encoding="utf-8",
    )

    pd.DataFrame({"coin_id": ["aaa"], "bitget_symbol": ["AAAUSDT"]}).to_csv(
        raw / "symbol_map.csv", index=False
    )
    pd.DataFrame(
        {
            "open_time": ["2026-01-01 23:00:00+00:00", "2026-01-02 23:00:00+00:00"],
            "close": [11.0, 25.0],
        }
    ).to_csv(raw / "candles" / "AAAUSDT_mark.csv", index=False)
    return output, raw, raw / "symbol_map.csv"


def _audit(output: Path, raw: Path, symbol_map: Path) -> dict:
    return audit_artifacts(
        output_dir=output,
        raw_dir=raw,
        symbol_map=symbol_map,
        initial_capital=INITIAL_CAPITAL,
        cost_bps=20.0,
        max_gross=1.75,
    )


def _failed_names(result: dict) -> set[str]:
    return {item["name"] for item in result["hard_failures"]}


def test_clean_ledger_replays_open_increase_reduce_close_reopen(tmp_path: Path) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)

    result = _audit(output, raw, symbol_map)

    assert result["passed"] is True
    assert result["reconstructed_equity"] == pytest.approx(FINAL_EQUITY, abs=1e-9)
    assert not result["hard_failures"]
    names = {item["name"] for item in result["checks"]}
    assert "position notional = snapshot quantity x fill price" in names
    assert "position snapshots match the replayed trade ledger" in names
    assert "every position snapshot maps to an open/increase fill" in names


def test_funding_credit_and_debit_move_replayed_equity(tmp_path: Path) -> None:
    output, _, _ = _write_fixture(tmp_path)
    trades = pd.read_csv(output / "oos_trades.csv", parse_dates=["timestamp"])
    funding = pd.read_csv(output / "oos_funding.csv", parse_dates=["timestamp"])
    margin_events = pd.read_csv(
        output / "oos_margin_events.csv", parse_dates=["timestamp"]
    )
    cutoff = pd.Timestamp("2026-01-02 23:00:00+00:00")
    marks = {"aaa": 25.0}

    with_funding = _replay_equity(
        trades=trades,
        funding=funding,
        margin_events=margin_events,
        initial_capital=INITIAL_CAPITAL,
        cutoff=cutoff,
        marks_by_symbol=marks,
    )
    without_funding = _replay_equity(
        trades=trades,
        funding=funding.iloc[0:0],
        margin_events=margin_events,
        initial_capital=INITIAL_CAPITAL,
        cutoff=cutoff,
        marks_by_symbol=marks,
    )

    assert with_funding == pytest.approx(FINAL_EQUITY, abs=1e-9)
    assert with_funding - without_funding == pytest.approx(
        float(funding["amount"].sum()), abs=1e-12
    )


def test_margin_add_and_remove_do_not_change_equity(tmp_path: Path) -> None:
    output, _, _ = _write_fixture(tmp_path)
    trades = pd.read_csv(output / "oos_trades.csv", parse_dates=["timestamp"])
    funding = pd.read_csv(output / "oos_funding.csv", parse_dates=["timestamp"])
    margin_events = pd.read_csv(
        output / "oos_margin_events.csv", parse_dates=["timestamp"]
    )
    cutoff = pd.Timestamp("2026-01-02 23:00:00+00:00")
    marks = {"aaa": 25.0}

    with_events = _replay_equity(
        trades=trades,
        funding=funding,
        margin_events=margin_events,
        initial_capital=INITIAL_CAPITAL,
        cutoff=cutoff,
        marks_by_symbol=marks,
    )
    without_events = _replay_equity(
        trades=trades,
        funding=funding,
        margin_events=margin_events.iloc[0:0],
        initial_capital=INITIAL_CAPITAL,
        cutoff=cutoff,
        marks_by_symbol=marks,
    )

    assert with_events == pytest.approx(without_events, abs=1e-9)


def test_tampered_trade_fee_fails_the_audit(tmp_path: Path) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    trades = pd.read_csv(output / "oos_trades.csv")
    trades.loc[0, "fee"] = float(trades.loc[0, "fee"]) + 0.01
    trades.to_csv(output / "oos_trades.csv", index=False)

    result = _audit(output, raw, symbol_map)

    assert result["passed"] is False
    assert "normal trade fee = notional x 20bps" in _failed_names(result)


def test_tampered_final_equity_fails_the_audit(tmp_path: Path) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    daily = pd.read_csv(output / "oos_daily.csv")
    daily.loc[daily.index[-1], "equity"] = FINAL_EQUITY + 1.0
    daily.to_csv(output / "oos_daily.csv", index=False)

    result = _audit(output, raw, symbol_map)

    assert result["passed"] is False
    failed = _failed_names(result)
    assert "independent event replay reconstructs final equity" in failed
    assert "daily returns reproduce the reported equity path" in failed


def test_tampered_hourly_gross_fails_the_independent_gross_replay(tmp_path: Path) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    gross = pd.read_csv(output / "oos_gross_exposure.csv")
    gross.loc[1, "gross_exposure"] = float(gross.loc[1, "gross_exposure"]) + 0.01
    gross.to_csv(output / "oos_gross_exposure.csv", index=False)

    result = _audit(output, raw, symbol_map)

    assert result["passed"] is False
    assert "independent hourly gross replay reproduces every gross observation" in _failed_names(result)


def test_increase_snapshot_notional_uses_the_new_fill_not_the_weighted_entry(
    tmp_path: Path,
) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    positions = pd.read_csv(output / "oos_positions.csv")
    increase = positions.loc[1]
    # The fixture's increase snapshot is valid even though its notional
    # (15 * 12 = 180) is not quantity * weighted entry (15 * 10.666...).
    assert increase["notional"] != pytest.approx(
        increase["quantity"] * increase["entry_price"]
    )
    assert _audit(output, raw, symbol_map)["passed"] is True

    positions.loc[1, "notional"] = 999.0
    positions.to_csv(output / "oos_positions.csv", index=False)
    result = _audit(output, raw, symbol_map)
    assert result["passed"] is False
    assert "position notional = snapshot quantity x fill price" in _failed_names(result)


def test_tampered_intermediate_daily_equity_fails_the_daily_replay(
    tmp_path: Path,
) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    daily = pd.read_csv(output / "oos_daily.csv")
    daily.loc[0, "equity"] = float(daily.loc[0, "equity"]) + 0.5
    daily.to_csv(output / "oos_daily.csv", index=False)

    result = _audit(output, raw, symbol_map)

    assert result["passed"] is False
    failed = _failed_names(result)
    assert "independent daily replay reproduces every reported equity point" in failed
    # The final point itself is untouched, so the final-point check still passes.
    assert "independent event replay reconstructs final equity" not in failed


def test_tampered_open_snapshot_is_rejected(tmp_path: Path) -> None:
    output, raw, symbol_map = _write_fixture(tmp_path)
    positions = pd.read_csv(output / "oos_positions.csv")
    positions.loc[0, "notional"] = 999.0
    positions.to_csv(output / "oos_positions.csv", index=False)
    result = _audit(output, raw, symbol_map)
    assert result["passed"] is False
    assert "position notional = snapshot quantity x fill price" in _failed_names(result)
